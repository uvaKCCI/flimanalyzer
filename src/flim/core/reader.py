"""Reading data files into tables: the same in the GUI and in batch mode.

Each file becomes one table, with the columns of the file and `Source` (the file as
a URI), `Directory` and `File` (deprecated, removed in 0.8.0: `Source` replaces
them). Nothing else is
done to the data: renaming, dropping, calculating, categories from file names and
joining the tables are steps of a workflow. The one exception is the column type of
columns with known category names (`Treatment`, `FOV`, ...): they are read as text,
so values such as `01` keep their leading zero, and become categories, because saved
text tables don't keep their column types.
"""

import codecs
import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from flim.core.columns import CLASH_TEMPLATE, make_room, unique_name

logger = logging.getLogger(__name__)

SOURCE, DIRECTORY, FILE = "Source", "Directory", "File"
ADDED = (SOURCE, DIRECTORY, FILE)  # the columns the reader adds, first
LEFT_OUT = "left out"  # why a file in `exclude` was skipped
READER = "Read"  # the reader's name in renamed columns, e.g. "Source (before Read)"

# column names read as categories (the category columns of FLIMAnalyzer's tables)
KNOWN_CATEGORIES = (
    "AE Label", "Cat", "Category", "Cell", "Cell line", "Cluster", "Combined",
    "Compartment", "FOV", "New Cat", "Origin", "Time", "Treatment", "Treatment 1",
    "Treatment 1 & 2", "Treatment 2", "Well",
    "Cell line-Cell", "Cell line-Compartment", "Cell line-FOV", "Cell line-Treatment",
    "Compartment-Cell", "Compartment-FOV", "Compartment-Treatment", "FOV-Cell",
    "FOV-Time", "FOV-Treatment", "FOV-Well", "Time-Well", "Treatment-Cell",
    "Treatment-FOV", "Treatment-Time",
)  # fmt: skip

_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:\S+$")  # a scheme of 2+ characters


class ReadSettings(BaseModel):
    """How data files are read.

    The settings of the readers, of Open Tables and of Import Tables.
    """

    delimiter: str = Field(
        default="\t,",
        title="Column delimiters",
        description="Each of these characters separates columns; \\t is a tab.",
        json_schema_extra={"escapes": True},
    )
    extensions: list[str] = Field(
        default=[".txt", ".csv"],
        title="Files to include",
        description="In folders (given with -i, or to flimbatch): the files with these"
        " extensions, for example .txt, .csv. Files chosen one by one are read whatever"
        " their extension.",
        json_schema_extra={"words": True},
    )
    encoding: str = Field(
        default="utf-8", title="Text encoding", description="For example utf-8 or latin-1."
    )
    exclude: list[str] = Field(
        default=[],
        title="Files to exclude",
        description="File names without folder, for example Results_old.txt.",
        json_schema_extra={"words": True},
    )
    existing: Literal["keep", "rename"] = Field(
        default="keep",
        title="File's own Source, Directory, File",
        description="A file's own Source, Directory or File column: keep (Source only"
        " if its values are URIs) or rename it.",
    )
    clash_name: str = Field(
        default=CLASH_TEMPLATE,
        title="Name of renamed column",
        description="{name} is the column's name, {tool} the reader's short name (Read).",
    )

    @field_validator("encoding")
    @classmethod
    def _known_encoding(cls, encoding: str) -> str:
        """Return the encoding if it is a known text encoding.

        Raises:
            ValueError: If Python has no text encoding of this name.
        """
        problem = encoding_problem(encoding)
        if problem:
            raise ValueError(problem)
        return encoding

    @field_validator("extensions")
    @classmethod
    def _dotted(cls, extensions: list[str]) -> list[str]:
        """Return the extensions in lower case with a leading dot (`TXT` -> `.txt`)."""
        return ["." + e.strip().lstrip(".").lower() for e in extensions if e.strip().lstrip(".")]


def encoding_problem(encoding: str) -> Optional[str]:
    """Return why a text encoding can't be used to read files; None if it can.

    Args:
        encoding: The name of the encoding, e.g. `utf-8` or `latin-1`.

    Returns:
        The message, or None if Python has a text encoding of this name.
    """
    try:
        info = codecs.lookup(encoding)
    except LookupError:
        info = None
    # codecs.lookup also finds codecs from bytes to bytes, e.g. base64
    if info is None or not getattr(info, "_is_text_encoding", True):
        return f"unknown text encoding '{encoding}'; for example utf-8 or latin-1"
    return None


def source_uri(path: Union[str, os.PathLike]) -> str:
    """Return the URI of a data file, e.g. `file:///data/9SR/Results-a-Dox15_01.txt`.

    Args:
        path: The file; a relative path is resolved against the working directory.

    Returns:
        The `file` URI of the absolute path, with symbolic links resolved.
    """
    return Path(path).resolve().as_uri()


def is_uri(value: Any) -> bool:
    """Return whether a value is a well-formed URI, e.g. `file:///data/a.txt`.

    A well-formed URI is a text with a scheme of two or more characters (so that a
    Windows drive letter is not a scheme), a colon, and no white space.

    Args:
        value: The value; values other than texts are not URIs.

    Returns:
        True if the value is a well-formed URI.
    """
    return isinstance(value, str) and bool(_URI.match(value))


def find_files(
    paths: Iterable[Union[str, os.PathLike]], settings: Optional[ReadSettings] = None
) -> tuple[list[Path], dict[str, str]]:
    """Return the data files among files and folders (with their subfolders).

    A file given directly is taken whatever its extension; in folders, only the files
    with one of `settings.extensions` (in any letter case) are taken. Files named in
    `settings.exclude` are left out.

    Args:
        paths: Files and folders; relative paths are resolved against the working
            directory.
        settings: The file extensions and the file names to leave out. Defaults to
            `ReadSettings()`.

    Returns:
        The absolute paths of the files, sorted, each once; and why a path was
        skipped (`not found`, or `LEFT_OUT`), by path.
    """
    settings = settings or ReadSettings()
    extensions = tuple(e.lower() for e in settings.extensions)
    found, skipped = [], {}
    for path in (Path(os.path.abspath(p)) for p in paths):
        if path.is_dir():
            candidates = [p for p in path.rglob("*") if p.is_file()]
            candidates = [p for p in candidates if p.suffix.lower() in extensions]
        elif path.is_file():
            candidates = [path]
        else:
            skipped[str(path)] = "not found"
            continue
        for file in candidates:
            if file.name in settings.exclude:
                skipped[str(file)] = LEFT_OUT
            else:
                found.append(file)
    return sorted(dict.fromkeys(found)), skipped


@dataclass
class Reading:
    """The result of `read_tables`.

    Attributes:
        tables: One table per file, by name (the file name; numbered if two files
            have the same name).
        skipped: Why a file was not read, by path.
        warnings: Messages for the user, e.g. renamed columns.
        files: The file each table was read from, by the table's name.
    """

    tables: dict = field(default_factory=dict)
    skipped: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    files: dict = field(default_factory=dict)


def read_file(
    path: Union[str, os.PathLike],
    settings: Optional[ReadSettings] = None,
    nrows: Optional[int] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Read one data file into a table.

    The table gets the columns `Source`, `Directory` and `File`, first. With
    `settings.existing` `keep`, a file's own `Directory` and `File` columns are kept,
    and its own `Source` column if all its values are URIs; other columns of these
    names are renamed with `settings.clash_name`. Columns of `KNOWN_CATEGORIES` are
    read as text and become categories.

    Args:
        path: The file.
        settings: How to read it. Defaults to `ReadSettings()`.
        nrows: Read only this many rows (e.g. 0: the header only); None reads all
            rows.

    Returns:
        The table, and warnings (e.g. a renamed column).

    Raises:
        ValueError: If the file can't be read as a table, or not with the encoding,
            or the encoding is unknown.
        OSError: If the file can't be opened.
    """
    settings = settings or ReadSettings()
    path = Path(path)
    if problem := encoding_problem(settings.encoding):  # e.g. a model not validated
        raise ValueError(f"{path.name}: {problem}")
    delimiter = "|".join(re.escape(d) for d in settings.delimiter) or None
    try:
        table = pd.read_csv(
            path,
            sep=delimiter,
            engine="python",
            dtype={c: "object" for c in KNOWN_CATEGORIES},
            nrows=nrows,
            encoding=settings.encoding,
        )
    except (pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as err:
        raise ValueError(f"{path.name}: not a readable table ({err})") from None
    warnings = []
    values = {SOURCE: source_uri(path), DIRECTORY: str(path.parent), FILE: path.name}
    if settings.existing == "keep":
        own = [c for c in (DIRECTORY, FILE) if c in table.columns]
        if SOURCE in table.columns:
            sources = table[SOURCE].dropna()
            if sources.map(is_uri).all():
                own.append(SOURCE)  # provenance of a table saved by FLIMAnalyzer
        for column in own:
            values.pop(column)
    renames = make_room(table.columns, list(values), settings.clash_name, tool=READER)
    if renames:
        table = table.rename(columns=renames)
        for old, new in renames.items():
            warnings.append(f"{path.name}: the column '{old}' is renamed '{new}'")
    for column in KNOWN_CATEGORIES:
        if column in table.columns:
            table[column] = table[column].astype("category")
    for column, value in values.items():
        table[column] = value
    first = [c for c in ADDED if c in table.columns]
    return table[first + [c for c in table.columns if c not in first]], warnings


def read_tables(
    paths: Iterable[Union[str, os.PathLike]],
    settings: Optional[ReadSettings] = None,
    nrows: Optional[int] = None,
) -> Reading:
    """Read data files and folders, one table per file.

    A file that can't be read (`read_file` raises `ValueError` or `OSError`, e.g.
    permission denied) is skipped and named in `skipped`, with the reason; the others
    are read.

    Args:
        paths: Files and folders (with their subfolders; see `find_files`).
        settings: How to read them. Defaults to `ReadSettings()`.
        nrows: Read only this many rows of each file (0: the headers only); None
            reads all rows.

    Returns:
        The tables by name, the skipped paths and the warnings.
    """
    settings = settings or ReadSettings()
    files, skipped = find_files(paths, settings)
    reading = Reading(skipped=dict(skipped))
    for file in files:
        try:
            table, warnings = read_file(file, settings, nrows=nrows)
        except ValueError as err:
            reading.skipped[str(file)] = str(err)
            continue
        except OSError as err:  # e.g. permission denied
            reading.skipped[str(file)] = f"{file.name}: can't be opened ({err.strerror or err})"
            continue
        name = unique_name(file.name, file.name, reading.tables)
        reading.tables[name] = table
        reading.files[name] = Path(file)
        reading.warnings += warnings
    for path, reason in reading.skipped.items():
        logger.info(f"Not read: {path}: {reason}")
    return reading
