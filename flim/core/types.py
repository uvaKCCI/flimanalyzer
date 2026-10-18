"""Types of tool inputs and outputs.

Each type knows the Python classes it accepts (``pytypes``) and a ``pretty_name`` used
to display results, so tools never hardcode names such as ``"Table: ..."``. The classes
are given as import paths and resolved only when needed, so checking a value never
imports heavy libraries such as torch or dask.
"""

import importlib
import sys
from dataclasses import dataclass
from typing import Any, ClassVar, Optional

Metadata = dict[str, Any]
"""Information that travels with images (axes, dims, scale, physical pixel sizes, ...)."""


class DataType:
    """Base for the types of tool inputs and outputs."""

    pretty_name: ClassVar[str] = "Data"
    pytypes: ClassVar[tuple[str, ...]] = ()  # "module.Class" of the accepted classes

    @classmethod
    def python_classes(cls) -> tuple[type, ...]:
        """The accepted classes whose modules are already imported.

        A value can only be an instance of a class whose module has been imported, so
        modules that are not loaded yet are skipped instead of imported.
        """
        classes = []
        for path in cls.pytypes:
            module, _, name = path.rpartition(".")
            if module.split(".")[0] not in sys.modules:
                continue
            try:
                classes.append(getattr(importlib.import_module(module), name))
            except (ImportError, AttributeError):
                continue
        return tuple(classes)

    @classmethod
    def accepts(cls, value: Any) -> bool:
        return isinstance(value, cls.python_classes())

    @classmethod
    def display_name(cls, name: str) -> str:
        """How a result of this type is shown, e.g. ``"Table: Summary"``."""
        return f"{cls.pretty_name}: {name}"

    @staticmethod
    def of(value: Any) -> Optional[type["DataType"]]:
        """The type of ``value`` (the most specific one), None if no type accepts it."""
        matches = [t for t in _all_types() if t.accepts(value)]
        if not matches:
            return None
        return max(matches, key=lambda t: len(t.__mro__))


class TableType(DataType):
    pretty_name = "Table"
    pytypes = ("pandas.DataFrame", "pandas.Series")


class PlotType(DataType):
    pretty_name = "Plot"
    pytypes = ("matplotlib.figure.Figure",)


class ImageType(DataType):
    pretty_name = "Image"
    pytypes = ("numpy.ndarray", "dask.array.Array", "torch.Tensor")


class FileType(DataType):
    pretty_name = "File"
    pytypes = ("pathlib.Path",)


def _all_types() -> list[type[DataType]]:
    found, todo = [], list(DataType.__subclasses__())
    while todo:
        t = todo.pop()
        found.append(t)
        todo.extend(t.__subclasses__())
    return found


@dataclass(frozen=True)
class InputSpec:
    """An input a tool takes."""

    name: str
    type: type[DataType]
    optional: bool = False
    description: str = ""


@dataclass(frozen=True)
class OutputSpec:
    """A result a tool produces."""

    name: str
    type: type[DataType]
    description: str = ""

    @property
    def display_name(self) -> str:
        return self.type.display_name(self.name)
