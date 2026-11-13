"""Plot tools. They draw with pyplot and seaborn, holding pyplot_lock (draws_figures)."""

import contextvars
import functools
import itertools
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Optional, TypeVar, Union
import logging
import math
import warnings

import matplotlib.artist
import matplotlib.axes
import matplotlib.figure
import matplotlib.container
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import MatplotlibDeprecationWarning
from matplotlib.backend_bases import RendererBase
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from seaborn.categorical import Beeswarm as _SeabornBeeswarm

from flim.configs.plot import (
    BarPlotConfig,
    BoxPlotConfig,
    CategoricalPlotConfig,
    FLIRRPlotConfig,
    HeatmapConfig,
    HistogramConfig,
    KDEConfig,
    LinePlotConfig,
    PairPlotConfig,
    PlotConfig,
    PointSampling,
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

logger = logging.getLogger(__name__)

DEFAULT_LINESTYLES = ["-", "--", ":", "-."]

# the config type of a plot tool, for functions that return configs of the same type
PlotConfigT = TypeVar("PlotConfigT", bound=PlotConfig)


def add_picker(figure: matplotlib.figure.Figure) -> None:
    """Make the figure's axes and their artists pickable, so that they can be edited.

    The axes, their children and grandchildren, and the x and y labels become
    pickable.

    Args:
        figure: The figure.
    """
    for ax in figure.axes:
        ax.set_picker(True)
        for artist in ax.get_children():
            artist.set_picker(True)
            for child in artist.get_children():
                child.set_picker(True)
        ax.set_xlabel(ax.get_xlabel(), picker=True)
        ax.set_ylabel(ax.get_ylabel(), picker=True)


def clean_label(label: Any) -> str:
    """Return a group name as a label without quotes and parentheses.

    For example `('WT', '1')` becomes `WT, 1`; a group of one column (`('WT',)`)
    becomes its value, `WT`.

    Args:
        label: The group name: a value or a tuple of values.

    Returns:
        The label.
    """
    if isinstance(label, tuple) and len(label) == 1:
        label = label[0]
    return str(label).replace("'", "").replace("(", "").replace(")", "")


def tiles(
    n: int, per_row: int = 0, size: tuple[float, float] = (4.5, 3.5)
) -> tuple[matplotlib.figure.Figure, list[matplotlib.axes.Axes]]:
    """Create a figure of `n` plots in rows, with constrained layout.

    Args:
        n: The number of plots; at least 1.
        per_row: The plots per row; 0 for about as many rows as columns. Defaults
            to 0.
        size: The width and height of one plot, in inches.

    Returns:
        The figure and its `n` axes, row by row. Axes beyond `n` in the last row
        are removed from the figure.
    """
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


def arrange_legends(figure: matplotlib.figure.Figure, position: str) -> None:
    """Place the legends of a figure: outside its plots, inside a plot, or none.

    Legends with the same title (e.g. one per tile of a single figure) become one
    legend with the entries of all of them, each label once. Legends with different
    titles (e.g. the panels of a FLIRR plot) stay as they are, unless the position is
    `none`. A legend outside the plots switches the figure to constrained layout,
    which leaves room for it.

    Args:
        figure: The figure.
        position: `right`, `left`, `top` or `bottom` (one legend for the figure,
            outside its plots), `inside` (in the first plot that has a legend, else
            in the first plot), or `none` (all legends are removed).
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


def tidy_tiles(
    figure: matplotlib.figure.Figure, axes: Sequence[matplotlib.axes.Axes]
) -> None:
    """Move the words that all visible tile titles share into the figure title.

    The shared words at the start and at the end of the titles become the figure
    title, with its first letter in upper case; each tile keeps the rest of its
    title. Does nothing for fewer than two visible tiles, a tile without a title, or
    titles without shared words at their start or end.

    Args:
        figure: The figure.
        axes: The tiles.
    """
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


# plot_count_issues: more plots (windows or tiles) than MANY_PLOTS give a warning,
# more than TOO_MANY_PLOTS an error
MANY_PLOTS, TOO_MANY_PLOTS = 50, 300


def _feature_names(config: PlotConfig, inputs: Sequence[Any]) -> list[str]:
    """Return the config's features; for `all`, the input schema's features."""
    if config.features != "all":
        return list(config.features)
    schema = inputs[0] if inputs else None
    return schema.by_role("feature") if schema is not None else []


def plot_count_issues(field: str, n: int, what: str) -> list[Issue]:
    """Check the number of plots or tiles a config draws.

    Each plot or tile takes time to draw: for example, scatter plots of all pairs of
    50 features are 1,225 plots.

    Args:
        field: The config field the issue refers to.
        n: The number of plots or tiles.
        what: The start of the message, e.g. `10 x 10 panels`.

    Returns:
        An error if `n` is more than `TOO_MANY_PLOTS`, a warning if it is more than
        `MANY_PLOTS`, else no issue.
    """
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


def per_feature(config: PlotConfigT) -> list[PlotConfigT]:
    """Return one config per feature.

    Args:
        config: The config. Its `features` are a list, a dict of per-feature
            settings, or `all`.

    Returns:
        A copy of the config per feature; for a dict, each copy keeps its feature's
        settings. With `all`, the config itself, unsplit.
    """
    features = config.features
    if features == "all":
        return [config]
    if isinstance(features, dict):
        return [
            config.model_copy(update={"features": {f: s}}) for f, s in features.items()
        ]
    return [config.model_copy(update={"features": [f]}) for f in features]


class _Plot:
    """Shared by the plot tools: their outputs follow from config and input columns.

    A subclass's `run` is wrapped: after it returns, the legends of each figure are
    arranged (`arrange_legends`, for configs with a legend) and `finish` is called
    for each figure. While it runs, seaborn's swarms are not placed (see
    `freeze_swarms`), and the running tool can be cancelled while swarms are placed.
    """

    category = "Plot"
    draws_figures = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Wrap the subclass's own `run`, if it defines one (see the class)."""
        super().__init_subclass__(**kwargs)
        if "run" in cls.__dict__:  # wraps run: arranges legends, calls finish
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

    def finish(self, figure: matplotlib.figure.Figure) -> None:
        """Process a figure of the run once its layout is final; does nothing here.

        Args:
            figure: The figure.
        """

    @classmethod
    def output_names(cls, config: PlotConfig, features: list[str]) -> dict[str, type]:
        """Return the names and types of the outputs for the selected features.

        Args:
            config: The config.
            features: The selected features.

        Returns:
            Output name -> type. By default one plot per feature (see `plot_name`),
            or with `single_figure` one figure named after the tool.
        """
        if getattr(config, "single_figure", False):
            return {cls.name: PlotType}
        return {cls.plot_name(f): PlotType for f in sorted(features)}

    @classmethod
    def plot_name(cls, feature: str) -> str:
        """Return the name of a feature's plot: `<tool name> <feature>` by default."""
        return f"{cls.name} {feature}"

    @classmethod
    def output_schema(
        cls, config: PlotConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs, from the config and the input schema's features.

        Unlike `Tool.output_schema`, the tool is not run on sample rows. Tables among
        the outputs have unknown schemas.

        Args:
            config: The config.
            inputs: The input schemas; the first is the table plotted.

        Returns:
            Output name -> output (see `output_names`); none if the config selects
            all features and the input schema is unknown or incomplete.
        """
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

    def map_configs(self, config: PlotConfigT) -> list[PlotConfigT]:
        """Return one config per feature, so that the features run as separate tasks.

        With `single_figure`, or with all features selected, the config is not split.
        """
        if getattr(config, "single_figure", False):
            return [config]
        return per_feature(config)


def tile_columns(n: int, per_row: int = 0) -> int:
    """Return the number of plots per row of a single figure of `n` plots.

    Args:
        n: The number of plots.
        per_row: The plots per row asked for; 0 for about as many rows as columns.

    Returns:
        `per_row` (or the automatic number), at most `n` and at least 1.
    """
    return max(1, min(per_row or math.ceil(math.sqrt(n)), n))


def long_format(
    data: pd.DataFrame, features: Sequence[str], keep: Sequence[str]
) -> pd.DataFrame:
    """Stack the features into one value column, for seaborn's facets.

    Args:
        data: The table.
        features: The features to stack.
        keep: The columns kept with each value, e.g. the grouping columns.

    Returns:
        A table with the `keep` columns, a column `TILE_FEATURE` with the feature's
        name, and a column `TILE_VALUE` with its value: one row per row of `data`
        and feature.
    """
    return data[list(keep) + list(features)].melt(
        id_vars=list(keep),
        value_vars=list(features),
        var_name=TILE_FEATURE,
        value_name=TILE_VALUE,
    )


# column names in long_format tables (unlikely to clash with the data's columns)
TILE_FEATURE, TILE_VALUE = "__feature__", "__value__"


def label_tiles(
    grid: sns.FacetGrid,
    features: Sequence[str],
    ylim: Optional[Callable[[str], tuple[float, float]]] = None,
) -> None:
    """Set the titles, y labels and y limits of a facet grid's plots.

    Args:
        grid: The facet grid, one plot per feature in the order of `features`.
        features: The features; each plot's title and y label is its feature, with
            line breaks as spaces.
        ylim: A function that returns the y limits (low, high) of a feature's plot;
            None to keep seaborn's limits. Defaults to None.
    """
    for ax, feature in zip(grid.axes.flat, features):
        ax.set_title(str(feature).replace("\n", " "))
        ax.set_ylabel(str(feature).replace("\n", " "))
        if ylim is not None:
            ax.set_ylim(*ylim(feature))


def axis_range(values: pd.Series, fit: bool = True) -> tuple[float, float]:
    """Return axis limits for the values.

    Args:
        values: The values on the axis.
        fit: True for the range of the values; False for their range extended to
            include 0. Defaults to True.

    Returns:
        The low and high limit: the range with a margin of 5% of its width on each
        side. If all values are equal, the margin is 5% of the value, or 0.5 for 0.
    """
    low, high = float(values.min()), float(values.max())
    if not fit:
        low, high = min(0.0, low), max(0.0, high)
    margin = 0.05 * (high - low) or 0.05 * abs(high) or 0.5  # one value: still a range
    return low - margin, high + margin


# --- categorical plots ---


def as_strings(values: pd.Series) -> pd.Series:
    """Return the values as text, so that seaborn treats them as categories.

    Category columns keep the order of their categories (the order on the axes and
    in the legends), without the categories that do not occur.

    Args:
        values: The column.

    Returns:
        The column with text values; a category column stays a category column.
    """
    if isinstance(values.dtype, pd.CategoricalDtype):
        return values.cat.remove_unused_categories().cat.rename_categories(str)
    return values.astype("str")


def strings_for_categories(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of the table whose category columns have text values."""
    data = data.copy()
    for column in category_columns(data):
        data[column] = as_strings(data[column])
    return data


def catplot_figure(
    data: pd.DataFrame,
    feature: str,
    grouping: Sequence[str],
    kind: str,
    fit: bool = False,
) -> matplotlib.figure.Figure:
    """Draw a seaborn catplot of one feature.

    Rows without a value of the feature are left out.

    Args:
        data: The table.
        feature: The feature, on the y axis.
        grouping: Up to 4 grouping columns: x, hue, facet column and facet row, in
            this order. With one grouping column the plot is blue.
        kind: The kind of seaborn catplot, e.g. `box`, `swarm` or `violin`.
        fit: Whether the y axis fits the values (True) or includes 0 (False).
            Defaults to False.

    Returns:
        The figure, with pickable artists.
    """
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
    figure.get_axes()[0].set_ylim(*axis_range(data[feature], fit))
    add_picker(figure)
    return figure


def catplot_tiles(
    data: pd.DataFrame,
    features: Sequence[str],
    grouping: Sequence[str],
    kind: str,
    per_row: int,
    fit: bool = False,
) -> matplotlib.figure.Figure:
    """Draw one seaborn catplot of all features, a tile each.

    Args:
        data: The table.
        features: The features, a tile each, each with its own y axis.
        grouping: The grouping columns; the first two are x and hue. With one
            grouping column the plots are blue.
        kind: The kind of seaborn catplot, e.g. `box`, `swarm` or `violin`.
        per_row: The tiles per row; 0 for about as many rows as columns.
        fit: Whether the y axes fit the values (True) or include 0 (False).
            Defaults to False.

    Returns:
        The figure, with pickable artists.
    """
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
        return axis_range(data[feature], fit)

    label_tiles(grid, features, ylim)
    add_picker(grid.figure)
    return grid.figure


def sampled_rows(
    data: pd.DataFrame, points: Optional[PointSampling]
) -> tuple[pd.DataFrame, Optional[str]]:
    """Return the rows to draw: all, or a random sample that is the same on every run.

    Args:
        data: The table.
        points: Which points are drawn; None for all.

    Returns:
        The rows, in their order in the table, and a note saying how many of them are
        shown; None for all rows. All rows are drawn unless the mode is `sample` and
        the number of samples is less than the number of rows.
    """
    total = len(data)
    if points is None or points.mode != "sample" or not 0 < points.samples < total:
        return data, None
    rng = np.random.default_rng(points.random_seed)
    rows = np.sort(rng.choice(total, size=points.samples, replace=False))
    return (
        data.iloc[rows],
        f"{points.samples:,} samples of {total:,} measurements shown",
    )


def add_note(figure: matplotlib.figure.Figure, note: Optional[str]) -> None:
    """Add a small note below the plots, e.g. that a sample of the points is shown.

    The note is added to the figure's x label (`supxlabel`), one line per note.
    Without constrained layout, the bottom margin grows to make room.

    Args:
        figure: The figure.
        note: The note; None or empty for no note.
    """
    if not note:
        return
    # the figure's x label at its default position: constrained layout (also when the
    # legend's placement switches to it later) makes room for it, not for free text or
    # a label placed explicitly
    current = figure._supxlabel.get_text() if figure._supxlabel is not None else ""
    figure.supxlabel(
        f"{current}\n{note}" if current else note, fontsize="small", color="0.3"
    )
    if not figure.get_constrained_layout():
        figure.subplots_adjust(bottom=figure.subplotpars.bottom + 0.03)


class _CategoricalPlot(_Plot):
    """Shared by the seaborn catplot tools; `kind` is the kind of catplot."""

    kind = ""

    def run(
        self, data: pd.DataFrame, *, config: CategoricalPlotConfig
    ) -> dict[str, Any]:
        """Draw a catplot of each selected feature.

        Args:
            data: The table.
            config: The features, the grouping columns (x, hue, facet column and
                row), `single_figure` and `plots_per_row`, and, if the config has
                them, `fit_axes` and `points` (all points or a sample).

        Returns:
            One figure per feature, named `<tool name> <feature>`, or with
            `single_figure` one figure named after the tool. A note below the plots
            says if a sample of the points is shown.
        """
        data = strings_for_categories(data)
        features = sorted(selected_features(data, config.features))
        data, note = sampled_rows(data, getattr(config, "points", None))
        fit = getattr(config, "fit_axes", False)
        if config.single_figure and features:
            figure = catplot_tiles(
                data, features, config.grouping, self.kind, config.plots_per_row, fit
            )
            add_note(figure, note)
            return {self.name: figure}
        results = {}
        for feature in features:
            self.check_cancelled()  # plots of many points take long
            figure = catplot_figure(data, feature, config.grouping, self.kind, fit)
            add_note(figure, note)
            results[self.plot_name(feature)] = figure
        return results


@register_tool
class BoxPlot(_CategoricalPlot, Tool[BoxPlotConfig]):
    """Box plots of the features, grouped by up to 4 category columns."""

    name = "Box Plot"
    description = "Box plots of the features, grouped by up to 4 category columns."
    icon = "boxplot.png"
    kind = "box"


@register_tool
class SwarmPlot(_CategoricalPlot, Tool[SwarmPlotConfig]):
    """Swarm plots of the features, grouped by up to 4 category columns."""

    name = "Swarm Plot"
    description = "Swarm plots of the features, grouped by up to 4 category columns."
    icon = "swarmplot.png"
    kind = "swarm"

    def finish(self, figure: matplotlib.figure.Figure) -> None:
        """Place the swarms' points once, for the final layout (`freeze_swarms`)."""
        freeze_swarms(figure)


_running = contextvars.ContextVar("running_plot_tool", default=None)
# False while a tool plots: its swarms are placed once, by freeze_swarms
_place_swarms = contextvars.ContextVar("place_swarms", default=True)


def _beeswarm(self: _SeabornBeeswarm, orig_xyr: np.ndarray) -> np.ndarray:
    """Place the points of a swarm; replaces seaborn's `Beeswarm.beeswarm`.

    The positions are the same as seaborn's. The points are placed on a plain array
    (seaborn passes a masked one, whose indexing makes it twice as slow), and the
    running plot tool can be cancelled every 50 points, as placing a few thousand
    points can take seconds. While `_place_swarms` is False, the original positions
    are returned.
    """
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


def freeze_swarms(figure: matplotlib.figure.Figure) -> None:
    """Place the points of seaborn's swarms once, for the figure's final layout.

    seaborn places them again at every draw (each repaint or resize of a plot
    window), which takes seconds for a few thousand points. If points did not fit in
    their swarm (seaborn then draws them at its edges), a note says so.

    Args:
        figure: The figure; nothing is done if it has no swarms.
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
            "plot fewer points, e.g. filter the rows",
        )


@register_tool
class ViolinPlot(_CategoricalPlot, Tool[ViolinPlotConfig]):
    """Violin plots of the features, grouped by up to 4 category columns."""

    name = "Violin Plot"
    description = "Violin plots of the features, grouped by up to 4 category columns."
    icon = "violinplot.png"
    kind = "violin"


def grouped_meanbarplot(
    data: Optional[pd.DataFrame],
    feature: Sequence[str],
    ax: Optional[matplotlib.axes.Axes] = None,
    title: Optional[str] = None,
    bartype: str = "single",
    categories: Optional[Sequence[str]] = [],
    dropna: bool = True,
    pivot_level: int = 1,
    orientation: str = "horizontal",
    error_bar: str = "None",
    error_type: str = "std",
    legend: bool = True,
) -> Optional[matplotlib.figure.Figure]:
    """Draw a bar plot of the means of features, grouped by category columns.

    Without grouping columns, the plot has one bar (or stack) of the means of all
    rows. With grouping columns, it has a bar per group; if the bars are not stacked
    and there are more grouping columns than `pivot_level`, the first `pivot_level`
    grouping columns set the bars' colours (and the legend) and the others the
    positions on the axis. A grouped plot whose means are all missing shows the text
    `No data`.

    Args:
        data: The table; None draws nothing.
        feature: The features (column names); several only for stacked bars.
        ax: The axes to draw in; None for a new figure, which is then sized for the
            number of bars. Defaults to None.
        title: The plot's title; None for the features and the grouping columns,
            empty for none. Defaults to None.
        bartype: `single`, `stacked`, or `100% stacked` (each stack scaled to 100%
            of the sum of the absolute means). Defaults to `single`.
        categories: The grouping columns; None or empty for no grouping.
        dropna: Whether rows with a missing value of any feature are left out, so
            that the means of all features come from the same rows. Defaults to
            True.
        pivot_level: The number of grouping columns that set the bars' colours.
            Defaults to 1.
        orientation: `horizontal` or `vertical` bars. Defaults to `horizontal`.
        error_bar: `+/-` (both directions), `+` (away from the axis only) or `None`.
            Defaults to `None`.
        error_type: `std` for the standard deviation; any other value for the
            standard error of the mean. Defaults to `std`.
        legend: Whether the plot has a legend, for several grouping columns or
            stacked bars. Defaults to True.

    Returns:
        The figure; None if `data` is None or lacks a feature column.
    """
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
        values = data[list(feature)]
        if dropna:
            values = values.dropna(how="any")
        mean = pd.DataFrame(columns=feature)
        mean.loc[0] = values.mean()
        if error_bar != "None":
            error = pd.DataFrame(columns=feature)
            if error_type == "std":
                error.loc[0] = values.std()
            else:
                error.loc[0] = values.sem()
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
            logger.debug("Single value per group. Keeping index of original data.")
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
    """Keeps the error bar caps of bars at most `fraction` of the bars' width.

    Caps are sized in points, bars in data coordinates. This artist has the lowest
    z-order, so it is drawn before the bars at every draw (e.g. saving, resizing a
    window); it sets the caps' size from the narrowest bar's width at that moment, at
    most `2 * capsize`.
    """

    def __init__(
        self,
        caplines: Iterable[Line2D],
        bars: Iterable[Rectangle],
        capsize: float,
        horizontal: bool,
        fraction: float = 0.8,
    ) -> None:
        """Create the limiter for the caps of a set of bars.

        Args:
            caplines: The lines that draw the caps.
            bars: The bars.
            capsize: The error bars' `capsize`, in points; matplotlib draws caps
                twice as wide.
            horizontal: Whether the bars are horizontal (their width is then their
                height on screen).
            fraction: The largest cap size, as a fraction of the narrowest bar's
                width. Defaults to 0.8.
        """
        super().__init__()
        self.caplines, self.bars = list(caplines), list(bars)
        self.cap_width = 2 * capsize  # matplotlib draws caps 2 * capsize wide
        self.horizontal, self.fraction = horizontal, fraction
        self.set_zorder(-1e9)

    def draw(self, renderer: RendererBase) -> None:
        """Set the caps' size from the bars' current width; draws nothing itself."""
        if not self.bars or not self.get_visible():
            return
        sizes = [b.get_window_extent(renderer) for b in self.bars]
        pixels = min(box.height if self.horizontal else box.width for box in sizes)
        points = pixels * 72 / self.axes.figure.dpi
        width = max(0.0, min(self.cap_width, self.fraction * points))
        for line in self.caplines:
            line.set_markersize(width)


def limit_error_caps(
    ax: matplotlib.axes.Axes,
    capsize: float,
    horizontal: bool = False,
    fraction: float = 0.8,
) -> None:
    """Limit the error bar caps of the bars in the axes to a fraction of a bar's width.

    See `_CapLimiter`. Bars without error bars or without caps are left as they are.

    Args:
        ax: The axes.
        capsize: The error bars' `capsize`, in points.
        horizontal: Whether the bars are horizontal. Defaults to False.
        fraction: The largest cap size, as a fraction of the narrowest bar's width.
            Defaults to 0.8.
    """
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
    """Bar plots of the features' means, grouped by the category columns."""

    name = "Bar Plot"
    description = "Mean bar plots of the features, grouped by the category columns."
    icon = "barplot.png"

    @classmethod
    def plot_name(cls, feature: str) -> str:
        """Return the name of a feature's plot: the feature."""
        return feature

    @classmethod
    def output_names(
        cls, config: BarPlotConfig, features: list[str]
    ) -> dict[str, type]:
        """Return the outputs; stacked bars are one plot named `<f1>|<f2>|...`."""
        if config.bar_type == "single":
            return super().output_names(config, features)
        return {"|".join(features): PlotType}

    def run(self, data: pd.DataFrame, *, config: BarPlotConfig) -> dict[str, Any]:
        """Draw bar plots of the means of the selected features.

        Args:
            data: The table.
            config: The features, the grouping columns, `dropna`, `bar_type`
                (`single`, `stacked` or `100% stacked`), `orientation`, `error_bar`,
                `error_type`, and `single_figure` and `plots_per_row`.

        Returns:
            With stacked bars one plot of all features, named `<f1>|<f2>|...`. Else
            one plot per feature, named after the feature, or with `single_figure`
            one figure of tiles, named `Bar Plot`. See `grouped_meanbarplot`.
        """
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

    def map_configs(self, config: BarPlotConfig) -> list[BarPlotConfig]:
        """Return one config per feature, so that the features run as separate tasks.

        Stacked bars, `single_figure`, or all features selected: the config is not
        split.
        """
        if config.bar_type != "single" or config.single_figure:
            return [config]
        return per_feature(config)


def ci_to_errorbar(
    ci: Union[int, str, None],
) -> Union[tuple[str, int], str, None]:
    """Return seaborn's `errorbar` argument for a Line Plot `errorbar` setting.

    seaborn 0.12 replaced `ci=<n>` with `errorbar=("ci", <n>)`, `ci="sd"` with
    `errorbar="sd"` and `ci=None` with `errorbar=None`.

    Args:
        ci: The confidence interval in percent, `sd`, or None for no error bars.

    Returns:
        `("ci", ci)` for a number; `sd` and None unchanged.
    """
    if ci is None or ci == "sd":
        return ci
    return ("ci", ci)


@register_tool
class LinePlot(_Plot, Tool[LinePlotConfig]):
    """Line plots of the features along the first grouping column."""

    name = "Line Plot"
    description = (
        "Line plots of the features along the first grouping column; further grouping"
        " columns set hue, style, columns and rows."
    )
    icon = "lineplot.png"

    @classmethod
    def plot_name(cls, feature: str) -> str:
        """Return the name of a feature's plot: `Line Plot: <feature>`."""
        return f"Line Plot: {feature}"

    def run(self, data: pd.DataFrame, *, config: LinePlotConfig) -> dict[str, Any]:
        """Draw a line plot of each selected feature.

        Category columns with more than one value are drawn as text (categories).

        Args:
            data: The table.
            config: The features, the grouping columns (x, hue, style, facet column
                and row), `errorbar`, `err_style`, `markers`, and `single_figure` and
                `plots_per_row`.

        Returns:
            One figure per feature, named `Line Plot: <feature>`, or with
            `single_figure` one figure of tiles, named `Line Plot`.
        """
        data = data.copy()
        for column in category_columns(data):
            if data[column].nunique() > 1:
                data[column] = as_strings(data[column])
        features = sorted(selected_features(data, config.features))
        if config.single_figure and features:
            return {self.name: self.line_tiles(data, features, config)}
        return {
            self.plot_name(feature): self.line_figure(data, feature, config)
            for feature in features
        }

    def line_tiles(
        self, data: pd.DataFrame, features: Sequence[str], config: LinePlotConfig
    ) -> matplotlib.figure.Figure:
        """Draw all features as tiles of one figure.

        Args:
            data: The table.
            features: The features, a tile each.
            config: Up to 3 grouping columns (x, hue and style), `errorbar`,
                `err_style`, `markers` and `plots_per_row`.

        Returns:
            The figure. Without grouping columns, each feature is drawn along the
            rows of the table.
        """
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

    def line_figure(
        self, data: pd.DataFrame, feature: str, config: LinePlotConfig
    ) -> matplotlib.figure.Figure:
        """Draw a line plot of one feature.

        Args:
            data: The table.
            feature: The feature.
            config: The grouping columns (x, hue, style, facet column and row; with
                more than 3, a grid of plots), `errorbar`, `err_style` and
                `markers`.

        Returns:
            The figure. Without grouping columns, the feature is drawn along the rows
            of the table.
        """
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


def _distinct_colors(n: int) -> list[tuple[float, float, float]]:
    """Return `n` colours that differ from each other.

    Up to 10: seaborn's default palette. More: evenly spaced hues (seaborn's `husl`
    palette), so that no colour repeats.
    """
    return sns.color_palette(n_colors=n) if n <= 10 else sns.color_palette("husl", n)


def _shades(color: tuple[float, float, float], n: int) -> list[tuple[float, float, float]]:
    """Return `n` shades of a colour, from lighter to darker."""
    if n == 1:
        return [tuple(color)]
    shades = []
    for i in range(n):
        f = -0.45 + 0.8 * i / (n - 1)  # < 0: towards white, > 0: towards black
        target = 0.0 if f > 0 else 1.0
        shades.append(tuple(c + (target - c) * abs(f) for c in color))
    return shades


def _level_values(data: pd.DataFrame, column: str) -> list[Any]:
    """Return a grouping column's values in the order of `groupby`."""
    if isinstance(data[column].dtype, pd.CategoricalDtype):
        return list(data[column].cat.categories)
    return sorted(data[column].dropna().unique())


def group_styles(data: pd.DataFrame, groups: Sequence[str]) -> list[dict[str, Any]]:
    """Return the line style of each group, the same in every plot.

    With two grouping columns, the colour shows the value of the first column and
    the line style the value of the second (up to 4 values); with more values of the
    second column, shades of the first column's colour, from lighter to darker. With
    one grouping column, or more than two, each group has its own colour. Colours
    never repeat (`_distinct_colors`).

    Args:
        data: The table.
        groups: The grouping columns.

    Returns:
        The matplotlib style arguments of each group, in the order of
        `data.groupby(groups, observed=False)`.
    """
    if len(groups) == 2:
        first, second = (_level_values(data, g) for g in groups)
        colors = _distinct_colors(len(first))
        if len(second) <= len(DEFAULT_LINESTYLES):
            return [
                {"color": c, "linestyle": ls}
                for c in colors
                for ls in DEFAULT_LINESTYLES[: len(second)]
            ]
        return [{"color": shade} for c in colors for shade in _shades(c, len(second))]
    n = data.groupby(list(groups), observed=False).ngroups
    return [{"color": c} for c in _distinct_colors(n)]


def grouped_kdeplot(
    data: pd.DataFrame,
    column: str,
    ax: matplotlib.axes.Axes,
    groups: Sequence[str] = (),
    show_legend: bool = True,
    **kwargs: Any,
) -> None:
    """Draw KDE curves of a column, one per group, labelled with the group.

    Rows without a value are left out, and so are groups without rows. A curve that
    seaborn cannot draw is logged as an error and left out. The y axis starts at 0.

    Args:
        data: The table.
        column: The column.
        ax: The axes to draw in.
        groups: The grouping columns; none for one curve of all rows. Defaults to
            none.
        show_legend: Whether the axes get a legend of the groups (if any curve is
            drawn). Defaults to True.
        **kwargs: Passed to `seaborn.kdeplot`, e.g. `clip`.
    """
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
                logger.error(err)
        # from the curves drawn (none for e.g. a constant column)
        if show_legend and ax.get_legend_handles_labels()[0]:
            ax.legend(**group_legend_options(groups))
    else:
        try:
            sns.kdeplot(data[column], **kwargs)
        except Exception as err:
            logger.error(err)
    ax.autoscale(enable=True, axis="y")
    ax.set_ylim(0, None)


def group_legend_options(groups: Sequence[str]) -> dict[str, Any]:
    """Return the `Axes.legend` arguments of a legend of groups, right of the plot."""
    return dict(
        loc="upper left",
        title=", ".join(groups),
        bbox_to_anchor=(1.0, 1.0),
        fontsize="small",
        ncol=len(groups) // 30 + 1,
    )


@register_tool
class KDE(_Plot, Tool[KDEConfig]):
    """Kernel density estimates of the features, one curve per group."""

    name = "KDE"
    description = "Kernel density estimates of the features, one curve per group."
    icon = "kde.png"

    @classmethod
    def output_names(cls, config: KDEConfig, features: list[str]) -> dict[str, type]:
        """Return the outputs: one plot per feature, or one figure named `KDE`."""
        if config.single_figure:
            return {"KDE": PlotType}
        return super().output_names(config, features)

    def run(self, data: pd.DataFrame, *, config: KDEConfig) -> dict[str, Any]:
        """Draw the KDE curves of each selected feature, one curve per group.

        The curves are clipped to the range of the feature's finite values, and the
        x axis shows that range (unless the feature is constant).

        Args:
            data: The table.
            config: The features, the grouping columns, and `single_figure` and
                `plots_per_row`.

        Returns:
            One figure per feature, named `KDE <feature>`, or with `single_figure`
            one figure of tiles, named `KDE`; none without features.
        """
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

    def map_configs(self, config: KDEConfig) -> list[KDEConfig]:
        """Return one config per feature, unless `single_figure` is set."""
        return [config] if config.single_figure else per_feature(config)


@register_tool
class FrequencyHistogram(_Plot, Tool[HistogramConfig]):
    """Histograms of the features in percent of the measurements."""

    name = "Frequency Histogram"
    description = (
        "Histograms of the features in percent of the measurements (per group, unless"
        " stacked), optionally with the binned values as a table."
    )
    icon = "histogram.png"

    @classmethod
    def plot_name(cls, feature: str) -> str:
        """Return the name of a feature's plot: `Frequency Histo Plot: <feature>`."""
        return f"Frequency Histo Plot: {feature}"

    @classmethod
    def output_names(
        cls, config: HistogramConfig, features: list[str]
    ) -> dict[str, type]:
        """Return the outputs: the plots, and with `table` a table per feature."""
        names = {"Frequency Histogram": PlotType} if config.single_figure else {}
        for feature in sorted(features):
            if not config.single_figure:
                names[cls.plot_name(feature)] = PlotType
            if config.table:
                names[f"Frequency Histo Table: {feature}"] = TableType
        return names

    def run(self, data: pd.DataFrame, *, config: HistogramConfig) -> dict[str, Any]:
        """Draw a histogram of each selected feature.

        Args:
            data: The table.
            config: The features with their bins and range (`min`, `max`; None for
                the feature's minimum or maximum), `auto_range` (the range of the
                values for all features), the grouping columns, `stacked`,
                `histtype`, `cumulative`, `density`, `table`, and `single_figure` and
                `plots_per_row`.

        Returns:
            One figure per feature, named `Frequency Histo Plot: <feature>`, or with
            `single_figure` one figure of tiles, named `Frequency Histogram`. With
            `table`, also a table per feature, named `Frequency Histo Table:
            <feature>`: the bin edges (`bin edge low`, `bin edge high`) and a column
            of bin values per group (see `histogram`).
        """
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

    def map_configs(self, config: HistogramConfig) -> list[HistogramConfig]:
        """Return one config per feature, unless `single_figure` is set."""
        return [config] if config.single_figure else per_feature(config)

    @classmethod
    def validate(cls, config: HistogramConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config; the number of features is checked by `Tool.validate`."""
        # too few features: min_features, checked by Tool.validate
        return super().validate(config, inputs)

    @staticmethod
    def histogram(
        data: pd.DataFrame,
        column: str,
        groups: Sequence[str],
        stacked: bool,
        normalize: float = 100,
        ax: Optional[matplotlib.axes.Axes] = None,
        **kwargs: Any,
    ) -> tuple[np.ndarray, np.ndarray, list[str], matplotlib.figure.Figure]:
        """Draw a histogram of a column in percent of the measurements.

        Each group's bars are in percent of the group's measurements, or, if stacked,
        of all measurements. With `density`, the bars are matplotlib's density (an
        area of 1) instead of percent. Groups without rows are left out.

        Args:
            data: The table.
            column: The column.
            groups: The grouping columns; none for one histogram of all rows.
            stacked: Whether the groups' bars are stacked.
            normalize: The total of each histogram's bars (without `density`).
                Defaults to 100 (percent).
            ax: The axes to draw in; None for a new figure. Defaults to None.
            **kwargs: Passed to `Axes.hist`, e.g. `bins`, `range`, `histtype`,
                `cumulative` and `density`.

        Returns:
            The bin values (a row per group; with stacked groups each group's own
            values, not the heights of the stack), the bin edges, a table column name per
            group (`<group> [rel %]` or `<group> [density]`; `all` without groups),
            and the figure.
        """
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
            for name, group in grouped:  # in the order of the categories
                if len(group[column]) == 0:
                    continue
                names.append(name)
                values.append(group[column].values)
                count = total if stacked else group[column].count()
                weights.append(
                    np.ones_like(group[column].values) / float(count) * normalize
                )
        labels = [clean_label(n) for n in names]
        if groups:  # one label per group drawn
            kwargs["label"] = labels
        in_group = "" if stacked else "in each group "
        # density: matplotlib rescales the bars to an area of 1, not percent (#181)
        density = kwargs.get("density")
        if density:
            ax.set_ylabel(f"density {in_group}".strip())
        else:
            ax.set_ylabel(f"relative counts {in_group}[%]")
        unit = "density" if density else "rel %"
        names = [f"{label} [{unit}]" for label in labels]  # not ('ctrl',) [rel %]
        ax.set_xlabel(column)
        title = column.replace("\n", " ")
        if groups:
            title = f"{title} grouped by {', '.join(groups)}"
        ax.set_title(title)
        counts, edges, _ = ax.hist(
            values, weights=weights, stacked=stacked, alpha=0.5, **kwargs
        )
        if stacked and groups and np.ndim(counts) == 2:
            # matplotlib returns the heights of the stack; each group's own values
            # are the differences between its level and the one below
            counts = np.diff(counts, axis=0, prepend=0)
        if groups and len(counts) > 1:
            # in the order of the groups (stacked and step histograms: reversed)
            handles = dict(zip(*reversed(ax.get_legend_handles_labels())))
            ax.legend(
                [handles[label] for label in labels if label in handles],
                [label for label in labels if label in handles],
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
    """Correlation heatmap of the features, with the correlation table."""

    name = "Heatmap"
    description = "Correlation heatmap of the features, with the correlation table."
    icon = "heatmap.png"

    @classmethod
    def output_names(
        cls, config: HeatmapConfig, features: list[str]
    ) -> dict[str, type]:
        """Return the outputs: `Heatmap` and `Heatmap Correlation`."""
        return {"Heatmap": PlotType, "Heatmap Correlation": TableType}

    def run(self, data: pd.DataFrame, *, config: HeatmapConfig) -> dict[str, Any]:
        """Draw the correlations between the selected features as a heatmap.

        Args:
            data: The table.
            config: The features, the correlation method (`pearson`, `spearman` or
                `kendall`) and whether the cells show their values (`annotate`).

        Returns:
            `Heatmap`: the figure; `Heatmap Correlation`: the correlation matrix,
            with the features' names in a category column `Feature`.
        """
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
        ax.set_title("Correlation")
        corr = corr.reset_index().rename(columns={"index": "Feature"})
        corr["Feature"] = corr["Feature"].astype("category")
        return {"Heatmap": ax.get_figure(), "Heatmap Correlation": corr}

    def map_configs(self, config: HeatmapConfig) -> list[HeatmapConfig]:
        """Return the config unsplit: all features are in one heatmap."""
        return [config]


def _sampled(func: Callable[..., Any], keep: np.ndarray) -> Callable[..., Any]:
    """Wrap a seaborn plot function to draw only the rows where `keep` is True.

    PairGrid passes each panel's x, y and hue columns of the whole table; `keep`
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
    """A grid of scatter plots of feature pairs, with distributions on the diagonal."""

    name = "Pair Plot"
    description = (
        "A grid of scatter plots of feature pairs, colored by the first grouping"
        " column, with histograms or KDEs on the diagonal."
    )
    icon = "pairplot.png"

    @classmethod
    def output_names(
        cls, config: PairPlotConfig, features: list[str]
    ) -> dict[str, type]:
        """Return the output: one figure named `Pair Plot: <grouping>`."""
        return {f"Pair Plot: {config.grouping}": PlotType}

    def run(self, data: pd.DataFrame, *, config: PairPlotConfig) -> dict[str, Any]:
        """Draw a seaborn pair grid of the features.

        If the grid is square (the same features as columns and rows), its diagonal
        shows histograms or KDEs and the other panels scatter plots; otherwise all
        panels are scatter plots. With a sample of the points, all scatter plots show
        the same rows, and a note below the plots says so.

        Args:
            data: The table.
            config: The features of the columns (`x_vars`, else the selected
                features) and rows (`y_vars`, or the columns with `symmetric`),
                `corner` (the lower half only, for a symmetric grid), the first
                grouping column (the points' colours), `diagonal` (`Histogram` or
                `KDE`), `hist_bins` and `points` (all points or a sample).

        Returns:
            One figure, named `Pair Plot: <grouping>`.

        Raises:
            ValueError: If no features are selected for the columns or the rows.
        """
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
        if grid.square_grid:
            if config.diagonal == "Histogram":
                grid.map_diag(sns.histplot, bins=config.hist_bins)
            else:
                grid.map_diag(sns.kdeplot)
            grid.map_upper(scatter)
            grid.map_lower(scatter)
        else:
            # no diagonal: map_upper and map_lower would leave the panels whose row
            # and column numbers are equal empty
            grid.map(scatter)
        grid.add_legend()
        if sampled:
            add_note(
                grid.figure,
                f"{points.samples:,} samples of {total:,} measurements shown",
            )
        return {f"Pair Plot: {config.grouping}": grid.figure}

    @staticmethod
    def grid_vars(
        data: pd.DataFrame, config: PairPlotConfig
    ) -> tuple[list[str], list[str]]:
        """Return the features of the grid's columns and rows.

        Without `x_vars` (older settings), the selected features are the columns;
        with `symmetric`, the rows are the columns, else `y_vars`.
        """
        x_vars = config.x_vars or selected_features(data, config.features)
        y_vars = x_vars if config.symmetric else config.y_vars
        return x_vars, y_vars

    def map_configs(self, config: PairPlotConfig) -> list[PairPlotConfig]:
        """Return the config unsplit: all features are in one grid."""
        return [config]

    @classmethod
    def validate(cls, config: PairPlotConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config: features for the columns and rows, and the panel count.

        No columns (`x_vars`, unless all features are selected) or no rows (`y_vars`,
        unless `symmetric`) are errors; many panels are a warning, too many an error
        (see `plot_count_issues`).
        """
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
    """A scatter plot for each pair of features, colored by group."""

    name = "Scatter Plot"
    description = "A scatter plot for each pair of features, colored by group."
    icon = "scatter.png"

    @staticmethod
    def pairs(
        config: ScatterPlotConfig, features: Sequence[str]
    ) -> list[tuple[str, str]]:
        """Return the (x, y) features of each plot: all pairs, sorted by name.

        For a single pair, `x_axis` sets the feature on the x axis.
        """
        pairs = sorted(itertools.combinations(features, 2))
        if len(pairs) == 1 and config.x_axis is not None:
            (pair,) = pairs
            if config.x_axis == pair[1]:
                return [pair[::-1]]
        return pairs

    @classmethod
    def output_names(
        cls, config: ScatterPlotConfig, features: list[str]
    ) -> dict[str, type]:
        """Return the outputs: a plot per pair, or one figure named after the tool."""
        if config.single_figure:
            return {cls.name: PlotType}
        return {f"Scatter Plot: {pair}": PlotType for pair in cls.pairs(config, features)}

    def run(self, data: pd.DataFrame, *, config: ScatterPlotConfig) -> dict[str, Any]:
        """Draw a scatter plot of each pair of the selected features.

        With a sample of the points, all plots show the same rows, and a note below
        the plots says so.

        Args:
            data: The table.
            config: The features, `x_axis` (for a single pair), the grouping
                columns (a colour per group), `fit_axes`, `points` (all points or a
                sample), and `single_figure` and `plots_per_row`.

        Returns:
            One figure per pair, or with `single_figure` one figure of tiles, named
            `Scatter Plot: (<x>, <y>)` and `Scatter Plot`.
        """
        features = selected_features(data, config.features)
        pairs = self.pairs(config, features)
        # the same sampled rows in every plot
        data, note = sampled_rows(data, config.points)
        if config.single_figure and pairs:
            figure, axes = tiles(len(pairs), config.plots_per_row, size=(6, 4.5))
            for ax, pair in zip(axes, pairs):
                self.check_cancelled()  # many points take long
                self.scatter_figure(
                    data, pair, config.grouping, ax=ax, fit=config.fit_axes
                )
            tidy_tiles(figure, axes)
            add_note(figure, note)
            add_picker(figure)
            return {self.name: figure}
        results = {}
        for pair in pairs:
            self.check_cancelled()
            figure = self.scatter_figure(
                data, pair, config.grouping, fit=config.fit_axes
            )
            add_note(figure, note)
            results[f"Scatter Plot: {pair}"] = figure
        return results

    @staticmethod
    def scatter_figure(
        data: pd.DataFrame,
        pair: tuple[str, str],
        groups: Sequence[str],
        ax: Optional[matplotlib.axes.Axes] = None,
        fit: bool = False,
    ) -> matplotlib.figure.Figure:
        """Draw a scatter plot of a pair of features.

        Rows without a value of either feature are left out.

        Args:
            data: The table.
            pair: The features on the x and y axis.
            groups: The grouping columns; a colour and a legend entry per group.
            ax: The axes to draw in; None for a figure of its own. Defaults to None.
            fit: Whether the axes fit the values (True) or include 0 (False).
                Defaults to False.

        Returns:
            The figure.
        """
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
        ax.set_xlim(*axis_range(data[x], fit))
        ax.set_xlabel(x)
        ax.set_ylim(*axis_range(data[y], fit))
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
    def validate(cls, config: ScatterPlotConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config; many feature pairs (plots) are a warning or an error.

        See `plot_count_issues`.
        """
        issues = super().validate(config, inputs)
        n = len(_feature_names(config, inputs))
        pairs = n * (n - 1) // 2
        return issues + plot_count_issues(
            "features", pairs, f"{n} features: {pairs:,} feature pairs (plots)"
        )

    def map_configs(self, config: ScatterPlotConfig) -> list[ScatterPlotConfig]:
        """Return one config per pair of features, so that they run as separate tasks.

        With `single_figure`, or with all features selected, the config is not split.
        """
        if config.features == "all" or config.single_figure:
            return [config]
        return [
            config.model_copy(update={"features": list(pair)})
            for pair in itertools.combinations(config.features, 2)
        ]


def flirr_columns(
    columns: Iterable[str],
    flirr: Optional[str] = None,
    fad_a1: Optional[str] = None,
    nadph_a2: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return the FLIRR, FAD a1 % and NAD(P)H a2 % columns.

    A column not given is the first of `columns` whose name fits: `FLIRR` in any
    case for FLIRR; for FAD a1 % (NAD(P)H a2 %), a name with `FAD` (`NAD`), `a1`
    (`a2`) and `%`, without `FLIRR` or `/`.

    Args:
        columns: The column names to search, e.g. a table's numeric columns. They
            are iterated once for each column searched for.
        flirr: The FLIRR column; None to search for it.
        fad_a1: The FAD a1 % column; None to search for it.
        nadph_a2: The NAD(P)H a2 % column; None to search for it.

    Returns:
        The three columns; None for a column not given and not found.
    """

    def first(fits):
        return next((c for c in columns if fits(c)), None)

    def percent(c, *parts):
        return "FLIRR" not in c.upper() and "/" not in c and "%" in c and all(
            p in c for p in parts
        )

    return (
        flirr or first(lambda c: "FLIRR" in c.upper()),
        fad_a1 or first(lambda c: percent(c, "FAD", "a1")),
        nadph_a2 or first(lambda c: percent(c, "NAD", "a2")),
    )


@register_tool
class FLIRRPlot(_Plot, Tool[FLIRRPlotConfig]):
    """One figure of FAD a1 %, NAD(P)H a2 % and FLIRR plots, colored by group."""

    name = "FLIRR Plot"
    description = (
        "FAD a1% vs NAD(P)H a2% scatter, their KDEs, FLIRR KDE, FLIRR along the first"
        " grouping column and FLIRR mean bars."
    )
    icon = "flirrplot.png"

    @classmethod
    def output_names(
        cls, config: FLIRRPlotConfig, features: list[str]
    ) -> dict[str, type]:
        """Return the output: one figure named `FLIRR Plot: <grouping>`."""
        return {f"FLIRR Plot: {config.grouping}": PlotType}

    @classmethod
    def used_config(cls, config: FLIRRPlotConfig, tables: Sequence[Any]) -> FLIRRPlotConfig:
        """Return the config with the FLIRR, FAD a1 % and NAD(P)H a2 % columns found.

        The three columns (`flirr_columns`) fill their fields and `features`, the
        columns the figure plots.
        """
        if not tables or not isinstance(tables[0], pd.DataFrame):
            return config
        found = flirr_columns(
            tables[0].select_dtypes(include=np.number).columns,
            config.flirr,
            config.fad_a1,
            config.nadph_a2,
        )
        flirr, fad, nadph = found
        return config.model_copy(
            update={
                "flirr": flirr,
                "fad_a1": fad,
                "nadph_a2": nadph,
                "features": [c for c in found if c is not None],
            }
        )

    def run(self, data: pd.DataFrame, *, config: FLIRRPlotConfig) -> dict[str, Any]:
        """Draw the FLIRR figure.

        The panels: a scatter plot of FAD a1 % against NAD(P)H a2 %; KDEs of FAD
        a1 %, NAD(P)H a2 % and FLIRR; FLIRR along the first grouping column (line
        style from the second); and bars of the FLIRR means per group, with the
        standard error of the mean. The first grouping column sets the colours of the
        scatter plot and the KDEs.

        Args:
            data: The table.
            config: The grouping columns, and the FLIRR, FAD a1 % and NAD(P)H a2 %
                columns (`flirr`, `fad_a1`, `nadph_a2`; each None to find it by
                name, see `flirr_columns`).

        Returns:
            One figure, named `FLIRR Plot: <grouping>`.

        Raises:
            ValueError: If no grouping column is selected, or a FLIRR, FAD a1 % or
                NAD(P)H a2 % column is neither given nor found among the numeric
                columns.
        """
        grouping = list(config.grouping)
        if not grouping:
            raise ValueError(f"{self.name}: select at least one grouping column")
        flirr, fad, nadph = flirr_columns(
            data.select_dtypes(include=np.number).columns,
            config.flirr,
            config.fad_a1,
            config.nadph_a2,
        )
        if None in (flirr, fad, nadph):
            raise ValueError(
                f"{self.name}: needs a FLIRR column, and FAD a1 % and NAD(P)H a2 % columns"
            )
        scatter = [fad, nadph]
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

    def map_configs(self, config: FLIRRPlotConfig) -> list[FLIRRPlotConfig]:
        """Return the config unsplit: the plot has all its columns in one figure."""
        return [config]

    @classmethod
    def validate(cls, config: FLIRRPlotConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config: each FLIRR, FAD a1 % and NAD(P)H a2 % column is found.

        A column not given and not found by name among the input's features is an
        error, if the input schema is complete.
        """
        issues = super().validate(config, inputs)  # grouping: min_grouping
        schema = inputs[0] if inputs else None
        if schema is not None and schema.complete:
            found = flirr_columns(
                schema.by_role("feature"), config.flirr, config.fad_a1, config.nadph_a2
            )
            for field, column in zip(("flirr", "fad_a1", "nadph_a2"), found):
                if column is None:
                    title = type(config).model_fields[field].title
                    issues.append(
                        Issue(field, f"No {title} column found by name: choose one")
                    )
        return issues
