"""Statistics and ML tools, without wx (the legacy plugins are tested in
tests/test_analysis_plugins.py and tests/test_plugin_results.py)."""

import matplotlib.figure
import numpy as np
import pandas as pd
import pytest

from flim.configs import (
    CategorizerConfig,
    GMMConfig,
    KMeansConfig,
    KSStatsConfig,
    PCAConfig,
    RandomForestConfig,
    RelativeChangeConfig,
    SeriesAnalysisConfig,
    SummaryConfig,
)
from flim.configs.analysis import CategoryRule
from flim.core.schema import TableSchema
from flim.tools.ml import (
    Categorizer,
    GaussianMixedModel,
    KMeansClustering,
    PCAnalysis,
    RandomForest,
)
from flim.tools.statistics import KSStats, RelativeChange, SeriesAnalysis, Summarize

FEATURES = ["t1", "t2", "a1"]


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    rows = []
    for t, offset in (("WT", 0.0), ("KO", 100.0)):
        for fov in ("1", "2"):
            for cell in range(15):
                rows.append(
                    {
                        "Treatment": t,
                        "FOV": fov,
                        "Cell": str(cell),
                        "t1": rng.normal(400 + offset, 20),
                        "t2": rng.normal(3000 + offset, 100),
                        "a1": rng.uniform(60, 80),
                    }
                )
    df = pd.DataFrame(rows)
    for col in ("Treatment", "FOV", "Cell"):
        df[col] = df[col].astype("category")
    return df


@pytest.fixture
def schema(data):
    return TableSchema.from_frame(data)


# --- statistics ---


def test_summary_single_table(data):
    config = SummaryConfig(
        grouping=["Treatment"], features=["t1"], aggs=["count", "mean"]
    )
    ((name, table),) = Summarize()(data, config=config).items()
    assert name == "Table: Summary"
    assert list(table.columns) == ["Treatment", "t1\ncount", "t1\nmean"]
    assert table["t1\ncount"].tolist() == [30, 30]


def test_summary_per_feature_and_mapping(data):
    config = SummaryConfig(features=["t1", "t2"], single_table=False, aggs=["max"])
    results = Summarize()(data, config=config)
    assert list(results) == ["Table: Summary: t1", "Table: Summary: t2"]
    configs = Summarize().map_configs(config)
    assert [c.features for c in configs] == [["t1"], ["t2"]]
    assert Summarize().map_configs(
        config.model_copy(update={"single_table": True})
    ) == [config.model_copy(update={"single_table": True})]


def test_summary_lineage(schema):
    config = SummaryConfig(grouping=["Treatment"], features=["t1"], aggs=["mean"])
    output = Summarize.output_schema(config, [schema])["Summary"]
    assert output.schema.column("t1\nmean").derived_from == ["t1"]


def test_ks_stats(data):
    config = KSStatsConfig(
        grouping=["Treatment", "FOV"], features=["t1"], comparison="Treatment"
    )
    table = KSStats()(data, config=config)["Table: KS-stats: t1"]
    assert len(table) == 2  # one comparison per FOV
    assert set(table["dissimilar (<0.05)"]) == {"Yes"}  # the treatments differ by 100
    assert table["n (Treatment 1)"].tolist() == [15, 15]


def test_ks_stats_validate(data):
    one_value = TableSchema.from_frame(
        data[data["Treatment"] == "WT"].assign(
            Treatment=lambda d: d["Treatment"].cat.remove_unused_categories()
        )
    )
    issues = KSStats.validate(KSStatsConfig(features=["t1"]), [one_value])
    assert [i.field for i in issues] == ["comparison"]


def test_relative_change(data):
    config = RelativeChangeConfig(
        grouping=["FOV"], features=["t1"], reference_value="WT"
    )
    table = RelativeChange()(data, config=config)["Table: Relative Change"]
    wt = table[table["Treatment"] == "WT"]
    assert wt.groupby("FOV", observed=True)["rel t1"].mean().tolist() == pytest.approx(
        [1.0, 1.0]
    )
    ko = table[table["Treatment"] == "KO"]["rel t1"].mean()
    assert ko == pytest.approx(500 / 400, rel=0.05)


def test_relative_change_schema(schema):
    config = RelativeChangeConfig(features=["t1"])
    output = RelativeChange.output_schema(config, [schema])["Relative Change"]
    assert output.schema.column("rel t1").derived_from == ["t1"]
    issues = RelativeChange.validate(
        config.model_copy(update={"reference_value": "X"}), [schema]
    )
    assert [i.field for i in issues] == ["reference_value"]


def test_series_analysis():
    data = pd.DataFrame(
        {
            "Cell": pd.Categorical(["1", "2"]),
            "FLIRR\nmean\nDay 1": [1.0, 2.0],
            "FLIRR\nmean\nDay 2": [2.0, 2.0],
            "FLIRR\nmean\nDay 3": [4.0, 1.0],
        }
    )
    config = SeriesAnalysisConfig(
        features="all", statistics={"series_max", "delta", "delta_sum"}
    )
    table = SeriesAnalysis()(data, config=config)["Table: Series Analysis"]
    assert table["FLIRR\nmean\nSeries max"].tolist() == [4.0, 2.0]
    assert table["FLIRR\nmean\ndelta Day 1:Day 2"].tolist() == [1.0, 0.0]
    assert table["FLIRR\nmean\ndelta sum"].tolist() == [3.0, -1.0]
    assert "FLIRR\nmean\nDay 1" not in table  # merge_input is False
    with pytest.raises(ValueError, match="features"):
        SeriesAnalysis()(data, config=SeriesAnalysisConfig())
    issues = SeriesAnalysis.validate(
        SeriesAnalysisConfig(), [TableSchema.from_frame(data)]
    )
    assert [i.field for i in issues] == ["features"]


# --- machine learning ---


def test_pca(data):
    config = PCAConfig(features=FEATURES, n_components=2, explained_plot=True)
    results = PCAnalysis()(data, config=config)
    components = results["Table: PCA Components"]
    assert {"PC 1", "PC 2", "t1\nstandardized"} <= set(components.columns)
    assert results["Table: PCA Explained"]["explained var ratio"].sum() <= 1.0
    assert isinstance(results["Plot: PCA Explained Plot"], matplotlib.figure.Figure)


def test_pca_keeps_categories_aligned_with_rows_with_missing_values(data):
    data.loc[0, "t1"] = np.nan  # this row is dropped
    table = PCAnalysis()(data, config=PCAConfig(features=FEATURES))[
        "Table: PCA Components"
    ]
    assert len(table) == len(data) - 1
    assert table["Cell"].tolist() == data["Cell"].iloc[1:].tolist()
    assert not table.isna().any().any()


def test_kmeans(data):
    config = KMeansConfig(features=["t1"], n_clusters=2)
    table = KMeansClustering()(data, config=config)["Table: K-Means"]
    assert list(table.columns[:4]) == ["Treatment", "FOV", "Cell", "Cluster"]
    # the two treatments are 100 apart in t1: one cluster each
    assert pd.crosstab(table["Treatment"], table["Cluster"]).max(axis=1).tolist() == [
        30,
        30,
    ]


@pytest.mark.parametrize("method", ["EM", "Variational Bayesian"])
def test_gmm_is_reproducible(data, method):
    config = GMMConfig(features=["t1", "t2"], n_components=2, method=method)
    first = GaussianMixedModel()(data, config=config)
    second = GaussianMixedModel()(data, config=config)
    clustering = first["Table: GMM full, Feature Clustering"]
    pd.testing.assert_frame_equal(
        clustering, second["Table: GMM full, Feature Clustering"]
    )
    assert clustering[["GMM Prob Component 1", "GMM Prob Component 2"]].sum(
        axis=1
    ).to_numpy() == pytest.approx(1.0)
    assert len(first["Table: GMM full, Component Information Criteria"]) == 2


def test_random_forest(data):
    config = RandomForestConfig(
        features=FEATURES, target="Treatment", importance_plot=True
    )
    results = RandomForest()(data, config=config)
    importance = results["Table: Importance Score Data"]
    assert importance["Importance Score"].sum() == pytest.approx(1.0)
    assert importance["Feature"].iloc[0] in ("t1", "t2")  # the features that differ
    assert isinstance(results["Plot: Importance Score Plot"], matplotlib.figure.Figure)
    again = RandomForest()(data, config=config)["Table: Importance Score Data"]
    pd.testing.assert_frame_equal(importance, again)  # seeded


def test_random_forest_needs_a_target(data, schema):
    with pytest.raises(ValueError, match="target"):
        RandomForest()(data, config=RandomForestConfig(features=FEATURES))
    issues = RandomForest.validate(RandomForestConfig(features=FEATURES), [schema])
    assert [i.field for i in issues] == ["target"]


def test_categorizer(data):
    config = CategorizerConfig(
        name="Level",
        rules=[
            CategoryRule(value="low", feature="t1", min=0, max=450),
            CategoryRule(value="high", feature="t1", min=450, max=1000),
        ],
    )
    table = Categorizer()(data, config=config)["Table: Categorized"]
    assert list(table.columns[:4]) == ["Treatment", "FOV", "Cell", "Level"]
    assert list(table["Level"].cat.categories) == ["low", "high", "unassigned"]
    assert (table.loc[table["Treatment"] == "WT", "Level"] == "low").all()


def test_categorizer_gaps_get_the_default():
    data = pd.DataFrame({"x": [0.5, 1.5, 2.5]})
    config = CategorizerConfig(
        name="C",
        rules=[
            CategoryRule(value="a", feature="x", min=0, max=1),
            CategoryRule(value="b", feature="x", min=2, max=3),
        ],
    )
    table = Categorizer()(data, config=config)["Table: Categorized"]
    assert table["C"].tolist() == ["a", "unassigned", "b"]
