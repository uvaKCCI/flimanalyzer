import matplotlib.figure
import pandas as pd
import pytest

from flim.analysis.barplots import BarPlot
from flim.analysis.boxplots import BoxPlot
from flim.analysis.freqhisto import FreqHisto
from flim.analysis.gmm import GaussianMixedModel
from flim.analysis.heatmap import Heatmap
from flim.analysis.kde import KDE
from flim.analysis.kmeans import KMeansClustering
from flim.analysis.lineplots import LinePlot, ci_to_errorbar
from flim.analysis.pca import PCAnalysis
from flim.analysis.relativechange import RelativeChange
from flim.analysis.scatterplots import ScatterPlot
from flim.analysis.seriesanalyzer import SeriesAnalyzer
from flim.analysis.summarystats import SummaryStats
from flim.analysis.violinplot import ViolinPlot


def run(plugin_cls, input, **params):
    plugin = plugin_cls()
    plugin.configure(input=input, **params)
    return plugin.execute()


def test_summary_stats_matches_pandas(flim_data):
    feature = "NAD(P)H t1"
    df = run(
        SummaryStats,
        {"data": flim_data},
        grouping=["Treatment"],
        features=[feature],
        aggs=["count", "mean", "median"],
    )
    (summary,) = df.values()
    summary = summary.set_index("Treatment")
    expected = flim_data.groupby("Treatment", observed=True)[feature]
    pd.testing.assert_series_equal(
        summary[f"{feature}\nmean"], expected.mean(), check_names=False
    )
    pd.testing.assert_series_equal(
        summary[f"{feature}\nmedian"], expected.median(), check_names=False
    )
    assert (summary[f"{feature}\ncount"] == 30).all()


def test_summary_stats_without_grouping(flim_data, features):
    (summary,) = run(
        SummaryStats, {"data": flim_data}, grouping=[], features=features, aggs=["mean"]
    ).values()
    for f in features:
        assert summary[f"{f}\nmean"].iloc[0] == pytest.approx(flim_data[f].mean())


def test_pca_returns_components(flim_data, features):
    results = run(PCAnalysis, {"data": flim_data}, features=features)
    tables = [v for v in results.values() if isinstance(v, pd.DataFrame)]
    assert tables
    assert all(len(t) > 0 for t in tables)


def test_kmeans_assigns_clusters(flim_data, features):
    results = run(KMeansClustering, {"data": flim_data}, features=features, n_clusters=2)
    tables = [v for v in results.values() if isinstance(v, pd.DataFrame)]
    assert any(len(t) == len(flim_data) for t in tables)


@pytest.mark.parametrize("method", ["EM", "Variational Bayesian"])
def test_gmm_assigns_components(flim_data, features, method):
    results = run(
        GaussianMixedModel,
        {"data": flim_data},
        features=features,
        method=method,
        n_components=2,
        covar_type="full",
    )
    clusters = results["Table: GMM full, Feature Clustering"]
    assert len(clusters) == len(flim_data)
    assert set(clusters["GMM full"].cat.categories) <= {"GMM full 1", "GMM full 2"}
    probs = clusters[["GMM Prob Component 1", "GMM Prob Component 2"]].sum(axis=1)
    assert probs.to_numpy() == pytest.approx(1.0)
    criteria = results["Table: GMM full, Component Information Criteria"]
    assert list(criteria.columns) == ["Component", "BIC", "AIC"] and len(criteria) == 2
    covariance = results["Table: GMM full, Covariance, component 1"]
    assert covariance.shape == (len(features), len(features))


@pytest.mark.parametrize(
    "plugin_cls",
    [
        BarPlot,
        BoxPlot,
        FreqHisto,
        Heatmap,
        KDE,
        LinePlot,
        RelativeChange,
        ScatterPlot,
        SeriesAnalyzer,
        ViolinPlot,
    ],
)
def test_plugin_executes(plugin_cls, flim_data, features):
    results = run(plugin_cls, {"data": flim_data}, grouping=["Treatment"], features=features)
    assert results
    for value in results.values():
        assert isinstance(value, (pd.DataFrame, matplotlib.figure.Figure))


@pytest.mark.parametrize(
    "ci, errorbar", [(95, ("ci", 95)), (68, ("ci", 68)), ("sd", "sd"), (None, None)]
)
def test_ci_to_errorbar(ci, errorbar):
    assert ci_to_errorbar(ci) == errorbar


# seaborn/matplotlib API deprecations must not come back
@pytest.mark.filterwarnings("error:.*deprecated:FutureWarning")
@pytest.mark.filterwarnings("error::PendingDeprecationWarning")
@pytest.mark.filterwarnings("error::matplotlib.MatplotlibDeprecationWarning")
@pytest.mark.parametrize("plugin_cls", [LinePlot, Heatmap, BoxPlot])
@pytest.mark.parametrize("grouping", [["Treatment"], ["Treatment", "FOV"]])
def test_plots_without_deprecated_api(plugin_cls, flim_data, features, grouping):
    results = run(plugin_cls, {"data": flim_data}, grouping=grouping, features=features)
    assert results

