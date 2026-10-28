"""Configs of the Analysis tools: statistics, machine learning and autoencoders."""

from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import Field, model_validator

from flim.core.config import (
    BaseConfig,
    CategoryColumn,
    Device,
    FeatureColumn,
    Probability,
    Resources,
    TaskConfig,
)

Threads = Annotated[int, Field(ge=-1)]  # -1: all cores allocated to the task


class AnalysisConfig(TaskConfig):
    pass


# --- statistics ---


class StatisticsConfig(AnalysisConfig):
    pass


Aggregate = Literal[
    "count",
    "min",
    "max",
    "mean",
    "std",
    "sem",
    "median",
    "percentile(25)",
    "percentile(75)",
    "sum",
]
AGGREGATES: tuple[str, ...] = Aggregate.__args__


class SummaryConfig(StatisticsConfig):
    legacy_keys = {
        "aggs": "aggs",
        "single_table": "singledf",
        "flatten_index": "flattenindex",
    }

    aggs: list[Aggregate] = Field(default_factory=lambda: list(AGGREGATES))
    single_table: bool = True  # False: one table per feature
    flatten_index: bool = True


# alpha levels of the KS critical value table (flim.analysis.ksstats.calpha)
KSAlpha = Literal[0.1, 0.05, 0.025, 0.01, 0.005, 0.001]


class KSStatsConfig(StatisticsConfig):
    comparison: CategoryColumn = "Treatment"
    alpha: KSAlpha = 0.05


class RelativeChangeConfig(StatisticsConfig):
    method: Literal["mean", "median"] = "mean"
    reference_group: CategoryColumn = "Treatment"
    reference_value: str = "Ctrl"


SeriesStatistic = Literal[
    "series_min",
    "series_max",
    "series_range",
    "series_mean",
    "series_median",
    "delta",
    "delta_min",
    "delta_max",
    "delta_sum",
    "delta_cum",
    "delta_norm",
]
SERIES_STATISTICS: tuple[str, ...] = SeriesStatistic.__args__


class SeriesAnalysisConfig(StatisticsConfig):
    legacy_keys = {"statistics": None}

    statistics: set[SeriesStatistic] = Field(
        default_factory=lambda: set(SERIES_STATISTICS)
        - {"series_mean", "series_median"}
    )
    merge_input: bool = False

    @classmethod
    def _from_legacy(cls, params):
        # legacy: one boolean per statistic
        if not any(s in params for s in SERIES_STATISTICS):
            return {}
        defaults = cls.model_fields["statistics"].default_factory()
        return {
            "statistics": {s for s in SERIES_STATISTICS if params.pop(s, s in defaults)}
        }

    def _to_legacy(self):
        return {s: s in self.statistics for s in SERIES_STATISTICS}


# --- machine learning ---


class MLConfig(AnalysisConfig):
    legacy_keys = {"random_seed": None}

    random_seed: Optional[int] = None  # None: different results on every run


class ParallelResources(Resources):
    """For tools using scikit-learn's ``n_jobs``."""

    preferred_threads: Threads = -1


class PCAConfig(MLConfig):
    legacy_keys = {
        **MLConfig.legacy_keys,
        "keep_original": "keeporig",
        "keep_standardized": "keepstd",
        "explained_plot": "explainedhisto",
    }

    keep_original: bool = False
    keep_standardized: bool = True
    explained_plot: bool = False
    # number of components, or the fraction of variance to explain; None: all
    n_components: Union[Annotated[int, Field(ge=1)], Probability, None] = 0.999


class KMeansConfig(MLConfig):
    n_clusters: int = Field(default=2, ge=1)
    cluster_prefix: str = "Cluster"
    init: Literal["k-means++", "random"] = "k-means++"
    algorithm: Literal["lloyd", "elkan"] = "lloyd"
    n_init: int = Field(default=4, ge=1)
    max_iter: int = Field(default=300, ge=1)
    tolerance: float = Field(default=1e-4, gt=0)
    resources: ParallelResources = Field(default_factory=ParallelResources)

    @classmethod
    def _from_legacy(cls, params):
        # names removed in scikit-learn 1.3; both meant "lloyd"
        if params.get("algorithm") in ("auto", "full"):
            params["algorithm"] = "lloyd"
        return {}


class GMMConfig(MLConfig):
    legacy_keys = {**MLConfig.legacy_keys, "covariance": "covar_type"}

    method: Literal["EM", "Variational Bayesian"] = "EM"
    n_components: int = Field(default=2, ge=1)
    covariance: Literal["full", "tied", "diag", "spherical"] = "full"


class RandomForestConfig(MLConfig):
    legacy_keys = {
        **MLConfig.legacy_keys,
        "target": None,
        "importance_plot": "importancehisto",
    }

    target: Optional[CategoryColumn] = None  # the category column to predict
    n_estimators: int = Field(default=100, ge=1)
    test_size: Probability = 0.3
    importance_plot: bool = True
    resources: ParallelResources = Field(default_factory=ParallelResources)

    @classmethod
    def _from_legacy(cls, params):
        return {"target": params.pop("classifier", "") or None}

    def _to_legacy(self):
        return {"classifier": self.target or ""}


class CategoryRule(BaseConfig):
    """Rows whose ``feature`` lies in [min, max) get the category ``value``."""

    value: str
    feature: FeatureColumn
    min: float
    max: float

    @model_validator(mode="after")
    def _check_range(self):
        if self.min >= self.max:
            raise ValueError(f"'{self.value}': min ({self.min}) >= max ({self.max})")
        return self


def _default_rules():
    return [
        CategoryRule(value="negative", feature="FLIRR", min=-100000.0, max=-0.5),
        CategoryRule(value="neutral", feature="FLIRR", min=-0.5, max=0.5),
        CategoryRule(value="positive", feature="FLIRR", min=0.5, max=100000),
    ]


class CategorizerConfig(AnalysisConfig):
    legacy_keys = {"rules": None}

    name: str = "New Cat"  # name of the new category column
    rules: list[CategoryRule] = Field(default_factory=_default_rules)
    default: str = "unassigned"  # category of rows no rule matches
    merge_input: bool = True

    @model_validator(mode="after")
    def _check_overlaps(self):
        for i, a in enumerate(self.rules):
            for b in self.rules[i + 1 :]:
                if a.feature == b.feature and a.min < b.max and b.min < a.max:
                    raise ValueError(f"Rules '{a.value}' and '{b.value}' overlap")
        return self

    @classmethod
    def _from_legacy(cls, params):
        if "categories" not in params:
            return {}
        return {
            "rules": [
                CategoryRule(value=c["value"], **c["criteria"])
                for c in params.pop("categories")
            ]
        }

    def _to_legacy(self):
        return {
            "categories": [
                {
                    "value": r.value,
                    "criteria": {"feature": r.feature, "min": r.min, "max": r.max},
                }
                for r in self.rules
            ]
        }


# --- autoencoders ---

# names of the classes in flim.analysis.ml.autoencoder (not imported: needs torch)
AutoencoderName = Literal[
    "AE Simulator 1-6",
    "AE Simulator 1-3",
    "AE Dimensionality Reduction 2-10",
    "AE Dimensionality Reduction 2-5",
]

AE_FEATURES = [
    "FAD a1",
    "FAD a2",
    "FAD t1",
    "FAD t2",
    "FAD photons",
    "NAD(P)H a1",
    "NAD(P)H a2",
    "NAD(P)H t1",
    "NAD(P)H t2",
    "NAD(P)H photons",
]


class AutoencoderResources(Resources):
    preferred_device: Device = "auto"
    preferred_threads: Threads = -1


class AutoencoderConfig(AnalysisConfig):
    resources: AutoencoderResources = Field(default_factory=AutoencoderResources)

    @classmethod
    def _from_legacy(cls, params):
        if "device" in params:
            return {"resources": {"preferred_device": params.pop("device")}}
        return {}

    def _to_legacy(self):
        return {"device": self.resources.preferred_device}


PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
PositiveInt = Annotated[int, Field(ge=1)]


class AETrainConfig(AutoencoderConfig):
    legacy_keys = {
        "epochs": "epoches",
        "learning_rates": "learning_rate",
        "weight_decays": "weight_decay",
        "batch_sizes": "batch_size",
        "model_name": "modelfile",
        "architecture": "model",
        "random_seed": None,
    }

    grouping: list[CategoryColumn] = ["FOV", "Cell"]
    features: list[FeatureColumn] = Field(default_factory=lambda: list(AE_FEATURES))
    epochs: PositiveInt = 20
    # each combination of learning rate, weight decay and batch size trains a model
    learning_rates: list[PositiveFloat] = Field(default=[1e-4], min_length=1)
    weight_decays: list[NonNegativeFloat] = Field(default=[1e-8], min_length=1)
    batch_sizes: list[PositiveInt] = Field(default=[128], min_length=1)
    timeseries: CategoryColumn = "Treatment"
    model_name: str = "AEModel"  # base name of the saved model files
    architecture: AutoencoderName = "AE Dimensionality Reduction 2-10"
    rescale: bool = False
    create_plots: bool = True
    train_size: Probability = 0.7
    checkpoint_interval: PositiveInt = 20  # epochs
    random_seed: Optional[int] = None


class _ModelFilesConfig(AutoencoderConfig):
    legacy_keys = {"model_files": None}

    model_files: list[Path] = []

    @classmethod
    def _from_legacy(cls, params):
        values = super()._from_legacy(params)
        files = params.pop("modelfile", "")  # "", one path or a list
        if isinstance(files, (str, Path)):
            files = [files] if files else []
        return {**values, "model_files": files}

    def _to_legacy(self):
        files = [str(f) for f in self.model_files]
        return {**super()._to_legacy(), "modelfile": files if files else ""}


class AERunConfig(_ModelFilesConfig):
    pass


class AEAugmentConfig(_ModelFilesConfig):
    sets: PositiveInt = 1  # augmented copies of the data
    add_noise: bool = True
    snr_db: float = 0.0
