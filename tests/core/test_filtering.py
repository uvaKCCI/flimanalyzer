"""Filter trees (flim.core.filtering) and the Filter tool."""

import numpy as np
import pandas as pd
import pytest

from flim.configs import FilterConfig
from flim.configs.data import CategoryFilterNode as Category
from flim.configs.data import ExpressionFilterNode as Expression
from flim.configs.data import FilterGroup as Group
from flim.configs.data import RangeFilterNode as Range
from flim.core.filtering import (
    WindowFilters,
    apply_filters,
    validate_filters,
    label,
    window_filters,
    window_ranges,
    with_window_ranges,
)
from flim.core.schema import TableSchema
from flim.tools.data import Filter


@pytest.fixture
def data():
    return pd.DataFrame(
        {
            "t1": [1.0, 5.0, np.nan, 10.0],
            "FOV": pd.Categorical(["1", "2", "1", "2"]),
            "name": ["a", "b", "c", "d"],
        }
    )


def kept(data, *filters):
    return list(apply_filters(data, filters).data["name"])


def test_leaves(data):
    assert kept(data, Range(column="t1", low=2)) == ["b", "d"]  # missing: dropped
    assert kept(data, Range(column="t1", low=2, dropna=False)) == ["b", "c", "d"]
    assert kept(data, Range(column="t1", high=5)) == ["a", "b"]
    assert kept(data, Category(column="FOV", keep=["2"])) == ["b", "d"]
    assert kept(data, Expression(expression="t1 > 4 & t1 < 6")) == ["b"]
    assert kept(data, Range(column="t1", low=2), Category(column="FOV", keep=["1"])) == []


def test_groups_nest(data):
    either = Group(kind="any", filters=[Range(column="t1", high=2), Category(column="FOV", keep=["2"])])
    assert kept(data, either) == ["a", "b", "d"]
    assert kept(data, Group(kind="not", filters=[either])) == ["c"]
    assert kept(data, Group(kind="all", filters=[either, Expression(expression="t1 < 7")])) == ["a", "b"]
    for kind in ("all", "any", "not"):
        assert kept(data, Group(kind=kind)) == ["a", "b", "c", "d"]  # empty: keeps all


def test_disabled_and_missing_columns_keep_all_rows(data):
    everything = ["a", "b", "c", "d"]
    assert kept(data, Range(column="t1", high=0, enabled=False)) == everything
    assert kept(data, Group(kind="not", enabled=False)) == everything
    outcome = apply_filters(
        data,
        [
            Range(column="gone", high=0),
            Category(column="gone", keep=[]),
            Expression(expression="gone > 1"),
            Range(column="name", high=0),  # text, not a feature
        ],
    )
    assert len(outcome.data) == 4 and set(outcome.notes) == {
        "filters[0]", "filters[1]", "filters[2]", "filters[3]"
    }


def test_rows_dropped_per_leaf_on_the_input(data):
    outcome = apply_filters(data, [Range(column="t1", high=5), Category(column="FOV", keep=["1"])])
    assert outcome.dropped == [
        ("filters[0]", "t1 in [-inf, 5]", 2),
        ("filters[1]", "FOV in 1", 2),
    ]
    assert list(outcome.data.index) == [0]  # renumbered
    assert list(outcome.kept) == [True, False, False, False]


def test_expressions_must_be_allowed_conditions(data):
    with pytest.raises(ValueError, match="not a condition"):
        apply_filters(data, [Expression(expression="t1 * 2")])
    with pytest.raises(ValueError, match="not allowed"):
        apply_filters(data, [Expression(expression="t1.to_csv(1)")])


def test_validate_filters(data):
    filters = [
        Expression(expression="1 +"),
        Expression(expression="gone > 1"),
        Range(column="t1", high=2),
        Range(column="t1", low=5),  # no overlap with the one before
        Group(kind="any", filters=[Range(column="t1", high=2), Range(column="t1", low=5)]),
    ]
    problems = [(path, severity) for path, severity, _ in validate_filters(filters, list(data.columns))]
    assert problems == [
        ("filters[0].expression", "error"),
        ("filters[1].expression", "warning"),
        ("filters[3]", "warning"),
    ]  # under `any`, two ranges that don't overlap are fine


def test_labels():
    assert label(Range(column="t1", low=0, high=2.5)) == "t1 in [0, 2.5]"
    assert label(Category(column="FOV", keep=["1", "2"])) == "FOV in 1, 2"
    assert label(Group(kind="any", filters=[Range()])) == "any of 1 filters"


def test_filter_tool(data):
    config = FilterConfig(filters=[Range(column="t1", high=5)])
    (table,) = Filter()(data, config=config).values()
    assert list(table["name"]) == ["a", "b"]
    # a filter on a missing column keeps all rows: a warning only if it is used
    config = FilterConfig(filters=[Range(column="gone", high=1), Range(column="lost", enabled=False)])
    issues = Filter.validate(config, [TableSchema.from_frame(data)])
    assert [(i.field, i.severity) for i in issues] == [("filters[0].column", "warning")]
    config = FilterConfig(filters=[Group(kind="any", filters=[Expression(expression="1 +")])])
    (issue,) = Filter.validate(config, [TableSchema.from_frame(data)])
    assert (issue.field, issue.severity) == ("filters[0].filters[0].expression", "error")


def test_window_ranges_round_trip():
    filters = [
        Range(column="t1", low=0, high=2),
        Expression(expression="t1 > 1"),
        Range(column="t2", enabled=False),
        Range(column="t1", high=9),  # a second range on t1: not the windows'
    ]
    ranges = window_ranges(filters)
    assert [(r["name"], r["rangelow"], r["rangehigh"], r["selected"]) for r in ranges] == [
        ("t1", 0, 2, True), ("t2", float("-inf"), float("inf"), False)
    ]
    assert with_window_ranges(filters, ranges) == filters
    edited = [{**ranges[1], "rangehigh": 5.0, "selected": True}, {"name": "t3", "rangelow": 1, "rangehigh": 2}]
    changed = with_window_ranges(filters, edited)
    assert changed[2] == Range(column="t2", high=5.0)
    assert changed[0] == filters[0] and changed[1:2] + changed[3:4] == [filters[1], filters[3]]
    assert changed[4] == Range(column="t3", low=1, high=2)  # new: appended


def test_window_filters_of_the_settings():
    from flim.core.settings import AppSettings

    settings = AppSettings.default()
    settings.filters.use = True
    filters = window_filters(settings)
    assert isinstance(filters, WindowFilters) and filters.use
    assert len(filters.range_filters) == 38  # 39 defaults; NAD(P)H a2[%] twice
    assert sum(r["selected"] for r in filters.range_filters) == 3
