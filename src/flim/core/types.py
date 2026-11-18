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
    def content_hash(cls, value: Any) -> Optional[str]:
        """Return the SHA-256 of a value's content, which identifies it in a run.

        The hash depends on what the value holds, not on how it is stored in memory
        or pickled (see `flim.core.hashing`). The default returns None: values of
        this type are not hashed. Types of plugins override it to have their values
        identified in the run summary.

        Args:
            value: A value of this type.

        Returns:
            The hash, 64 hex digits; None if the value is not hashed.
        """
        return None

    @classmethod
    def describe(cls, value: Any) -> dict[str, str]:
        """Return how a value is listed in the run summary's `Inputs` table.

        Args:
            value: A value of this type.

        Returns:
            `identity` (for an object, its class, e.g. `pandas.DataFrame`), `size`
            (its size or shape), `type` (e.g. its dtype) and `details`; empty texts
            where there is nothing to say. The default gives only the class.
        """
        return {"identity": class_path(value), "size": "", "type": "", "details": ""}

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
    def content_hash(cls, value: Any) -> Optional[str]:
        """Return the SHA-256 of a table's shape, columns, dtypes, index and values.

        See `flim.core.hashing.table_hash`.

        Args:
            value: The DataFrame or Series.

        Returns:
            The hash, 64 hex digits.
        """
        from flim.core.hashing import table_hash

        return table_hash(value)

    @classmethod
    def describe(cls, value: Any) -> dict[str, str]:
        """Return a table's class, shape, dtypes and columns by role.

        Args:
            value: The DataFrame or Series.

        Returns:
            For example `pandas.DataFrame`, `34 rows x 10 cols`, `float64 (8),
            category (2)` and `categories: Treatment (2), FOV (2); 8 features; 0
            missing`.
        """
        import pandas as pd

        from flim.core.schema import TableSchema

        table = value.to_frame() if isinstance(value, pd.Series) else value
        counts = table.dtypes.astype(str).value_counts()
        types = ", ".join(f"{t} ({n})" for t, n in counts.items())
        schema = TableSchema.from_frame(table)
        parts = []
        categories = [c for c in schema.columns if c.role == "category"]
        if categories:
            parts.append(
                "categories: " + ", ".join(f"{c.name} ({len(c.levels or [])})" for c in categories)
            )
        parts.append(f"{len(schema.by_role('feature'))} features")
        others = schema.by_role("other")
        if others:
            parts.append(f"{len(others)} other columns")
        parts.append(f"{int(table.isna().sum().sum())} missing")
        rows, cols = table.shape
        return {
            "identity": class_path(value),
            "size": f"{rows} rows x {cols} cols",
            "type": types,
            "details": "; ".join(parts),
        }

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

    @classmethod
    def content_hash(cls, value: Any) -> Optional[str]:
        """Return the SHA-256 of an array's shape, dtype and values in C order.

        A Dask array is read a block of rows at a time; its chunks don't change the
        hash (see `flim.core.hashing.array_hash`).

        Args:
            value: The NumPy, Dask or PyTorch array.

        Returns:
            The hash, 64 hex digits.
        """
        from flim.core.hashing import array_hash

        return array_hash(value)

    @classmethod
    def describe(cls, value: Any) -> dict[str, str]:
        """Return an array's class, shape and dtype; its chunks or device.

        Args:
            value: The NumPy, Dask or PyTorch array.

        Returns:
            For example `dask.array.Array`, `3 x 256 x 256`, `uint16` and `chunks 1 x
            256 x 256`.
        """
        details = []
        chunks = getattr(value, "chunksize", None)  # a Dask array
        if chunks is not None:
            details.append("chunks " + " x ".join(str(int(n)) for n in chunks))
        device = getattr(value, "device", None)  # a PyTorch tensor (NumPy: none)
        if device is not None and type(value).__module__.startswith("torch"):
            details.append(f"device {device}")
        return {
            "identity": class_path(value),
            "size": " x ".join(str(int(n)) for n in value.shape),
            "type": str(value.dtype),
            "details": "; ".join(details),
        }


class FileType(DataType):
    """Files, as paths."""

    pretty_name = "File"
    pytypes = ("pathlib.Path",)
    kind = "file"

    @classmethod
    def content_hash(cls, value: Any) -> Optional[str]:
        """Return the SHA-256 of a file's bytes, as `sha256sum` gives it.

        Args:
            value: The path of the file.

        Returns:
            The hash, 64 hex digits; None if the path is not a file.
        """
        from flim.core.hashing import file_hash

        path = Path(value)
        return file_hash(path) if path.is_file() else None

    @classmethod
    def describe(cls, value: Any) -> dict[str, str]:
        """Return a file's path, size, format (its extension) and modification time.

        Args:
            value: The path of the file.

        Returns:
            For example `/data/a.txt`, `28.0 kB`, `txt` and `modified 2026-11-17
            09:12:04`.
        """
        import datetime

        path = Path(value).absolute()
        if not path.is_file():
            return {"identity": str(path), "size": "", "type": "", "details": "not a file"}
        info = path.stat()
        modified = datetime.datetime.fromtimestamp(info.st_mtime)
        return {
            "identity": str(path),
            "size": file_size(info.st_size),
            "type": path.suffix.lstrip(".") or "-",
            "details": f"modified {modified:%Y-%m-%d %H:%M:%S}",
        }

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


def class_path(value: Any) -> str:
    """Return a value's class as `<package>.<class>`, e.g. `pandas.DataFrame`."""
    cls = type(value)
    package = cls.__module__.split(".")[0]
    # the public names, e.g. dask.array.Array (module dask.array.core)
    known = {"pandas": "pandas", "numpy": "numpy", "torch": "torch"}
    if package == "dask" and cls.__name__ == "Array":
        return "dask.array.Array"
    return f"{known.get(package, cls.__module__)}.{cls.__name__}"


def file_size(size: int) -> str:
    """Return a size in bytes as text, e.g. `512 B`, `28.0 kB`, `1.4 MB` (powers of 1000)."""
    value = float(size)
    for unit in ("B", "kB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} TB"


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
