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

    orientation: Literal["vertical", "horizontal"] = "vertical"
    bar_type: Literal["single", "stacked", "100% stacked"] = "single"
    dropna: bool = True
    error_bar: Literal["+/-", "+", "None"] = "+/-"
    error_type: Literal["std", "s.e.m."] = "std"
    legend: bool = True

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
    errorbar: Union[Annotated[int, Field(gt=0, lt=100)], Literal["sd"], None] = 95
    err_style: Literal["bars", "band"] = "bars"
    markers: bool = True


# --- distributions ---


class DistributionPlotConfig(PlotConfig):
    pass


class KDEConfig(DistributionPlotConfig):
    legacy_dropped = frozenset({"return_plot"})  # always true

    single_plot: bool = False
    col_wrap: int = Field(default=5, ge=0)  # plots per row; 0: automatic


class HistogramRange(BaseConfig):
    min: float
    max: float
    bins: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def _check_range(self):
        if self.min >= self.max:
            raise ValueError(f"min ({self.min}) >= max ({self.max})")
        return self


class HistogramConfig(DistributionPlotConfig):
    legacy_keys = {"table": "datatable", "per_feature": None}

    bins: int = Field(default=30, ge=1)
    density: bool = False
    cumulative: bool = False
    histtype: Literal["bar", "barstacked", "step", "stepfilled"] = "step"
    stacked: bool = False
    table: bool = False  # also return the binned data as a table
    # range and bins per feature; other features use their data range and ``bins``
    per_feature: dict[FeatureColumn, HistogramRange] = {}

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

    mode: Literal["all", "sample"] = "all"
    samples: int = Field(default=20000, ge=1)
    random_seed: int = 0


class PairPlotConfig(PlotConfig):
    legacy_keys = {"diagonal": "diag_kind", "points": None}

    # rows and columns of the grid; empty: all ``features``
    x_vars: list[FeatureColumn] = []
    y_vars: list[FeatureColumn] = []
    diagonal: Literal["KDE", "Histogram"] = "Histogram"
    corner: bool = False
    hist_bins: int = Field(default=20, ge=1)
    points: PointSampling = Field(default_factory=PointSampling)

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

    correlation: Literal["pearson", "spearman", "kendall"] = "pearson"
    annotate: bool = False  # show the coefficients


class FLIRRPlotConfig(PlotConfig):
    pass
