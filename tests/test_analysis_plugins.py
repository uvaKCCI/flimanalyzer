import matplotlib.figure
import pandas as pd
import pytest

from flim.analysis.barplots import BarPlot
from flim.analysis.boxplots import BoxPlot
from flim.analysis.freqhisto import FreqHisto
from flim.analysis.heatmap import Heatmap
from flim.analysis.kde import KDE
from flim.analysis.kmeans import KMeansClustering
from flim.analysis.lineplots import LinePlot
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
