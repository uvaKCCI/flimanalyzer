"""Types of tool inputs and outputs.

Each type knows the Python classes it accepts (`pytypes`) and a `pretty_name` used
to display results, so tools never hardcode names such as `"Table: ..."`. The classes
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
            base: The path without the file extension, which the format adds.
            options: The format and its options (`save_options`).

        Returns:
            The file written.

        Raises:
            NotImplementedError: If values of this type cannot be saved as files (the
                default).
        """
        raise NotImplementedError(f"{cls.pretty_name} values cannot be saved as files")

    @classmethod
    def snapshot(cls, value: Any) -> Any:
        """Return a value for a run that later edits of `value` do not change.

        The default returns `value` itself, for values that are not edited in place.

        Args:
            value: A value of this type.

        Returns:
            The value for the run.
        """
        return value

    @classmethod
    def python_classes(cls) -> tuple[type, ...]:
        """Return the accepted classes whose top-level package is already imported.

        A value can only be an instance of a class whose package has been imported, so
        classes of packages that are not loaded are skipped; their modules are not
        imported. Classes that cannot be imported are skipped too.
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
        """Return whether `value` is an instance of one of the accepted classes."""
        return isinstance(value, cls.python_classes())

    @classmethod
    def display_name(cls, name: str) -> str:
        """Return how a result of this type is shown, e.g. `Table: Summary`."""
        return f"{cls.pretty_name}: {name}"

    @staticmethod
    def of(value: Any) -> Optional[type["DataType"]]:
        """Return the most specific type that accepts `value`, or None if none does."""
        matches = [t for t in _all_types() if t.accepts(value)]
        if not matches:
            return None
        return max(matches, key=lambda t: len(t.__mro__))


class TableType(DataType):
    """Tables: pandas DataFrames and Series."""

    pretty_name = "Table"
    pytypes = ("pandas.DataFrame", "pandas.Series")
    kind = "table"
    save_options = TableSaveOptions

    @classmethod
    def snapshot(cls, value: Any) -> Any:
        """Return a deep copy: a table window can change its table during a run."""
        return value.copy(deep=True)

    @classmethod
    def save(cls, value: Any, base: str | Path, options: TableSaveOptions) -> Path:
        """Save a table as text, without the row index (#119).

        Line breaks in column names (headers of several lines joined into one name)
        become spaces.

        Args:
            value: The DataFrame or Series.
            base: The path without the file extension, which the format adds.
            options: The format (e.g. tab- or comma-separated).

        Returns:
            The file written.
        """
        from flim.core.saving import write_table

        path = Path(f"{base}{options.extension}")
        write_table(value, path, options)
        return path


class PlotType(DataType):
    """Plots: matplotlib figures."""

    pretty_name = "Plot"
    pytypes = ("matplotlib.figure.Figure",)
    kind = "plot"
    save_options = PlotSaveOptions

    @classmethod
    def save(cls, value: Any, base: str | Path, options: PlotSaveOptions) -> Path:
        """Save a figure with matplotlib's `savefig`.

        Args:
            value: The figure.
            base: The path without the file extension, which the format adds.
            options: The format and, used for png only, the resolution (`dpi`).

        Returns:
            The file written.
        """
        path = Path(f"{base}{options.extension}")
        kwargs = {"dpi": options.dpi} if options.format == "png" else {}
        value.savefig(path, format=options.format, **kwargs)
        return path


class ImageType(DataType):
    """Images: NumPy, Dask and PyTorch arrays."""

    pretty_name = "Image"
    pytypes = ("numpy.ndarray", "dask.array.Array", "torch.Tensor")
    kind = "image"


class FileType(DataType):
    """Files, as paths."""

    pretty_name = "File"
    pytypes = ("pathlib.Path",)
    kind = "file"

    @classmethod
    def save(
        cls, value: Any, base: str | Path, options: Optional[SaveOptions] = None
    ) -> Path:
        """Copy the file as it is, keeping its extension.

        Args:
            value: The path of the file.
            base: The path of the copy without the file extension.
            options: Not used.

        Returns:
            The copy.
        """
        import shutil

        source = Path(value)
        path = Path(f"{base}{source.suffix}")
        shutil.copy2(source, path)
        return path


def _all_types() -> list[type[DataType]]:
    """Return all subclasses of `DataType`, including indirect ones."""
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
        """The name shown for the result.

        For example `Table: Summary`.
        """
        return self.type.display_name(self.name)
