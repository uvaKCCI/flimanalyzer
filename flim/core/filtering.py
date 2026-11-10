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

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel

from flim.core.calculate import evaluate, expression_columns


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


def label(node) -> str:
    """A short text for a node, e.g. `trp t1 in [0, 2500]`, `FOV in 1, 2`."""
    if node.kind == "range":
        low = "-inf" if node.low is None else f"{node.low:g}"
        high = "inf" if node.high is None else f"{node.high:g}"
        return f"{node.column} in [{low}, {high}]"
    if node.kind == "category":
        return f"{node.column} in {', '.join(str(v) for v in node.keep)}"
    if node.kind == "expression":
        return node.expression
    return f"{node.kind} of {len(node.filters)} filters"


def _all_rows(data) -> pd.Series:
    return pd.Series(True, index=data.index)


def _keeps(data: pd.DataFrame, node, path: str, outcome: Outcome) -> np.ndarray:
    """Whether each row is kept by a node; records what each enabled leaf drops."""
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


def _leaf(data: pd.DataFrame, node, path: str, outcome: Outcome) -> pd.Series:
    if node.kind == "expression":
        absent = [c for c in expression_columns(node.expression) if c not in data.columns]
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


def apply_filters(data: pd.DataFrame, filters) -> Outcome:
    """Keep the rows that every enabled filter of a list keeps (an `all` group).

    Args:
        data: The table (not changed).
        filters: The filter nodes (FilterConfig.filters).

    Returns:
        The rows kept, and what each leaf dropped.

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
    filters, columns=None, path: str = "filters", kind: str = "all"
) -> list[tuple[str, str, str]]:
    """Check a filter list before using it.

    Args:
        filters: The filter nodes.
        columns: The input table's columns (names); None: unknown.
        path: The list's path, for the messages.
        kind: The group the list belongs to (`all`, `any`, `not`).

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
                used = expression_columns(node.expression)
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
    """The table windows' filters, as their filter dialog edits them: whether they
    are used, whether dropped rows are shown, and the range filters
    (flim.core.filter.RangeFilter parameters) of the Filter tool's top-level range
    leaves, one per column."""

    use: bool = False
    show_dropped: bool = True
    range_filters: list[dict] = []


def window_filters(settings) -> WindowFilters:
    """The table windows' filters of the settings (AppSettings)."""
    from flim.tools.data import Filter

    return WindowFilters(
        use=settings.filters.use,
        show_dropped=settings.filters.show_dropped,
        range_filters=window_ranges(settings.tools.config(Filter).filters),
    )


def new_range(column: str) -> dict:
    """RangeFilter parameters of a new range filter: no limits, not used."""
    inf = float("inf")
    return {
        "name": column, "rangelow": -inf, "rangehigh": inf, "allowedmin": None,
        "allowedmax": None, "selected": False, "dropna": True,
    }  # fmt: skip


def range_params(node) -> dict:
    """A range leaf as RangeFilter parameters (no limit: infinite)."""
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


def range_node(params: dict):
    """RangeFilter parameters as a range leaf (infinite: no limit)."""
    from flim.configs.data import RangeFilterNode, range_of_legacy

    return RangeFilterNode(
        column=params["name"],
        enabled=bool(params.get("selected", True)),
        **range_of_legacy(params),
    )


def window_ranges(filters) -> list[dict]:
    """The top-level range leaves (the first per column) as RangeFilter parameters."""
    seen, ranges = set(), []
    for node in filters:
        if node.kind == "range" and node.column not in seen:
            seen.add(node.column)
            ranges.append(range_params(node))
    return ranges


def with_window_ranges(filters, ranges: list[dict]) -> list:
    """Return the filters with the top-level range leaves (the first per column)
    replaced by RangeFilter parameters; new columns are appended as range leaves."""
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


def default_ranges() -> list:
    """The range leaves of new settings: the range filters of FLIMAnalyzer 0.6."""
    from flim.core.settings import default_range_filters

    return [range_node(f.get_params()) for f in default_range_filters()]


def leaf_counts(outcome: Outcome) -> Optional[str]:
    """One line on the rows each leaf dropped, e.g. for the run summary."""
    parts = [f"{text}: {n}" for _, text, n in outcome.dropped if n]
    return "dropped rows: " + "; ".join(parts) if parts else None
