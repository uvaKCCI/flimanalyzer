"""Statistics and ML tools, without wx."""

import matplotlib.figure
import numpy as np
import pandas as pd
import pytest
from scipy import stats

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
        grouping=["Treatment"], features=["t1"], aggs=["count", "mean", "median"]
    )
    ((name, table),) = Summarize()(data, config=config).items()
    assert name == "Table: Summary"
    assert list(table.columns) == ["Treatment", "t1\ncount", "t1\nmean", "t1\nmedian"]
    assert table["t1\ncount"].tolist() == [30, 30]
    table = table.set_index("Treatment")
    expected = data.groupby("Treatment", observed=True)["t1"]
    pd.testing.assert_series_equal(
        table["t1\nmean"], expected.mean(), check_names=False
    )
    pd.testing.assert_series_equal(
        table["t1\nmedian"], expected.median(), check_names=False
    )


def test_summary_per_feature_and_mapping(data):
    config = SummaryConfig(features=["t1", "t2"], single_table=False, aggs=["max"])
    results = Summarize()(data, config=config)
    assert list(results) == ["Table: Summary: t1", "Table: Summary: t2"]
    configs = Summarize().map_configs(config)
    assert [c.features for c in configs] == [["t1"], ["t2"]]
    assert Summarize().map_configs(
        config.model_copy(update={"single_table": True})
    ) == [config.model_copy(update={"single_table": True})]


def test_summary_without_grouping(flim_data, features):
    config = SummaryConfig(features=features, aggs=["mean"])
    (summary,) = Summarize()(flim_data, config=config).values()
    for f in features:
        assert summary[f"{f}\nmean"].iloc[0] == pytest.approx(flim_data[f].mean())


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


def test_ks_statistics_match_scipy(flim_data):
    feature = "NAD(P)H t1"
    config = KSStatsConfig(
        grouping=["Treatment"], features=[feature], comparison="Treatment"
    )
    (table,) = KSStats()(flim_data, config=config).values()
    row = table.iloc[0]
    wt = flim_data.loc[flim_data["Treatment"] == "WT", feature]
    ko = flim_data.loc[flim_data["Treatment"] == "KO", feature]
    expected = stats.ks_2samp(wt, ko)
    assert row["statistic"] == pytest.approx(expected.statistic)
    assert row["p-values"] == pytest.approx(expected.pvalue)
    assert {row["n (Treatment 1)"], row["n (Treatment 2)"]} == {len(wt), len(ko)}


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


def test_relative_change_aligns_on_grouping_only():
    # #178: the reference values align on the grouping columns only, not on
    # every other category column. The KO rows keep their relative values even
    # though their Cell values are not present in the WT (reference) rows.
    data = pd.DataFrame(
        {
            "Treatment": pd.Categorical(["WT"] * 2 + ["KO"] * 3),
            "FOV": pd.Categorical(["1", "2", "1", "1", "2"]),
            "Cell": pd.Categorical(["1", "2", "3", "4", "5"]),
            "t1": [10.0, 20.0, 11.0, 22.0, 33.0],
        }
    )
    config = RelativeChangeConfig(
        grouping=["FOV"], features=["t1"], reference_value="WT"
    )
    table = RelativeChange()(data, config=config)["Table: Relative Change"]
    assert table["rel t1"].isna().sum() == 0
    # divided by the WT mean of the same FOV: FOV 1 -> 10, FOV 2 -> 20
    assert table.loc[table["Cell"] == "3", "rel t1"].iloc[0] == pytest.approx(1.1)
    assert table.loc[table["Cell"] == "4", "rel t1"].iloc[0] == pytest.approx(2.2)
    assert table.loc[table["Cell"] == "5", "rel t1"].iloc[0] == pytest.approx(1.65)


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
    assert len(clustering) == len(data)
    assert set(clustering["GMM full"].cat.categories) <= {"GMM full 1", "GMM full 2"}
    assert clustering[["GMM Prob Component 1", "GMM Prob Component 2"]].sum(
        axis=1
    ).to_numpy() == pytest.approx(1.0)
    criteria = first["Table: GMM full, Component Information Criteria"]
    assert len(criteria) == 2
    assert list(criteria.columns) == ["Component", "BIC", "AIC"]
    covariance = first["Table: GMM full, Covariance, component 1"]
    assert covariance.shape == (2, 2)


def test_random_forest(data):
    config = RandomForestConfig(
        features=FEATURES, target="Treatment", importance_plot=True
    )
    results = RandomForest()(data, config=config)
    importance = results["Table: Importance Score Data"]
    assert set(importance["Feature"]) == set(FEATURES)
    assert importance["Importance Score"].sum() == pytest.approx(1.0)
    assert importance["Importance Score"].is_monotonic_decreasing
    assert importance["Feature"].iloc[0] in ("t1", "t2")  # the features that differ
    assert isinstance(results["Plot: Importance Score Plot"], matplotlib.figure.Figure)
    again = RandomForest()(data, config=config)["Table: Importance Score Data"]
    pd.testing.assert_frame_equal(importance, again)  # seeded


def test_random_forest_ignores_grouping_columns_among_the_features(flim_data):
    data = flim_data.copy()
    data["Score"] = np.arange(len(data), dtype=float)
    config = RandomForestConfig(
        grouping=["Score"],  # a grouping column that is also selected as a feature
        features=["NAD(P)H t1", "Score"],
        target="Treatment",
        n_estimators=10,
        importance_plot=False,
    )
    results = RandomForest()(data, config=config)
    assert list(results["Table: Importance Score Data"]["Feature"]) == ["NAD(P)H t1"]


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


def test_categorizer_assigns_bins(flim_data):
    data = flim_data.copy()
    data["score"] = np.linspace(-1, 1, len(data))
    config = CategorizerConfig(
        features=["score"],
        name="Level",
        rules=[
            CategoryRule(value="low", feature="score", min=-1.0, max=-0.2),
            CategoryRule(value="high", feature="score", min=-0.2, max=0.5),
        ],
        default="other",
        merge_input=False,
    )
    (table,) = Categorizer()(data, config=config).values()
    expected = pd.cut(data["score"], bins=[-1.0, -0.2, 0.5], labels=["low", "high"])
    expected = expected.cat.add_categories("other").fillna("other")
    assert list(table["Level"]) == list(expected)
    assert table["Level"].dtype == "category"
    assert "other" in set(table["Level"])  # outside all rules: the default
