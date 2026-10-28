"""Configs of the Plot tools."""

import logging
from typing import Annotated, Literal, Union

from pydantic import Field, ValidationError, model_validator

from flim.core.config import BaseConfig, FeatureColumn, TaskConfig


class PlotConfig(TaskConfig):
    pass


# --- categorical plots: one plot per feature, grouped by the category columns ---


class CategoricalPlotConfig(PlotConfig):
    pass


class BarPlotConfig(CategoricalPlotConfig):
    legacy_dropped = frozenset({"display", "ordering"})  # unused

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
    legend: bool = Field(default=True, title="Legend")

    @classmethod
    def _from_legacy(cls, params):
        if params.get("error_type") == "s.e.m":
            params["error_type"] = "s.e.m."
        return {}


class BoxPlotConfig(CategoricalPlotConfig):
    pass


class ViolinPlotConfig(CategoricalPlotConfig):
    pass


class SwarmPlotConfig(CategoricalPlotConfig):
    pass


class LinePlotConfig(CategoricalPlotConfig):
    legacy_keys = {"errorbar": "ci"}
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


class DistributionPlotConfig(PlotConfig):
    pass


class KDEConfig(DistributionPlotConfig):
    legacy_dropped = frozenset({"return_plot"})  # always true

    single_plot: bool = Field(
        default=False,
        title="One figure",
        description="All features in one figure; otherwise one figure per feature.",
    )
    col_wrap: int = Field(
        default=5,
        ge=0,
        title="Plots per row",
        description="One figure: plots per row; 0: automatic.",
    )


class HistogramRange(BaseConfig):
    min: float = Field(title="Min")
    max: float = Field(title="Max")
    bins: int = Field(default=30, ge=1, title="Bins")

    @model_validator(mode="after")
    def _check_range(self):
        if self.min >= self.max:
            raise ValueError(f"min ({self.min}) >= max ({self.max})")
        return self


class HistogramConfig(DistributionPlotConfig):
    legacy_keys = {"table": "datatable", "per_feature": None}

    bins: int = Field(default=30, ge=1, title="Bins")
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
    per_feature: dict[FeatureColumn, HistogramRange] = Field(
        default={},
        title="Ranges per feature",
        description="Range and bins per feature; others use their data range.",
    )

    @classmethod
    def _from_legacy(cls, params):
        # The plugin reads entries {"min", "max", "bins"}. Its defaults are lists
        # [min, max, bins, groups] that it never read, so lists are skipped to keep
        # the plots unchanged.
        per_feature = {}
        for feature, spec in (params.pop("featuresettings", {}) or {}).items():
            if not isinstance(spec, dict):
                continue
            try:
                per_feature[feature] = HistogramRange(**spec)
            except (TypeError, ValidationError) as err:
                logging.debug(f"Histogram settings of {feature} skipped: {err}")
        return {"per_feature": per_feature}

    def _to_legacy(self):
        return {
            "featuresettings": {
                feature: r.model_dump(include={"min", "max", "bins"})
                for feature, r in self.per_feature.items()
            }
        }


# --- other plots ---


class ScatterPlotConfig(PlotConfig):
    """A scatter plot for each pair of ``features``."""


class PointSampling(BaseConfig):
    """Which points scatter panels draw; the same sample on every run."""

    mode: Literal["all", "sample"] = Field(
        default="all",
        title="Points",
        description="all, or a random sample (the same on every run).",
    )
    samples: int = Field(default=20000, ge=1, title="Samples")
    random_seed: int = Field(default=0, title="Random seed")


class PairPlotConfig(PlotConfig):
    legacy_keys = {"diagonal": "diag_kind", "points": None}

    # rows and columns of the grid; empty: all ``features``
    x_vars: list[FeatureColumn] = Field(
        default=[], title="Columns", description="Features of the columns; none: all."
    )
    y_vars: list[FeatureColumn] = Field(
        default=[], title="Rows", description="Features of the rows; none: all."
    )
    diagonal: Literal["KDE", "Histogram"] = Field(default="Histogram", title="Diagonal")
    corner: bool = Field(
        default=False, title="Lower half only", description="Omit the upper triangle."
    )
    hist_bins: int = Field(default=20, ge=1, title="Histogram bins")
    points: PointSampling = Field(default_factory=PointSampling, title="Scatter points")

    @model_validator(mode="after")
    def _check_vars(self):
        if isinstance(self.features, list) and self.features:
            missing = [v for v in self.x_vars + self.y_vars if v not in self.features]
            if missing:
                raise ValueError(f"x_vars/y_vars not in features: {missing}")
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
        return {"points": points} if points else {}

    def _to_legacy(self):
        return {
            "plotting": self.points.mode,
            "samples": self.points.samples,
            "random_seed": self.points.random_seed,
        }


class HeatmapConfig(PlotConfig):
    legacy_keys = {"correlation": "corr_type", "annotate": "numbers"}

    correlation: Literal["pearson", "spearman", "kendall"] = Field(
        default="pearson", title="Correlation"
    )
    annotate: bool = Field(
        default=False, title="Show values", description="Write the coefficients."
    )


class FLIRRPlotConfig(PlotConfig):
    # the FLIRR, FAD a1 % and NAD(P)H a2 % columns are found by name
    hidden_fields = frozenset({"features"})
