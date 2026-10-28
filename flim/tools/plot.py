"""Plot tools. They draw with pyplot and seaborn, holding pyplot_lock (draws_figures)."""

import itertools
import logging
import math
import warnings

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import MatplotlibDeprecationWarning

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
    """A group name, e.g. ``('WT', '1')``, as a label without quotes and parentheses."""
    return str(label).replace("'", "").replace("(", "").replace(")", "")


def per_feature(config) -> list:
    """One config per feature (all features in one config if they are "all")."""
    if config.features == "all":
        return [config]
    return [config.model_copy(update={"features": [f]}) for f in config.features]


class _Plot:
    """Shared by the plot tools: their outputs follow from config and input columns."""

    category = "Plot"
    draws_figures = True

    @classmethod
    def output_names(cls, config, features: list[str]) -> dict[str, type]:
        """Output name → type for the selected features (default: one plot each)."""
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
        return per_feature(config)


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


class _CategoricalPlot(_Plot):
    kind = ""

    def run(self, data, *, config):
        data = strings_for_categories(data)
        return {
            self.plot_name(feature): catplot_figure(
                data, feature, config.grouping, self.kind
            )
            for feature in sorted(selected_features(data, config.features))
        }


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
    if ax is None:
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
        chartbox = ax.get_position()
        if bartype == "100% stacked":
            ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.set_position(
            [
                chartbox.x0,
                chartbox.y0,
                chartbox.width * (1 - 0.2 * no_legendcols),
                chartbox.height,
            ]
        )
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
            title = f"{title} grouped by {categories}"
    if len(title) > 0:
        ax.set_title(title)
    return fig


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
        groups = (
            [features]
            if config.bar_type != "single"
            else [[f] for f in sorted(features)]
        )
        results = {}
        for group in groups:
            figure = grouped_meanbarplot(
                data,
                group,
                categories=config.grouping,
                dropna=config.dropna,
                bartype=config.bar_type,
                orientation=config.orientation,
                error_bar=config.error_bar,
                error_type=config.error_type,
                legend=config.legend,
            )
            add_picker(figure)
            results["|".join(group)] = figure
        return results

    def map_configs(self, config):
        return per_feature(config) if config.bar_type == "single" else [config]


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
        return {
            self.plot_name(feature): self.line_figure(data, feature, config)
            for feature in sorted(selected_features(data, config.features))
        }

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


def grouped_kdeplot(data, column, ax, groups=(), show_legend=True, **kwargs):
    """KDE curves of ``column``, one per group."""
    kwargs = {**kwargs, "ax": ax, "warn_singular": False}
    data = data[list(groups) + [column]].dropna(how="any", subset=[column])
    if groups:
        styles = []
        if len(groups) == 2:
            values = [data[g].unique() for g in groups]
            palette = sns.color_palette()
            if len(values[0]) <= len(palette) and len(values[1]) <= len(
                DEFAULT_LINESTYLES
            ):
                styles = [
                    {"color": c, "linestyle": ls}
                    for c in palette[: len(values[0])]
                    for ls in DEFAULT_LINESTYLES[: len(values[1])]
                ]
        labels = []
        for index, (name, group) in enumerate(
            data.groupby(list(groups), observed=False)
        ):
            if len(group[column]) == 0:
                continue
            if len(styles) > index:
                kwargs.update(styles[index])
            try:
                sns.kdeplot(group[column], **kwargs)
            except Exception as err:
                logging.error(err)
            labels.append(clean_label(name))
        if show_legend:
            ax.legend(
                labels=labels,
                loc="upper left",
                title=", ".join(groups),
                bbox_to_anchor=(1.0, 1.0),
                fontsize="small",
                ncol=len(groups) // 30 + 1,
            )
    else:
        try:
            sns.kdeplot(data[column], **kwargs)
        except Exception as err:
            logging.error(err)
    ax.autoscale(enable=True, axis="y")
    ax.set_ylim(0, None)


@register_tool
class KDE(_Plot, Tool[KDEConfig]):
    name = "KDE"
    description = "Kernel density estimates of the features, one curve per group."
    icon = "kde.png"

    @classmethod
    def output_names(cls, config, features):
        if config.single_plot:
            return {"KDE": PlotType}
        return super().output_names(config, features)

    def run(self, data, *, config):
        features = sorted(selected_features(data, config.features))
        if not features:
            return {}
        single = config.single_plot
        if single:
            n = len(features)
            cols = config.col_wrap or math.ceil(math.sqrt(n))
            cols = min(cols, n)
            rows = math.ceil(n / cols)
            figure, axes = plt.subplots(rows, cols, squeeze=False)
            axes = axes.flatten()
            for ax in axes[n:]:
                figure.delaxes(ax)
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
                # one legend, next to the last plot of the first row
                show_legend=not single or i == min(cols, len(features)) - 1,
            )
            if np.isfinite([low, high]).all():
                ax.set_xlim(low, high)
            if not single:
                figure.tight_layout()
                add_picker(figure)
                results[self.plot_name(feature)] = figure
        if single:
            figure.tight_layout()
            add_picker(figure)
            results["KDE"] = figure
        return results

    def map_configs(self, config):
        return [config] if config.single_plot else per_feature(config)


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
        names = {}
        for feature in sorted(features):
            names[cls.plot_name(feature)] = PlotType
            if config.table:
                names[f"Frequency Histo Table: {feature}"] = TableType
        return names

    def run(self, data, *, config):
        results = {}
        for feature in sorted(selected_features(data, config.features)):
            settings = config.per_feature.get(feature)
            if settings is not None:
                value_range, bins = (settings.min, settings.max), settings.bins
            else:
                value_range = (data[feature].min(), data[feature].max())
                bins = config.bins
            values, edges, names, figure = self.histogram(
                data,
                feature,
                groups=config.grouping,
                stacked=config.stacked,
                range=value_range,
                bins=bins,
                histtype=config.histtype,
                cumulative=config.cumulative,
                density=config.density,
            )
            results[self.plot_name(feature)] = figure
            if config.table:
                table = pd.DataFrame(
                    {"bin edge low": edges[:-1], "bin edge high": edges[1:]}
                )
                for name, column in zip(names, np.atleast_2d(values)):
                    table[name] = column
                results[f"Frequency Histo Table: {feature}"] = table
        return results

    @staticmethod
    def histogram(data, column, groups, stacked, normalize=100, **kwargs):
        """Histogram in percent of all (stacked) or of each group's measurements."""
        figure, ax = plt.subplots(constrained_layout=True)
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
            title = f"{title} grouped by {list(groups)}"
        ax.set_title(title)
        figure.set_size_inches(8, 8)
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
        ax.set_title(f"Data grouped by {grouping}" if grouping else "Data ungrouped")
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
        features = selected_features(data, config.features)
        x_vars = config.x_vars or features
        y_vars = config.y_vars or features
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
            corner=config.corner,
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

    def map_configs(self, config):
        return [config]


@register_tool
class ScatterPlot(_Plot, Tool[ScatterPlotConfig]):
    name = "Scatter Plot"
    description = "A scatter plot for each pair of features, colored by group."
    icon = "scatter.png"

    @classmethod
    def output_names(cls, config, features):
        return {
            f"Scatter Plot: {pair}": PlotType
            for pair in sorted(itertools.combinations(features, 2))
        }

    def run(self, data, *, config):
        features = selected_features(data, config.features)
        return {
            f"Scatter Plot: {pair}": self.scatter_figure(data, pair, config.grouping)
            for pair in sorted(itertools.combinations(features, 2))
        }

    @staticmethod
    def scatter_figure(data, pair, groups):
        x, y = pair
        figure, ax = plt.subplots(constrained_layout=True)
        data = data[list(groups) + list(pair)].dropna(how="any", subset=list(pair))
        figure.set_figheight(6)
        figure.set_figwidth(12)
        options = {"alpha": 0.5, "marker": "o", "s": 10}
        if groups:
            for name, group in data.groupby(list(groups), observed=False):
                if len(group[x]) > 0 and len(group[y]) > 0:
                    ax.scatter(group[x], group[y], label=name, **options)
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
            ax.set_title(f"Data grouped by {list(groups)}")
        add_picker(figure)
        return figure

    def map_configs(self, config):
        if config.features == "all":
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
        figure = plt.figure()
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
        figure.tight_layout()
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
