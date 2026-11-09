"""Types of tool inputs and outputs.

Each type knows the Python classes it accepts (``pytypes``) and a ``pretty_name`` used
to display results, so tools never hardcode names such as ``"Table: ..."``. The classes
are given as import paths and resolved only when needed, so checking a value never
imports heavy libraries such as torch or dask.
"""

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Optional

from flim.core.saving import PlotSaveOptions, SaveOptions, TableSaveOptions

Metadata = dict[str, Any]
"""Information that travels with images (axes, dims, scale, physical pixel sizes, ...)."""


class DataType:
    """Base for the types of tool inputs and outputs."""

    pretty_name: ClassVar[str] = "Data"
    pytypes: ClassVar[tuple[str, ...]] = ()  # "module.Class" of the accepted classes
    kind: ClassVar[str] = "data"  # names the type in save options, e.g. "table"
    # how values are saved as files (flim.core.saving); None: they are pickled
    save_options: ClassVar[Optional[type[SaveOptions]]] = None

    @classmethod
    def save(cls, value: Any, base: str | Path, options: SaveOptions) -> Path:
        """Save a value as a file.

        Args:
            value: The value.
            base: The path without the file ending, which the format adds.
            options: The format and its options (`save_options`).

        Returns:
            The file written.
        """
        raise NotImplementedError(f"{cls.pretty_name} values cannot be saved as files")

    @classmethod
    def snapshot(cls, value: Any) -> Any:
        """Return a value for a run that later edits of `value` do not change.

        The default returns `value` itself, for values that are not edited in place.
        """
        return value

    @classmethod
    def python_classes(cls) -> tuple[type, ...]:
        """The accepted classes whose top-level package is already imported.

        A value can only be an instance of a class whose package has been imported, so
        classes of packages that are not loaded are skipped; their modules are not
        imported.
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
    kind = "table"
    save_options = TableSaveOptions

    @classmethod
    def snapshot(cls, value):
        """A copy: a table window can change its table while a run reads it."""
        return value.copy(deep=True)

    @classmethod
    def save(cls, value, base, options: TableSaveOptions) -> Path:
        """Save a table without the row index (#119); line breaks in column names
        (headers of several lines joined into one name) become spaces."""
        from flim.core.saving import write_table

        path = Path(f"{base}{options.extension}")
        write_table(value, path, options)
        return path


class PlotType(DataType):
    pretty_name = "Plot"
    pytypes = ("matplotlib.figure.Figure",)
    kind = "plot"
    save_options = PlotSaveOptions

    @classmethod
    def save(cls, value, base, options: PlotSaveOptions) -> Path:
        """Save a figure with matplotlib's `savefig`; `dpi` for png only."""
        path = Path(f"{base}{options.extension}")
        kwargs = {"dpi": options.dpi} if options.format == "png" else {}
        value.savefig(path, format=options.format, **kwargs)
        return path


class ImageType(DataType):
    pretty_name = "Image"
    pytypes = ("numpy.ndarray", "dask.array.Array", "torch.Tensor")
    kind = "image"


class FileType(DataType):
    pretty_name = "File"
    pytypes = ("pathlib.Path",)
    kind = "file"

    @classmethod
    def save(cls, value, base, options=None) -> Path:
        """Copy the file as it is, keeping its ending."""
        import shutil

        source = Path(value)
        path = Path(f"{base}{source.suffix}")
        shutil.copy2(source, path)
        return path


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
    many: bool = (
        False  # a dict of named values of this type, e.g. tables to concatenate
    )


@dataclass(frozen=True)
class OutputSpec:
    """A result a tool produces."""

    name: str
    type: type[DataType]
    description: str = ""
    schema: Any = None  # flim.core.schema.TableSchema of a table, if known

    @property
    def display_name(self) -> str:
        return self.type.display_name(self.name)
