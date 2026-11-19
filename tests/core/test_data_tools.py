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
    save_results({"Reordered": df}, str(tmp_path), "Order Category Values")
    saved = pd.read_csv(tmp_path / "Reordered.txt", sep="\t")
    assert list(saved.columns) == [str(c) for c in df.columns]
    assert list(saved["Treatment"]) == list(df["Treatment"])


def test_category_order_appends_values_not_configured(data):
    # as the GUI's editor: values not configured follow, in their order in the data
    data["Treatment"] = data["Treatment"].cat.set_categories(["KO", "WT", "Het"])
    data["Cell"] = data["Cell"].astype(str)  # a text column: values in data order
    config = CategoryOrderConfig(categories={"Treatment": ["WT"], "Cell": ["3", "1"]})
    tool = CategoryOrder()
    df = table(tool(data, config=config))
    assert list(df["Treatment"].cat.categories) == ["WT", "KO", "Het"]
    assert list(df["Cell"].cat.categories) == ["3", "1", "0", "2", "4"]
    assert df["Treatment"].notna().all() and df["Cell"].notna().all()
    assert list(df["Treatment"].iloc[[0, -1]]) == ["WT", "KO"]
    # "Het" has no rows: not named
    assert tool.context.warnings == [
        "Treatment: values not in the configured order, placed after it: KO",
        "Cell: values not in the configured order, placed after it: 0, 2, 4",
    ]
    tool = CategoryOrder()
    tool(data, config=CategoryOrderConfig(categories={"Treatment": ["WT", "KO"]}))
    assert tool.context.warnings == []


def test_category_order_without_categories(data):
    df = table(CategoryOrder()(data))
    pd.testing.assert_frame_equal(df, data)


def test_concat(data):
    tables = {"A": data.iloc[:8], "B": data.iloc[8:]}
    df = table(Concat()(tables, config=ConcatConfig()))
    assert len(df) == len(data)
    assert df["Input"].value_counts().to_dict() == {"A": 8, "B": 12}
    assert df["Input"].dtype == "category"
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


def test_merge_combines_identical_columns_and_names_the_others(data, prefect_harness):
    from flim.core.runner import run_flow

    keys = ["Treatment", "FOV", "Cell"]
    left = data[keys + ["t1", "t2"]].assign(Source="file:///a.txt")
    right = data[keys + ["t1"]].assign(t2=data["t2"] + 1, Source="file:///a.txt")
    df = table(Merge()(left, right))
    # t1 and Source agree: one column each; t2 differs: both, with suffixes
    assert list(df.columns) == keys + ["t1", "t2 (left)", "Source", "t2 (right)"]
    kept = table(Merge()(left, right, config=MergeConfig(combine_identical=False)))
    assert {"t1 (left)", "t1 (right)", "Source (left)"} <= set(kept.columns)
    old = table(Merge()(left, right, config=MergeConfig(suffix_left="_x", suffix_right="_y")))
    assert {"t2_x", "t2_y"} <= set(old.columns)
    with pytest.raises(ValueError, match="must differ"):
        MergeConfig(suffix_left="_a", suffix_right="_a")
    run = run_flow("merge", lambda: Merge()(left, right))
    messages = [a.get("message") or "" for _, a in run.graph.nodes(data=True) if "tool" in a]
    assert any("1 column(s) of both tables differ" in m and "'t2'" in m for m in messages)


def test_merge_outer_join_takes_the_value_of_either_side():
    left = pd.DataFrame({"FOV": pd.Categorical(["1", "2"]), "t1": [1.0, 2.0], "Note": pd.Categorical(["a", "b"])})
    right = pd.DataFrame({"FOV": pd.Categorical(["2", "3"]), "t1": [2, 3], "Note": pd.Categorical(["b", "c"])})
    df = table(Merge()(left, right, config=MergeConfig(how="outer")))
    # equal where both have a value (2.0 and 2): one column, filled from either side
    assert list(df.columns) == ["FOV", "Note", "t1"]  # category columns first
    assert list(df["t1"]) == [1.0, 2.0, 3.0] and list(df["Note"]) == ["a", "b", "c"]
    assert isinstance(df["Note"].dtype, pd.CategoricalDtype)  # the left table's type


def _keyed(fovs, values):
    return pd.DataFrame({"FOV": pd.Categorical(fovs), "x": values})


@pytest.mark.parametrize(
    "how, rows",
    [
        ("inner", [("1", 1.0, 10.0)]),
        ("left", [("1", 1.0, 10.0), (None, 2.0, None), (None, 3.0, None)]),
        ("right", [("1", 1.0, 10.0), (None, None, 20.0)]),
        ("outer", [("1", 1.0, 10.0), (None, 2.0, None), (None, 3.0, None), (None, None, 20.0)]),
    ],
)
def test_merge_does_not_pair_missing_key_values(how, rows):
    left = _keyed(["1", None, None], [1.0, 2.0, 3.0])
    right = _keyed(["1", None], [10.0, 20.0])
    tool = Merge()
    merged = table(tool(left, right, config=MergeConfig(how=how)))
    values = merged.astype(object).where(merged.notna(), None)
    assert sorted(map(tuple, values.values.tolist()), key=str) == sorted(rows, key=str)
    assert list(merged.columns) == ["FOV", "x (left)", "x (right)"]
    (warning, _) = tool.context.warnings  # and the suffixes warning
    first = "kept without a match" if how in ("left", "outer") else "left out"
    second = "kept without a match" if how in ("right", "outer") else "left out"
    assert warning == (
        "rows with no value in a column merged on (FOV) match no row:"
        f" 2 of the first table ({first}); 1 of the second table ({second})"
    )


def test_merge_without_columns_to_merge_on():
    left = _keyed(["1"], [1.0])
    right = pd.DataFrame({"Cell": pd.Categorical(["1"]), "y": [2.0]})
    schemas = [TableSchema.from_frame(left), TableSchema.from_frame(right)]
    issues = Merge.validate(MergeConfig(), schemas)
    assert [(i.field, i.message, i.severity) for i in issues] == [
        ("on", "The two tables have no shared category columns to merge on", "error")
    ]
    assert Merge.validate(MergeConfig(), [schemas[0], schemas[0]]) == []
    assert Merge.validate(MergeConfig(), [None, schemas[1]]) == []  # not known
    with pytest.raises(ValueError, match="Merge: the two tables have no shared category"):
        Merge()(left, right)
    (issue,) = Merge.validate(MergeConfig(on=[]), [None, None])
    assert issue.message == "Select at least one column to merge on"
    with pytest.raises(ValueError, match="select at least one column to merge on"):
        Merge()(left, left, config=MergeConfig(on=[]))


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
    # single-line columns: their names go into one category column, their values
    # into one value column
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
    # the other level: the features become a category, the treatments become columns
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


def test_unpivot_fills_missing_header_lines():
    """A column with fewer header lines (FLIRR next to FLIRR / standardized, after
    Scale with Keep original): its missing line gets the label."""
    data = pd.DataFrame({
        "FOV": pd.Categorical(["1", "2"]), "FLIRR": [1.0, 2.0], "FLIRR\nstandardized": [-1.0, 1.0],
    })  # fmt: skip
    config = UnpivotConfig(category_name="Scaling mode", missing_label="original")
    df = table(Unpivot()(data, config=config))
    assert list(df.columns) == ["FOV", "Scaling mode", "FLIRR"]
    assert list(df["Scaling mode"]) == ["original", "original", "standardized", "standardized"]
    assert list(df["FLIRR"]) == [1.0, 2.0, -1.0, 1.0]
    (issue,) = Unpivot.validate_data(UnpivotConfig(), [data])
    assert issue.field == "missing_label" and "'FLIRR'" in issue.message and "'none'" in issue.message


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
    assert concat["Concatenated"].schema.column("Input").levels == ["A", "B"]
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


def test_split_warns_about_rows_without_a_grouping_value(data):
    data.loc[data.index[:2], "FOV"] = np.nan
    tool = Split()
    results = tool(data, config=SplitConfig(grouping=["Treatment", "FOV"]))
    assert sum(len(t) for t in results.values()) == len(data) - 2  # as before
    assert tool.context.warnings == ["2 rows left out: no value in the grouping column 'FOV'"]
    tool = Split()
    tool(data.dropna(), config=SplitConfig(grouping=["Treatment", "FOV"]))
    assert tool.context.warnings == []


def test_pivot_warns_about_rows_without_a_category_value(data):
    data.loc[data.index[0], "Treatment"] = np.nan
    data.loc[data.index[1], "Cell"] = np.nan
    tool = Pivot()
    pivoted = table(tool(data, config=PivotConfig(grouping=["Treatment"], features=["t1"])))
    expected = data.dropna().groupby(["FOV", "Cell", "Treatment"], observed=True)["t1"].mean()
    assert pivoted.set_index(["FOV", "Cell"])["t1\nWT"].dropna().to_dict() == (
        expected.xs("WT", level="Treatment").to_dict()
    )
    assert tool.context.warnings == [
        "2 rows left out: no value in the category columns 'Treatment', 'Cell'"
    ]


def test_split_needs_columns(data):
    # a valid setting (its default), but the run needs a column to split by
    config = SplitConfig.model_validate(SplitConfig().model_dump(mode="json"))
    assert config.grouping == []
    issues = Split.validate(config, [TableSchema.from_frame(data)])
    assert [(i.field, i.message) for i in issues] == [
        ("grouping", "Select at least 1 grouping column")
    ]
    with pytest.raises(ValueError, match="select at least 1 grouping column"):
        Split()(data, config=config)


def test_split_outputs_known_from_the_schema(data):
    schema = TableSchema.from_frame(data)
    outputs = Split.output_schema(SplitConfig(grouping=["Treatment"]), [schema])
    assert sorted(outputs) == ["Split: Treatment=KO", "Split: Treatment=WT"]


# --- Scale ---


def test_scale_methods_and_names(data):
    from flim.configs import ScaleConfig
    from flim.tools.data import Scale

    features = ["FLIRR"] if "FLIRR" in data.columns else [
        c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
    ][:1]
    (feature,) = features
    for method, suffix in (("standardize", "standardized"), ("min-max", "min-max"),
                           ("robust", "robust")):
        (table,) = Scale()(data, config=ScaleConfig(features=features, method=method)).values()
        column = table[f"{feature}\n{suffix}"]
        assert feature in table.columns  # kept by default
        if method == "standardize":
            assert column.mean() == pytest.approx(0, abs=1e-9)
            assert column.std(ddof=0) == pytest.approx(1)
        elif method == "min-max":
            assert (column.min(), column.max()) == pytest.approx((0, 1))
        else:
            assert column.median() == pytest.approx(0, abs=1e-9)


def test_scale_is_the_same_function_as_standardize_input(data):
    import numpy as np

    from flim.configs import ScaleConfig
    from flim.tools.data import Scale
    from flim.tools.ml import standardized

    feature = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])][0]
    (table,) = Scale()(data, config=ScaleConfig(features=[feature])).values()
    expected = standardized(data[[feature]].to_numpy(dtype=float))[:, 0]
    np.testing.assert_allclose(table[f"{feature}\nstandardized"], expected)


def test_scale_within_groups_and_replacing(data):
    from flim.configs import ScaleConfig
    from flim.tools.data import Scale

    feature = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])][0]
    group = [c for c in data.columns if isinstance(data[c].dtype, pd.CategoricalDtype)][0]
    config = ScaleConfig(features=[feature], method="min-max", grouping=[group],
                         keep_original=False)
    (table,) = Scale()(data, config=config).values()
    name = f"{feature}\nmin-max"
    assert feature not in table.columns
    assert list(table.columns).index(name) == list(data.columns).index(feature)  # in place
    for _, rows in table.groupby(group, observed=True):
        assert (rows[name].min(), rows[name].max()) == pytest.approx((0, 1))


def test_scale_keeps_missing_values(data):
    import numpy as np

    from flim.configs import ScaleConfig
    from flim.tools.data import Scale

    feature = [c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])][0]
    data = data.copy()
    data.loc[data.index[0], feature] = np.nan
    (table,) = Scale()(data, config=ScaleConfig(features=[feature])).values()
    assert np.isnan(table[f"{feature}\nstandardized"].iloc[0])
    assert table[f"{feature}\nstandardized"].iloc[1:].notna().all()


# --- Fuse and Separate Categories ---


def _cells():
    return pd.DataFrame(
        {
            "FOV": pd.Categorical(["1", "1", "2"]),
            "Cell": pd.Categorical(["1", "2", "1"]),
            "t1": [1.0, 2.0, 3.0],
        }
    )


def test_fuse_categories_places_and_keeps():
    from flim.configs import FuseCategoriesConfig
    from flim.tools.data import FuseCategories

    (fused,) = FuseCategories()(_cells(), config=FuseCategoriesConfig(grouping=["FOV", "Cell"])).values()
    assert list(fused.columns) == ["FOV", "Cell", "FOV:Cell", "t1"]  # after the last
    assert list(fused["FOV:Cell"]) == ["1:1", "1:2", "2:1"]
    assert isinstance(fused["FOV:Cell"].dtype, pd.CategoricalDtype)
    config = FuseCategoriesConfig(grouping=["FOV", "Cell"], name="ID", keep_original=False)
    (fused,) = FuseCategories()(_cells(), config=config).values()
    assert list(fused.columns) == ["ID", "t1"]


def test_new_column_takes_the_name_of_a_removed_column():
    from flim.configs import FuseCategoriesConfig, SeparateCategoriesConfig
    from flim.tools.data import FuseCategories, SeparateCategories

    data = _cells().assign(Treatment=pd.Categorical(["a", "b", "a"]))
    config = FuseCategoriesConfig(grouping=["FOV", "Cell"], name="FOV", keep_original=False)
    tool = FuseCategories()
    (fused,) = tool(data, config=config).values()
    assert list(fused.columns) == ["FOV", "t1", "Treatment"]  # in place of FOV and Cell
    assert list(fused["FOV"]) == ["1:1", "1:2", "2:1"]
    assert tool.context.warnings == [] and FuseCategories.validate_data(config, [data]) == []
    config = SeparateCategoriesConfig(column="FOV", names=["FOV", "N"], keep_original=False)
    tool = SeparateCategories()
    (separated,) = tool(fused, config=config).values()
    assert list(separated.columns) == ["FOV", "N", "t1", "Treatment"]
    assert list(separated["FOV"]) == ["1", "1", "2"] and list(separated["N"]) == ["1", "2", "1"]
    assert tool.context.warnings == [] and SeparateCategories.validate_data(config, [fused]) == []
    # the original kept: the new column gets a number, after the separated column
    kept = config.model_copy(update={"keep_original": True})
    (separated,) = SeparateCategories()(fused, config=kept).values()
    assert list(separated.columns) == ["FOV", "FOV_1", "N", "t1", "Treatment"]


def test_fuse_then_separate_round_trip():
    from flim.configs import FuseCategoriesConfig, SeparateCategoriesConfig
    from flim.tools.data import FuseCategories, SeparateCategories

    config = FuseCategoriesConfig(grouping=["FOV", "Cell"], keep_original=False)
    (fused,) = FuseCategories()(_cells(), config=config).values()
    config = SeparateCategoriesConfig(column="FOV:Cell", keep_original=False)
    (back,) = SeparateCategories()(fused, config=config).values()
    assert list(back.columns) == ["FOV", "Cell", "t1"]
    pd.testing.assert_frame_equal(
        back.astype(str), _cells().astype(str), check_dtype=False
    )


def test_separate_by_patterns_and_validation():
    from flim.configs import SeparateCategoriesConfig
    from flim.configs.data import CategoryPattern
    from flim.tools.data import SeparateCategories

    data = pd.DataFrame({"File": pd.Categorical(["/d/ctrl/c1.txt", "/d/dox/c2.txt"]), "t1": [1.0, 2.0]})
    config = SeparateCategoriesConfig(
        column="File", mode="pattern",
        patterns=[CategoryPattern(name="Treatment", regex=r"/d/(.*?)/")],
    )
    (table,) = SeparateCategories()(data, config=config).values()
    assert list(table["Treatment"]) == ["ctrl", "dox"]
    issues = SeparateCategories.validate(SeparateCategoriesConfig(mode="pattern"), [])
    assert {i.field for i in issues} == {"column", "patterns"}


def test_separate_warns_in_the_run_summary(prefect_harness):
    from flim.configs import SeparateCategoriesConfig
    from flim.core.runner import run_flow
    from flim.tools.data import SeparateCategories

    data = pd.DataFrame({"ID": pd.Categorical(["a:1", "b"]), "t1": [1.0, 2.0]})

    def build():
        SeparateCategories()(data, config=SeparateCategoriesConfig(column="ID", names=["L", "N"]))

    run = run_flow("separate", build)
    messages = [a.get("message") for _, a in run.graph.nodes(data=True) if "tool" in a]
    assert any("have not 2 parts" in (m or "") for m in messages)



def _cells_of(table):
    """An example table as its header and rows of values."""
    return [list(table.columns)] + table.astype(object).where(table.notna(), None).values.tolist()

def test_fuse_example_and_data_validation():
    from flim.configs import FuseCategoriesConfig
    from flim.tools.data import FuseCategories

    config = FuseCategoriesConfig(grouping=["FOV", "Cell"])
    example = FuseCategories.example(config, [_cells()])
    assert _cells_of(example)[:2] == [["FOV", "Cell", "\u2192 FOV:Cell"], ["1", "1", "1:1"]]
    assert FuseCategories.validate_data(config, [_cells()]) == []
    data = _cells()
    data["Time"] = pd.Categorical(["0:30", "1:00", "0:30"])
    issues = FuseCategories.validate_data(FuseCategoriesConfig(grouping=["FOV", "Time"]), [data])
    assert [(i.field, i.severity) for i in issues] == [("delimiter", "warning")]
    assert FuseCategories.example(FuseCategoriesConfig(grouping=["FOV"]), [data]) is None


def test_separate_example_and_data_validation():
    from flim.configs import SeparateCategoriesConfig
    from flim.configs.data import CategoryPattern
    from flim.tools.data import SeparateCategories

    data = pd.DataFrame({"File": pd.Categorical(["/d/Results-ko_01.txt", "/d/Results-wt.txt"])})
    config = SeparateCategoriesConfig(
        column="File", delimiters=["-", "_"], names=["", "Treatment", "Cell"],
        part="file name without extension",
    )
    example = SeparateCategories.example(config, [data])
    assert _cells_of(example)[:2] == [
        [config.column, "\u2192 Treatment", "\u2192 Cell"], [data[config.column].iloc[0], "ko", "01"]
    ]
    (issue,) = SeparateCategories.validate_data(config, [data])
    assert issue.field == "names" and "'Results-wt'" in issue.message
    bad = SeparateCategoriesConfig(
        column="File", mode="pattern", patterns=[CategoryPattern(name="X", regex="(")]
    )
    (issue,) = SeparateCategories.validate_data(bad, [data])
    assert issue.severity == "error" and "not a valid pattern" in issue.message


def test_rename_columns_in_order_and_unique():
    from flim.configs import RenameColumnsConfig
    from flim.configs.data import Replacement
    from flim.tools.data import RenameColumns

    data = pd.DataFrame({"Exc1_-Ch1-_t1": [1.0], "Exc2_-Ch3-_t1": [2.0], "x": [3.0]})
    (renamed,) = RenameColumns()(data, config=RenameColumnsConfig()).values()
    assert list(renamed.columns) == ["trp t1", "FAD t1", "x"]
    # in order: the second replacement applies to the first one's result
    config = RenameColumnsConfig(
        replacements=[Replacement(part="_t1", new=" y"), Replacement(part=" y", new=" z")]
    )
    example = RenameColumns.example(config, [data])
    assert _cells_of(example)[:2] == [["Column", "\u2192 New name"], ["Exc1_-Ch1-_t1", "Exc1_-Ch1- z"]]
    assert _cells_of(RenameColumns.example(RenameColumnsConfig(), [data]))[1] == ["Exc1_-Ch1-_t1", "trp t1"]
    clash = RenameColumnsConfig(replacements=[Replacement(part="Exc2_-Ch3-_", new="Exc1_-Ch1-_")])
    with pytest.raises(ValueError, match="not unique"):
        RenameColumns().run(data, config=clash)
    with pytest.raises(ValueError, match="needs the part"):
        RenameColumnsConfig(replacements=[Replacement(part="", new="a")])


def test_rename_columns_reports_against_the_names_at_each_step():
    from flim.configs import RenameColumnsConfig
    from flim.configs.data import Replacement
    from flim.tools.data import RenameColumns

    data = pd.DataFrame({"a_t1": [1.0], "x": [2.0]})
    # " y" occurs only after the first replacement; "a_" no more after it
    config = RenameColumnsConfig(
        replacements=[
            Replacement(part="_t1", new=" y"),
            Replacement(part=" y", new=" z"),
            Replacement(part="_t1", new="w"),
        ]
    )
    tool = RenameColumns()
    (renamed,) = tool(data, config=config).values()
    assert list(renamed.columns) == ["a z", "x"]
    assert tool.context.applied == 2
    assert [(entry.part, entry.new) for _, entry, _ in tool.context.skipped] == [("_t1", "w")]


def test_drop_columns_match_modes():
    from flim.configs import DropColumnsConfig
    from flim.configs.data import DropRule
    from flim.tools.data import DropColumns

    data = pd.DataFrame({"Exc1_t1": [1], "t1": [2], "t1 sd": [3], "sd t1": [4], " ": [5]})

    def kept(*rules):
        config = DropColumnsConfig(drop=[DropRule(text=t, match=m) for t, m in rules])
        (table,) = DropColumns()(data, config=config).values()
        return list(table.columns)

    assert kept() == ["Exc1_t1", "t1", "t1 sd", "sd t1"]  # the empty header
    assert kept(("Exc1_", "contains")) == ["t1", "t1 sd", "sd t1"]
    assert kept(("t1", "starts with")) == ["Exc1_t1", "sd t1"]
    assert kept(("t1", "ends with")) == ["t1 sd"]
    assert kept(("t1", "is")) == ["Exc1_t1", "t1 sd", "sd t1"]
    assert _cells_of(DropColumns.example(DropColumnsConfig(), [data])) == [
        ["Dropped column"], ["Exc1_t1"], ["(empty header)"]
    ]


def test_separate_by_template():
    from flim.configs.data import SeparateCategoriesConfig
    from flim.tools.data import SeparateCategories

    data = pd.DataFrame({"Source": ["file:///d/Results-a-ctrl_1.txt", "file:///d/Results-b-ko_12.txt", "file:///d/x.txt"]})
    config = SeparateCategoriesConfig(
        column="Source", mode="template", part="file name without extension",
        template="Results-{FOV}-{Treatment}_{Cell}",
    )  # fmt: skip
    (table,) = SeparateCategories()(data, config=config).values()
    assert list(table["FOV"])[:2] == ["a", "b"] and list(table["Cell"])[:2] == ["1", "12"]
    assert table["Treatment"].isna().iloc[2]  # x.txt does not fit
    # the dialog's example line: the first row
    example = SeparateCategories.example(config, [data])
    assert _cells_of(example)[1][1:] == ["a", "ctrl", "1"]
    assert example.columns[1:].tolist() == ["\u2192 FOV", "\u2192 Treatment", "\u2192 Cell"]
    (issue,) = SeparateCategories.validate_data(config, [data])
    assert issue.field == "template" and "do not fit" in issue.message
    # {} skips a part; a template without names is an error
    skip = config.model_copy(update={"template": "{}-{FOV}-{}"})
    (table,) = SeparateCategories()(data.iloc[:2], config=skip).values()
    assert list(table["FOV"]) == ["a", "b"] and "Treatment" not in table.columns
    issues = SeparateCategories.validate(config.model_copy(update={"template": "Results"}), [])
    assert any(i.field == "template" and "no part with a name" in i.message for i in issues)


def test_separate_modes_of_earlier_versions_are_read():
    from flim.configs.data import SeparateCategoriesConfig

    assert SeparateCategoriesConfig(mode="patterns").mode == "pattern"
    assert SeparateCategoriesConfig(mode="delimiters").mode == "delimiter"


@pytest.mark.parametrize("mode", ["vertical", "horizontal"])
def test_concat_of_one_table_passes_it_on_unchanged(data, mode):
    from flim.configs import ConcatConfig
    from flim.tools.data import Concat

    (table,) = Concat()({"only": data}, config=ConcatConfig(mode=mode, add_input=True)).values()
    pd.testing.assert_frame_equal(table, data)  # no Input column
    assert table is not data


def test_concat_side_by_side_pairs_rows_by_position():
    """Tables whose row labels are not 0, 1, 2, ... (rows left after filtering) are
    paired by position; they were paired by label, giving empty rows."""
    from flim.configs import ConcatConfig
    from flim.tools.data import Concat

    a = pd.DataFrame({"FOV": pd.Categorical(list("abcdef")), "x": [1.0, 2, 3, 4, 5, 6]})
    b = pd.DataFrame({"y": [10.0, 20, 30, 40, 50, 60]})
    config = ConcatConfig(mode="horizontal", numbers_only=False)
    (table,) = Concat()({"A": a.iloc[[0, 2, 4]], "B": b.iloc[[1, 3, 5]]}, config=config).values()
    assert len(table) == 3 and list(table.index) == [0, 1, 2]
    assert list(table["x"]) == [1.0, 3.0, 5.0] and list(table["y"]) == [20.0, 40.0, 60.0]


def _flim_table():
    return pd.DataFrame({
        "Treatment": pd.Categorical(["ctrl", "ctrl", "dox", "dox"]),
        "FOV": pd.Categorical(["1", "2", "1", "2"]),
        "FLIRR": [0.4, 0.5, 0.6, 0.7],
        "FAD a1[%]": [70.0, 72.0, 75.0, 77.0],
    })  # fmt: skip


def test_reshaping_examples_show_the_result_rows():
    from flim.tools.data import Pivot, Unpivot

    example = Unpivot.example(Unpivot.config_class(features="all"), [_flim_table()])
    assert example.attrs["caption"] == "the first 2 rows become 4 rows"
    assert all(c.startswith("→ ") for c in example.columns)  # all made by the tool
    example = Pivot.example(Pivot.config_class(grouping=["Treatment"], features="all"), [_flim_table()])
    assert example.attrs["caption"].startswith("the result has 2 rows")
    assert example.columns[0] == "→ FOV"


def test_scale_example_shows_features_before_and_after():
    from flim.tools.data import Scale

    example = Scale.example(Scale.config_class(features=["FLIRR"]), [_flim_table()])
    assert list(example.columns) == ["FLIRR", "→ FLIRR / standardized"]
    assert example.iloc[:, 1].mean() == pytest.approx(0)


def test_categorize_example_shows_a_row_per_category():
    from flim.configs.analysis import CategoryRule
    from flim.tools.ml import Categorizer

    config = Categorizer.config_class(name="Level", rules=[CategoryRule(value="high", feature="FLIRR", min=0.55, max=1)])
    example = Categorizer.example(config, [_flim_table()])
    assert _cells_of(example) == [["FLIRR", "→ Level"], [0.4, config.default], [0.6, "high"]]


def test_pivot_without_other_category_columns_gives_one_row():
    """The pivoted column is the only category column: the means over all rows."""
    from flim.tools.data import Pivot

    table = pd.DataFrame({"Treatment": pd.Categorical(["ctrl", "ctrl", "dox"]), "FLIRR": [0.4, 0.6, 0.8]})
    (result,) = Pivot().run(table, config=Pivot.config_class(grouping=["Treatment"], features="all")).values()
    assert list(result.columns) == ["FLIRR\nctrl", "FLIRR\ndox"]
    assert result.iloc[0].tolist() == pytest.approx([0.5, 0.8]) and len(result) == 1


def test_separate_and_fuse_warn_about_a_taken_column_name():
    """A new column whose name the table has gets a number, with a warning."""
    from flim.tools.data import FuseCategories, SeparateCategories

    table = pd.DataFrame({"Source": pd.Categorical(["a_1", "b_2"]), "FOV": pd.Categorical(["x", "y"]), "Cell": pd.Categorical(["1", "2"])})
    config = SeparateCategories.config_class(column="Source", mode="delimiter", delimiters=["_"], names=["FOV", "Cell"])
    issues = [(i.field, i.message, i.severity) for i in SeparateCategories.validate_data(config, [table])]
    assert ("names", "the table already has a column 'FOV': the new column is named 'FOV_1'", "warning") in issues
    assert list(SeparateCategories.example(config, [table]).columns) == ["Source", "→ FOV_1", "→ Cell_1"]
    tool = SeparateCategories()
    (result,) = tool.run(table, config=config).values()
    assert {"FOV", "FOV_1", "Cell", "Cell_1"} <= set(result.columns)  # nothing replaced
    fuse = FuseCategories.config_class(grouping=["FOV", "Cell"], name="FOV")
    issues = FuseCategories.validate_data(fuse, [table])
    assert [(i.field, i.severity) for i in issues] == [("name", "warning")] and "'FOV_1'" in issues[0].message
