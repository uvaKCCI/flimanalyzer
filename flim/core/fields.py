"""What the fields of a config hold, for building editors (dialogs) from them.

``describe(config_class)`` turns each Pydantic field into a :class:`FieldSpec`: its
kind (checkbox, choice, column list, ...), choices, bounds, title and help. It does
not import wx, so other front ends can use it too.
"""

import types
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Union

import annotated_types
from pydantic import BaseModel

from flim.core.config import ColumnRole, ValueOf, fixed_value

# fields of every config that are not edited
METADATA_FIELDS = ("classname", "version")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    title: str
    kind: str  # see describe_annotation
    description: str = ""
    optional: bool = False  # None is allowed
    choices: tuple = ()  # choice, multichoice
    role: Optional[str] = None  # column, columns: "category" or "feature"
    allow_all: bool = False  # columns: "all" is allowed (all features)
    item_type: Optional[type] = None  # numbers: int or float
    model: Optional[type] = None  # model, models: the nested config class
    column_field: Optional[str] = None  # value: the field naming the column
    bounds: dict = field(default_factory=dict)  # ge, gt, le, lt
    hidden: bool = False  # only one value is allowed, or metadata


def title_of(name: str) -> str:
    """``"n_components"`` → ``"N components"``."""
    text = name.replace("_", " ")
    return text[:1].upper() + text[1:]


def describe(model: type[BaseModel]) -> list[FieldSpec]:
    """The editable fields of a config class, in definition order."""
    specs = []
    for name, info in model.model_fields.items():
        hidden = (
            name in METADATA_FIELDS
            or name in getattr(model, "hidden_fields", ())
            or fixed_value(model, name)[0]
        )
        spec = describe_annotation(info.annotation, list(info.metadata))
        specs.append(
            FieldSpec(
                name=name,
                title=info.title or title_of(name),
                description=info.description or "",
                hidden=hidden or spec.get("hidden", False),
                **{k: v for k, v in spec.items() if k != "hidden"},
            )
        )
    return specs


def visible(specs: list[FieldSpec]) -> list[FieldSpec]:
    """Fields shown in a dialog: not hidden, and nested models with something to edit."""
    return [
        s
        for s in specs
        if not s.hidden and not (s.kind == "model" and not visible(describe(s.model)))
    ]


def _unwrap(annotation, metadata):
    """(annotation without Annotated, metadata list)."""
    while typing.get_origin(annotation) is Annotated:
        args = typing.get_args(annotation)
        annotation, metadata = args[0], metadata + list(args[1:])
    return annotation, metadata


def _role(metadata) -> Optional[str]:
    return next((m.role for m in metadata if isinstance(m, ColumnRole)), None)


def _bounds(metadata) -> dict:
    bounds = {}
    for m in metadata:
        for key, cls in (
            ("ge", annotated_types.Ge),
            ("gt", annotated_types.Gt),
            ("le", annotated_types.Le),
            ("lt", annotated_types.Lt),
        ):
            if isinstance(m, cls):
                bounds[key] = getattr(m, key)
        # Field(gt=...) inside Annotated arrives as a FieldInfo
        for item in getattr(m, "metadata", ()):
            bounds.update(_bounds([item]))
    return bounds


def _is_union(annotation) -> bool:
    return typing.get_origin(annotation) in (Union, types.UnionType)


def _is_model(annotation) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def describe_annotation(annotation, metadata=()) -> dict:
    """Kind and details of a field type.

    Kinds: bool, choice, multichoice, int, float, number (int or float), mixed (a
    number or one of ``choices``), text, value (a value of the column another field
    names), column, columns, path, paths, numbers, model, models, json (anything else).
    """
    annotation, metadata = _unwrap(annotation, list(metadata))
    optional = False
    if _is_union(annotation):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        optional = len(args) < len(typing.get_args(annotation))
        # list of columns or "all"
        lists = [a for a in args if typing.get_origin(_unwrap(a, [])[0]) is list]
        literals = [a for a in args if typing.get_origin(a) is Literal]
        if lists and literals and typing.get_args(literals[0]) == ("all",):
            spec = describe_annotation(lists[0], metadata)
            return {**spec, "allow_all": True, "optional": optional}
        kinds = [describe_annotation(a, metadata) for a in args]
        if len(kinds) == 1:
            return {**kinds[0], "optional": optional}
        bounds = {}
        for k in kinds:
            bounds.update(k.get("bounds", {}))
        names = {k["kind"] for k in kinds}
        if names <= {"int", "float"}:
            return {"kind": "number", "optional": optional, "bounds": bounds}
        if names <= {"int", "float", "choice"}:
            # a number or one of some values, e.g. a confidence level or "sd"
            choices = tuple(c for k in kinds for c in k.get("choices", ()))
            return {
                "kind": "mixed",
                "optional": optional,
                "choices": choices,
                "bounds": bounds,
            }
        return {"kind": "json", "optional": optional}

    origin = typing.get_origin(annotation)
    role = _role(metadata)
    if annotation is bool:
        return {"kind": "bool"}
    if origin is Literal:
        return {"kind": "choice", "choices": typing.get_args(annotation)}
    if annotation is str:
        value_of = next((m for m in metadata if isinstance(m, ValueOf)), None)
        if value_of is not None:
            return {"kind": "value", "column_field": value_of.column_field}
        return {"kind": "column", "role": role} if role else {"kind": "text"}
    if annotation in (int, float):
        return {"kind": annotation.__name__, "bounds": _bounds(metadata)}
    if annotation is Path:
        return {"kind": "path"}
    if _is_model(annotation):
        return {"kind": "model", "model": annotation}
    if origin in (list, set, tuple):
        (item,) = typing.get_args(annotation)[:1] or (Any,)
        item, item_metadata = _unwrap(item, [])
        if typing.get_origin(item) is Literal:
            return {"kind": "multichoice", "choices": typing.get_args(item)}
        item_role = _role(item_metadata) or role
        if item is str and item_role:
            return {"kind": "columns", "role": item_role}
        if item in (int, float):
            return {
                "kind": "numbers",
                "item_type": item,
                "bounds": _bounds(item_metadata),
            }
        if item is Path:
            return {"kind": "paths"}
        if _is_model(item):
            return {"kind": "models", "model": item}
    return {"kind": "json"}
