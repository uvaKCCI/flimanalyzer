"""Filtering the rows of a table by a filter tree.

A tree is a list of nodes (FilterConfig.filters), combined as an `all` group: a row is
kept if every enabled node keeps it. Leaves: `range` (a feature's values in [low,
high]), `category` (a category column's values to keep), `expression` (a condition, as
Calculate's expressions). Groups: `all`, `any`, `not`; they nest. Every node is
evaluated on the input table; the masks are combined by the tree, and the table is
copied once at the end, so the order of the nodes doesn't matter.

A node that is not enabled, an empty group, and a leaf on a column the table doesn't
have keep all rows, as the range filters did up to FLIMAnalyzer 0.6.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel

from flim.core.calculate import evaluate, expression_columns, quote_columns

if TYPE_CHECKING:
    from flim.configs.data import FilterNode, RangeFilterNode
    from flim.core.settings import AppSettings


@dataclass
class Outcome:
    """The result of `apply_filters`.

    Attributes:
        data: The rows kept, numbered from 0.
        kept: Whether each input row is kept.
        dropped: (path, label, number of input rows the leaf drops) per enabled leaf,
            e.g. `("filters[2]", "trp t1 in [0, 2500]", 12)`.
        notes: Leaves that keep all rows because their column is missing or not a
            feature, by path.
    """

    data: pd.DataFrame
    kept: pd.Series
    dropped: list = field(default_factory=list)
    notes: dict = field(default_factory=dict)


def label(node: "FilterNode") -> str:
    """Return a short text for a node, e.g. `trp t1 in [0, 2500]`, `FOV in 1, 2`.

    Args:
        node: The filter node.

    Returns:
        For a range, `<column> in [<low>, <high>]` (`-inf`, `inf` without a limit);
        for a category filter, `<column> in <values>`; for an expression, the
        expression; for a group, `<kind> of <n> filters`.
    """
    if node.kind == "range":
        low = "-inf" if node.low is None else f"{node.low:g}"
        high = "inf" if node.high is None else f"{node.high:g}"
        return f"{node.column} in [{low}, {high}]"
    if node.kind == "category":
        return f"{node.column} in {', '.join(str(v) for v in node.keep)}"
    if node.kind == "expression":
        return node.expression
    return f"{node.kind} of {len(node.filters)} filters"


def _all_rows(data: pd.DataFrame) -> pd.Series:
    """Return a mask that keeps all rows of a table."""
    return pd.Series(True, index=data.index)


def _keeps(
    data: pd.DataFrame, node: "FilterNode", path: str, outcome: Outcome
) -> np.ndarray:
    """Return whether each row is kept by a node; record what enabled leaves drop."""
    if not node.enabled:
        return np.ones(len(data), dtype=bool)
    if node.kind in ("all", "any", "not"):
        masks = [
            _keeps(data, child, f"{path}.filters[{i}]", outcome)
            for i, child in enumerate(node.filters)
        ]
        if not masks:
            return np.ones(len(data), dtype=bool)
        if node.kind == "any":
            return np.logical_or.reduce(masks)
        joined = np.logical_and.reduce(masks)
        return ~joined if node.kind == "not" else joined
    mask = np.asarray(_leaf(data, node, path, outcome), dtype=bool)
    outcome.dropped.append((path, label(node), int((~mask).sum())))
    return mask


def _leaf(
    data: pd.DataFrame, node: "FilterNode", path: str, outcome: Outcome
) -> pd.Series:
    """Return whether each row is kept by a leaf; note a missing or wrong column."""
    if node.kind == "expression":
        used = expression_columns(quote_columns(node.expression, data.columns))
        absent = [c for c in used if c not in data.columns]
        if absent:
            outcome.notes[path] = f"no column {', '.join(repr(c) for c in absent)}"
            return _all_rows(data)
        result = evaluate(data, node.expression)
        if not pd.api.types.is_bool_dtype(result):
            raise ValueError(f"'{node.expression}' is not a condition (true or false)")
        return result.fillna(False).astype(bool)
    if node.column not in data.columns:
        outcome.notes[path] = f"no column '{node.column}'"
        return _all_rows(data)
    values = data[node.column]
    if node.kind == "category":
        return values.isin(node.keep)
    if not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values):
        outcome.notes[path] = f"'{node.column}' is not a feature"
        return _all_rows(data)
    inside = values.notna() if node.dropna else _all_rows(data)
    if node.low is not None:
        inside &= ~(values < node.low)
    if node.high is not None:
        inside &= ~(values > node.high)
    return inside


def apply_filters(data: pd.DataFrame, filters: Sequence["FilterNode"]) -> Outcome:
    """Keep the rows that every enabled filter of a list keeps (an `all` group).

    Args:
        data: The table (not changed).
        filters: The filter nodes (`FilterConfig.filters`).

    Returns:
        The rows kept, whether each input row is kept, what each enabled leaf
        dropped, and the leaves that keep all rows because of their column.

    Raises:
        ValueError: If an expression is not allowed or is not a condition.
    """
    outcome = Outcome(data=data, kept=_all_rows(data))
    masks = [
        _keeps(data, node, f"filters[{i}]", outcome) for i, node in enumerate(filters)
    ]
    kept = np.logical_and.reduce(masks) if masks else np.ones(len(data), dtype=bool)
    outcome.kept = pd.Series(np.asarray(kept, dtype=bool), index=data.index)
    outcome.data = data[outcome.kept.to_numpy()].reset_index(drop=True)
    return outcome


def check(
    filters: Sequence["FilterNode"],
    columns: Optional[Collection[str]] = None,
    path: str = "filters",
    kind: str = "all",
) -> list[tuple[str, str, str]]:
    """Check a filter list before using it.

    Nodes that are not enabled are not checked; groups are checked with their
    nodes.

    Args:
        filters: The filter nodes.
        columns: The input table's columns (names); None: unknown.
        path: The list's path, for the messages. Defaults to `filters`.
        kind: The group the list belongs to (`all`, `any`, `not`). Defaults to
            `all`.

    Returns:
        (path, severity, message) per problem: `error` for an expression that is not
        allowed, `warning` for an expression on columns the table doesn't have (it
        keeps all rows) and for two ranges on one column in the same `all` group that
        don't overlap (they drop all rows).
    """
    problems = []
    ranges: dict = {}
    for i, node in enumerate(filters):
        where = f"{path}[{i}]"
        if not node.enabled:
            continue
        if node.kind in ("all", "any", "not"):
            problems += check(node.filters, columns, f"{where}.filters", node.kind)
            continue
        if node.kind == "expression":
            try:
                used = expression_columns(quote_columns(node.expression, columns or ()))
            except ValueError as err:
                problems.append((f"{where}.expression", "error", str(err)))
                continue
            absent = [c for c in used if columns is not None and c not in columns]
            if absent:
                missing = ", ".join(repr(c) for c in absent)
                problems.append(
                    (f"{where}.expression", "warning", f"keeps all rows: no column {missing}")
                )
        if node.kind == "range" and kind == "all":
            ranges.setdefault(node.column, []).append((i, node))
    for column, nodes in ranges.items():
        lows = [n.low for _, n in nodes if n.low is not None]
        highs = [n.high for _, n in nodes if n.high is not None]
        if lows and highs and max(lows) > min(highs):
            i = nodes[-1][0]
            problems.append(
                (
                    f"{path}[{i}]",
                    "warning",
                    f"the ranges on '{column}' don't overlap: all rows are dropped",
                )
            )
    return problems


class WindowFilters(BaseModel):
    """The table windows' filters, as their filter dialog edits them.

    Whether they are used (`Filter Data`, the switch of all of them), whether
    dropped rows are shown, the range filters (`flim.core.filter.RangeFilter`
    parameters) of the Filter tool's top-level range leaves, one per column, and the
    values kept of the category columns that hide values.
    """

    use: bool = False
    show_dropped: bool = True
    range_filters: list[dict] = []
    category_filters: dict[str, list] = {}


def window_filters(settings: "AppSettings") -> WindowFilters:
    """Return the table windows' filters of the settings.

    Args:
        settings: The settings; the range filters come from the Filter tool's
            config (see `window_ranges`).

    Returns:
        The filters.
    """
    from flim.tools.data import Filter

    return WindowFilters(
        use=settings.filters.use,
        show_dropped=settings.filters.show_dropped,
        range_filters=window_ranges(settings.tools.config(Filter).filters),
    )


def new_range(column: str) -> dict[str, Any]:
    """Return the `RangeFilter` parameters of a new range filter: no limits, not used.

    Args:
        column: The feature column.

    Returns:
        The parameters, with infinite limits and missing values dropped.
    """
    inf = float("inf")
    return {
        "name": column, "rangelow": -inf, "rangehigh": inf, "allowedmin": None,
        "allowedmax": None, "selected": False, "dropna": True,
    }  # fmt: skip


def range_params(node: "RangeFilterNode") -> dict[str, Any]:
    """Return a range leaf as `RangeFilter` parameters (no limit: infinite).

    Args:
        node: The range leaf.

    Returns:
        The parameters; `selected` is whether the leaf is enabled.
    """
    inf = float("inf")
    return {
        "name": node.column,
        "rangelow": -inf if node.low is None else node.low,
        "rangehigh": inf if node.high is None else node.high,
        "allowedmin": None,
        "allowedmax": None,
        "selected": node.enabled,
        "dropna": node.dropna,
    }


def range_node(params: dict[str, Any]) -> "RangeFilterNode":
    """Return `RangeFilter` parameters as a range leaf (infinite: no limit).

    Args:
        params: The parameters: `name` (the column), the limits, `selected`
            (default True) and `dropna`.

    Returns:
        The range leaf, enabled if `selected` is.

    Raises:
        KeyError: If `params` has no `name`.
        pydantic.ValidationError: If the low limit is larger than the high limit.
    """
    from flim.configs.data import RangeFilterNode, range_of_legacy

    return RangeFilterNode(
        column=params["name"],
        enabled=bool(params.get("selected", True)),
        **range_of_legacy(params),
    )


def window_ranges(filters: Sequence["FilterNode"]) -> list[dict[str, Any]]:
    """Return the top-level range leaves as `RangeFilter` parameters.

    Args:
        filters: The filter nodes; of several range leaves on one column, the
            first is taken.

    Returns:
        The parameters, one per column, in the order of the leaves.
    """
    seen, ranges = set(), []
    for node in filters:
        if node.kind == "range" and node.column not in seen:
            seen.add(node.column)
            ranges.append(range_params(node))
    return ranges


def with_window_ranges(
    filters: Sequence["FilterNode"], ranges: list[dict[str, Any]]
) -> list["FilterNode"]:
    """Return the filters with the top-level range leaves replaced by range filters.

    Of several range leaves on one column, the first is replaced. Range filters of
    columns without a top-level range leaf are appended as range leaves. Range
    leaves of columns without a range filter are kept.

    Args:
        filters: The filter nodes.
        ranges: `RangeFilter` parameters, one per column.

    Returns:
        A new list of nodes; `filters` is not changed.
    """
    by_column = {p["name"]: p for p in ranges}
    result, seen = [], set()
    for node in filters:
        if node.kind == "range" and node.column not in seen:
            seen.add(node.column)
            if node.column in by_column:
                result.append(range_node(by_column[node.column]))
                continue
        result.append(node)
    result += [range_node(p) for name, p in by_column.items() if name not in seen]
    return result


def default_ranges() -> list["RangeFilterNode"]:
    """Return the range leaves of new settings.

    They are the range filters of FLIMAnalyzer 0.6.
    """
    from flim.core.settings import default_range_filters

    return [range_node(f.get_params()) for f in default_range_filters()]


def leaf_counts(outcome: Outcome) -> Optional[str]:
    """Return one line on the rows each leaf dropped, e.g. for the run summary.

    Args:
        outcome: The result of `apply_filters`.

    Returns:
        A text for the leaves that dropped rows, or None if none did, for example
        `dropped rows: <label>: <n>; ...`.
    """
    parts = [f"{text}: {n}" for _, text, n in outcome.dropped if n]
    return "dropped rows: " + "; ".join(parts) if parts else None


def window_settings(filters: WindowFilters) -> dict[str, Any]:
    """Return a table window's filters as the Filter tool's settings.

    Args:
        filters: The window's filters.

    Returns:
        `enabled` (the window's `Filter Data`) and `filters`: a range leaf per
        range filter (enabled if selected) and a category leaf per category column
        that hides values, as JSON data.
    """
    nodes = [node.model_dump(mode="json") for node in with_window_ranges([], filters.range_filters)]
    nodes += [
        {"enabled": True, "kind": "category", "column": column, "keep": list(keep)}
        for column, keep in filters.category_filters.items()
    ]
    return {"enabled": filters.use, "filters": nodes}


@dataclass
class WindowPart:
    """The part of the Filter tool's settings that a table window uses.

    Attributes:
        use: `enabled`, the switch of all filters; None if the settings don't have
            it.
        ranges: `RangeFilter` parameters of the top-level range leaves.
        categories: The values kept, of the first enabled top-level category leaf
            of each column.
        unused: The number of filters a table window doesn't use: expressions,
            groups, further leaves of a column and category leaves that are off.
    """

    use: Optional[bool]
    ranges: list[dict[str, Any]]
    categories: dict[str, list]
    unused: int


def window_part(settings: dict[str, Any]) -> WindowPart:
    """Return the part of the Filter tool's settings that a table window uses.

    Args:
        settings: The Filter tool's settings, or a part of them, with `filters`
            and, if set, `enabled`.

    Returns:
        The switch, the range filters, the category filters and the number of
        filters left unused.

    Raises:
        ValueError: If the settings are not valid Filter settings.
    """
    from flim.configs.data import FilterConfig

    config = FilterConfig.model_validate({"filters": settings.get("filters") or []})
    ranges = window_ranges(config.filters)
    categories: dict[str, list] = {}
    unused = 0
    first_range = set()
    for node in config.filters:
        if node.kind == "range" and node.column not in first_range:
            first_range.add(node.column)
        elif node.kind == "category" and node.enabled and node.column not in categories:
            categories[node.column] = list(node.keep)
        else:
            unused += 1
    use = settings.get("enabled")
    return WindowPart(None if use is None else bool(use), ranges, categories, unused)


def file_data_ranges(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return range filters, all selected, from feature settings ({column: {low, high, dropna}}).

    Args:
        data: The settings by column, as `Save Feature Settings...` writes them; a
            missing or None limit means no limit.

    Returns:
        `RangeFilter` parameters, one per column.
    """
    ranges = []
    for column, limits in data.items():
        low, high = limits.get("low"), limits.get("high")
        ranges.append(
            new_range(column) | {
                "rangelow": float("-inf") if low is None else low,
                "rangehigh": float("inf") if high is None else high,
                "dropna": limits.get("dropna", True),
                "selected": True,
            }
        )  # fmt: skip
    return ranges
