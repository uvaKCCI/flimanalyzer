"""Configs of the Plot tools."""

import logging
from typing import Annotated, ClassVar, Literal, Optional, Union

from pydantic import Field, ValidationError, field_validator, model_validator

from flim.core.config import BaseConfig, FeatureColumn, TaskConfig

LegendPosition = Literal["right", "top", "bottom", "left", "inside", "none"]
OUTSIDE_POSITIONS = ("right", "top", "bottom", "left", "none")  # (and none)


class PlotConfig(TaskConfig):
    """Base of the configs of all plot tools."""

    legacy_keys = {"legend_position": None}
    # the grouping column whose values the legend shows (its index; e.g. 1: the
    # second, the first being the x axis); None: the tool has no such legend
    legend_grouping: ClassVar[Optional[int]] = 0

    legend_position: LegendPosition = Field(
        default="right",
        title="Legend",
        description="Outside the plots (right, top, bottom, left), inside, or none.",
        json_schema_extra={"order": 401},  # after the grouping it shows
    )

    @classmethod
    def has_legend(cls, values) -> bool:
        if cls.legend_grouping is None:
            return False
        return len(values.get("grouping") or []) > cls.legend_grouping

    @classmethod
    def allowed_values(cls, values):
        allowed = super().allowed_values(values)
        if not cls.has_legend(values):  # nothing to place
            allowed["legend_position"] = (values.get("legend_position", "right"),)
        return allowed

    @model_validator(mode="after")
    def _allowed(self):
        self._apply_allowed_values()
        return self


# --- categorical plots: one plot per feature, grouped by the category columns ---


class PointSampling(BaseConfig):
    """Which points are drawn: all, or a random sample that is the same on every run."""

    mode: Literal["all", "sample"] = Field(
        default="all",
        title="Show",
        description="All points, or a random sample (the same on every run).",
    )
    samples: int = Field(default=20000, ge=1, title="Samples")
    random_seed: int = Field(default=0, title="Random seed")

    @classmethod
    def allowed_values(cls, values):
        # the sample's size and seed: only for a sample
        if values.get("mode", "all") == "all":
            return {
                "samples": (values.get("samples"),),
                "random_seed": (values.get("random_seed"),),
            }
        return {}


class TiledPlotConfig(PlotConfig):
    """Base of the configs of plot tools that draw one figure per feature (or feature
    pair), with the option to draw them as tiles of a single figure instead.

    Plot tools that always draw one figure (e.g. Heatmap) base their configs on
    PlotConfig. Where a tool cannot tile in some cases (e.g. with more grouping
    columns than ``max_tiled_grouping``, as those become facets), ``allowed_values``
    turns the option off and dialogs hide it.
    """

    legacy_keys = {
        **PlotConfig.legacy_keys,
        "single_figure": None,
        "plots_per_row": None,
    }
    # with more grouping columns, the tool's plots are facets already: no single figure
    max_tiled_grouping: ClassVar[Optional[int]] = None

    # right above the features (410): what is plotted, and how
    single_figure: bool = Field(
        default=False,
        title="Single figure",
        description="All plots as tiles of one figure; otherwise one figure each.",
        json_schema_extra={"order": 408},
    )
    plots_per_row: int = Field(
        default=5,
        ge=0,
        title="Plots per row",
        description="Plots per row of the single figure; 0: automatic.",
        json_schema_extra={"order": 408.5},
    )

    @classmethod
    def allowed_values(cls, values):
        allowed = super().allowed_values(values)
        per_row = (values.get("plots_per_row", 5),)
        limit = cls.max_tiled_grouping
        if limit is not None and len(values.get("grouping") or []) > limit:
            return {**allowed, "single_figure": (False,), "plots_per_row": per_row}
        if not values.get("single_figure"):
            return {**allowed, "plots_per_row": per_row}  # only for a single figure
        if "legend_position" not in allowed:  # one legend for all tiles: outside
            allowed["legend_position"] = OUTSIDE_POSITIONS
        return allowed


class CategoricalPlotConfig(TiledPlotConfig):
    # x and hue; further grouping columns become facet columns and rows
    max_tiled_grouping = 2
    legend_grouping = 1  # the hue


class BarPlotConfig(CategoricalPlotConfig):
    legacy_dropped = frozenset({"display", "ordering"})  # unused

    max_tiled_grouping = None  # bars are grouped in one plot, not in facets

    @classmethod
    def allowed_values(cls, values):
        allowed = super().allowed_values(values)
        # stacked bars: all features are in one plot already
        if values.get("bar_type", "single") != "single":
            allowed.update(
                single_figure=(False,), plots_per_row=(values.get("plots_per_row", 5),)
            )
        return allowed

    orientation: Literal["vertical", "horizontal"] = Field(
        default="vertical", title="Orientation"
    )
    bar_type: Literal["single", "stacked", "100% stacked"] = Field(
        default="single",
        title="Bars",
        description="single: one plot per feature; stacked: the features in one plot.",
    )
    dropna: bool = Field(
        default=True,
        title="Drop missing",
        description="Leave out rows without a value.",
    )
    error_bar: Literal["+/-", "+", "None"] = Field(default="+/-", title="Error bars")
    error_type: Literal["std", "s.e.m."] = Field(default="std", title="Error")

    @classmethod
    def _from_legacy(cls, params):
        if params.get("error_type") == "s.e.m":
            params["error_type"] = "s.e.m."
        # the plugin's legend on/off: the legend position "none" for off
        if "legend" in params and not params.pop("legend"):
            return {"legend_position": "none"}
        params.pop("legend", None)
        return {}

    def _to_legacy(self):
        return {"legend": self.legend_position != "none"}

    @classmethod
    def has_legend(cls, values):
        # stacked bars: a legend of the features
        if values.get("bar_type", "single") != "single":
            return True
        return super().has_legend(values)


class BoxPlotConfig(CategoricalPlotConfig):
    pass


class ViolinPlotConfig(CategoricalPlotConfig):
    pass


class SwarmPlotConfig(CategoricalPlotConfig):
    legacy_keys = {**CategoricalPlotConfig.legacy_keys, "points": None}

    # a swarm places each point: many points take long
    points: PointSampling = Field(
        default_factory=lambda: PointSampling(samples=2000), title="Points"
    )


class LinePlotConfig(CategoricalPlotConfig):
    legacy_keys = {**CategoricalPlotConfig.legacy_keys, "errorbar": "ci"}
    max_tiled_grouping = 3  # x, hue and style
    legacy_dropped = frozenset({"display", "ordering", "x", "hue", "style", "col"})

    # confidence interval in percent, standard deviation, or None for no error bars
    errorbar: Union[Annotated[int, Field(gt=0, lt=100)], Literal["sd"], None] = Field(
        default=95,
        title="Error",
        description="Confidence interval in percent, sd, or empty for none.",
    )
    err_style: Literal["bars", "band"] = Field(default="bars", title="Error style")
    markers: bool = Field(default=True, title="Markers")


# --- distributions ---


class DistributionPlotConfig(TiledPlotConfig):
    """Plots of each feature's distribution."""


class KDEConfig(DistributionPlotConfig):
    legacy_keys = {
        **DistributionPlotConfig.legacy_keys,
        "single_figure": "single_plot",
        "plots_per_row": "col_wrap",
    }
    legacy_dropped = frozenset({"return_plot"})  # always true


DEFAULT_BINS = 30


class HistogramRange(BaseConfig):
    """Range and bins of one feature's histogram; empty min or max: the data's."""

    min: Optional[float] = Field(default=None, title="Min")
    max: Optional[float] = Field(default=None, title="Max")
    bins: int = Field(default=DEFAULT_BINS, ge=1, title="Bins")

    @model_validator(mode="after")
    def _check_range(self):
        if self.min is not None and self.max is not None and self.min >= self.max:
            raise ValueError(f"min ({self.min}) >= max ({self.max})")
        return self


class HistogramConfig(DistributionPlotConfig):
    legacy_keys = {
        **DistributionPlotConfig.legacy_keys,
        "table": "datatable",
        "features": None,
        "sync_bins": None,
        "auto_range": None,
    }
    # settings of the features that are the same for all if a field of the config is
    # set: settings field -> config field (dialogs keep them in step)
    synced_settings: ClassVar[dict[str, str]] = {"bins": "sync_bins"}
    # settings of the features that are not used if a field of the config is set:
    # settings field -> config field (dialogs grey them out, the values are kept)
    disabled_settings: ClassVar[dict[str, str]] = {
        "min": "auto_range",
        "max": "auto_range",
    }

    features: dict[FeatureColumn, HistogramRange] = Field(
        default={},
        title="Features",
        description="Check the features to plot; empty min or max: the data's range.",
    )
    # right above the features table (features: 410)
    auto_range: bool = Field(
        default=False,
        title="Auto min/max range",
        description=(
            "Each feature's min and max in the data; the min and max in the table are"
            " kept, but not used."
        ),
        json_schema_extra={"order": 409},
    )
    sync_bins: bool = Field(
        default=False,
        title="Same bins for all",
        description="All features get the same number of bins.",
        json_schema_extra={"order": 409.5},
    )
    density: bool = Field(default=False, title="Density")
    cumulative: bool = Field(default=False, title="Cumulative")
    histtype: Literal["bar", "barstacked", "step", "stepfilled"] = Field(
        default="step", title="Style"
    )
    stacked: bool = Field(
        default=False,
        title="Stacked",
        description="Groups stacked, in percent of all rows (else of each group's).",
    )
    table: bool = Field(
        default=False,
        title="Binned data table",
        description="Also return the binned values as a table.",
    )

    @model_validator(mode="before")
    @classmethod
    def _older_global_bins(cls, data):
        """Configs with a global "bins" (before 2.0 was released): the bins of the
        features without their own."""
        if isinstance(data, dict) and "bins" in data:
            data = dict(data)
            bins = data.pop("bins")
            features = data.get("features")
            if isinstance(features, dict):
                data["features"] = {
                    f: ({"bins": bins, **s} if isinstance(s, dict) else s)
                    for f, s in features.items()
                }
            elif isinstance(features, (list, tuple)):
                data["features"] = {f: {"bins": bins} for f in features}
        return data

    @field_validator("features", mode="before")
    @classmethod
    def _features_from_list(cls, features):
        """A list of features: each with the default range and bins."""
        if isinstance(features, (list, tuple)):
            return {f: {} for f in features}
        return features

    @model_validator(mode="after")
    def _same_bins(self):
        """With a global bin, all features get the first feature's bins."""
        if self.sync_bins and self.features:
            bins = next(iter(self.features.values())).bins
            # through __dict__: assignments would run the validators again
            self.__dict__["features"] = {
                f: r if r.bins == bins else r.model_copy(update={"bins": bins})
                for f, r in self.features.items()
            }
        return self

    @classmethod
    def _from_legacy(cls, params):
        # the plugin: a list of features, and {"min", "max", "bins"} per feature in
        # "featuresettings". Its defaults there are lists [min, max, bins, groups]
        # that it never read; they are skipped to keep the plots unchanged.
        features = params.pop("features", [])
        if not isinstance(features, list):  # "all_features": not a fixed set
            logging.info("Frequency Histogram: 'all features' is not kept")
            features = []
        settings = {}
        for feature, spec in (params.pop("featuresettings", {}) or {}).items():
            if not isinstance(spec, dict):
                continue
            try:
                settings[feature] = HistogramRange(**spec)
            except (TypeError, ValidationError) as err:
                logging.debug(f"Histogram settings of {feature} skipped: {err}")
        params.pop("bins", None)  # not used by the plugin
        return {"features": {f: settings.get(f, HistogramRange()) for f in features}}

    def _to_legacy(self):
        # the plugin uses a feature's settings only if all three are set; its "bins"
        # was not used
        return {
            "features": list(self.features),
            "featuresettings": {
                feature: {"min": r.min, "max": r.max, "bins": r.bins}
                for feature, r in self.features.items()
                if r.min is not None and r.max is not None and not self.auto_range
            },
            "bins": DEFAULT_BINS,
        }


# --- other plots ---


class ScatterPlotConfig(TiledPlotConfig):
    """A scatter plot for each pair of ``features``."""

    legacy_keys = {
        **TiledPlotConfig.legacy_keys,
        "points": None,
        "x_axis": None,
    }

    points: PointSampling = Field(default_factory=PointSampling, title="Points")
    x_axis: Optional[FeatureColumn] = Field(
        default=None,
        title="X axis",
        description="With two features: the one on the x axis (else the first of"
        " each pair).",
        json_schema_extra={"order": 411},  # right after the features
    )

    @classmethod
    def allowed_values(cls, values):
        allowed = super().allowed_values(values)
        features = values.get("features")
        if isinstance(features, list) and len(set(features)) == 2:
            allowed["x_axis"] = tuple(dict.fromkeys(features))  # first: the default
        else:  # one plot per pair: the first of the pair on the x axis
            allowed["x_axis"] = (None,)
        return allowed


class PairPlotConfig(PlotConfig):
    """A grid of scatter plots: one per (row feature, column feature).

    ``features`` is not edited: it is set to the grid's features (columns, then rows).
    Configs that only set ``features`` (older settings) use them as the columns.
    """

    legacy_keys = {
        **PlotConfig.legacy_keys,
        "diagonal": "diag_kind",
        "points": None,
        "symmetric": None,
    }
    hidden_fields = frozenset({"features"})

    symmetric: bool = Field(
        default=True,
        title="Same rows as columns",
        description="The grid's rows are its columns; otherwise choose them separately.",
    )
    x_vars: list[FeatureColumn] = Field(
        default=[], title="Grid columns", description="The features of the columns."
    )
    y_vars: list[FeatureColumn] = Field(
        default=[],
        title="Grid rows",
        description="The features of the rows.",
    )
    diagonal: Literal["KDE", "Histogram"] = Field(default="Histogram", title="Diagonal")
    corner: bool = Field(
        default=False,
        title="Lower half only",
        description="Omit the upper triangle of the (symmetric) grid.",
    )
    hist_bins: int = Field(default=20, ge=1, title="Histogram bins")
    points: PointSampling = Field(default_factory=PointSampling, title="Scatter points")

    @classmethod
    def allowed_values(cls, values):
        allowed = super().allowed_values(values)
        if values.get("symmetric", True):  # the rows are the columns
            return {**allowed, "y_vars": (list(values.get("x_vars") or []),)}
        return {**allowed, "corner": (False,)}  # a lower half needs a symmetric grid

    @model_validator(mode="after")
    def _grid_features(self):
        # set through __dict__: assignments would run the validators again
        values = self.__dict__
        if not self.x_vars and isinstance(self.features, list):
            values["x_vars"] = list(self.features)
        self._apply_allowed_values()
        if self.x_vars or self.y_vars:
            values["features"] = list(dict.fromkeys(self.x_vars + self.y_vars))
        return self

    @classmethod
    def _from_legacy(cls, params):
        points = {}
        for key, field in (
            ("plotting", "mode"),
            ("samples", "samples"),
            ("random_seed", "random_seed"),
        ):
            if key in params:
                points[field] = params.pop(key)
        values = {"points": points} if points else {}
        # the plugin's dialog always set the rows to the columns
        x_vars, y_vars = params.get("x_vars") or [], params.get("y_vars") or []
        values["symmetric"] = not y_vars or x_vars == y_vars
        return values

    def _to_legacy(self):
        return {
            "plotting": self.points.mode,
            "samples": self.points.samples,
            "random_seed": self.points.random_seed,
        }


class HeatmapConfig(PlotConfig):
    legacy_keys = {
        **PlotConfig.legacy_keys,
        "correlation": "corr_type",
        "annotate": "numbers",
    }
    legend_grouping = None  # a colour bar, no legend

    correlation: Literal["pearson", "spearman", "kendall"] = Field(
        default="pearson", title="Correlation"
    )
    annotate: bool = Field(
        default=False, title="Show values", description="Write the coefficients."
    )


class FLIRRPlotConfig(PlotConfig):
    legend_grouping = None  # each panel has its own
    # the FLIRR, FAD a1 % and NAD(P)H a2 % columns are found by name
    hidden_fields = frozenset({"features"})
