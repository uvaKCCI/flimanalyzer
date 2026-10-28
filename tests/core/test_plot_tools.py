"""Plot tools, without wx (the legacy plugins are tested in tests/test_plugin_results.py)."""

import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from flim.configs import (
    BarPlotConfig,
    BoxPlotConfig,
    FLIRRPlotConfig,
    HeatmapConfig,
    HistogramConfig,
    KDEConfig,
    LinePlotConfig,
    PairPlotConfig,
    ScatterPlotConfig,
    SwarmPlotConfig,
    ViolinPlotConfig,
)
from flim.configs.plot import HistogramRange
from flim.core.schema import TableSchema
from flim.core.types import PlotType, TableType
from flim.tools.plot import (
    BarPlot,
    BoxPlot,
    FLIRRPlot,
    FrequencyHistogram,
    Heatmap,
    KDE,
    LinePlot,
    PairPlot,
    ScatterPlot,
    SwarmPlot,
    ViolinPlot,
)


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    rows = []
    for t, offset in (("WT", 0.0), ("KO", 10.0)):
        for fov in ("1", "2"):
            for cell in range(8):
                a1, a2 = rng.uniform(20, 40), rng.uniform(60, 80)
                rows.append(
                    {
                        "Treatment": t,
                        "FOV": fov,
                        "Cell": str(cell),
                        "t1": rng.normal(400 + offset, 20),
                        "t2": rng.normal(3000 + offset, 100),
                        "FAD a1%": a1,
                        "NAD(P)H a2%": a2,
                        "FLIRR": a2 / a1,
                    }
                )
    df = pd.DataFrame(rows)
    for col in ("Treatment", "FOV", "Cell"):
        df[col] = df[col].astype("category")
    return df


CASES = [
    (
        BoxPlot,
        BoxPlotConfig(grouping=["Treatment", "FOV"], features=["t1", "t2"]),
        ["Plot: Box Plot t1", "Plot: Box Plot t2"],
    ),
    (
        SwarmPlot,
        SwarmPlotConfig(grouping=["Treatment"], features=["t1"]),
        ["Plot: Swarm Plot t1"],
    ),
    (ViolinPlot, ViolinPlotConfig(features=["t1"]), ["Plot: Violin Plot t1"]),
    (
        BarPlot,
        BarPlotConfig(grouping=["Treatment", "FOV"], features=["t2", "t1"]),
        ["Plot: t1", "Plot: t2"],
    ),
    (
        BarPlot,
        BarPlotConfig(
            grouping=["Treatment"], features=["t1", "t2"], bar_type="stacked"
        ),
        ["Plot: t1|t2"],
    ),
    (
        LinePlot,
        LinePlotConfig(grouping=["FOV", "Treatment"], features=["t1"]),
        ["Plot: Line Plot: t1"],
    ),
    (
        LinePlot,
        LinePlotConfig(grouping=["FOV", "Treatment", "Cell", "FOV"], features=["t1"]),
        ["Plot: Line Plot: t1"],
    ),
    (
        KDE,
        KDEConfig(grouping=["Treatment", "FOV"], features=["t1", "t2"]),
        ["Plot: KDE t1", "Plot: KDE t2"],
    ),
    (
        KDE,
        KDEConfig(features=["t1", "t2", "FLIRR"], single_plot=True, col_wrap=2),
        ["Plot: KDE"],
    ),
    (
        FrequencyHistogram,
        HistogramConfig(grouping=["Treatment"], features=["t1"], table=True),
        ["Plot: Frequency Histo Plot: t1", "Table: Frequency Histo Table: t1"],
    ),
    (
        Heatmap,
        HeatmapConfig(features=["t1", "t2", "FLIRR"]),
        ["Plot: Heatmap", "Table: Heatmap Correlation"],
    ),
    (
        PairPlot,
        PairPlotConfig(
            grouping=["Treatment"],
            features=["t1", "t2"],
            points={"mode": "sample", "samples": 10},
        ),
        ["Plot: Pair Plot: ['Treatment']"],
    ),
    (
        ScatterPlot,
        ScatterPlotConfig(grouping=["Treatment"], features=["t1", "t2", "FLIRR"]),
        [
            "Plot: Scatter Plot: ('t1', 'FLIRR')",
            "Plot: Scatter Plot: ('t2', 'FLIRR')",
            "Plot: Scatter Plot: ('t1', 't2')",
        ],
    ),
    (
        FLIRRPlot,
        FLIRRPlotConfig(grouping=["Treatment", "FOV"]),
        ["Plot: FLIRR Plot: ['Treatment', 'FOV']"],
    ),
]


@pytest.mark.parametrize(
    "tool, config, names", CASES, ids=lambda v: getattr(v, "name", None)
)
def test_plot_tool(data, tool, config, names):
    plt.close("all")
    results = tool()(data, config=config)
    assert sorted(results) == sorted(names)
    for name, value in results.items():
        expected = (
            matplotlib.figure.Figure if name.startswith("Plot: ") else pd.DataFrame
        )
        assert isinstance(value, expected)
    # figures are not left in pyplot's registry (the plugins leaked some)
    assert plt.get_fignums() == []


@pytest.mark.parametrize(
    "tool, config, names", CASES, ids=lambda v: getattr(v, "name", None)
)
def test_output_schema_names_without_drawing(data, tool, config, names):
    plt.close("all")
    outputs = tool.output_schema(config, [TableSchema.from_frame(data)])
    assert sorted(o.display_name for o in outputs.values()) == sorted(names)
    assert plt.get_fignums() == []


def test_output_schema_all_features(data):
    config = BoxPlotConfig(features="all")
    outputs = BoxPlot.output_schema(config, [TableSchema.from_frame(data)])
    assert set(outputs) == {
        f"Box Plot {f}" for f in ["t1", "t2", "FAD a1%", "NAD(P)H a2%", "FLIRR"]
    }
    assert BoxPlot.output_schema(config, [None]) == {}
    histogram = FrequencyHistogram.output_schema(
        HistogramConfig(features=["t1"], table=True), [None]
    )
    assert histogram["Frequency Histo Table: t1"].type is TableType
    assert histogram["Frequency Histo Plot: t1"].type is PlotType


def test_map_configs():
    assert [
        c.features for c in BoxPlot().map_configs(BoxPlotConfig(features=["a", "b"]))
    ] == [["a"], ["b"]]
    stacked = BarPlotConfig(features=["a", "b"], bar_type="stacked")
    assert BarPlot().map_configs(stacked) == [stacked]
    pairs = ScatterPlot().map_configs(ScatterPlotConfig(features=["a", "b", "c"]))
    assert [c.features for c in pairs] == [["a", "b"], ["a", "c"], ["b", "c"]]
    single = KDEConfig(features=["a", "b"], single_plot=True)
    assert KDE().map_configs(single) == [single]


def test_kde_single_plot_with_one_feature(data):
    # the plugin raised NameError here
    results = KDE()(data, config=KDEConfig(features=["t1"], single_plot=True))
    assert list(results) == ["Plot: KDE"]


def test_histogram_bins(data):
    config = HistogramConfig(
        features=["t1", "t2"],
        bins=12,
        table=True,
        per_feature={"t1": HistogramRange(min=300, max=500, bins=5)},
    )
    results = FrequencyHistogram()(data, config=config)
    t1 = results["Table: Frequency Histo Table: t1"]
    assert len(t1) == 5 and t1["bin edge low"].iloc[0] == 300
    # t2 uses the config's bins, not t1's (the plugin carried them over)
    t2 = results["Table: Frequency Histo Table: t2"]
    assert len(t2) == 12
    assert t2["all [rel %]"].sum() == pytest.approx(100)


def test_flirr_plot_needs_grouping_and_columns(data):
    with pytest.raises(ValueError, match="grouping"):
        FLIRRPlot()(data, config=FLIRRPlotConfig())
    with pytest.raises(ValueError, match="FLIRR column"):
        FLIRRPlot()(
            data.drop(columns="FLIRR"), config=FLIRRPlotConfig(grouping=["Treatment"])
        )
    schema = TableSchema.from_frame(data.drop(columns="FLIRR"))
    issues = FLIRRPlot.validate(FLIRRPlotConfig(), [schema])
    assert [i.field for i in issues] == ["grouping", None]


def test_flirr_plot_has_no_empty_axes(data):
    figure = FLIRRPlot()(data, config=FLIRRPlotConfig(grouping=["Treatment"]))[
        "Plot: FLIRR Plot: ['Treatment']"
    ]
    assert len(figure.axes) == 6


def test_bar_plot_without_values(data):
    # e.g. a feature that is missing (NaN) in every row; this used to raise IndexError
    data["t1"] = np.nan
    results = BarPlot()(
        data, config=BarPlotConfig(grouping=["Treatment"], features=["t1"])
    )
    (figure,) = results.values()
    assert "No data" in [t.get_text() for t in figure.axes[0].texts]
