"""The Data tools, without wx (the legacy plugins are tested in tests/test_data_plugins.py)."""

import numpy as np
import pandas as pd
import pytest

from flim.configs import (
    CategoryOrderConfig,
    ConcatConfig,
    FilterConfig,
    MergeConfig,
    PivotConfig,
    SortConfig,
    UnpivotConfig,
)
from flim.configs.data import RangeFilterSpec
from flim.core.schema import TableSchema
from flim.tools.data import (
    CategoryOrder,
    Concat,
    Filter,
    Merge,
    Pivot,
    Sort,
    Unpivot,
    unique_name,
)


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    rows = [
        {
            "Treatment": t,
            "FOV": f,
            "Cell": str(c),
            "t1": rng.normal(400, 20),
            "t2": rng.normal(3000, 100),
        }
        for t in ("WT", "KO")
        for f in ("1", "2")
        for c in range(5)
    ]
    df = pd.DataFrame(rows)
    for col in ("Treatment", "FOV", "Cell"):
        df[col] = df[col].astype("category")
    return df


def table(results):
    (value,) = results.values()
    return value


def test_category_order(data):
    config = CategoryOrderConfig(categories={"Treatment": ["WT", "KO"]})
    df = table(CategoryOrder()(data, config=config))
    assert list(df["Treatment"].cat.categories) == ["WT", "KO"]
    assert df["Treatment"].cat.ordered
    assert df["Treatment"].iloc[0] == "WT" and df["Treatment"].iloc[-1] == "KO"
    assert list(data["Treatment"].cat.categories) == ["KO", "WT"]  # input untouched


def test_category_order_without_categories(data):
    df = table(CategoryOrder()(data))
    pd.testing.assert_frame_equal(df, data)


def test_concat(data):
    tables = {"A": data.iloc[:8], "B": data.iloc[8:]}
    df = table(Concat()(tables, config=ConcatConfig()))
    assert len(df) == len(data)
    assert df["Source"].value_counts().to_dict() == {"A": 8, "B": 12}
    wide = table(
        Concat()(
            {"A": data[["Treatment", "t1"]], "B": data[["FOV", "t2"]]},
            config=ConcatConfig(mode="horizontal", numbers_only=True),
        )
    )
    assert list(wide.columns) == ["Treatment", "t1", "t2"]


def test_filter(data):
    low, high = data["t1"].quantile([0.25, 0.75])
    config = FilterConfig(
        category_filters={"Treatment": ["WT"]},
        range_filters=[
            RangeFilterSpec(column="t1", low=low, high=high, selected=True),
            RangeFilterSpec(column="t2", low=0, high=1, selected=False),  # not applied
        ],
    )
    df = table(Filter()(data, config=config))
    expected = data[(data["Treatment"] == "WT") & data["t1"].between(low, high)]
    assert len(df) == len(expected) > 0
    assert list(df.index) == list(range(len(df)))


def test_merge(data):
    left = data[["Treatment", "FOV", "Cell", "t1"]]
    right = data[["Treatment", "FOV", "Cell", "t2"]]
    df = table(Merge()(left, right))
    assert len(df) == len(data)
    assert list(df.columns) == ["Treatment", "FOV", "Cell", "t1", "t2"]
    by_fov = table(
        Merge()(
            left.iloc[:3],
            right,
            config=MergeConfig(how="left", on=["Treatment", "FOV", "Cell"]),
        )
    )
    assert len(by_fov) == 3


def test_pivot(data):
    df = table(
        Pivot()(data, config=PivotConfig(grouping=["Treatment"], features=["t1"]))
    )
    assert {"t1\nWT", "t1\nKO"} <= set(df.columns)
    assert len(df) == 10  # one row per FOV/Cell


def test_pivot_all_features(data):
    df = table(Pivot()(data, config=PivotConfig(grouping=["Treatment"])))
    assert {"t1\nWT", "t2\nKO"} <= set(df.columns)


def test_sort(data):
    df = table(Sort()(data, config=SortConfig(features=["t1"], ascending=False)))
    assert df["t1"].is_monotonic_decreasing
    assert list(df.index) == list(range(len(data)))


def test_unpivot(data):
    df = table(Unpivot()(data, config=UnpivotConfig(features=["t1", "t2"])))
    assert len(df) == 2 * len(data)
    assert set(df["Category"]) == {"t1", "t2"}


def test_unique_name():
    assert unique_name("", "Category", []) == "Category"
    assert unique_name("Treatment", "Category", ["Treatment"]) == "Treatment_1"
    # the plugin looped forever here
    assert unique_name("T", "Category", ["T", "T_1"]) == "T_2"


def test_output_schemas(data):
    schema = TableSchema.from_frame(data)
    pivoted = Pivot.output_schema(
        PivotConfig(grouping=["Treatment"], features=["t1"]), [schema]
    )
    assert pivoted["Pivoted"].schema.names == ["FOV", "Cell", "t1\nKO", "t1\nWT"]
    assert pivoted["Pivoted"].schema.column("t1\nKO").derived_from == ["t1"]
    assert pivoted["Pivoted"].schema.column("FOV").derived_from == ["FOV"]
    merged = Merge.output_schema(MergeConfig(), [schema, schema])
    assert merged["Merged"].schema.complete
    concat = Concat.output_schema(ConcatConfig(), [{"A": schema, "B": schema}])
    assert concat["Concatenated"].schema.column("Source").levels == ["A", "B"]
    unpivoted = Unpivot.output_schema(UnpivotConfig(features=["t1"]), [schema])
    assert unpivoted["Unpivoted"].schema.column("Category").levels == ["t1"]
