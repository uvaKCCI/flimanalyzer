"""Configs of the workflows: their own fields plus the configs of their steps.

A workflow config owns the fields its steps share (grouping, features, ...); each step
config holds only the settings of that step. ``bound_fields`` names the fields the
workflow sets in each step: they are copied from the workflow config when it is
validated, hidden in dialogs and not saved.
"""

import copy
from typing import Annotated, ClassVar, Optional

from pydantic import Field, model_validator

from flim.configs.analysis import (
    AE_FEATURES,
    AEAugmentConfig,
    AERunConfig,
    AETrainConfig,
    AutoencoderResources,
)
from flim.core.config import CategoryColumn, FeatureColumn, TaskConfig, ValueOf


class WorkflowConfig(TaskConfig):
    legacy_keys = {"strict": None}
    legacy_dropped = frozenset({"executor"})  # an execution option

    # step name -> fields the workflow sets in that step's config. Fields the workflow
    # config also has are copied from it; the workflow's code sets the others.
    bound_fields: ClassVar[dict[str, frozenset[str]]] = {}

    # False: step settings naming columns that changed upstream are replaced by the
    # closest match (and reported); True: they are errors to fix before running.
    # None: the mode's default, False in the GUI and True in batch runs.
    strict: Optional[bool] = Field(
        default=None,
        title="Strict",
        description=(
            "Columns that changed upstream are errors to fix; otherwise they are"
            " replaced by the closest match. Automatic: strict in batch runs only."
        ),
    )

    @model_validator(mode="after")
    def _share_fields(self):
        for step, names in self.bound_fields.items():
            config = getattr(self, step)
            for name in names & set(type(self).model_fields):
                value = getattr(self, name)
                if getattr(config, name) != value:
                    setattr(config, name, copy.deepcopy(value))
        return self

    def _after_dump(self, data):
        for step, names in self.bound_fields.items():
            if isinstance(data.get(step), dict):
                for name in names:
                    data[step].pop(name, None)
        return data


class BasicFLIRRConfig(WorkflowConfig):
    grouping: list[CategoryColumn] = ["Treatment", "FOV", "Cell"]
    # values the workflow used to take from the data, now settings with that default
    reference_value: Annotated[Optional[str], ValueOf("grouping")] = Field(
        default=None,
        title="Reference value",
        description=(
            "Relative changes: the features are divided by their mean in the rows with"
            " this value of the first grouping column. Empty: its first value (in the"
            " order of its categories)."
        ),
    )
    fad_a1: Optional[FeatureColumn] = Field(
        default=None,
        title="Scatter x (FAD a1 %)",
        description="Empty: found by name (FAD, a1, %).",
    )
    nadph_a2: Optional[FeatureColumn] = Field(
        default=None,
        title="Scatter y (NAD(P)H a2 %)",
        description="Empty: found by name (NAD, a2, %).",
    )
    features: list[FeatureColumn] = [
        "FAD a1",
        "FAD a1%",
        "FAD a2",
        "FAD a2%",
        "FAD t1",
        "FAD t2",
        "FAD photons",
        "NAD(P)H a1",
        "NAD(P)H a1%",
        "NAD(P)H a2",
        "NAD(P)H a2%",
        "NAD(P)H t1",
        "NAD(P)H t2",
        "NAD(P)H photons",
    ]


# legacy workflow parameters that are settings of the training step
_TRAINING_KEYS = (
    "epoches",
    "learning_rate",
    "weight_decay",
    "batch_size",
    "model",
    "rescale",
    "checkpoint_interval",
)
_SHARED = frozenset({"grouping", "features", "resources"})


def _workflow_training(**changes) -> AETrainConfig:
    """Training step defaults of the autoencoder workflows."""
    return AETrainConfig(
        epochs=6,
        learning_rates=[1e-5, 2e-5],
        weight_decays=[1e-7, 1e-8],
        batch_sizes=[128, 64],
        rescale=True,
        checkpoint_interval=2,
        **changes,
    )


class _AEWorkflowConfig(WorkflowConfig):
    legacy_keys = {**WorkflowConfig.legacy_keys, "training": None}
    bound_fields = {"training": _SHARED | {"timeseries"}}

    grouping: list[CategoryColumn] = ["Treatment", "FOV", "Cell"]
    features: list[FeatureColumn] = Field(default_factory=lambda: list(AE_FEATURES))
    timeseries: CategoryColumn = Field(default="Treatment", title="Time series")
    resources: AutoencoderResources = Field(default_factory=AutoencoderResources)
    training: AETrainConfig

    @classmethod
    def _from_legacy(cls, params):
        values = {}
        if "device" in params:
            values["resources"] = {"preferred_device": params.pop("device")}
        legacy = {k: params.pop(k) for k in _TRAINING_KEYS if k in params}
        default = cls.model_fields["training"].default_factory()
        values["training"] = AETrainConfig.from_legacy_params(
            {**default.to_legacy_params(), **legacy}
        )
        return values

    def _to_legacy(self):
        params = self.training.to_legacy_params()
        return {
            **{k: params[k] for k in _TRAINING_KEYS},
            "device": self.resources.preferred_device,
        }


class AETuneConfig(_AEWorkflowConfig):
    """FLIM Data Augmentation Tuning: trains autoencoders, then augments the data."""

    legacy_keys = {**_AEWorkflowConfig.legacy_keys, "augment": None}
    bound_fields = {**_AEWorkflowConfig.bound_fields, "augment": _SHARED}

    training: AETrainConfig = Field(
        default_factory=lambda: _workflow_training(architecture="AE Simulator 1-6")
    )
    # the workflow simulates without noise
    augment: AEAugmentConfig = Field(
        default_factory=lambda: AEAugmentConfig(sets=4, add_noise=False)
    )

    @classmethod
    def _from_legacy(cls, params):
        values = super()._from_legacy(params)
        augment = cls.model_fields["augment"].default_factory()
        if "sets" in params:
            augment.sets = params.pop("sets")
        return {**values, "augment": augment}

    def _to_legacy(self):
        return {**super()._to_legacy(), "sets": self.augment.sets}


class AEFeatureConfig(_AEWorkflowConfig):
    """FLIM Feature Analysis: trains autoencoders, then runs them on the data."""

    legacy_keys = {
        **_AEWorkflowConfig.legacy_keys,
        "run": None,
        "control_group": "ctrl_group",
    }
    # the run step uses the models the training step saves
    bound_fields = {
        **_AEWorkflowConfig.bound_fields,
        "run": _SHARED | {"model_files"},
    }

    training: AETrainConfig = Field(default_factory=_workflow_training)
    run: AERunConfig = Field(default_factory=AERunConfig)
    control_group: Annotated[str, ValueOf("timeseries")] = Field(
        default="Ctrl",
        title="Control",
        description="The value of the time series column used as control.",
    )
