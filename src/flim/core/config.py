"""Configuration models of tools: *how* a task processes its input.

Configs are Pydantic models: validated when created and when a field changes, saved as
JSON, and the source from which the GUI builds configuration dialogs.
"""

import copy
import logging
import typing
from collections.abc import Iterator, Sequence
import dataclasses
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    Optional,
    Self,
    Union,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo

if TYPE_CHECKING:
    from flim.core.schema import TableSchema

logger = logging.getLogger(__name__)


class BaseConfig(BaseModel):
    """Base of all configuration models."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, arbitrary_types_allowed=True
    )

    classname: Optional[str] = (
        None  # tool class, "module.Class", for loading/reproducing
    )
    version: Optional[str] = None  # FLIMAnalyzer version that wrote the config

    @classmethod
    def allowed_values(cls, values: dict[str, Any]) -> dict[str, tuple]:
        """Return the fields that allow only some of their values, given the others.

        E.g. a lower half of a grid only exists if the grid is symmetric; legends of
        a single figure are not inside a plot. Dialogs offer only the allowed values,
        and hide a field with one. Configs that define this apply it with
        `_apply_allowed_values` at the end of their validator.

        Args:
            values: The config's field values, by name.

        Returns:
            Field name -> the allowed values (the first: the default); empty for this
            base class.
        """
        return {}

    @classmethod
    def fixed_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Return the fields with one allowed value: name -> the value.

        Args:
            values: The config's field values, by name (see `allowed_values`).
        """
        return {n: v[0] for n, v in cls.allowed_values(values).items() if len(v) == 1}

    def _apply_allowed_values(self) -> None:
        """Set each field whose value is not allowed to its first allowed value."""
        # through __dict__: assignments would run the validators again
        for name, allowed in self.allowed_values(self.__dict__).items():
            if self.__dict__.get(name) not in allowed:
                self.__dict__[name] = allowed[0]

    # no return annotation: pydantic would take it as the output's schema, and the
    # serialization JSON schema of every config would lose its fields
    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler):
        """Dump the fields; leave out a missing version, and classname where unused."""
        data = handler(self)
        # the version is set once per settings file; classname names the tool of a
        # task config (see TaskConfig) and means nothing in nested models such as
        # Resources
        if data.get("version") is None:
            data.pop("version", None)
        if data.get("classname") is None:
            if isinstance(self, TaskConfig):
                # created before its tool was registered
                data["classname"] = self._registered_classname()
            else:
                data.pop("classname", None)
        return self._after_dump(data)

    def _after_dump(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return the dumped fields, adjusted by subclasses; unchanged here."""
        return data


# --- annotated field types: meaning for validation and for the GUI's widgets ---


@dataclass(frozen=True)
class ColumnRole:
    """Marks a field as naming table columns of a kind.

    The kind (`role`) is `category`, `feature` or `label` (a category or text
    column, e.g. `Source`).
    """

    role: str


@dataclass(frozen=True)
class ValueOf:
    """Marks a field as holding a value of a category column.

    The column is the one that the field `column_field` of the same config names
    (of a list of columns: the first).
    """

    column_field: str


CategoryColumn = Annotated[str, ColumnRole("category")]
FeatureColumn = Annotated[str, ColumnRole("feature")]
LabelColumn = Annotated[str, ColumnRole("label")]  # a category or text column
AllFeatures = Literal["all"]
Device = Literal["auto", "cpu", "cuda", "mps"]
Probability = Annotated[float, Field(gt=0, lt=1)]


def column_role(field: FieldInfo) -> Optional[str]:
    """Return the `ColumnRole` of a field, also inside `list[...]` or unions.

    Args:
        field: The field.

    Returns:
        The role; None if the field has none.
    """
    for meta in field.metadata:
        if isinstance(meta, ColumnRole):
            return meta.role
    return _column_role_of(field.annotation)


def _column_role_of(annotation: Any) -> Optional[str]:
    """Return the first `ColumnRole` in a type annotation and its arguments."""
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
    """Return whether a field allows only one value, e.g. `Literal["cpu"]`.

    Such fields are not shown in configuration dialogs.

    Args:
        model: The model class.
        name: The field's name.

    Returns:
        `(True, value)` for a `Literal` of one value, else `(False, None)`.
    """
    annotation = model.model_fields[name].annotation
    if typing.get_origin(annotation) is Literal:
        values = typing.get_args(annotation)
        if len(values) == 1:
            return True, values[0]
    return False, None


# --- resources and the task config base ---


class Resources(BaseConfig):
    """What a task requests.

    What it gets depends on the machine it runs on (see `flim.core.tool.RunContext`).

    Defaults are conservative (CPU, one thread); tools that can use more widen the
    allowed values in a subclass.
    """

    # shown collapsed in dialogs (rarely changed)
    advanced: ClassVar[bool] = True

    preferred_device: Literal["cpu"] = Field(
        default="cpu",
        title="Device",
        description="The device to compute on, if available where the task runs.",
    )
    # threads/processes inside one task; -1 = all cores (see tool.resolve_threads)
    preferred_threads: Literal[1] = Field(
        default=1,
        title="Threads",
        description="Threads within the task: 1 (tools that use one thread).",
    )


# legacy plugin parameters that no config holds: the input tables ("input")
# and options of the run and of the dialogs
LEGACY_IGNORED = frozenset(
    {"input", "autosave", "working_dir", "saveconfig", "config_file", "_config"}
)
LEGACY_ALL_FEATURES = "all_features"
_NOT_LEGACY = ("classname", "version", "resources")


class TaskConfig(BaseConfig):
    """Base of the configs of all tools and workflows.

    `from_legacy_params` and `to_legacy_params` convert from and to the parameter
    dicts of the 0.5 plugins (as stored in 0.5 settings files). Fields are matched by
    name; `legacy_keys` names the legacy key where it differs, or None for fields the
    hooks `_from_legacy` and `_to_legacy` convert (or that have no legacy key).
    """

    legacy_keys: ClassVar[dict[str, Optional[str]]] = {}
    # legacy keys that are dropped: unused, or meaningless for tasks
    legacy_dropped: ClassVar[frozenset[str]] = frozenset()
    # inherited fields the tool does not use; not shown in dialogs
    hidden_fields: ClassVar[frozenset[str]] = frozenset()
    # the minimum number of features and grouping columns the tool needs; see
    # requirement_issues
    min_features: ClassVar[int] = 0
    min_grouping: ClassVar[int] = 0

    grouping: list[CategoryColumn] = Field(
        default=[],
        title="Grouping",
        description="Category columns to group the data by, in this order.",
    )
    features: Union[list[FeatureColumn], AllFeatures] = Field(
        default=[], title="Features", description="The feature columns to use."
    )
    prefix: Optional[str] = Field(
        default=None,
        title="Result prefix",
        # names the results: shown with the output settings in dialogs
        json_schema_extra={"section": "output"},
        description="Text put in front of the names of the results.",
    )
    resources: Resources = Field(default_factory=Resources, title="Resources")

    @model_validator(mode="after")
    def _set_classname(self) -> Self:
        """Set the classname of the registered tool of this config, unless given."""
        if self.classname is None:
            # not setattr: that would run the validators again
            self.__dict__["classname"] = self._registered_classname()
        return self

    def _registered_classname(self) -> Optional[str]:
        """Return `module.Class` of the registered tool of this config; None if none.

        Tools are registered when their module is imported. A config created before
        that has no classname; it is filled in when the config is dumped.
        """
        from flim.core.registry import tools

        tool = tools.for_config(self)
        return f"{tool.__module__}.{tool.__qualname__}" if tool else None

    @classmethod
    def from_legacy_params(cls, params: dict[str, Any]) -> Self:
        """Return the config for a legacy plugin parameter dict.

        See the class docstring. The keys in `LEGACY_IGNORED` and `legacy_dropped` are
        ignored; other unknown keys are logged and ignored. `all_features` becomes
        `all`.

        Args:
            params: The legacy parameters (not changed).

        Returns:
            The config.

        Raises:
            pydantic.ValidationError: If a value is not valid for its field.
        """
        # ignored keys first: "input" holds the input tables at run time
        params = copy.deepcopy(
            {k: v for k, v in params.items() if k not in LEGACY_IGNORED}
        )
        values = cls._from_legacy(params)
        for name in cls.model_fields:
            key = cls.legacy_keys.get(name, name)
            if name in values or name in _NOT_LEGACY or key is None:
                continue
            if key in params:
                values[name] = params.pop(key)
        if values.get("features") == LEGACY_ALL_FEATURES:
            values["features"] = "all"
        unknown = set(params) - cls.legacy_dropped
        if unknown:
            logger.warning(
                f"{cls.__name__}: ignoring unknown parameters {sorted(unknown)}"
            )
        return cls(**values)

    def to_legacy_params(self) -> dict[str, Any]:
        """Return the plugin parameter dict for this config (see the class docstring).

        `all` features become `all_features`; `classname`, `version` and `resources`
        have no legacy key.
        """
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
    def _from_legacy(cls, params: dict[str, Any]) -> dict[str, Any]:
        """Convert (and pop) the legacy parameters that need more than a rename."""
        return {}

    def _to_legacy(self) -> dict[str, Any]:
        """Return the legacy parameters that need more than a rename."""
        return {}


@dataclass(frozen=True)
class Issue:
    """A problem found when validating a config, e.g. against its input data.

    `field` is a path into the config, e.g. `"x_vars[1]"` or
    `"range_filters[0].column"`. A `"guessed"` issue reports a value that was
    replaced (`old`) by the closest match (`suggestion`) after an upstream change.
    """

    field: Optional[str]
    message: str
    severity: Literal["error", "warning", "guessed"] = "error"
    step: Optional[str] = None  # workflow step, None for a single tool
    old: Any = None
    suggestion: Any = None


def requirement_issues(
    config: "TaskConfig", schemas: Sequence[Optional["TableSchema"]] = ()
) -> list[Issue]:
    """Return issues if a config selects fewer features or grouping columns than needed.

    The minimums are the config's `min_features` and `min_grouping`. "All features"
    is counted against the input schemas (the distinct feature columns of the known
    and complete ones), and not validated if none of them is known and complete.

    Args:
        config: The config.
        schemas: The schemas of the input tables; None for an unknown one.

    Returns:
        One error per field below its minimum.
    """
    issues = []
    minimums = (("features", config.min_features), ("grouping", config.min_grouping))
    for name, least in minimums:
        if not least or name not in type(config).model_fields:
            continue
        value = getattr(config, name)
        if value == "all":
            known = [s for s in schemas if s is not None and getattr(s, "complete", False)]
            if not known:
                continue
            count = len({c.name for s in known for c in s.columns if c.role == "feature"})
        else:
            count = len(value)
        if count < least:
            what = "feature" if name == "features" else "grouping column"
            plural = "s" if least > 1 else ""
            issues.append(Issue(name, f"Select at least {least} {what}{plural}"))
    return issues


def column_references(
    config: BaseModel, path: str = ""
) -> Iterator[tuple[str, str, str]]:
    """Yield every column a config names, with its path and role.

    Also the columns in nested models (e.g. range filters), and in lists and dict
    keys of column fields. `features` set to `all` names no column.

    Args:
        config: The config.
        path: The prefix of the paths, e.g. `filters[0].`. Defaults to none.

    Yields:
        `(path, column, role)`, e.g. `("features[2]", "FAD tm", "feature")`; a dict
        key's path has the key's `repr`, e.g. `ranges['FLIRR']`.
    """
    for name, field in type(config).model_fields.items():
        value = getattr(config, name)
        field_path = f"{path}{name}"
        role = column_role(field)
        if role is not None:
            if name == "features" and value == "all":
                continue
            if isinstance(value, str):
                yield field_path, value, role
            elif isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    yield f"{field_path}[{i}]", v, role
            elif isinstance(value, dict):
                for k in value:
                    yield f"{field_path}[{k!r}]", k, role
        elif isinstance(value, BaseModel):
            yield from column_references(value, f"{field_path}.")
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                if isinstance(v, BaseModel):
                    yield from column_references(v, f"{field_path}[{i}].")
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, BaseModel):
                    yield from column_references(v, f"{field_path}[{k!r}].")


def part_feature(config: Any) -> str:
    """Return the one feature of a part's config (`features` a list or dict of one).

    Args:
        config: A config of `map_configs`.

    Returns:
        The feature; empty if the config has not exactly one (e.g. `all`).
    """
    features = getattr(config, "features", None)
    if isinstance(features, (list, dict)) and len(features) == 1:
        return str(next(iter(features)))
    return ""


# --- processing: how a step treats input that doesn't match its settings ---

Skippable = Literal["none", "some", "all"]


class Processing(BaseModel):
    """How a step processes input that doesn't match its settings.

    The `processing` group of a workflow step, of a workflow file (for all its
    steps) and of a tool file. Every field is optional; the layers are merged per
    key, a step's over the workflow's (`ProcessingRules.of`). Field keys are config
    field paths as the validation reports them, e.g. `features` or `training.grouping`.

    Attributes:
        strict: Whether columns the settings name that are not in the input are
            errors (True) or replaced by the closest column of the same role
            (False): one value for every field, or a value per field (fields not
            listed are strict); None: not set (strict).
        skippable: Per field: `none` (every entry has to apply), `some` (entries
            may be skipped while at least one applies) or `all` (every entry may be
            skipped); fields not listed are `none`. Only the fields the tool
            declares (`Tool.skippable_fields`).
        required: Per skippable field: the entries that have to apply although the
            field is skippable (list elements, or keys of dict fields; a rule, e.g.
            a calculation, by some of its fields, e.g. `{"name": "FLIRR"}`).
    """

    model_config = ConfigDict(extra="forbid")

    strict: Union[bool, dict[str, bool], None] = Field(
        default=None,
        description="Columns not in the input: errors (true) or replaced by the"
        " closest column of the same role (false); a value for every field, or per"
        " field. Not set: strict.",
    )
    skippable: dict[str, Skippable] = Field(
        default={},
        description="Per field: none (every entry has to apply), some (at least one),"
        " all (every entry may be skipped). Not listed: none.",
    )
    required: dict[str, list[Any]] = Field(
        default={},
        description="Per skippable field: the entries that have to apply.",
    )

    def is_empty(self) -> bool:
        """Return whether no field is set."""
        return self.strict is None and not self.skippable and not self.required


def _covers(key: str, path: str) -> bool:
    """Return whether a field key covers a path: the field itself or a part of it."""
    return path == key or path.startswith((key + "[", key + "."))


@dataclass(frozen=True)
class ProcessingRules:
    """The merged `processing` of a step: what applies to each field.

    Attributes:
        strict: The value for fields without one of their own.
        strict_fields: Field key -> its own `strict`.
        skippable: Field key -> `none`, `some` or `all`.
        required: Field key -> the entries that have to apply.
    """

    strict: bool = True
    strict_fields: dict = dataclasses.field(default_factory=dict)
    skippable: dict = dataclasses.field(default_factory=dict)
    required: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def of(cls, *layers: Optional[Processing]) -> "ProcessingRules":
        """Merge `processing` layers per key, the later over the earlier.

        A single `strict` value replaces every field's value of the earlier layers;
        a dict replaces the values of the fields it lists.

        Args:
            *layers: The layers, lowest first, e.g. the workflow's, then the step's;
                None for a layer that isn't set.

        Returns:
            The rules.
        """
        strict, fields, skippable, required = True, {}, {}, {}
        for layer in layers:
            if layer is None:
                continue
            if isinstance(layer.strict, bool):
                strict, fields = layer.strict, {}
            elif isinstance(layer.strict, dict):
                fields = {**fields, **layer.strict}
            skippable = {**skippable, **layer.skippable}
            required = {**required, **layer.required}
        return cls(strict, fields, skippable, required)

    def is_strict(self, path: str) -> bool:
        """Return whether a field's missing columns are errors, else guessed.

        Args:
            path: The field's path, e.g. `features[2]`; the longest key that covers
                it decides.

        Returns:
            The field's own value, else the value for every field.
        """
        keys = [k for k in self.strict_fields if _covers(k, path)]
        return self.strict_fields[max(keys, key=len)] if keys else self.strict

    def skip(self, field: str) -> str:
        """Return a field's `skippable`: `none`, `some` or `all`."""
        return self.skippable.get(field, "none")
