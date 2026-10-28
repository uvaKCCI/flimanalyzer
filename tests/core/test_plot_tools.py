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
        KDEConfig(features=["t1", "t2", "FLIRR"], single_figure=True, plots_per_row=2),
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
    single = KDEConfig(features=["a", "b"], single_figure=True)
    assert KDE().map_configs(single) == [single]


def test_kde_single_plot_with_one_feature(data):
    # the plugin raised NameError here
    results = KDE()(data, config=KDEConfig(features=["t1"], single_figure=True))
    assert list(results) == ["Plot: KDE"]


def test_histogram_bins(data):
    config = HistogramConfig(
        features={"t1": HistogramRange(min=300, max=500, bins=5), "t2": {}},
        table=True,
    )
    results = FrequencyHistogram()(data, config=config)
    t1 = results["Table: Frequency Histo Table: t1"]
    assert len(t1) == 5 and t1["bin edge low"].iloc[0] == 300
    # t2 has the default bins, not t1's (the plugin carried them over)
    t2 = results["Table: Frequency Histo Table: t2"]
    assert len(t2) == 30
    assert t2["all [rel %]"].sum() == pytest.approx(100)
    # only a min: the max of the data
    config = HistogramConfig(features={"t2": {"min": 2900}}, table=True)
    t2 = FrequencyHistogram()(data, config=config)["Table: Frequency Histo Table: t2"]
    assert t2["bin edge low"].iloc[0] == 2900
    assert t2["bin edge high"].iloc[-1] == pytest.approx(data["t2"].max())


def test_histogram_needs_features(data):
    issues = FrequencyHistogram.validate(
        HistogramConfig(), [TableSchema.from_frame(data)]
    )
    assert [i.field for i in issues] == ["features"]


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


def test_pair_plot_lower_half_needs_the_same_columns_and_rows(data):
    # seaborn failed on a lower half with more columns than rows
    config = PairPlotConfig(
        symmetric=False, x_vars=["t1", "t2"], y_vars=["FLIRR"], corner=True
    )
    assert not config.corner  # only symmetric grids have a lower half
    (figure,) = PairPlot()(data, config=config).values()
    assert len(figure.axes) == 2  # the full (1 x 2) grid
    square = PairPlotConfig(features=["t1", "t2"], corner=True)
    assert square.corner
    (lower,) = PairPlot()(data, config=square).values()
    full = PairPlotConfig(features=["t1", "t2"])
    (figure,) = PairPlot()(data, config=full).values()
    assert len(lower.axes) == len(figure.axes) - 1  # without the upper panel


def test_pair_plot_needs_features(data):
    schema = TableSchema.from_frame(data)
    assert [i.field for i in PairPlot.validate(PairPlotConfig(), [schema])] == [
        "x_vars"
    ]
    rows_missing = PairPlotConfig(symmetric=False, x_vars=["t1"])
    assert [i.field for i in PairPlot.validate(rows_missing, [schema])] == ["y_vars"]
    with_vars = PairPlotConfig(symmetric=False, x_vars=["t1"], y_vars=["t2"])
    assert PairPlot.validate(with_vars, [schema]) == []
    with pytest.raises(ValueError, match="select the features"):
        PairPlot()(data, config=PairPlotConfig())


SINGLE = [
    (BoxPlot, BoxPlotConfig, ["Treatment", "FOV"]),
    (SwarmPlot, SwarmPlotConfig, ["Treatment"]),
    (ViolinPlot, ViolinPlotConfig, []),
    (LinePlot, LinePlotConfig, ["FOV", "Treatment"]),
    (LinePlot, LinePlotConfig, []),
    (ScatterPlot, ScatterPlotConfig, ["Treatment"]),
    (KDE, KDEConfig, ["Treatment"]),
    (FrequencyHistogram, HistogramConfig, ["Treatment"]),
    (BarPlot, BarPlotConfig, ["Treatment", "FOV"]),
]


@pytest.mark.parametrize(
    "tool, config_class, grouping", SINGLE, ids=lambda v: getattr(v, "name", None)
)
def test_single_figure(data, tool, config_class, grouping):
    plt.close("all")
    config = config_class(
        features=["t1", "t2", "FLIRR"],
        grouping=grouping,
        single_figure=True,
        plots_per_row=2,
    )
    results = tool()(data, config=config)
    figures = {k: v for k, v in results.items() if k.startswith("Plot: ")}
    assert list(figures) == [f"Plot: {tool.name}"]
    (figure,) = figures.values()
    # a tile for each of the 3 features (Scatter Plot: each of the 3 feature pairs)
    assert len([ax for ax in figure.axes if ax.has_data()]) >= 3
    assert tool().map_configs(config) == [config]  # one task
    outputs = tool.output_schema(config, [TableSchema.from_frame(data)])
    assert list(outputs) == [tool.name]
    assert plt.get_fignums() == []


def test_single_figure_needs_few_grouping_columns():
    # more grouping columns: the plots are facets already, no single figure
    many = ["Treatment", "FOV", "Cell"]
    assert not BoxPlotConfig(grouping=many, single_figure=True).single_figure
    assert LinePlotConfig(grouping=many, single_figure=True).single_figure
    assert not LinePlotConfig(
        grouping=many + ["Treatment"], single_figure=True
    ).single_figure
    # bars: any grouping (they are not facets); stacked bars are one plot already
    assert BarPlotConfig(grouping=many, single_figure=True).single_figure
    assert not BarPlotConfig(bar_type="stacked", single_figure=True).single_figure
    assert set(BoxPlotConfig.fixed_fields({"grouping": many})) == {
        "single_figure",
        "plots_per_row",
    }
    two = {"grouping": ["Treatment", "FOV"]}  # x and hue: a legend
    assert set(BoxPlotConfig.fixed_fields({**two, "single_figure": True})) == set()
    # plots per row: only for a single figure
    assert set(BoxPlotConfig.fixed_fields(two)) == {"plots_per_row"}
    # one grouping column (the x axis): no legend to place
    assert "legend_position" in BoxPlotConfig.fixed_fields({"grouping": ["Treatment"]})


def test_swarm_plot_sample(data):
    plt.close("all")
    config = SwarmPlotConfig(
        features=["t1"],
        grouping=["Treatment"],
        points={"mode": "sample", "samples": 10},
    )
    (figure,) = SwarmPlot()(data, config=config).values()
    assert [t.get_text() for t in figure.texts] == [
        f"10 samples of {len(data)} measurements shown"
    ]
    points = sum(len(c.get_offsets()) for ax in figure.axes for c in ax.collections)
    assert points == 10
    # the same sample on every run
    (again,) = SwarmPlot()(data, config=config).values()
    offsets = lambda f: [
        c.get_offsets().tolist() for ax in f.axes for c in ax.collections
    ]
    assert offsets(again) == offsets(figure)
    assert (
        SwarmPlotConfig().points.mode == "all"
        and SwarmPlotConfig().points.samples == 2000
    )
    # the sample's size and seed only matter for a sample
    from flim.configs.plot import PointSampling

    assert set(PointSampling.fixed_fields({"mode": "all"})) == {
        "samples",
        "random_seed",
    }
    assert PointSampling.fixed_fields({"mode": "sample"}) == {}


def test_histogram_auto_range(data):
    config = HistogramConfig(
        features={"t1": {"min": 300, "max": 500}}, auto_range=True, table=True
    )
    table = FrequencyHistogram()(data, config=config)[
        "Table: Frequency Histo Table: t1"
    ]
    # the data's range; the min and max are kept in the config
    assert table["bin edge low"].iloc[0] == pytest.approx(data["t1"].min())
    assert table["bin edge high"].iloc[-1] == pytest.approx(data["t1"].max())
    assert (config.features["t1"].min, config.features["t1"].max) == (300, 500)
    assert (
        config.to_legacy_params()["featuresettings"] == {}
    )  # older versions: data range


@pytest.mark.parametrize(
    "tool, config_class",
    [
        (FrequencyHistogram, HistogramConfig),
        (ScatterPlot, ScatterPlotConfig),
        (BarPlot, BarPlotConfig),
    ],
    ids=lambda v: getattr(v, "name", None),
)
def test_single_figure_shares_legend_and_title(data, tool, config_class):
    config = config_class(
        features=["t1", "t2", "FLIRR"], grouping=["Treatment"], single_figure=True
    )
    results = tool()(data, config=config)
    (figure,) = [v for k, v in results.items() if k.startswith("Plot: ")]
    assert "grouped by treatment" in figure.get_suptitle().lower()
    titles = [ax.get_title() for ax in figure.axes]
    assert not any("grouped by" in t for t in titles)  # in the figure title only
    assert sum(ax.get_legend() is not None for ax in figure.axes) == 0  # one for all
    if figure.legends:  # the groups, without the tuple's punctuation
        assert {t.get_text() for t in figure.legends[0].get_texts()} == {"KO", "WT"}


def test_tidy_tiles_keeps_different_legends():
    from flim.tools.plot import tidy_tiles

    figure, axes = plt.subplots(1, 2)
    for ax, labels in zip(axes, (["a", "b"], ["a", "c"])):
        for label in labels:
            ax.plot([0, 1], label=label)
        ax.legend()
        ax.set_title(f"{labels[1]} x grouped by T")
    tidy_tiles(figure, list(axes))
    assert all(ax.get_legend() is not None for ax in axes) and not figure.legends
    assert [ax.get_title() for ax in axes] == ["b", "c"]
    assert figure.get_suptitle() == "X grouped by T"
    plt.close(figure)


def draw(figure):
    """Draws a figure as saving does (figures of a run have no pyplot canvas)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    FigureCanvasAgg(figure).draw()


def cap_ratio(figure):
    """Largest error bar cap width / bar width (along the cap) after drawing."""
    draw(figure)
    ratios = []
    for ax in figure.axes:
        for c in ax.containers:
            if getattr(c, "errorbar", None) is None:
                continue
            horizontal = c.orientation == "horizontal"
            boxes = [p.get_window_extent() for p in c.patches]
            bar = (
                min(b.height if horizontal else b.width for b in boxes)
                * 72
                / figure.dpi
            )
            ratios += [line.get_markersize() / bar for line in c.errorbar.lines[1]]
    return max(ratios)


@pytest.mark.parametrize("orientation", ["vertical", "horizontal"])
def test_error_bar_caps_fit_their_bars(orientation):
    n = 600
    many = pd.DataFrame(
        {
            "Cell": pd.Categorical([str(i % 60) for i in range(n)]),
            "x": np.arange(n) % 7 + 1.0,
        }
    )
    config = BarPlotConfig(features=["x"], grouping=["Cell"], orientation=orientation)
    (figure,) = BarPlot()(many, config=config).values()
    assert cap_ratio(figure) <= 0.8 + 1e-6
    figure.set_size_inches(2, 2)  # smaller: the caps shrink with the bars
    assert cap_ratio(figure) <= 0.8 + 1e-6


def test_error_bar_caps_of_wide_bars_keep_their_size(data):
    config = BarPlotConfig(features=["t1"], grouping=["Treatment"])
    (figure,) = BarPlot()(data, config=config).values()
    draw(figure)
    caps = [
        line.get_markersize()
        for c in figure.axes[0].containers
        if getattr(c, "errorbar", None)
        for line in c.errorbar.lines[1]
    ]
    assert max(caps) == 12  # matplotlib's cap width for capsize 6


@pytest.mark.parametrize("single", [False, True])
def test_scatter_plot_sample(data, single):
    config = ScatterPlotConfig(
        features=["t1", "t2", "FLIRR"],
        single_figure=single,
        points={"mode": "sample", "samples": 10},
    )
    figures = list(ScatterPlot()(data, config=config).values())
    for figure in figures:
        assert [t.get_text() for t in figure.texts] == [
            f"10 samples of {len(data)} measurements shown"
        ]
    offsets = [
        c.get_offsets() for f in figures for ax in f.axes for c in ax.collections
    ]
    assert all(len(o) == 10 for o in offsets)
    # the same cells in every plot: t1 is x in two of them
    assert offsets[0][:, 0].tolist() == offsets[1][:, 0].tolist()
    assert (
        ScatterPlotConfig().points.mode == "all"
        and ScatterPlotConfig().points.samples == 20000
    )


def test_kde_single_figure_legend_with_a_constant_feature(data):
    data.insert(3, "a offset", 0.0)  # no curves: its plot comes first
    config = KDEConfig(
        features="all", grouping=["Treatment"], single_figure=True, plots_per_row=3
    )
    (figure,) = KDE()(data, config=config).values()
    (legend,) = figure.legends  # one, for the figure
    assert sorted(t.get_text() for t in legend.get_texts()) == ["KO", "WT"]
    assert legend.get_title().get_text() == "Treatment"
    # each group has one colour in all plots
    colors = {}
    for ax in figure.axes:
        for line in ax.get_lines():
            colors.setdefault(line.get_label(), set()).add(str(line.get_color()))
    assert {label: len(c) for label, c in colors.items()} == {"KO": 1, "WT": 1}


def _legends(figure):
    return [ax.get_legend() for ax in figure.axes if ax.get_legend() is not None]


LEGEND_TOOLS = [
    (KDE, KDEConfig, {"grouping": ["Treatment"]}),
    (FrequencyHistogram, HistogramConfig, {"grouping": ["Treatment"]}),
    (ScatterPlot, ScatterPlotConfig, {"grouping": ["Treatment"]}),
    (BoxPlot, BoxPlotConfig, {"grouping": ["Treatment", "FOV"]}),
    (SwarmPlot, SwarmPlotConfig, {"grouping": ["Treatment", "FOV"]}),
    (ViolinPlot, ViolinPlotConfig, {"grouping": ["Treatment", "FOV"]}),
    (LinePlot, LinePlotConfig, {"grouping": ["Treatment", "FOV"]}),
    (BarPlot, BarPlotConfig, {"grouping": ["Treatment", "FOV"]}),
]


@pytest.mark.parametrize("single_figure", [False, True])
@pytest.mark.parametrize("position", ["right", "top", "bottom", "left", "inside", "none"])
@pytest.mark.parametrize(
    "tool, config_class, grouping",
    LEGEND_TOOLS,
    ids=lambda v: getattr(v, "name", None) if isinstance(v, type) else None,
)
def test_legend_position(data, tool, config_class, grouping, position, single_figure):
    plt.close("all")
    if single_figure and position == "inside":
        # one legend for all tiles: outside the plots only
        config = config_class(
            features=["t1", "t2"], single_figure=True, legend_position="inside", **grouping
        )
        assert config.legend_position != "inside"
        return
    config = config_class(
        features=["t1", "t2"],
        single_figure=single_figure,
        legend_position=position,
        **grouping,
    )
    results = tool()(data, config=config)
    figures = [v for k, v in results.items() if k.startswith("Plot: ")]
    assert figures
    for figure in figures:
        if position == "none":
            assert not _legends(figure) and not figure.legends
        elif position == "inside":
            assert len(_legends(figure)) == 1 and not figure.legends
        else:
            assert not _legends(figure) and len(figure.legends) == 1
            assert sorted(t.get_text() for t in figure.legends[0].get_texts())


def test_legend_position_where_there_is_none():
    # no hue: no legend to place
    assert "legend_position" in KDEConfig.fixed_fields({"grouping": []})
    assert "legend_position" not in KDEConfig.fixed_fields({"grouping": ["Treatment"]})
    assert "legend_position" in HeatmapConfig.fixed_fields({})
    # bars: the legacy legend checkbox
    assert BarPlotConfig.from_legacy_params({"legend": False}).legend_position == "none"
    assert BarPlotConfig(legend_position="none").to_legacy_params()["legend"] is False
    assert BarPlotConfig().to_legacy_params()["legend"] is True
