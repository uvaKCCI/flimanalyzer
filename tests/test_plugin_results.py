"""Results of analysis and data tools, checked against independent calculations."""

import matplotlib.figure
import numpy as np
import pandas as pd
import pytest
from scipy import stats

FEATURE = "NAD(P)H t1"


def _run(plugin_cls, data, **params):
    tool = plugin_cls()
    tool.configure(input={"data": data} if not isinstance(data, dict) else data, **params)
    return tool.execute()


def test_ks_statistics_match_scipy(flim_data):
    from flim.analysis.ksstats import KSStats

    (table,) = _run(KSStats, flim_data, grouping=["Treatment"], features=[FEATURE], comparison="Treatment").values()
    row = table.iloc[0]
    wt = flim_data.loc[flim_data["Treatment"] == "WT", FEATURE]
    ko = flim_data.loc[flim_data["Treatment"] == "KO", FEATURE]
    expected = stats.ks_2samp(wt, ko)
    assert row["statistic"] == pytest.approx(expected.statistic)
    assert row["p-values"] == pytest.approx(expected.pvalue)
    assert {row["n (Treatment 1)"], row["n (Treatment 2)"]} == {len(wt), len(ko)}


def test_ks_statistics_per_group(flim_data):
    from flim.analysis.ksstats import KSStats

    (table,) = _run(
        KSStats, flim_data, grouping=["FOV", "Treatment"], features=[FEATURE], comparison="Treatment"
    ).values()
    assert sorted(table["FOV"].astype(str)) == ["1", "2", "3"]  # one comparison per FOV


def test_categorizer_assigns_bins(flim_data):
    from flim.analysis.categorizer import Categorizer

    data = flim_data.copy()
    data["score"] = np.linspace(-1, 1, len(data))
    categories = [
        {"value": "low", "criteria": {"feature": "score", "min": -1.0, "max": -0.2}},
        {"value": "high", "criteria": {"feature": "score", "min": -0.2, "max": 0.5}},
    ]
    (table,) = _run(
        Categorizer,
        data,
        grouping=["Treatment"],
        features=["score"],
        name="Level",
        categories=categories,
        default="other",
        merge_input=False,
    ).values()
    expected = pd.cut(data["score"], bins=[-1.0, -0.2, 0.5], labels=["low", "high"])
    expected = expected.cat.add_categories("other").fillna("other")
    assert list(table["Level"]) == list(expected)
    assert table["Level"].dtype == "category"
    assert "other" in set(table["Level"])  # outside all bins: the default


def test_random_forest_importances(flim_data):
    from flim.analysis.randomforest import RandomForest

    features = ["NAD(P)H t1", "NAD(P)H t2", "FAD a1[%]"]
    results = _run(
        RandomForest,
        flim_data,
        grouping=["Treatment"],
        features=features,
        classifier="Treatment",
        n_estimators=20,
        importancehisto=True,
    )
    importances = results["Importance Score Data"]
    assert set(importances["Feature"]) == set(features)
    assert importances["Importance Score"].sum() == pytest.approx(1.0)
    assert importances["Importance Score"].is_monotonic_decreasing
    assert isinstance(results["Importance Score Plot"], matplotlib.figure.Figure)


def test_random_forest_ignores_grouping_columns_among_the_features(flim_data):
    from flim.analysis.randomforest import RandomForest

    data = flim_data.copy()
    data["Score"] = np.arange(len(data), dtype=float)
    results = _run(
        RandomForest,
        data,
        grouping=["Score"],  # a grouping column that is also selected as a feature
        features=["NAD(P)H t1", "Score"],
        classifier="Treatment",
        n_estimators=10,
        importancehisto=False,
    )
    assert list(results["Importance Score Data"]["Feature"]) == ["NAD(P)H t1"]


def test_merge_on_shared_categories(flim_data):
    from flim.data.mergedata import Merger

    left = flim_data[["Treatment", "FOV", "Cell", FEATURE]]
    right = flim_data[["Treatment", "FOV", "Cell", "FAD a1[%]"]]
    (merged,) = _run(Merger, {"left": left, "right": right}, how="inner").values()
    assert len(merged) == len(flim_data)
    assert list(merged.columns[:3]) == ["Treatment", "FOV", "Cell"]  # categories first
    assert {FEATURE, "FAD a1[%]"} <= set(merged.columns)
    assert all(merged[c].dtype == "category" for c in ("Treatment", "FOV", "Cell"))


def test_order_categories(flim_data):
    from flim.data.categories import CategoryOrder

    categories = {
        "Treatment": {"values": ["WT", "KO"]},
        "FOV": {"values": ["3", "2", "1"]},
    }
    (table,) = _run(CategoryOrder, flim_data, categories=categories, inplace=False).values()
    assert list(table["Treatment"].cat.categories) == ["WT", "KO"]
    assert table["Treatment"].cat.ordered
    assert list(table["FOV"].iloc[:10]) == ["3"] * 10  # sorted by the new order
    assert table.iloc[0]["Treatment"] == "WT"


@pytest.mark.parametrize("plugin", ["SwarmPlot", "KDE", "BoxPlot", "ViolinPlot", "LinePlot", "FreqHisto"])
def test_plots_draw_one_figure_per_feature(flim_data, plugin):
    import flim.plugin as registry

    cls = next(c for group in registry.PLUGINS.values() for c in group.values() if c.__name__ == plugin)
    tool = cls()
    tool.configure(input={"data": flim_data}, grouping=["Treatment"], features=[FEATURE, "FAD a1[%]"])
    figures = [v for v in tool.execute().values() if isinstance(v, matplotlib.figure.Figure)]
    assert len(figures) == 2
    # mapped parameters: one call per feature when run in parallel
    assert [p["features"] for p in tool.get_mapped_parameters()] == [[FEATURE], ["FAD a1[%]"]]


def test_flirr_plot(flim_data):
    from flim.analysis.flirr import FLIRRPlot

    data = flim_data.copy()
    data["FLIRR"] = data["NAD(P)H a2[%]"] / data["FAD a1[%]"]
    results = _run(
        FLIRRPlot,
        data,
        grouping=["Treatment", "FOV"],
        features=["FLIRR", "NAD(P)H a2[%]", "FAD a1[%]"],
    )
    figures = [v for v in results.values() if isinstance(v, matplotlib.figure.Figure)]
    assert figures and all(len(f.axes) >= 3 for f in figures)


@pytest.mark.parametrize("error_bar", ["+/-", "+"])
def test_bar_plot_heights_are_group_means(flim_data, error_bar):
    from flim.analysis.barplots import BarPlot

    tool = BarPlot()
    tool.configure(input={"data": flim_data}, grouping=["Treatment"], features=[FEATURE], error_bar=error_bar)
    (fig,) = [v for v in tool.execute().values() if isinstance(v, matplotlib.figure.Figure)]
    heights = sorted(round(p.get_height(), 6) for p in fig.axes[0].patches if p.get_height())
    expected = sorted(round(v, 6) for v in flim_data.groupby("Treatment", observed=True)[FEATURE].mean())
    assert heights == expected
