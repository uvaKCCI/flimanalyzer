"""Configuration models of tools: *how* a task processes its input.

Configs are Pydantic models: validated when created and when a field changes, saved as
JSON, and the source from which the GUI builds configuration dialogs.
"""

import copy
import logging
import typing
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal, Optional, Self, Union

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator
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

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        # the version is set once per settings file; classname names the tool of a
        # task config (see TaskConfig) and means nothing in nested models such as
        # Resources
        if data.get("version") is None:
            data.pop("version", None)
        if data.get("classname") is None and not isinstance(self, TaskConfig):
            data.pop("classname", None)
        return self._after_dump(data)

    def _after_dump(self, data: dict) -> dict:
        """Adjusts the dumped fields of this model (subclasses)."""
        return data


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


# legacy parameters of every plugin that are not part of a config: the input (1),
# execution (3) and the dialogs' "save configuration" option
LEGACY_IGNORED = frozenset(
    {"input", "autosave", "working_dir", "saveconfig", "config_file"}
)
LEGACY_ALL_FEATURES = "all_features"
_NOT_LEGACY = ("classname", "version", "resources")


class TaskConfig(BaseConfig):
    """Base of the configs of all tools and workflows.

    ``from_legacy_params`` and ``to_legacy_params`` convert from and to the parameter
    dicts of the current plugins (``AbstractPlugin.params``). Fields are matched by
    name; ``legacy_keys`` names the legacy key where it differs, or None for fields the
    hooks ``_from_legacy`` and ``_to_legacy`` convert (or that have no legacy key).
    """

    legacy_keys: ClassVar[dict[str, Optional[str]]] = {}
    # legacy keys that are dropped: unused, or meaningless for tasks
    legacy_dropped: ClassVar[frozenset[str]] = frozenset()

    grouping: list[CategoryColumn] = []
    features: Union[list[FeatureColumn], AllFeatures] = []
    prefix: Optional[str] = None  # prefix for result names
    resources: Resources = Field(default_factory=Resources)

    @model_validator(mode="after")
    def _set_classname(self):
        """Names the registered tool of this config, unless a classname is given."""
        if self.classname is None:
            from flim.core.registry import tools

            tool = tools.for_config(self)
            if tool is not None:
                # not setattr: that would run the validators again
                self.__dict__["classname"] = f"{tool.__module__}.{tool.__qualname__}"
        return self

    @classmethod
    def from_legacy_params(cls, params: dict) -> Self:
        """The config for a plugin's parameter dict; unknown keys are logged."""
        params = copy.deepcopy(dict(params))
        values = cls._from_legacy(params)
        for name in cls.model_fields:
            key = cls.legacy_keys.get(name, name)
            if name in values or name in _NOT_LEGACY or key is None:
                continue
            if key in params:
                values[name] = params.pop(key)
        if values.get("features") == LEGACY_ALL_FEATURES:
            values["features"] = "all"
        unknown = set(params) - LEGACY_IGNORED - cls.legacy_dropped
        if unknown:
            logging.warning(
                f"{cls.__name__}: ignoring unknown parameters {sorted(unknown)}"
            )
        return cls(**values)

    def to_legacy_params(self) -> dict:
        """The plugin parameter dict for this config."""
        params = {}
        for name in type(self).model_fields:
            key = self.legacy_keys.get(name, name)
            if name in _NOT_LEGACY or key is None:
                continue
            params[key] = copy.deepcopy(getattr(self, name))
        if params.get("features") == "all":
            params["features"] = LEGACY_ALL_FEATURES
        params.update(self._to_legacy())
        return params

    @classmethod
    def _from_legacy(cls, params: dict) -> dict:
        """Converts (and pops) the legacy parameters that need more than a rename."""
        return {}

    def _to_legacy(self) -> dict:
        """Legacy parameters that need more than a rename."""
        return {}


@dataclass(frozen=True)
class Issue:
    """A problem found when validating a config, e.g. against its input data."""

    field: Optional[str]
    message: str
    severity: Literal["error", "warning"] = "error"
