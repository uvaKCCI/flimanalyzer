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
    label,
    validate_filters,
    window_filters,
    window_part,
    window_ranges,
    window_settings,
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
    """The names of the rows kept by filter nodes, or by a Filter config."""
    if len(filters) == 1 and isinstance(filters[0], FilterConfig):
        filters = filters[0]
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


def test_groups_leave_out_unused_filters(data):
    """Filters off or on a missing column do not count in a group."""
    half = Range(column="t1", high=5)  # keeps a, b
    off = Range(column="t1", high=0, enabled=False)
    missing = Range(column="gone", high=0)
    for unused in (off, missing):
        assert kept(data, Group(kind="any", filters=[unused, half])) == ["a", "b"]
        assert kept(data, Group(kind="not", filters=[unused])) == ["a", "b", "c", "d"]
        assert kept(data, Group(kind="not", filters=[unused, half])) == ["c", "d"]
        assert kept(data, Group(kind="any", filters=[unused])) == ["a", "b", "c", "d"]
    inner = Group(kind="any", filters=[off, missing])  # left out: nothing in use
    assert kept(data, Group(kind="not", filters=[inner])) == ["a", "b", "c", "d"]
    assert kept(data, Group(kind="any", filters=[inner, half])) == ["a", "b"]


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
    config = FilterConfig(features={"filters": [Range(column="t1", high=5)]})
    (table,) = Filter()(data, config=config).values()
    assert list(table["name"]) == ["a", "b"]
    # a filter on a missing column is not used: a warning only if it is switched on
    config = FilterConfig(
        features={"filters": [Range(column="gone", high=1), Range(column="lost", enabled=False)]}
    )
    issues = Filter.validate(config, [TableSchema.from_frame(data)])
    assert [(i.field, i.severity) for i in issues] == [("features.filters[0].column", "warning")]
    assert issues[0].message.endswith("is not in the input: this filter is not used")
    config = FilterConfig(other={"filters": [Group(kind="any", filters=[Expression(expression="1 +")])]})
    (issue,) = Filter.validate(config, [TableSchema.from_frame(data)])
    assert (issue.field, issue.severity) == ("other.filters[0].filters[0].expression", "error")


def parts(**values):
    """A Filter config: the parts' filters as lists, the switches as `<part>_on`."""
    config = {"enabled": values.pop("enabled", True)}
    for part in ("features", "categories", "other"):
        config[part] = {"filters": values.get(part, []), "enabled": values.get(f"{part}_on", True)}
    return FilterConfig(**config)


def test_a_row_is_kept_if_every_part_keeps_it(data):
    config = parts(
        features=[Range(column="t1", high=6)],
        categories=[Category(column="FOV", keep=["2"])],
        other=[Expression(expression="t1 > 2")],
    )
    outcome = apply_filters(data, config)
    assert list(outcome.data["name"]) == ["b"]
    assert [path for path, _, _ in outcome.dropped] == [
        "features.filters[0]", "categories.filters[0]", "other.filters[0]"
    ]  # fmt: skip


def test_a_filter_applies_only_if_every_switch_on_its_way_is_on(data):
    everything = ["a", "b", "c", "d"]
    ranges = [Range(column="t1", high=2)]
    assert kept(data, parts(features=ranges)) == ["a"]
    assert kept(data, parts(features=ranges, enabled=False)) == everything  # top level
    assert kept(data, parts(features=ranges, features_on=False)) == everything  # part
    off = [Range(column="t1", high=2, enabled=False)]
    assert kept(data, parts(features=off)) == everything  # leaf
    group = Group(enabled=False, filters=[Range(column="t1", high=2)])
    assert kept(data, parts(other=[group])) == everything  # group
    # a switch narrows: an enabled leaf in a part that is off stays off
    both = parts(features=ranges, features_on=False, categories=[Category(column="FOV", keep=["1"])])
    assert kept(data, both) == ["a", "c"]
    assert apply_filters(data, parts(features=ranges, enabled=False)).dropped == []
    # the tool: all rows with the top-level switch off
    (table,) = Filter()(data, config=parts(features=ranges, enabled=False)).values()
    assert list(table["name"]) == everything


def test_validate_only_the_filters_in_use(data):
    config = parts(
        features=[Range(column="t1", high=2)],
        other=[Range(column="t1", low=5), Expression(expression="1 +")],
    )
    problems = [(path, severity) for path, severity, _ in validate_filters(config, list(data.columns))]
    # the parts form one `all` group: the ranges on t1 don't overlap
    assert problems == [("other.filters[1].expression", "error"), ("other.filters[0]", "warning")]
    off = config.model_copy(update={"other": config.other.model_copy(update={"enabled": False})})
    assert validate_filters(off, list(data.columns)) == []
    schema = [TableSchema.from_frame(data)]
    config = parts(categories=[Category(column="FOV", keep=["9"])], categories_on=False)
    assert Filter.validate(config, schema) == []  # a value not in the column, not in use
    config = parts(categories=[Category(column="FOV", keep=["9"])])
    assert [i.field for i in Filter.validate(config, schema)] == ["categories.filters[0].keep"]


def test_one_filter_per_column_in_features_and_categories():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="two range filters on 't1'"):
        FilterConfig(features={"filters": [Range(column="t1"), Range(column="t1", low=1)]})
    with pytest.raises(ValidationError, match="two category filters on 'FOV'"):
        FilterConfig(categories={"filters": [Category(column="FOV"), Category(column="FOV")]})
    with pytest.raises(ValidationError):  # only range leaves in features
        FilterConfig(features={"filters": [Category(column="FOV")]})
    # further filters on a column: in the other filters
    config = FilterConfig(
        features={"filters": [Range(column="t1")]}, other={"filters": [Range(column="t1", low=1)]}
    )
    assert len(config.other.filters) == 1


def test_flat_filters_of_development_builds_convert_by_kind():
    flat = [
        Range(column="t1", high=2),
        Category(column="FOV", keep=["1"], enabled=False),
        Expression(expression="t1 > 0"),
        Range(column="t1", low=1),  # the second on t1: other
        Category(column="FOV", keep=["2"]),  # likewise
        Group(kind="any", filters=[Range(column="t2")]),
    ]
    config = FilterConfig.model_validate(
        {"enabled": False, "filters": [n.model_dump(mode="json") for n in flat]}
    )
    assert not config.enabled
    assert config.features.filters == [flat[0]]
    assert config.categories.filters == [flat[1]]
    assert config.other.filters == [flat[2], flat[3], flat[4], flat[5]]
    assert "filters" not in config.model_dump()
    # nothing is lost: the same rows are kept as by the flat list
    data = pd.DataFrame({"t1": [0.5, 1.5, 3.0], "t2": [1.0, 1.0, 1.0], "FOV": pd.Categorical(["1", "2", "2"])})
    assert apply_filters(data, config.model_copy(update={"enabled": True})).kept.tolist() == (
        apply_filters(data, flat).kept.tolist()
    )


def test_settings_of_0_6_convert_by_kind():
    config = FilterConfig(range_filters={"t1": {"high": 2}}, category_filters={"FOV": ["1"]})
    assert config.features.filters == [Range(column="t1", high=2)]
    assert config.categories.filters == [Category(column="FOV", keep=["1"])]
    assert config.other.filters == [] and config.enabled
    legacy = {"range_filters": [{"name": "t1", "rangelow": 0, "rangehigh": 2}], "category_filters": {"F": ["a"]}}
    config = FilterConfig.from_legacy_params({**legacy, "features": [], "use": False})
    assert (config.enabled, len(config.features.filters), len(config.categories.filters)) == (False, 1, 1)


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
    settings.filters.features.enabled = True
    filters = window_filters(settings)
    assert isinstance(filters, WindowFilters)
    assert filters.features.enabled and not filters.categories.enabled
    assert len(filters.range_filters) == 38  # the defaults, one per column
    assert sum(r["selected"] for r in filters.range_filters) == 3
    assert filters.category_filters == {}


def test_use_of_development_builds_is_read_as_both_switches():
    from flim.core.settings import FilterSettings

    for model in (WindowFilters, FilterSettings):
        on = model.model_validate({"use": True})
        assert on.features.enabled and on.categories.enabled
        assert "use" not in on.model_dump()
        off = model.model_validate({"use": False})
        assert not off.features.enabled and not off.categories.enabled
    with pytest.raises(ValueError):
        FilterSettings.model_validate({"use": "not a boolean"})


def test_window_settings_hold_only_the_range_filters():
    filters = WindowFilters(
        features={"enabled": True},
        categories={"enabled": True},
        range_filters=[{"name": "t1", "rangelow": 0, "rangehigh": 2, "selected": True}],
        category_filters={"FOV": ["1"]},
    )
    settings = window_settings(filters)
    assert set(settings) == {"features"}
    assert settings["features"]["enabled"] is True
    assert [n["column"] for n in settings["features"]["filters"]] == ["t1"]
    part = window_part(settings)
    assert (part.use, [r["name"] for r in part.ranges], part.unused) == (True, ["t1"], 0)


def test_window_part_ignores_category_filters_of_earlier_presets():
    earlier = {  # a preset of a development build: the switch and a flat list
        "enabled": False,
        "filters": [
            Range(column="t1", high=2).model_dump(mode="json"),
            Category(column="FOV", keep=["1"]).model_dump(mode="json"),
        ],
    }
    part = window_part(earlier)
    assert part.use is False  # the earlier `Filter Data`: the range filters' switch
    assert [r["name"] for r in part.ranges] == ["t1"] and part.unused == 1
    # a part without switches leaves Filter Features as it is
    assert window_part({"features": {"filters": []}}).use is None
    # the top-level switch narrows the part's
    assert window_part({"enabled": False, "features": {"enabled": True}}).use is False


def test_processing_of_workflow_file_steps_names_the_parts():
    from flim.core.config import Processing
    from flim.core.workflowfile import processing_issues

    config = parts(features=[Range(column="t1", high=2)])
    rules = Processing(
        skippable={"features": "some", "other": "all"}, required={"features": [{"column": "t1"}]}
    )
    assert processing_issues(Filter, rules, config, "step 1") == ([], [])
    rules = Processing(required={"features": [{"column": "t9"}]}, skippable={"filters": "some"})
    _, errors = processing_issues(Filter, rules, config, "step 1")
    assert any("can't skip entries of 'filters'" in e for e in errors)
    assert any("{'column': 't9'} is not an entry of features" in e for e in errors)


def test_workflow_file_step_with_a_range_on_a_missing_column(data):
    from flim.core.config import Processing, ProcessingRules
    from flim.core.validation import resolve_step

    config = parts(features=[Range(column="gone", high=2)], other=[Range(column="t1", high=5)])
    schema = TableSchema.from_frame(data)
    rules = ProcessingRules.of(Processing(skippable={"features": "some"}))
    resolution = resolve_step(Filter, config, [schema], rules)
    assert resolution.errors == [] and resolution.config == config  # the tool skips it
    tool = Filter()
    tool._processing = rules
    (table,) = tool(data, config=config).values()
    assert list(table["name"]) == ["a", "b"]  # the range on t1 applies
