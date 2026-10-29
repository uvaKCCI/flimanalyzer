"""Configs of the Analysis tools: statistics, machine learning and autoencoders."""

from pathlib import Path
from typing import Annotated, Literal, Optional, Union

from pydantic import AfterValidator, Field, field_validator, model_validator

from flim.core.config import (
    BaseConfig,
    CategoryColumn,
    Device,
    FeatureColumn,
    Probability,
    Resources,
    TaskConfig,
    ValueOf,
)

def _not_zero(threads: int) -> int:
    if threads == 0:
        raise ValueError("0 threads: use -1 (all cores) or a positive number")
    return threads


# -1: all cores allocated to the task
Threads = Annotated[int, Field(ge=-1), AfterValidator(_not_zero)]


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
    }
    # flat headers ("FLIRR\nmean") always: other tools name columns by text
    legacy_dropped = frozenset({"flattenindex"})

    aggs: list[Aggregate] = Field(
        default_factory=lambda: list(AGGREGATES), title="Statistics"
    )
    single_table: bool = Field(
        default=True,
        title="Single table",
        description="One table for all features; otherwise one table per feature.",
    )


# alpha levels of the KS critical value table (flim.analysis.ksstats.calpha)
KSAlpha = Literal[0.1, 0.05, 0.025, 0.01, 0.005, 0.001]


class KSStatsConfig(StatisticsConfig):
    comparison: CategoryColumn = Field(
        default="Treatment",
        title="Compare",
        description=(
            "Its values are compared pairwise, separately within each group of the"
            " other grouping columns."
        ),
    )
    alpha: KSAlpha = Field(default=0.05, title="Significance level")


class RelativeChangeConfig(StatisticsConfig):
    method: Literal["mean", "median"] = Field(
        default="mean", title="Reference statistic"
    )
    reference_group: CategoryColumn = Field(
        default="Treatment",
        title="Reference column",
        description="The category column that holds the reference value.",
    )
    reference_value: Annotated[str, ValueOf("reference_group")] = Field(
        default="Ctrl",
        title="Reference value",
        description="Features are divided by their mean or median in these rows.",
    )


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
        - {"series_mean", "series_median"},
        title="Statistics",
    )
    merge_input: bool = Field(
        default=False,
        title="Include the input",
        description="Also include the series' features in the result.",
    )

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
    hidden_fields = frozenset({"grouping"})

    random_seed: Optional[int] = Field(
        default=0,
        title="Random seed",
        description="The same results on every run; empty: different on every run.",
    )


class ParallelResources(Resources):
    """For tools using scikit-learn's ``n_jobs``."""

    preferred_threads: Threads = Field(
        default=-1,
        title="Threads",
        description="Threads within the task (1 or more); -1: all cores allocated to the task.",
    )


class PCAConfig(MLConfig):
    legacy_keys = {
        **MLConfig.legacy_keys,
        "keep_original": "keeporig",
        "keep_standardized": "keepstd",
        "explained_plot": "explainedhisto",
    }

    keep_original: bool = Field(
        default=False,
        title="Include the features",
        description="Also include the original features in the result.",
    )
    keep_standardized: bool = Field(
        default=True,
        title="Include standardized features",
        description="Also include the standardized features in the result.",
    )
    explained_plot: bool = Field(
        default=False,
        title="Explained variance plot",
        description="A bar plot of the variance each component explains.",
    )
    n_components: Union[Annotated[int, Field(ge=1)], Probability, None] = Field(
        default=0.999,
        title="Components",
        description=(
            "A number of components, or the fraction of the variance to explain"
            " (0 to 1); empty: all components."
        ),
    )


class KMeansConfig(MLConfig):
    n_clusters: int = Field(default=2, ge=1, title="Clusters")
    cluster_prefix: str = Field(
        default="Cluster",
        title="Cluster column",
        description='Name of the new column; clusters are named "<name> 1", ...',
    )
    init: Literal["k-means++", "random"] = Field(
        default="k-means++", title="Initialization"
    )
    algorithm: Literal["lloyd", "elkan"] = Field(default="lloyd", title="Algorithm")
    n_init: int = Field(
        default=4,
        ge=1,
        title="Runs",
        description="Runs with different starting centers; the best is kept.",
    )
    max_iter: int = Field(default=300, ge=1, title="Max iterations")
    tolerance: float = Field(default=1e-4, gt=0, title="Tolerance")
    resources: ParallelResources = Field(
        default_factory=ParallelResources, title="Resources"
    )

    @classmethod
    def _from_legacy(cls, params):
        # names removed in scikit-learn 1.3; both meant "lloyd"
        if params.get("algorithm") in ("auto", "full"):
            params["algorithm"] = "lloyd"
        return {}


class GMMConfig(MLConfig):
    legacy_keys = {**MLConfig.legacy_keys, "covariance": "covar_type"}

    method: Literal["EM", "Variational Bayesian"] = Field(default="EM", title="Method")
    n_components: int = Field(
        default=2,
        ge=1,
        title="Components",
        description="Components of the model; BIC and AIC are reported for 1 to n.",
    )
    covariance: Literal["full", "tied", "diag", "spherical"] = Field(
        default="full", title="Covariance"
    )


class RandomForestConfig(MLConfig):
    legacy_keys = {
        **MLConfig.legacy_keys,
        "target": None,
        "importance_plot": "importancehisto",
    }

    # the grouping columns are left out of the features
    hidden_fields = frozenset()

    target: Optional[CategoryColumn] = Field(
        default=None, title="Predict", description="The category column to predict."
    )
    n_estimators: int = Field(default=100, ge=1, title="Trees")
    test_size: Probability = Field(
        default=0.3,
        title="Test fraction",
        description="Fraction of the rows kept for testing the accuracy.",
    )
    importance_plot: bool = Field(default=True, title="Importance plot")
    resources: ParallelResources = Field(
        default_factory=ParallelResources, title="Resources"
    )

    @classmethod
    def _from_legacy(cls, params):
        return {"target": params.pop("classifier", "") or None}

    def _to_legacy(self):
        return {"classifier": self.target or ""}


class CategoryRule(BaseConfig):
    """Rows whose ``feature`` lies in (min, max] get the category ``value``."""

    value: str = Field(title="Value")
    feature: FeatureColumn = Field(title="Feature")
    min: float = Field(title="Min")
    max: float = Field(title="Max")

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
    hidden_fields = frozenset({"grouping"})

    name: str = Field(
        default="New Cat",
        title="New column",
        description="Name of the new category column.",
    )
    rules: list[CategoryRule] = Field(
        default_factory=_default_rules,
        title="Rules",
        description=(
            "Rows whose feature lies in a rule's range (min < value <= max) get the"
            " rule's value; the first matching rule wins."
        ),
    )
    default: str = Field(
        default="unassigned",
        title="Default value",
        description="The value of rows that no rule matches.",
    )
    merge_input: bool = Field(
        default=True,
        title="Include the input",
        description="Keep all input columns; otherwise only categories and features.",
    )

    @classmethod
    def allowed_values(cls, values):
        # the features kept: only without the input's columns (dialogs hide them)
        if values.get("merge_input", True):
            return {"features": (values.get("features"),)}
        return {}

    @field_validator("rules")
    @classmethod
    def _check_overlaps(cls, rules):
        for i, a in enumerate(rules):
            for b in rules[i + 1 :]:
                if a.feature == b.feature and a.min < b.max and b.min < a.max:
                    raise ValueError(f"Rules '{a.value}' and '{b.value}' overlap")
        return rules

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


DEFAULT_DEVICE = "auto"  # see flim.analysis.ml.device (that module needs torch)


class AutoencoderResources(Resources):
    preferred_device: Device = Field(
        default=DEFAULT_DEVICE,
        title="Device",
        description="auto: a GPU if there is one where the task runs, else the CPU.",
    )
    preferred_threads: Threads = Field(
        default=-1,
        title="Threads",
        description="Threads within the task (1 or more); -1: all cores allocated to the task.",
    )


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

    grouping: list[CategoryColumn] = Field(
        default=["FOV", "Cell"],
        title="Grouping",
        description=(
            "Training and validation sets are split by these groups (e.g. cells)."
        ),
    )
    features: list[FeatureColumn] = Field(
        default_factory=lambda: list(AE_FEATURES), title="Features"
    )
    epochs: PositiveInt = Field(default=20, title="Epochs")
    # each combination of learning rate, weight decay and batch size trains a model
    learning_rates: list[PositiveFloat] = Field(
        default=[1e-4],
        min_length=1,
        title="Learning rates",
        description="Comma-separated; one model per combination with the others.",
    )
    weight_decays: list[NonNegativeFloat] = Field(
        default=[1e-8],
        min_length=1,
        title="Weight decays",
        description="Comma-separated.",
    )
    batch_sizes: list[PositiveInt] = Field(
        default=[128], min_length=1, title="Batch sizes", description="Comma-separated."
    )
    timeseries: CategoryColumn = Field(
        default="Treatment",
        title="Time series",
        description="Not used to split the training and validation sets.",
    )
    model_name: str = Field(
        default="AEModel",
        title="Model name",
        description="Base name of the saved model files.",
    )
    architecture: AutoencoderName = Field(
        default="AE Dimensionality Reduction 2-10", title="Architecture"
    )
    rescale: bool = Field(
        default=False,
        title="Rescale",
        description="Reconstructed values in the units of the input (not 0..1).",
    )
    create_plots: bool = Field(default=True, title="Loss plots")
    train_size: Probability = Field(
        default=0.7,
        title="Training fraction",
        description="Fraction of the groups used for training; the rest validates.",
    )
    checkpoint_interval: PositiveInt = Field(
        default=20,
        title="Checkpoint every",
        description="Save the model every n epochs (and after the last).",
    )
    random_seed: Optional[int] = Field(
        default=None,
        title="Random seed",
        description="The same split and starting weights on every run; empty: random.",
    )

    @classmethod
    def _from_legacy(cls, params):
        # workflows pass one value of each grid when they map over the combinations
        for key in ("learning_rate", "weight_decay", "batch_size"):
            if key in params and not isinstance(params[key], (list, tuple)):
                params[key] = [params[key]]
        return super()._from_legacy(params)


class _ModelFilesConfig(AutoencoderConfig):
    legacy_keys = {"model_files": None}

    model_files: list[Path] = Field(
        default=[],
        title="Model files",
        description="Models saved by Autoencoder: Train (one result per model).",
    )

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
    hidden_fields = frozenset({"grouping"})


class AEAugmentConfig(_ModelFilesConfig):
    grouping: list[CategoryColumn] = Field(
        default=[],
        title="Grouping",
        description="The last column (e.g. Cell) is renumbered in each copy.",
    )
    sets: PositiveInt = Field(
        default=1, title="Copies", description="Simulated copies."
    )
    add_noise: bool = Field(
        default=True,
        title="Add noise",
        description="Add white noise before simulating.",
    )
    snr_db: float = Field(default=0.0, title="Signal-to-noise (dB)")
