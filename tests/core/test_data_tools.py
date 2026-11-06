"""The Data tools, without wx."""

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
    SplitConfig,
    SummaryConfig,
    UnpivotConfig,
)
from flim.configs.data import RangeSettings
from flim.core.schema import TableSchema
from flim.tools.statistics import Summarize
from flim.tools.data import (
    CategoryOrder,
    Concat,
    Filter,
    Merge,
    Pivot,
    Sort,
    Split,
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
    config = CategoryOrderConfig(
        categories={"Treatment": ["WT", "KO"], "FOV": ["2", "1"]}
    )
    df = table(CategoryOrder()(data, config=config))
    assert list(df["Treatment"].cat.categories) == ["WT", "KO"]
    assert df["Treatment"].cat.ordered
    assert df["Treatment"].iloc[0] == "WT" and df["Treatment"].iloc[-1] == "KO"
    assert list(df["FOV"].iloc[:5]) == ["2"] * 5  # sorted by the new order
    assert list(data["Treatment"].cat.categories) == ["KO", "WT"]  # input untouched


def test_category_order_renumbers_the_rows(data, tmp_path):
    # the rows are numbered in their new order, and an autosaved table starts with
    # the data, not with the old row numbers (#119)
    from flim.results import save_results

    config = CategoryOrderConfig(categories={"Treatment": ["WT", "KO"]})
    df = table(CategoryOrder()(data, config=config))
    assert list(df.index) == list(range(len(data)))
    save_results({"Reordered": df}, str(tmp_path), "Order Categories")
    saved = pd.read_csv(tmp_path / "Reordered.txt", sep="\t")
    assert list(saved.columns) == [str(c) for c in df.columns]
    assert list(saved["Treatment"]) == list(df["Treatment"])


def test_category_order_without_categories(data):
    df = table(CategoryOrder()(data))
    pd.testing.assert_frame_equal(df, data)


def test_concat(data):
    tables = {"A": data.iloc[:8], "B": data.iloc[8:]}
    df = table(Concat()(tables, config=ConcatConfig()))
    assert len(df) == len(data)
    assert df["Source"].value_counts().to_dict() == {"A": 8, "B": 12}
    assert df["Source"].dtype == "category"
    assert df["Treatment"].dtype == "category"
    assert "Old Index" not in df.columns
    wide = table(
        Concat()(
            {"A": data[["Treatment", "t1"]], "B": data[["FOV", "t2"]]},
            config=ConcatConfig(mode="horizontal", numbers_only=True),
        )
    )
    assert list(wide.columns) == ["Treatment", "t1", "t2"]
    # all columns: a name already taken gets the table's name (#176)
    wide = table(
        Concat()(
            {"A": data[["Treatment", "t1"]], "B": data[["Treatment", "t2"]]},
            config=ConcatConfig(mode="horizontal"),
        )
    )
    assert list(wide.columns) == ["Treatment", "t1", "Treatment (B)", "t2"]
    assert len(wide) == len(data)


def test_filter(data):
    low, high = data["t1"].quantile([0.25, 0.75])
    config = FilterConfig(
        category_filters={"Treatment": ["WT"]},
        range_filters={"t1": RangeSettings(low=low, high=high)},
    )
    df = table(Filter()(data, config=config))
    expected = data[(data["Treatment"] == "WT") & data["t1"].between(low, high)]
    assert len(df) == len(expected) > 0
    assert set(df["Treatment"]) == {"WT"}
    assert list(df.index) == list(range(len(df)))
    assert len(data) == 20  # input untouched


def test_filter_open_ranges_and_missing_values(data):
    data.loc[0, "t1"] = np.nan
    above = table(
        Filter()(data, config=FilterConfig(range_filters={"t1": {"low": 400}}))
    )
    assert (above["t1"] >= 400).all() and len(above) < len(data)
    keep_missing = FilterConfig(range_filters={"t1": {"low": 400, "dropna": False}})
    assert table(Filter()(data, config=keep_missing))["t1"].isna().sum() == 1


def test_merge(data):
    left = data[["Treatment", "FOV", "Cell", "t1"]]
    right = data[["Treatment", "FOV", "Cell", "t2"]]
    df = table(Merge()(left, right))
    assert len(df) == len(data)
    assert list(df.columns) == ["Treatment", "FOV", "Cell", "t1", "t2"]
    assert all(df[c].dtype == "category" for c in ("Treatment", "FOV", "Cell"))
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
    # no features: all of them
    df = table(Pivot()(data, config=PivotConfig(grouping=["Treatment"])))
    assert {"t1\nWT", "t2\nKO"} <= set(df.columns)


def test_sort(data):
    df = table(Sort()(data, config=SortConfig(features=["t1"], ascending=False)))
    assert df["t1"].is_monotonic_decreasing
    assert list(df.index) == list(range(len(data)))


def test_unpivot_single_line_columns(data):
    df = table(Unpivot()(data, config=UnpivotConfig(features=["t1", "t2"])))
    assert len(df) == 2 * len(data)
    # the level of single-line columns: the feature; the values in one column
    assert list(df.columns) == ["Treatment", "FOV", "Cell", "Feature", "Value"]
    assert list(df["Feature"].cat.categories) == ["t1", "t2"]
    np.testing.assert_allclose(
        df.loc[df["Feature"] == "t1", "Value"].to_numpy(), data["t1"].to_numpy()
    )
    named = UnpivotConfig(features=["t1", "t2"], category_name="Lifetime")
    assert "Lifetime" in table(Unpivot()(data, config=named))


def test_unpivot_is_the_inverse_of_pivot(data):
    pivoted = table(Pivot()(data, config=PivotConfig(grouping=["Treatment"])))
    assert pivoted.attrs["header_levels"] == ["Feature", "Treatment"]
    df = table(Unpivot()(pivoted, config=UnpivotConfig()))  # the last level
    assert list(df.columns) == ["FOV", "Cell", "Treatment", "t1", "t2"]
    assert "header_levels" not in df.attrs  # single lines again
    back = df.set_index(["Treatment", "FOV", "Cell"]).sort_index()
    original = data.set_index(["Treatment", "FOV", "Cell"]).sort_index()
    pd.testing.assert_frame_equal(back, original, check_categorical=False)
    # the other level: the features become a category, the treatments columns
    df = table(Unpivot()(pivoted, config=UnpivotConfig(level="Feature")))
    assert list(df.columns) == ["FOV", "Cell", "Feature", "KO", "WT"]


def test_unpivot_a_pivoted_summary_by_any_level(data):
    summary = table(
        Summarize()(
            data,
            config=SummaryConfig(
                grouping=["Treatment", "FOV"], features=["t1"], aggs=["mean", "std"]
            ),
        )
    )
    assert summary.attrs["header_levels"] == ["Feature", "Statistic"]
    pivoted = table(
        Pivot()(
            summary,
            config=PivotConfig(grouping=["Treatment"], features=["t1\nmean", "t1\nstd"]),
        )
    )
    assert "t1\nmean\nKO" in pivoted
    assert pivoted.attrs["header_levels"] == ["Feature", "Statistic", "Treatment"]
    df = table(Unpivot()(pivoted, config=UnpivotConfig(level="Statistic")))
    assert list(df.columns) == ["FOV", "Statistic", "t1\nKO", "t1\nWT"]
    assert df.attrs["header_levels"] == ["Feature", "Treatment"]


def test_unpivot_a_summary_of_several_features(data):
    summary = table(
        Summarize()(
            data,
            config=SummaryConfig(grouping=["Treatment"], features="all", aggs=["mean"]),
        )
    )
    # the statistic (line 2; by name or position) becomes a category column
    for level in ("", "Statistic", "Level 2", "2"):
        df = table(Unpivot()(summary, config=UnpivotConfig(level=level)))
        assert list(df.columns) == ["Treatment", "Statistic", "t1", "t2"], level
    # the feature (line 1): a column of feature names, one of means
    df = table(Unpivot()(summary, config=UnpivotConfig(level="Feature")))
    assert list(df.columns) == ["Treatment", "Feature", "mean"]
    assert list(df["Feature"].cat.categories) == ["t1", "t2"]


def test_unpivot_strips_feature_prefix_with_regex_characters():
    # pivoted column headers have the form "<feature>\n<category>"
    data = pd.DataFrame(
        {
            "FOV": pd.Categorical(["1", "2"]),
            "Value (a.u.)\nWT": [1.0, 2.0],
            "Value (a.u.)\nKO": [3.0, 4.0],
        }
    )
    config = UnpivotConfig(
        features=["Value (a.u.)\nWT", "Value (a.u.)\nKO"], category_name="Treatment"
    )
    df = table(Unpivot()(data, config=config))
    assert set(df["Treatment"]) == {"WT", "KO"}


def test_unpivot_without_recorded_levels(data):
    pivoted = table(Pivot()(data, config=PivotConfig(grouping=["Treatment"])))
    pivoted.attrs.clear()  # e.g. saved as text and read back
    df = table(Unpivot()(pivoted, config=UnpivotConfig(level="Level 2")))
    assert "Level 2" in df and "t1" in df
    with pytest.raises(ValueError, match="No header level 'Treatment'"):
        Unpivot().run(pivoted, config=UnpivotConfig(level="Treatment"))


def test_unpivot_needs_the_same_number_of_header_lines(data):
    pivoted = table(Pivot()(data, config=PivotConfig(grouping=["Treatment"])))
    pivoted["t3"] = 1.0
    with pytest.raises(ValueError, match="different numbers of header lines"):
        Unpivot().run(pivoted, config=UnpivotConfig())


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
    assert unpivoted["Unpivoted"].schema.column("Feature").levels == ["t1"]
    # the pivot's level names reach the unpivot through the schemas
    assert pivoted["Pivoted"].schema.header_levels == ["Feature", "Treatment"]
    unpivoted = Unpivot.output_schema(UnpivotConfig(), [pivoted["Pivoted"].schema])
    assert unpivoted["Unpivoted"].schema.names == ["FOV", "Cell", "Treatment", "t1"]


def test_category_order_keeps_the_order_of_other_columns():
    import numpy as np

    from flim.configs import CategoryOrderConfig
    from flim.tools.data import CategoryOrder

    treatments = ["Dox15", "Dox30", "Dox45", "Dox60", "ctrl"]
    rows = [(t, fov) for t in treatments for fov in "abcde" for _ in range(20)]
    data = pd.DataFrame(rows, columns=["Treatment", "FOV"]).astype("category")
    data["x"] = np.arange(len(data))
    order = ["ctrl"] + treatments[:4]
    config = CategoryOrderConfig(categories={"Treatment": order})
    table = CategoryOrder()(data, config=config)["Table: Reordered"]
    assert list(table["Treatment"].unique()) == order
    for _, group in table.groupby("Treatment", observed=True):
        assert list(group["FOV"]) == sorted(group["FOV"])  # a, b, c, d, e as before
        assert list(group["x"]) == sorted(group["x"])


def test_split(data):
    data["Treatment"] = pd.Categorical(data["Treatment"], categories=["WT", "KO", "Het"])
    results = Split().run(data, config=SplitConfig(grouping=["Treatment", "FOV"]))
    # in the order of the categories; "Het" has no rows: no table
    assert list(results) == [
        "Split: Treatment=WT, FOV=1",
        "Split: Treatment=WT, FOV=2",
        "Split: Treatment=KO, FOV=1",
        "Split: Treatment=KO, FOV=2",
    ]
    table = results["Split: Treatment=KO, FOV=2"]
    assert len(table) == 5
    assert set(table["Treatment"]) == {"KO"} and set(table["FOV"]) == {"2"}
    assert list(table.columns) == list(data.columns)
    assert sum(len(t) for t in results.values()) == len(data)


def test_split_needs_columns():
    with pytest.raises(ValueError, match="columns to split by"):
        SplitConfig(grouping=[])


def test_split_outputs_known_from_the_schema(data):
    schema = TableSchema.from_frame(data)
    outputs = Split.output_schema(SplitConfig(grouping=["Treatment"]), [schema])
    assert sorted(outputs) == ["Split: Treatment=KO", "Split: Treatment=WT"]
