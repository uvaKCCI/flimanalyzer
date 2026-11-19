"""Filtering the rows of a table by the Filter tool's settings.

The settings (`FilterConfig`) have three parts: `features` (range leaves, one per
feature column), `categories` (category leaves, one per category column) and `other`
(nodes of any kind). A row is kept if every part keeps it; a part keeps a row if
every node of its list keeps it (an `all` group). Leaves: `range` (a feature's
values in [low, high]), `category` (a category column's values to keep),
`expression` (a condition, as Calculate's expressions). Groups: `all`, `any`, `not`;
they nest. A leaf is used only if every `enabled` on its way is on: the top-level
switch, its part's, its groups' and its own. Every node is evaluated on the input
table; the masks are combined, and the table is copied once at the end, so the
order of the nodes doesn't matter.

A node that is not enabled, an empty group, and a leaf on a column the table doesn't
have are not used: they drop no rows. A group combines only the masks of the nodes
it uses, and a group that uses none is not used itself. So a filter that is not used
neither makes an `any` group keep every row nor a `not` group drop every row. A
range filter on a missing column dropped no rows up to FLIMAnalyzer 0.6 either.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from flim.core.calculate import evaluate, expression_columns, quote_columns
from flim.core.settings import FilterSwitch

if TYPE_CHECKING:
    from flim.configs.data import FilterConfig, FilterNode, RangeFilterNode
    from flim.core.settings import AppSettings


@dataclass
class Outcome:
    """The result of `apply_filters`.

    Attributes:
        data: The rows kept, numbered from 0.
        kept: Whether each input row is kept.
        dropped: (path, label, number of input rows the leaf drops) per leaf in use,
            e.g. `("features.filters[2]", "trp t1 in [0, 2500]", 12)`.
        notes: Leaves that are not used because their column is missing or not a
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
) -> Optional[np.ndarray]:
    """Return whether each row is kept by a node; record what enabled leaves drop.

    Returns:
        The mask; None for a node that is not used: not enabled, an empty group, a
        leaf on a column the table does not have, or a group that uses none of its
        nodes.
    """
    if not node.enabled:
        return None
    if node.kind in ("all", "any", "not"):
        masks = [
            mask
            for i, child in enumerate(node.filters)
            if (mask := _keeps(data, child, f"{path}.filters[{i}]", outcome)) is not None
        ]
        if not masks:
            return None
        if node.kind == "any":
            return np.logical_or.reduce(masks)
        joined = np.logical_and.reduce(masks)
        return ~joined if node.kind == "not" else joined
    kept = _leaf(data, node, path, outcome)
    mask = None if kept is None else np.asarray(kept, dtype=bool)
    outcome.dropped.append((path, label(node), 0 if mask is None else int((~mask).sum())))
    return mask


def _leaf(
    data: pd.DataFrame, node: "FilterNode", path: str, outcome: Outcome
) -> Optional[pd.Series]:
    """Return whether each row is kept by a leaf; None for a missing or wrong column.

    A missing or wrong column is noted in `outcome.notes`.
    """
    if node.kind == "expression":
        used = expression_columns(quote_columns(node.expression, data.columns))
        absent = [c for c in used if c not in data.columns]
        if absent:
            outcome.notes[path] = f"no column {', '.join(repr(c) for c in absent)}"
            return None
        result = evaluate(data, node.expression)
        if not pd.api.types.is_bool_dtype(result):
            raise ValueError(f"'{node.expression}' is not a condition (true or false)")
        return result.fillna(False).astype(bool)
    if node.column not in data.columns:
        outcome.notes[path] = f"no column '{node.column}'"
        return None
    values = data[node.column]
    if node.kind == "category":
        return values.isin(node.keep)
    if not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values):
        outcome.notes[path] = f"'{node.column}' is not a feature"
        return None
    inside = values.notna() if node.dropna else _all_rows(data)
    if node.low is not None:
        inside &= ~(values < node.low)
    if node.high is not None:
        inside &= ~(values > node.high)
    return inside


def _lists(
    filters: Union["FilterConfig", Sequence["FilterNode"]],
) -> list[tuple[str, Sequence["FilterNode"]]]:
    """Return the node lists in use with their paths, e.g. `features.filters`.

    For settings: the lists of the parts that are on, none if the top-level switch
    is off; for a list of nodes: the list, at `filters`.
    """
    if isinstance(filters, (list, tuple)):
        return [("filters", filters)]
    from flim.configs.data import FILTER_PARTS

    if not filters.enabled:
        return []
    parts = [(name, getattr(filters, name)) for name in FILTER_PARTS]
    return [(f"{name}.filters", part.filters) for name, part in parts if part.enabled]


def apply_filters(
    data: pd.DataFrame, filters: Union["FilterConfig", Sequence["FilterNode"]]
) -> Outcome:
    """Keep the rows that every filter in use keeps.

    Args:
        data: The table (not changed).
        filters: The Filter tool's settings, or a list of filter nodes (an `all`
            group).

    Returns:
        The rows kept, whether each input row is kept, what each leaf in use
        dropped, and the leaves that are not used because of their column.

    Raises:
        ValueError: If an expression is not allowed or is not a condition.
    """
    outcome = Outcome(data=data, kept=_all_rows(data))
    masks = [
        mask
        for path, nodes in _lists(filters)
        for i, node in enumerate(nodes)
        if (mask := _keeps(data, node, f"{path}[{i}]", outcome)) is not None
    ]
    kept = np.logical_and.reduce(masks) if masks else np.ones(len(data), dtype=bool)
    outcome.kept = pd.Series(np.asarray(kept, dtype=bool), index=data.index)
    outcome.data = data[outcome.kept.to_numpy()].reset_index(drop=True)
    return outcome


def validate_filters(
    filters: Union["FilterConfig", Sequence["FilterNode"]],
    columns: Optional[Collection[str]] = None,
) -> list[tuple[str, str, str]]:
    """Validate filters before using them.

    Only the nodes in use are validated (see `apply_filters`); groups are validated
    with their nodes. The top-level lists of the parts form one `all` group.

    Args:
        filters: The Filter tool's settings, or a list of filter nodes (at
            `filters`).
        columns: The input table's columns (names); None: unknown.

    Returns:
        (path, severity, message) per problem: `error` for an expression that is not
        allowed, `warning` for an expression on columns the table doesn't have (it
        is not used) and for two ranges on one column in the same `all` group that
        don't overlap (they drop all rows).
    """
    problems: list = []
    ranges: dict = {}
    for path, nodes in _lists(filters):
        problems += _validate(nodes, columns, path, ranges)
    return problems + _overlaps(ranges)


def _validate(
    filters: Sequence["FilterNode"],
    columns: Optional[Collection[str]],
    path: str,
    ranges: Optional[dict] = None,
) -> list[tuple[str, str, str]]:
    """Validate a node list; collect its range leaves by column into `ranges`.

    Args:
        filters: The nodes.
        columns: The input table's columns; None: unknown.
        path: The list's path, for the messages.
        ranges: Where the range leaves of an `all` group are collected, column ->
            [(path, node)]; None for a list that is not an `all` group (its ranges
            are not compared).

    Returns:
        The problems, as `validate_filters` returns them; the overlaps of the
        groups inside, not those of this list.
    """
    problems = []
    for i, node in enumerate(filters):
        where = f"{path}[{i}]"
        if not node.enabled:
            continue
        if node.kind in ("all", "any", "not"):
            inner: Optional[dict] = {} if node.kind == "all" else None
            problems += _validate(node.filters, columns, f"{where}.filters", inner)
            problems += _overlaps(inner or {})
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
                    (f"{where}.expression", "warning", f"not used: no column {missing}")
                )
        if node.kind == "range" and ranges is not None:
            ranges.setdefault(node.column, []).append((where, node))
    return problems


def _overlaps(ranges: dict) -> list[tuple[str, str, str]]:
    """Return a warning per column whose ranges (of one `all` group) don't overlap."""
    problems = []
    for column, nodes in ranges.items():
        lows = [n.low for _, n in nodes if n.low is not None]
        highs = [n.high for _, n in nodes if n.high is not None]
        if lows and highs and max(lows) > min(highs):
            problems.append(
                (
                    nodes[-1][0],
                    "warning",
                    f"the ranges on '{column}' don't overlap: all rows are dropped",
                )
            )
    return problems


class WindowFilters(BaseModel):
    """A table window's filters, as its `Filter Features...` dialog edits them.

    A `use` of earlier settings (`Filter Data`, the switch of all filters) sets
    both switches.

    Attributes:
        features: `Filter Features`: whether the range filters are used.
        categories: `Filter Categories`: whether the category values hidden
            through a column header are used.
        show_dropped: Whether the rows the range filters drop are shown in a new
            window.
        range_filters: The range filters (`flim.core.filter.RangeFilter`
            parameters), one per column: the Filter tool's range filters
            (`features`).
        category_filters: The values kept of the category columns that hide
            values.
    """

    features: FilterSwitch = Field(default_factory=FilterSwitch)
    categories: FilterSwitch = Field(default_factory=FilterSwitch)
    show_dropped: bool = True
    range_filters: list[dict] = []
    category_filters: dict[str, list] = {}

    @model_validator(mode="before")
    @classmethod
    def _from_use(cls, values: Any) -> Any:
        """Read `use`, the switch of all filters, as both switches."""
        if isinstance(values, dict) and "use" in values:
            values = dict(values)
            use = values.pop("use")  # validated as the switches
            for name in ("features", "categories"):
                values.setdefault(name, {"enabled": use})
        return values


def window_filters(settings: "AppSettings") -> WindowFilters:
    """Return the filters new table windows start with.

    Args:
        settings: The settings: the switches are the `filters` setting, the range
            filters those of the Filter tool (`features`, see `window_ranges`).

    Returns:
        The filters; no category values are hidden.
    """
    from flim.tools.data import Filter

    return WindowFilters(
        features=settings.filters.features.model_copy(),
        categories=settings.filters.categories.model_copy(),
        show_dropped=settings.filters.show_dropped,
        range_filters=window_ranges(settings.tools.config(Filter).features.filters),
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
    """Return range leaves as `RangeFilter` parameters.

    Args:
        filters: The filter nodes, e.g. the Filter tool's range filters
            (`features.filters`); other kinds are left out and, of several range
            leaves on one column, the first is taken.

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
    """Return filter nodes with the range leaves replaced by range filters.

    Of several range leaves on one column, the first is replaced. Range filters of
    columns without a range leaf are appended as range leaves. Range leaves of
    columns without a range filter, and nodes of other kinds, are kept.

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
    """Return a table window's range filters as a part of the Filter tool's settings.

    Args:
        filters: The window's filters.

    Returns:
        `features`: `enabled` (the window's `Filter Features`) and `filters` (a
        range leaf per range filter, enabled if selected), as JSON data. The
        category values are not part of it.
    """
    nodes = with_window_ranges([], filters.range_filters)
    return {
        "features": {
            "enabled": filters.features.enabled,
            "filters": [node.model_dump(mode="json") for node in nodes],
        }
    }


@dataclass
class WindowPart:
    """The part of the Filter tool's settings that a table window uses.

    Attributes:
        use: Whether the range filters are used: the `enabled` of `features`, and
            the top-level `enabled` if the settings have it; None if the settings
            have neither (e.g. a file of `Save Feature Settings...`).
        ranges: `RangeFilter` parameters of the range filters (`features`).
        unused: The number of filters a table window doesn't use: those of
            `categories` and `other`.
    """

    use: Optional[bool]
    ranges: list[dict[str, Any]]
    unused: int


def window_part(settings: dict[str, Any]) -> WindowPart:
    """Return the part of the Filter tool's settings that a table window uses.

    Settings of earlier versions (a flat `filters` list) are converted first: their
    range leaves become `features`, one per column (see
    `flim.configs.data.split_filters`). Their top-level `enabled` (from a table
    window: `Filter Data`) is then the switch of the range filters.

    Args:
        settings: The Filter tool's settings, or a part of them, e.g. `features`
            alone, or `enabled` and `filters`.

    Returns:
        The switch, the range filters and the number of filters left unused.

    Raises:
        ValueError: If the settings are not valid Filter settings.
    """
    from flim.configs.data import FilterConfig

    keys = ("enabled", "features", "categories", "other", "filters")
    config = FilterConfig.model_validate({k: v for k, v in settings.items() if k in keys})
    features = settings.get("features")
    given = "enabled" in settings or (isinstance(features, dict) and "enabled" in features)
    use = config.enabled and config.features.enabled if given else None
    unused = len(config.categories.filters) + len(config.other.filters)
    return WindowPart(use, window_ranges(config.features.filters), unused)


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
