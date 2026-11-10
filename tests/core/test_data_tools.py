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
        column="File", mode="patterns",
        patterns=[CategoryPattern(name="Treatment", regex=r"/d/(.*?)/")],
    )
    (table,) = SeparateCategories()(data, config=config).values()
    assert list(table["Treatment"]) == ["ctrl", "dox"]
    issues = SeparateCategories.validate(SeparateCategoriesConfig(mode="patterns"), [])
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


def test_fuse_example_and_data_checks():
    from flim.configs import FuseCategoriesConfig
    from flim.tools.data import FuseCategories

    config = FuseCategoriesConfig(grouping=["FOV", "Cell"])
    assert FuseCategories.example(config, [_cells()]) == "FOV 1, Cell 1 → FOV:Cell 1:1"
    assert FuseCategories.validate_data(config, [_cells()]) == []
    data = _cells()
    data["Time"] = pd.Categorical(["0:30", "1:00", "0:30"])
    issues = FuseCategories.validate_data(FuseCategoriesConfig(grouping=["FOV", "Time"]), [data])
    assert [(i.field, i.severity) for i in issues] == [("delimiter", "warning")]
    assert FuseCategories.example(FuseCategoriesConfig(grouping=["FOV"]), [data]) is None


def test_separate_example_and_data_checks():
    from flim.configs import SeparateCategoriesConfig
    from flim.configs.data import CategoryPattern
    from flim.tools.data import SeparateCategories

    data = pd.DataFrame({"File": pd.Categorical(["/d/Results-ko_01.txt", "/d/Results-wt.txt"])})
    config = SeparateCategoriesConfig(
        column="File", delimiters=["-", "_"], names=["", "Treatment", "Cell"],
        part="file name without extension",
    )
    assert SeparateCategories.example(config, [data]) == (
        "/d/Results-ko_01.txt → Treatment ko, Cell 01"
    )
    (issue,) = SeparateCategories.validate_data(config, [data])
    assert issue.field == "names" and "'Results-wt'" in issue.message
    bad = SeparateCategoriesConfig(
        column="File", mode="patterns", patterns=[CategoryPattern(name="X", regex="(")]
    )
    (issue,) = SeparateCategories.validate_data(bad, [data])
    assert issue.severity == "error" and "not a valid pattern" in issue.message
