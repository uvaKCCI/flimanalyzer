"""Plot tools. They draw with pyplot and seaborn, holding pyplot_lock (draws_figures)."""

import contextvars
import functools
import itertools
from typing import Optional
import logging
import math
import warnings

import matplotlib.artist
import matplotlib.figure
import matplotlib.container
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import MatplotlibDeprecationWarning
from seaborn.categorical import Beeswarm as _SeabornBeeswarm

from flim.configs.plot import (
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
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.schema import TableSchema
from flim.core.tool import Tool
from flim.core.types import OutputSpec, PlotType, TableType
from flim.tools.common import category_columns, selected_features

DEFAULT_LINESTYLES = ["-", "--", ":", "-."]


def add_picker(figure) -> None:
    """Makes the figure's axes, their children and grandchildren pickable (the GUI
    edits picked labels and artists)."""
    for ax in figure.axes:
        ax.set_picker(True)
        for artist in ax.get_children():
            artist.set_picker(True)
            for child in artist.get_children():
                child.set_picker(True)
        ax.set_xlabel(ax.get_xlabel(), picker=True)
        ax.set_ylabel(ax.get_ylabel(), picker=True)


def clean_label(label) -> str:
    """A group name, e.g. ``('WT', '1')``, as a label without quotes and parentheses;
    a group of one column (``('WT',)``) is its value."""
    if isinstance(label, tuple) and len(label) == 1:
        label = label[0]
    return str(label).replace("'", "").replace("(", "").replace(")", "")


def tiles(n: int, per_row: int = 0, size=(4.5, 3.5)):
    """A figure of ``n`` plots, ``per_row`` (0: about square) per row: (figure, axes)."""
    cols = min(per_row or math.ceil(math.sqrt(n)), n)
    rows = math.ceil(n / cols)
    figure, axes = plt.subplots(
        rows,
        cols,
        squeeze=False,
        figsize=(size[0] * cols, size[1] * rows),
        layout="constrained",
    )
    axes = list(axes.flatten())
    for ax in axes[n:]:
        figure.delaxes(ax)
    return figure, axes[:n]


OUTSIDE_LOC = {
    "right": "outside right upper",
    "left": "outside left upper",
    "top": "outside upper center",
    "bottom": "outside lower center",
}


def arrange_legends(figure, position: str) -> None:
    """Places the legends of a figure: one legend for the figure outside its plots
    (right, top, bottom, left), inside the first plot with one, or none.

    Legends with the same title (e.g. one per tile of a single figure) become one,
    with all their entries. Legends with different titles (e.g. the panels of a FLIRR
    plot) stay as they are.
    """
    axes_legends = [ax for ax in figure.axes if ax.get_legend() is not None]
    legends = [ax.get_legend() for ax in axes_legends] + list(figure.legends)
    if not legends:
        return
    if position == "none":
        for legend in legends:
            legend.remove()
        return
    titles = {legend.get_title().get_text() for legend in legends}
    if len(titles) > 1:
        return
    entries = {}
    for legend in legends:
        for handle, text in zip(legend.legend_handles, legend.get_texts()):
            entries.setdefault(text.get_text(), handle)
    for legend in legends:
        legend.remove()
    options = dict(title=titles.pop() or None, fontsize="small")
    if position == "inside":
        host = axes_legends[0] if axes_legends else figure.axes[0]
        host.legend(list(entries.values()), list(entries), loc="best", **options)
        return
    figure.set_layout_engine("constrained")  # leaves room for the legend
    columns = (
        min(len(entries), 6)
        if position in ("top", "bottom")
        else len(entries) // 30 + 1
    )
    figure.legend(
        list(entries.values()),
        list(entries),
        loc=OUTSIDE_LOC[position],
        ncol=columns,
        **options,
    )


def tidy_tiles(figure, axes) -> None:
    """For tiles of a single figure: the words all tile titles share (at their start
    or end) as the figure title, each tile keeping its own part. (Their legends are
    combined by arrange_legends.)"""
    axes = [ax for ax in axes if ax.get_visible()]
    if len(axes) < 2:
        return
    titles = [ax.get_title().split() for ax in axes]
    if not all(titles):
        return
    shortest = min(len(t) for t in titles)
    start = 0
    while start < shortest and len({t[start] for t in titles}) == 1:
        start += 1
    end = 0
    while end < shortest - start and len({t[-1 - end] for t in titles}) == 1:
        end += 1
    if start == 0 and end == 0:
        return
    shared = titles[0][:start] + (titles[0][len(titles[0]) - end :] if end else [])
    for ax, words in zip(axes, titles):
        ax.set_title(" ".join(words[start : len(words) - end]))
    text = " ".join(shared)
    figure.suptitle(text[:1].upper() + text[1:])


# more plots than this (one window each, or tiles): a warning, an error
MANY_PLOTS, TOO_MANY_PLOTS = 50, 300


def _feature_names(config, inputs) -> list:
    """The features a config selects: its list, or (for "all") the input's."""
    if config.features != "all":
        return list(config.features)
    schema = inputs[0] if inputs else None
    return schema.by_role("feature") if schema is not None else []


def plot_count_issues(field: str, n: int, what: str) -> list:
    """A warning for many plots, an error for too many (they take long and each
    plot or tile is drawn): e.g. scatter plots of all pairs of 50 features."""
    if n > TOO_MANY_PLOTS:
        return [
            Issue(
                field,
                f"{what}: too many (at most {TOO_MANY_PLOTS}); select fewer features",
            )
        ]
    if n > MANY_PLOTS:
        return [Issue(field, f"{what}: drawing them takes long", "warning")]
    return []


def per_feature(config) -> list:
    """One config per feature (all features in one config if they are "all"); a
    dict of per-feature settings keeps each feature's."""
    features = config.features
    if features == "all":
        return [config]
    if isinstance(features, dict):
        return [
            config.model_copy(update={"features": {f: s}}) for f, s in features.items()
        ]
    return [config.model_copy(update={"features": [f]}) for f in features]


class _Plot:
    """Shared by the plot tools: their outputs follow from config and input columns."""

    category = "Plot"
    draws_figures = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "run" in cls.__dict__:  # legends arranged as configured, figures finished
            run = cls.__dict__["run"]

            @functools.wraps(run)
            def run_plot(self, *inputs, config):
                running = _running.set(self)  # e.g. to cancel placing swarms
                placing = _place_swarms.set(False)
                try:
                    results = run(self, *inputs, config=config)
                    figures = [
                        v
                        for v in results.values()
                        if isinstance(v, matplotlib.figure.Figure)
                    ]
                    for figure in figures:
                        if getattr(config, "legend_grouping", None) is not None:
                            arrange_legends(figure, config.legend_position)
                        self.finish(figure)
                    return results
                finally:
                    _place_swarms.reset(placing)
                    _running.reset(running)

            cls.run = run_plot

    def finish(self, figure) -> None:
        """Called for each figure of a run once its layout is final."""

    @classmethod
    def output_names(cls, config, features: list[str]) -> dict[str, type]:
        """Output name → type for the selected features (default: one plot each, or
        a single figure named after the tool)."""
        if getattr(config, "single_figure", False):
            return {cls.name: PlotType}
        return {cls.plot_name(f): PlotType for f in sorted(features)}

    @classmethod
    def plot_name(cls, feature: str) -> str:
        return f"{cls.name} {feature}"

    @classmethod
    def output_schema(cls, config, inputs):
        schema = inputs[0] if inputs else None
        if config.features == "all":
            if schema is None or not schema.complete:
                return {}
            features = schema.by_role("feature")
        else:
            features = list(config.features)
        return {
            name: OutputSpec(
                name, t, schema=TableSchema.unknown() if t is TableType else None
            )
            for name, t in cls.output_names(config, features).items()
        }

    def map_configs(self, config):
        if getattr(config, "single_figure", False):
            return [config]
        return per_feature(config)


def tile_columns(n: int, per_row: int = 0) -> int:
    """Plots per row of a single figure of ``n`` plots (0: about square)."""
    return max(1, min(per_row or math.ceil(math.sqrt(n)), n))


def long_format(data, features, keep) -> pd.DataFrame:
    """``features`` stacked into one value column (with a feature column), for
    seaborn's facets; ``keep``: the columns kept with each value."""
    return data[list(keep) + list(features)].melt(
        id_vars=list(keep),
        value_vars=list(features),
        var_name=TILE_FEATURE,
        value_name=TILE_VALUE,
    )


# column names in long_format tables (unlikely to clash with the data's columns)
TILE_FEATURE, TILE_VALUE = "__feature__", "__value__"


def label_tiles(grid, features, ylim=None) -> None:
    """Titles (the feature), y labels and y limits of a facet grid's plots."""
    for ax, feature in zip(grid.axes.flat, features):
        ax.set_title(str(feature).replace("\n", " "))
        ax.set_ylabel(str(feature).replace("\n", " "))
        if ylim is not None:
            ax.set_ylim(*ylim(feature))


# --- categorical plots ---


def strings_for_categories(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    for column in category_columns(data):
        data[column] = data[column].astype("str")
    return data


def catplot_figure(data, feature, grouping, kind):
    """A seaborn catplot of ``feature``: x, hue, col and row from the grouping columns."""
    data = data[list(grouping) + [feature]].dropna(how="any", subset=[feature])
    roles = dict(zip(("x", "hue", "col", "row"), grouping))
    if len(grouping) == 1:
        roles["color"] = "blue"
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="vert: bool was deprecated",
            category=MatplotlibDeprecationWarning,
        )
        grid = sns.catplot(data=data, y=feature, kind=kind, **roles)
    figure = grid.figure
    figure.get_axes()[0].set_ylim(
        min(0, data[feature].min()) * 0.95, max(0, data[feature].max()) * 1.05
    )
    add_picker(figure)
    return figure


def catplot_tiles(data, features, grouping, kind, per_row):
    """One seaborn catplot of all ``features``, a tile each (x and hue from the
    first two grouping columns)."""
    long = long_format(data, features, grouping).dropna(subset=[TILE_VALUE])
    roles = dict(zip(("x", "hue"), grouping))
    if len(grouping) == 1:
        roles["color"] = "blue"
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="vert: bool was deprecated",
            category=MatplotlibDeprecationWarning,
        )
        grid = sns.catplot(
            data=long,
            y=TILE_VALUE,
            col=TILE_FEATURE,
            col_order=list(features),
            col_wrap=tile_columns(len(features), per_row),
            sharey=False,
            kind=kind,
            **roles,
        )

    def ylim(feature):
        values = data[feature]
        return min(0, values.min()) * 0.95, max(0, values.max()) * 1.05

    label_tiles(grid, features, ylim)
    add_picker(grid.figure)
    return grid.figure


def sampled_rows(data: pd.DataFrame, points) -> tuple[pd.DataFrame, Optional[str]]:
    """The rows to draw: all, or a random sample that is the same on every run; and
    a note saying how many are shown (None for all)."""
    total = len(data)
    if points is None or points.mode != "sample" or not 0 < points.samples < total:
        return data, None
    rng = np.random.default_rng(points.random_seed)
    rows = np.sort(rng.choice(total, size=points.samples, replace=False))
    return (
        data.iloc[rows],
        f"{points.samples:,} samples of {total:,} measurements shown",
    )


def add_note(figure, note: Optional[str], y: float = 0.005) -> None:
    """A small note below the plots, e.g. that a sample of the points is shown."""
    if note:
        figure.text(
            0.5, y, note, ha="center", va="bottom", fontsize="small", color="0.3"
        )
        if not figure.get_constrained_layout():
            figure.subplots_adjust(bottom=figure.subplotpars.bottom + 0.03)


class _CategoricalPlot(_Plot):
    kind = ""

    def run(self, data, *, config):
        data = strings_for_categories(data)
        features = sorted(selected_features(data, config.features))
        data, note = sampled_rows(data, getattr(config, "points", None))
        if config.single_figure and features:
            figure = catplot_tiles(
                data, features, config.grouping, self.kind, config.plots_per_row
            )
            add_note(figure, note)
            return {self.name: figure}
        results = {}
        for feature in features:
            self.check_cancelled()  # plots of many points take long
            figure = catplot_figure(data, feature, config.grouping, self.kind)
            add_note(figure, note)
            results[self.plot_name(feature)] = figure
        return results


@register_tool
class BoxPlot(_CategoricalPlot, Tool[BoxPlotConfig]):
    name = "Box Plot"
    description = "Box plots of the features, grouped by up to 4 category columns."
    icon = "boxplot.png"
    kind = "box"


@register_tool
class SwarmPlot(_CategoricalPlot, Tool[SwarmPlotConfig]):
    name = "Swarm Plot"
    description = "Swarm plots of the features, grouped by up to 4 category columns."
    icon = "swarmplot.png"
    kind = "swarm"

    def finish(self, figure) -> None:
        freeze_swarms(figure)


_running = contextvars.ContextVar("running_plot_tool", default=None)
# False while a tool plots: its swarms are placed once, by freeze_swarms
_place_swarms = contextvars.ContextVar("place_swarms", default=True)


def _beeswarm(self, orig_xyr):
    """seaborn's Beeswarm.beeswarm, with the same positions: on a plain array
    (seaborn passes a masked one, whose indexing makes it twice as slow), and
    cancellable, as placing a few thousand points can take seconds."""
    orig_xyr = np.asarray(orig_xyr, dtype=float)
    if not _place_swarms.get():
        return orig_xyr
    midline = orig_xyr[0, 0]
    swarm = np.empty_like(orig_xyr)
    swarm[0] = orig_xyr[0]
    tool = _running.get()
    for i in range(1, len(orig_xyr)):
        if tool is not None and i % 50 == 0:
            tool.check_cancelled()
        xyr_i = orig_xyr[i]
        neighbors = self.could_overlap(xyr_i, swarm[:i])
        candidates = self.position_candidates(xyr_i, neighbors)
        candidates = candidates[np.argsort(np.abs(candidates[:, 0] - midline))]
        swarm[i] = self.first_non_overlapping_candidate(candidates, neighbors)
    return swarm


_SeabornBeeswarm.beeswarm = _beeswarm


def freeze_swarms(figure) -> None:
    """Places the points of seaborn's swarms once, for the figure's final layout.

    seaborn places them again at every draw (each repaint or resize of a plot
    window), which takes seconds for a few thousand points. A note says how many
    points did not fit in their swarm (seaborn piles them up at its edges).
    """
    swarms = [
        c for ax in figure.axes for c in ax.collections if "draw" in c.__dict__
    ]
    if not swarms:
        return
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        placing = _place_swarms.set(True)
        try:
            figure.draw_without_rendering()
        finally:
            _place_swarms.reset(placing)
    for collection in swarms:
        del collection.draw  # the points stay where they are
    misplaced = [w for w in caught if "cannot be placed" in str(w.message)]
    if misplaced:
        add_note(
            figure,
            "Some points do not fit in their swarm and are drawn at its edges: "
            "sample fewer points, or use a strip plot",
            y=0.03,
        )


@register_tool
class ViolinPlot(_CategoricalPlot, Tool[ViolinPlotConfig]):
    name = "Violin Plot"
    description = "Violin plots of the features, grouped by up to 4 category columns."
    icon = "violinplot.png"
    kind = "violin"


def grouped_meanbarplot(
    data,
    feature,
    ax=None,
    title=None,
    bartype="single",
    categories=[],
    dropna=True,
    pivot_level=1,
    orientation="horizontal",
    error_bar="None",
    error_type="std",
    legend=True,
):
    """Bar plot of the means of the ``feature`` columns, grouped by ``categories``."""
    stacked = not bartype == "single"
    if data is None or not all(e in data.columns.values for e in feature):
        return None
    own_figure = ax is None  # only a figure of its own is sized and adjusted here
    if own_figure:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    capsize = 6
    if categories is None:
        categories = []
    if len(categories) == 0:
        mean = pd.DataFrame(columns=feature)
        mean.loc[0] = data[feature].mean()
        if error_bar != "None":
            error = pd.DataFrame(columns=feature)
            if error_type == "std":
                error.loc[0] = data[feature].std()
            else:
                error.loc[0] = data[feature].sem()
        else:
            error = None
        if bartype == "100% stacked":
            total = mean.abs().sum(axis=1)
            mean = mean.div(total, axis=0) * 100.0
            if error is not None:
                error = error.div(total, axis=0) * 100.0
        if error_bar == "+":
            error_vals = error.to_numpy().flatten()
            error = [[np.zeros_like(error_vals), error_vals]]
        ticklabels = ""
        if orientation == "horizontal":
            mean.plot.barh(ax=ax, xerr=error, stacked=stacked, capsize=capsize)
        else:
            mean.plot.bar(ax=ax, yerr=error, stacked=stacked, capsize=capsize)
    else:
        cols = list(categories) + list(feature)
        if dropna:
            groupeddata = (
                data[cols]
                .dropna(how="any", subset=feature)
                .groupby(categories, observed=True)
            )
        else:
            groupeddata = data[cols].groupby(categories, observed=True)
        mean = groupeddata.mean()
        if groupeddata.ngroups == len(data):
            dataindex = data.set_index(list(categories), drop=True).index
            logging.debug("Single value per group. Keeping index of original data.")
            mean = mean.reindex(index=dataindex)
        if error_bar != "None":
            error = groupeddata.std() if error_type == "std" else groupeddata.sem()
        else:
            error = None
        if bartype == "100% stacked":
            total = mean.abs().sum(axis=1)
            mean = mean.div(total, axis=0) * 100.0
            if error is not None:
                error = error.div(total, axis=0) * 100.0
        num_bars = len(mean)
        if mean.dropna(how="all").empty:  # e.g. all values missing
            ax.text(
                0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes
            )
            ax.set_title(
                "|".join(feature).replace("\n", " ") if title is None else title
            )
            return fig
        if not stacked and pivot_level < len(categories):
            unstack_level = list(range(pivot_level))
            mean = mean.unstack(unstack_level).dropna(how="all", axis=0)
            if error is not None:
                error = error.unstack(unstack_level).dropna(how="all", axis=0)
        if error_bar == "+":
            error = error.transpose()
            dim = error.shape
            zeros = np.zeros_like(error)
            stacked_error = np.empty((error.shape[0] + zeros.shape[0], error.shape[1]))
            stacked_error[::2, :] = zeros
            stacked_error[1::2, :] = error
            error = stacked_error.reshape([dim[0], 2, dim[1]])
        ticklabels = mean.index.values
        if own_figure:
            fig.set_figheight(1 + num_bars // 8)
            fig.set_figwidth(6)
        if orientation == "horizontal":
            mean.plot.barh(
                ax=ax, xerr=error, width=0.8, stacked=stacked, capsize=capsize
            )
        else:
            mean.plot.bar(
                ax=ax, yerr=error, width=0.8, stacked=stacked, capsize=capsize
            )

    if len(categories) > 1 or stacked:
        ticklabels = [clean_label(label) for label in ticklabels]
        h, labels = ax.get_legend_handles_labels()
        if stacked:
            ltitle = ""
            labels = feature
        elif len(categories) > 1:
            ltitle = ", ".join(categories[0:pivot_level])
            labels = [clean_label(label) for label in labels]
            labels = [", ".join(label.split(",")[1:]) for label in labels]
            if orientation == "horizontal":
                ax.set_ylabel(", ".join(categories[pivot_level:]))
            else:
                ax.set_xlabel(", ".join(categories[pivot_level:]))
        no_legendcols = len(categories) // 30 + 1
        if bartype == "100% stacked":
            ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        if legend:
            ax.legend(
                labels=labels,
                title=ltitle,
                loc="upper left",
                bbox_to_anchor=(1.0, 1.0),
                fontsize="small",
                ncol=no_legendcols,
            )
        else:
            ax.legend().remove()
    else:
        ax.legend().remove()
    if orientation == "horizontal":
        ax.set_yticklabels(ticklabels)
    else:
        ax.set_xticklabels(ticklabels)
    if title is None:
        title = "|".join(feature).replace("\n", " ")
        if len(categories) > 0:
            title = f"{title} grouped by {', '.join(categories)}"
    if len(title) > 0:
        ax.set_title(title)
    limit_error_caps(ax, capsize, horizontal=orientation == "horizontal")
    return fig


class _CapLimiter(matplotlib.artist.Artist):
    """Keeps the error bar caps of bars at most ``fraction`` of the bars' width.

    Caps are sized in points, bars by the axes: drawn first in its axes (before the
    bars), at every draw (saving, resized windows), it sets the caps' size from the
    bars' width at that moment.
    """

    def __init__(self, caplines, bars, capsize, horizontal, fraction=0.8):
        super().__init__()
        self.caplines, self.bars = list(caplines), list(bars)
        self.cap_width = 2 * capsize  # matplotlib draws caps 2 * capsize wide
        self.horizontal, self.fraction = horizontal, fraction
        self.set_zorder(-1e9)

    def draw(self, renderer):
        if not self.bars or not self.get_visible():
            return
        sizes = [b.get_window_extent(renderer) for b in self.bars]
        pixels = min(box.height if self.horizontal else box.width for box in sizes)
        points = pixels * 72 / self.axes.figure.dpi
        width = max(0.0, min(self.cap_width, self.fraction * points))
        for line in self.caplines:
            line.set_markersize(width)


def limit_error_caps(ax, capsize, horizontal=False, fraction=0.8) -> None:
    """Error bar caps of the bars in ``ax``: at most ``fraction`` of a bar's width."""
    for container in ax.containers:
        errorbar = getattr(container, "errorbar", None)
        if isinstance(container, matplotlib.container.BarContainer) and errorbar:
            _, caplines, _ = errorbar.lines
            if caplines:
                ax.add_artist(
                    _CapLimiter(
                        caplines, container.patches, capsize, horizontal, fraction
                    )
                )


@register_tool
class BarPlot(_Plot, Tool[BarPlotConfig]):
    name = "Bar Plot"
    description = "Mean bar plots of the features, grouped by the category columns."
    icon = "barplot.png"

    @classmethod
    def plot_name(cls, feature):
        return feature

    @classmethod
    def output_names(cls, config, features):
        if config.bar_type == "single":
            return super().output_names(config, features)
        return {"|".join(features): PlotType}

    def run(self, data, *, config):
        features = selected_features(data, config.features)
        options = dict(
            categories=config.grouping,
            dropna=config.dropna,
            bartype=config.bar_type,
            orientation=config.orientation,
            error_bar=config.error_bar,
            error_type=config.error_type,
            legend=True,  # placed by arrange_legends
        )
        if config.bar_type != "single":  # all features in one plot
            figure = grouped_meanbarplot(data, features, **options)
            add_picker(figure)
            return {"|".join(features): figure}
        features = sorted(features)
        if config.single_figure and features:
            figure, axes = tiles(len(features), config.plots_per_row, size=(6, 4.5))
            for ax, feature in zip(axes, features):
                self.check_cancelled()
                grouped_meanbarplot(data, [feature], ax=ax, **options)
            tidy_tiles(figure, axes)
            add_picker(figure)
            return {self.name: figure}
        results = {}
        for feature in features:
            figure = grouped_meanbarplot(data, [feature], **options)
            add_picker(figure)
            results[feature] = figure
        return results

    def map_configs(self, config):
        if config.bar_type != "single" or config.single_figure:
            return [config]
        return per_feature(config)


def ci_to_errorbar(ci):
    """seaborn's errorbar argument for a Line Plot ``errorbar`` setting.

    seaborn 0.12 replaced ci=<n> with errorbar=("ci", <n>), ci="sd" with
    errorbar="sd" and ci=None with errorbar=None.
    """
    if ci is None or ci == "sd":
        return ci
    return ("ci", ci)


@register_tool
class LinePlot(_Plot, Tool[LinePlotConfig]):
    name = "Line Plot"
    description = (
        "Line plots of the features along the first grouping column; further grouping"
        " columns set hue, style, columns and rows."
    )
    icon = "lineplot.png"

    @classmethod
    def plot_name(cls, feature):
        return f"Line Plot: {feature}"

    def run(self, data, *, config):
        data = data.copy()
        for column in category_columns(data):
            if data[column].nunique() > 1:
                data[column] = data[column].astype("str")
        features = sorted(selected_features(data, config.features))
        if config.single_figure and features:
            return {self.name: self.line_tiles(data, features, config)}
        return {
            self.plot_name(feature): self.line_figure(data, feature, config)
            for feature in features
        }

    def line_tiles(self, data, features, config):
        """All features as tiles of one figure (up to 3 grouping columns)."""
        grouping = list(config.grouping)
        per_row = config.plots_per_row
        if not grouping:  # each feature along the rows of the table
            figure, axes = tiles(len(features), per_row)
            for ax, feature in zip(axes, features):
                data[feature].plot(ax=ax)
                ax.set_title(str(feature).replace("\n", " "))
            add_picker(figure)
            return figure
        grid = sns.relplot(
            data=long_format(data, features, grouping),
            y=TILE_VALUE,
            col=TILE_FEATURE,
            col_order=list(features),
            col_wrap=tile_columns(len(features), per_row),
            kind="line",
            facet_kws={"sharey": False},
            errorbar=ci_to_errorbar(config.errorbar),
            err_style=config.err_style,
            markers=config.markers,
            **dict(zip(("x", "hue", "style"), grouping)),
        )
        label_tiles(grid, features)
        add_picker(grid.figure)
        return grid.figure

    def line_figure(self, data, feature, config):
        grouping = list(config.grouping)
        options = dict(
            errorbar=ci_to_errorbar(config.errorbar),
            err_style=config.err_style,
            markers=config.markers,
        )
        roles = dict(zip(("x", "hue", "style", "col", "row"), grouping))
        if len(grouping) > 3:  # a grid of plots
            figure = sns.relplot(
                data=data, y=feature, kind="line", **roles, **options
            ).figure
        else:
            figure, ax = plt.subplots()
            if grouping:
                sns.lineplot(ax=ax, data=data, y=feature, **roles, **options)
            else:
                data[feature].plot(ax=ax)
        add_picker(figure)
        return figure


def group_styles(data, groups) -> list[dict]:
    """Colour (and, for two grouping columns, line style) of each group, in the order
    of ``data.groupby(groups, observed=False)``: the same in every plot."""
    if len(groups) == 2:
        values = [
            data[g].cat.categories if hasattr(data[g], "cat") else data[g].unique()
            for g in groups
        ]
        if len(values[1]) <= len(DEFAULT_LINESTYLES):
            colors = sns.color_palette(n_colors=len(values[0]))
            return [
                {"color": c, "linestyle": ls}
                for c in colors
                for ls in DEFAULT_LINESTYLES[: len(values[1])]
            ]
    n = data.groupby(list(groups), observed=False).ngroups
    return [{"color": c} for c in sns.color_palette(n_colors=n)]


def grouped_kdeplot(data, column, ax, groups=(), show_legend=True, **kwargs):
    """KDE curves of ``column``, one per group, labelled with the group."""
    kwargs = {**kwargs, "ax": ax, "warn_singular": False}
    data = data[list(groups) + [column]].dropna(how="any", subset=[column])
    if groups:
        styles = group_styles(data, groups)
        for index, (name, group) in enumerate(
            data.groupby(list(groups), observed=False)
        ):
            if len(group[column]) == 0:
                continue
            style = styles[index] if index < len(styles) else {}
            try:
                sns.kdeplot(group[column], label=clean_label(name), **kwargs, **style)
            except Exception as err:
                logging.error(err)
        # from the curves drawn (none for e.g. a constant column)
        if show_legend and ax.get_legend_handles_labels()[0]:
            ax.legend(**group_legend_options(groups))
    else:
        try:
            sns.kdeplot(data[column], **kwargs)
        except Exception as err:
            logging.error(err)
    ax.autoscale(enable=True, axis="y")
    ax.set_ylim(0, None)


def group_legend_options(groups) -> dict:
    return dict(
        loc="upper left",
        title=", ".join(groups),
        bbox_to_anchor=(1.0, 1.0),
        fontsize="small",
        ncol=len(groups) // 30 + 1,
    )


@register_tool
class KDE(_Plot, Tool[KDEConfig]):
    name = "KDE"
    description = "Kernel density estimates of the features, one curve per group."
    icon = "kde.png"

    @classmethod
    def output_names(cls, config, features):
        if config.single_figure:
            return {"KDE": PlotType}
        return super().output_names(config, features)

    def run(self, data, *, config):
        features = sorted(selected_features(data, config.features))
        if not features:
            return {}
        single = config.single_figure
        if single:
            figure, axes = tiles(len(features), config.plots_per_row)
        results = {}
        for i, feature in enumerate(features):
            if single:
                ax = axes[i]
            else:
                figure, ax = plt.subplots()
            values = data[feature].replace([np.inf, -np.inf], np.nan).dropna()
            low, high = values.min(), values.max()
            grouped_kdeplot(
                data,
                feature,
                ax,
                groups=config.grouping,
                clip=(low, high),
                show_legend=True,  # a single figure: combined by arrange_legends
            )
            if np.isfinite([low, high]).all() and low < high:  # not for constants
                ax.set_xlim(low, high)
            if not single:
                figure.tight_layout()
                add_picker(figure)
                results[self.plot_name(feature)] = figure
        if single:
            add_picker(figure)
            results["KDE"] = figure
        return results

    def map_configs(self, config):
        return [config] if config.single_figure else per_feature(config)


@register_tool
class FrequencyHistogram(_Plot, Tool[HistogramConfig]):
    name = "Frequency Histogram"
    description = (
        "Histograms of the features in percent of the measurements (per group, unless"
        " stacked), optionally with the binned values as a table."
    )
    icon = "histogram.png"

    @classmethod
    def plot_name(cls, feature):
        return f"Frequency Histo Plot: {feature}"

    @classmethod
    def output_names(cls, config, features):
        names = {"Frequency Histogram": PlotType} if config.single_figure else {}
        for feature in sorted(features):
            if not config.single_figure:
                names[cls.plot_name(feature)] = PlotType
            if config.table:
                names[f"Frequency Histo Table: {feature}"] = TableType
        return names

    def run(self, data, *, config):
        results = {}
        features = sorted(selected_features(data, config.features))
        if config.single_figure and features:
            figure, axes = tiles(len(features), config.plots_per_row, size=(5, 4.5))
            results["Frequency Histogram"] = figure
        for i, feature in enumerate(features):
            settings = config.features[feature]
            auto = config.auto_range
            low = data[feature].min() if auto or settings.min is None else settings.min
            high = data[feature].max() if auto or settings.max is None else settings.max
            value_range, bins = (low, high), settings.bins
            values, edges, names, feature_figure = self.histogram(
                data,
                feature,
                groups=config.grouping,
                stacked=config.stacked,
                ax=axes[i] if config.single_figure else None,
                range=value_range,
                bins=bins,
                histtype=config.histtype,
                cumulative=config.cumulative,
                density=config.density,
            )
            if not config.single_figure:
                results[self.plot_name(feature)] = feature_figure
            if config.table:
                table = pd.DataFrame(
                    {"bin edge low": edges[:-1], "bin edge high": edges[1:]}
                )
                for name, column in zip(names, np.atleast_2d(values)):
                    table[name] = column
                results[f"Frequency Histo Table: {feature}"] = table
        if config.single_figure and features:
            tidy_tiles(figure, axes)
        return results

    def map_configs(self, config):
        return [config] if config.single_figure else per_feature(config)

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if not config.features:
            issues.append(Issue("features", "Check the features to plot"))
        return issues

    @staticmethod
    def histogram(data, column, groups, stacked, normalize=100, ax=None, **kwargs):
        """Histogram in percent of all (stacked) or of each group's measurements, in
        ``ax`` (default: a new figure)."""
        own_figure = ax is None
        if own_figure:
            figure, ax = plt.subplots(constrained_layout=True)
            figure.set_size_inches(8, 8)
        else:
            figure = ax.get_figure()
        total = data[column].dropna(axis=0, how="all").count()
        values, weights, names = [], [], []
        if not groups:
            names.append("all")
            values = data[column].values
            kwargs["label"] = "all"
            weights = np.ones_like(values) / float(total) * normalize
        else:
            grouped = data.groupby(list(groups), observed=True)
            kwargs["label"] = list(grouped.groups)
            for name, group in grouped:
                if len(group[column]) == 0:
                    continue
                names.append(name)
                values.append(group[column].values)
                count = total if stacked else group[column].count()
                weights.append(
                    np.ones_like(group[column].values) / float(count) * normalize
                )
        in_group = "" if stacked else "in each group "
        ax.set_ylabel(f"relative counts {in_group}[%]")
        names = [f"{n} [rel %]" for n in names]
        ax.set_xlabel(column)
        title = column.replace("\n", " ")
        if groups:
            title = f"{title} grouped by {', '.join(groups)}"
        ax.set_title(title)
        counts, edges, _ = ax.hist(
            values, weights=weights, stacked=stacked, alpha=0.5, **kwargs
        )
        if groups and len(counts) > 1:
            h, labels = ax.get_legend_handles_labels()
            ax.legend(
                labels=[clean_label(label) for label in labels],
                loc="upper left",
                title=", ".join(groups),
                bbox_to_anchor=(1.0, 1.0),
                fontsize="small",
                ncol=len(counts) // 30 + 1,
            )
        add_picker(figure)
        return np.array(counts), edges, names, figure


@register_tool
class Heatmap(_Plot, Tool[HeatmapConfig]):
    name = "Heatmap"
    description = "Correlation heatmap of the features, with the correlation table."
    icon = "heatmap.png"

    @classmethod
    def output_names(cls, config, features):
        return {"Heatmap": PlotType, "Heatmap Correlation": TableType}

    def run(self, data, *, config):
        features = selected_features(data, config.features)
        corr = data[features].corr(method=config.correlation)
        figure, ax = plt.subplots(constrained_layout=True)
        ax = sns.heatmap(
            corr,
            ax=ax,
            vmin=-1,
            vmax=1,
            cmap=sns.diverging_palette(20, 220, n=200),
            square=True,
            annot=config.annotate,
        )
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
        ax.set_xticklabels(
            ax.get_xticklabels(), rotation=45, horizontalalignment="right"
        )
        grouping = config.grouping
        ax.set_title(
            f"Data grouped by {', '.join(grouping)}" if grouping else "Data ungrouped"
        )
        corr = corr.reset_index().rename(columns={"index": "Feature"})
        corr["Feature"] = corr["Feature"].astype("category")
        return {"Heatmap": ax.get_figure(), "Heatmap Correlation": corr}

    def map_configs(self, config):
        return [config]


def _sampled(func, keep):
    """Wraps a seaborn plot function to draw only the rows where ``keep`` is True.

    PairGrid passes each panel's x, y and hue columns of the whole table; ``keep``
    is a boolean array over the table's (reset, 0..n-1) index.
    """

    def plot(x, y, hue=None, **kwargs):
        mask = keep[x.index.to_numpy()]
        if hue is not None:
            hue = hue[mask]
        return func(x=x[mask], y=y[mask], hue=hue, **kwargs)

    return plot


@register_tool
class PairPlot(_Plot, Tool[PairPlotConfig]):
    name = "Pair Plot"
    description = (
        "A grid of scatter plots of feature pairs, colored by the first grouping"
        " column, with histograms or KDEs on the diagonal."
    )
    icon = "pairplot.png"

    @classmethod
    def output_names(cls, config, features):
        return {f"Pair Plot: {config.grouping}": PlotType}

    def run(self, data, *, config):
        x_vars, y_vars = self.grid_vars(data, config)
        if not x_vars or not y_vars:
            raise ValueError(f"{self.name}: select the features to plot")
        # a lower half exists only if the columns and rows are the same features
        # (seaborn fails otherwise); the config allows it only for symmetric grids
        corner = config.corner and list(x_vars) == list(y_vars)
        hue = config.grouping[0] if config.grouping else None
        columns = list(
            dict.fromkeys(list(x_vars) + list(y_vars) + ([hue] if hue else []))
        )
        data = data[columns].reset_index(drop=True)
        total = len(data)
        points = config.points
        sampled = points.mode == "sample" and 0 < points.samples < total
        scatter = sns.scatterplot
        if sampled:
            rng = np.random.default_rng(points.random_seed)
            keep = np.zeros(total, dtype=bool)
            keep[rng.choice(total, size=points.samples, replace=False)] = True
            scatter = _sampled(sns.scatterplot, keep)
        grid = sns.PairGrid(
            data,
            diag_sharey=False,
            x_vars=x_vars,
            y_vars=y_vars,
            hue=hue,
            dropna=True,
            corner=corner,
        )
        if config.diagonal == "Histogram":
            grid.map_diag(sns.histplot, bins=config.hist_bins)
        else:
            grid.map_diag(sns.kdeplot)
        grid.map_upper(scatter)
        grid.map_lower(scatter)
        grid.add_legend()
        if sampled:
            grid.figure.text(
                0.5,
                0.005,
                f"{points.samples:,} samples of {total:,} measurements shown",
                ha="center",
                va="bottom",
                fontsize="small",
                color="0.3",
            )
            grid.figure.subplots_adjust(bottom=grid.figure.subplotpars.bottom + 0.03)
        return {f"Pair Plot: {config.grouping}": grid.figure}

    @staticmethod
    def grid_vars(data, config) -> tuple[list, list]:
        """The features of the grid's columns and rows; all numeric columns if the
        config selects "all" features (older settings)."""
        x_vars = config.x_vars or selected_features(data, config.features)
        y_vars = x_vars if config.symmetric else config.y_vars
        return x_vars, y_vars

    def map_configs(self, config):
        return [config]

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if not config.x_vars and config.features != "all":
            issues.append(Issue("x_vars", "Select the features of the grid columns"))
        if not config.symmetric and not config.y_vars:
            issues.append(Issue("y_vars", "Select the features of the grid rows"))
        columns = config.x_vars or _feature_names(config, inputs)
        rows = columns if config.symmetric else config.y_vars
        issues += plot_count_issues(
            "x_vars", len(columns) * len(rows), f"{len(columns)} x {len(rows)} panels"
        )
        return issues


@register_tool
class ScatterPlot(_Plot, Tool[ScatterPlotConfig]):
    name = "Scatter Plot"
    description = "A scatter plot for each pair of features, colored by group."
    icon = "scatter.png"

    @classmethod
    def output_names(cls, config, features):
        if config.single_figure:
            return {cls.name: PlotType}
        return {
            f"Scatter Plot: {pair}": PlotType
            for pair in sorted(itertools.combinations(features, 2))
        }

    def run(self, data, *, config):
        features = selected_features(data, config.features)
        pairs = sorted(itertools.combinations(features, 2))
        # the same sample in every plot: the same cells
        data, note = sampled_rows(data, config.points)
        if config.single_figure and pairs:
            figure, axes = tiles(len(pairs), config.plots_per_row, size=(6, 4.5))
            for ax, pair in zip(axes, pairs):
                self.check_cancelled()  # many points take long
                self.scatter_figure(data, pair, config.grouping, ax=ax)
            tidy_tiles(figure, axes)
            add_note(figure, note)
            add_picker(figure)
            return {self.name: figure}
        results = {}
        for pair in pairs:
            self.check_cancelled()
            figure = self.scatter_figure(data, pair, config.grouping)
            add_note(figure, note)
            results[f"Scatter Plot: {pair}"] = figure
        return results

    @staticmethod
    def scatter_figure(data, pair, groups, ax=None):
        """A scatter plot of ``pair``, in ``ax`` (default: a figure of its own)."""
        x, y = pair
        own_figure = ax is None
        if own_figure:
            figure, ax = plt.subplots(constrained_layout=True)
            figure.set_figheight(6)
            figure.set_figwidth(12)
        else:
            figure = ax.get_figure()
        data = data[list(groups) + list(pair)].dropna(how="any", subset=list(pair))
        options = {"alpha": 0.5, "marker": "o", "s": 10}
        if groups:
            for name, group in data.groupby(list(groups), observed=False):
                if len(group[x]) > 0 and len(group[y]) > 0:
                    ax.scatter(group[x], group[y], label=clean_label(name), **options)
        else:
            ax.scatter(data[x], data[y], **options)
        ax.set_xlim(min(0, data[x].min()) * 1.05, max(0, data[x].max()) * 1.05)
        ax.set_xlabel(x)
        ax.set_ylim(min(0, data[y].min()) * 1.05, max(0, data[y].max()) * 1.05)
        ax.set_ylabel(y)
        if groups:
            h, labels = ax.get_legend_handles_labels()
            ax.legend(
                labels=[clean_label(label) for label in labels],
                loc="upper left",
                title=", ".join(groups),
                bbox_to_anchor=(1.0, 1.0),
                fontsize="small",
                ncol=len(groups) // 30 + 1,
            )
            ax.set_title(f"Data grouped by {', '.join(groups)}")
        if own_figure:
            add_picker(figure)
        return figure

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        n = len(_feature_names(config, inputs))
        pairs = n * (n - 1) // 2
        return issues + plot_count_issues(
            "features", pairs, f"{n} features: {pairs:,} feature pairs (plots)"
        )

    def map_configs(self, config):
        if config.features == "all" or config.single_figure:
            return [config]
        return [
            config.model_copy(update={"features": list(pair)})
            for pair in itertools.combinations(config.features, 2)
        ]


def flirr_columns(columns) -> tuple[str, list[str]]:
    """The FLIRR column and the two scatter features (FAD a1 %, NAD(P)H a2 %), found by
    name."""
    flirr = [c for c in columns if "FLIRR" in c.upper()]
    scatter = [
        c
        for c in columns
        if "FLIRR" not in c.upper()
        and "/" not in c
        and (
            ("FAD" in c and "a1" in c and "%" in c)
            or ("NAD" in c and "a2" in c and "%" in c)
        )
    ]
    return (flirr[0] if flirr else None), scatter


@register_tool
class FLIRRPlot(_Plot, Tool[FLIRRPlotConfig]):
    name = "FLIRR Plot"
    description = (
        "FAD a1% vs NAD(P)H a2% scatter, their KDEs, FLIRR KDE, FLIRR along the first"
        " grouping column and FLIRR mean bars."
    )
    icon = "flirrplot.png"

    @classmethod
    def output_names(cls, config, features):
        return {f"FLIRR Plot: {config.grouping}": PlotType}

    def run(self, data, *, config):
        grouping = list(config.grouping)
        if not grouping:
            raise ValueError(f"{self.name}: select at least one grouping column")
        flirr, scatter = flirr_columns(data.select_dtypes(include=np.number).columns)
        if flirr is None or len(scatter) < 2:
            raise ValueError(
                f"{self.name}: needs a FLIRR column, and FAD a1 % and NAD(P)H a2 % columns"
            )
        hue = grouping[0]
        # constrained layout: panels and labels without overlap
        figure = plt.figure(figsize=(16, 10), layout="constrained")
        ax1 = plt.subplot2grid((3, 5), (0, 0), colspan=2, rowspan=2, fig=figure)
        ax2 = plt.subplot2grid((3, 5), (0, 2), colspan=1, fig=figure)
        ax3 = plt.subplot2grid((3, 5), (0, 3), colspan=1, fig=figure)
        ax4 = plt.subplot2grid((3, 5), (0, 4), colspan=1, fig=figure)
        ax5 = plt.subplot2grid((3, 5), (1, 2), colspan=3, fig=figure)
        ax6 = plt.subplot2grid((3, 5), (2, 0), colspan=5, fig=figure)
        sns.scatterplot(ax=ax1, data=data, x=scatter[0], y=scatter[1], hue=hue)
        sns.kdeplot(ax=ax2, data=data, x=scatter[0], hue=hue, legend=False)
        sns.kdeplot(ax=ax3, data=data, x=scatter[1], hue=hue, legend=False)
        sns.kdeplot(ax=ax4, data=data, x=flirr, hue=hue, legend=False)
        sns.lineplot(
            ax=ax5,
            data=data,
            x=hue,
            y=flirr,
            style=grouping[1] if len(grouping) > 1 else None,
            legend=True,
        )
        grouped_meanbarplot(
            data,
            [flirr],
            ax=ax6,
            title=None,
            bartype="single",
            categories=grouping,
            dropna=True,
            pivot_level=1,
            orientation="vertical",
            error_bar="+",
            error_type="sem",
            legend=False,
        )
        add_picker(figure)
        return {f"FLIRR Plot: {config.grouping}": figure}

    def map_configs(self, config):
        return [config]

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if not config.grouping:
            issues.append(Issue("grouping", "Select at least one grouping column"))
        schema = inputs[0] if inputs else None
        if schema is not None and schema.complete:
            flirr, scatter = flirr_columns(schema.by_role("feature"))
            if flirr is None or len(scatter) < 2:
                issues.append(
                    Issue(
                        None,
                        "The input needs a FLIRR column, and FAD a1 % and NAD(P)H a2 %"
                        " columns",
                    )
                )
        return issues
