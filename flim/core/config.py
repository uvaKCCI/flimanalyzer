"""Configuration models of tools: *how* a task processes its input.

Configs are Pydantic models: validated when created and when a field changes, saved as
JSON, and the source from which the GUI builds configuration dialogs.
"""

import typing
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo


class BaseConfig(BaseModel):
    """Base of all configuration models."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, arbitrary_types_allowed=True
    )

    classname: Optional[str] = (
        None  # tool class, "module.Class", for loading/reproducing
    )
    version: Optional[str] = None  # FLIMAnalyzer version that wrote the config


# --- annotated field types: meaning for validation and for the GUI's widgets ---


@dataclass(frozen=True)
class ColumnRole:
    """Marks a field as naming table columns of a kind: "category" or "feature"."""

    role: str


CategoryColumn = Annotated[str, ColumnRole("category")]
FeatureColumn = Annotated[str, ColumnRole("feature")]
AllFeatures = Literal["all"]
Device = Literal["auto", "cpu", "cuda", "mps"]
Probability = Annotated[float, Field(gt=0, lt=1)]


def column_role(field: FieldInfo) -> Optional[str]:
    """The ColumnRole of a field, also inside list[...] or unions; None if it has none."""
    for meta in field.metadata:
        if isinstance(meta, ColumnRole):
            return meta.role
    return _column_role_of(field.annotation)


def _column_role_of(annotation) -> Optional[str]:
    if typing.get_origin(annotation) is Annotated:
        for meta in typing.get_args(annotation)[1:]:
            if isinstance(meta, ColumnRole):
                return meta.role
    for arg in typing.get_args(annotation):
        role = _column_role_of(arg)
        if role:
            return role
    return None


def fixed_value(model: type[BaseModel], name: str) -> tuple[bool, Any]:
    """(True, value) if the field allows only one value, e.g. ``Literal["cpu"]``.

    Such fields are not shown in configuration dialogs.
    """
    annotation = model.model_fields[name].annotation
    if typing.get_origin(annotation) is Literal:
        values = typing.get_args(annotation)
        if len(values) == 1:
            return True, values[0]
    return False, None


# --- resources and the task config base ---


class Resources(BaseConfig):
    """What a task requests; the executor decides what it actually gets.

    Defaults are conservative (CPU, one thread); tools that can use more widen the
    allowed values in a subclass.
    """

    preferred_device: Literal["cpu"] = "cpu"
    # threads/processes inside one task; -1 = all cores allocated to the task
    preferred_threads: Literal[1] = 1


class TaskConfig(BaseConfig):
    """Base of the configs of all tools and workflows."""

    grouping: list[CategoryColumn] = []
    features: Union[list[FeatureColumn], AllFeatures] = []
    prefix: Optional[str] = None  # prefix for result names
    resources: Resources = Field(default_factory=Resources)


@dataclass(frozen=True)
class Issue:
    """A problem found when validating a config, e.g. against its input data."""

    field: Optional[str]
    message: str
    severity: Literal["error", "warning"] = "error"
