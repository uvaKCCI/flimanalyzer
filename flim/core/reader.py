"""Reading data files into tables: the same in the GUI and in batch mode.

Each file becomes one table, with the columns of the file and `Source` (the file as
a URI), `Directory` and `File` (deprecated: `Source` replaces them). Nothing else is
done to the data: renaming, dropping, calculating, categories from file names and
joining the tables are steps of a workflow. The one exception is the column type of
columns with known category names (`Treatment`, `FOV`, ...): they are read as text,
so values such as `01` keep their leading zero, and become categories, because saved
text tables don't keep their column types.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from flim.core.columns import CLASH_TEMPLATE, make_room, unique_name

logger = logging.getLogger(__name__)

SOURCE, DIRECTORY, FILE = "Source", "Directory", "File"
ADDED = (SOURCE, DIRECTORY, FILE)  # the columns the reader adds, first
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
    """How data files are read (the settings of the readers, Open Tables and Import
    Tables)."""

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
        " endings, for example .txt, .csv. Files chosen one by one are read whatever"
        " their ending.",
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

    @field_validator("extensions")
    @classmethod
    def _dotted(cls, extensions: list[str]) -> list[str]:
        """Return the endings in lower case with a leading dot (`TXT` -> `.txt`)."""
        return ["." + e.strip().lstrip(".").lower() for e in extensions if e.strip().lstrip(".")]


def source_uri(path) -> str:
    """The URI of a data file, e.g. ``file:///data/9SR/Results-a-Dox15_01.txt``."""
    return Path(path).resolve().as_uri()


def is_uri(value) -> bool:
    """Whether a value is a well-formed URI: a scheme of two or more characters (not
    a Windows drive letter), a colon, and no spaces, e.g. ``file:///data/a.txt``."""
    return isinstance(value, str) and bool(_URI.match(value))


def find_files(paths, settings: Optional[ReadSettings] = None) -> tuple[list[Path], dict]:
    """Return the data files among files and folders (with their subfolders).

    Args:
        paths: Files and folders.
        settings: The file types and the file names to leave out.

    Returns:
        The files, sorted, each once; and why a path was skipped, by path.
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
                skipped[str(file)] = "left out"
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
    """

    tables: dict = field(default_factory=dict)
    skipped: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def read_file(path, settings: Optional[ReadSettings] = None, nrows=None) -> tuple:
    """Read one data file into a table.

    Args:
        path: The file.
        settings: How to read it.
        nrows: Read only this many rows (e.g. 0: the header only).

    Returns:
        The table, and warnings (e.g. a renamed column).

    Raises:
        ValueError: If the file can't be read as a table.
    """
    settings = settings or ReadSettings()
    path = Path(path)
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


def read_tables(paths, settings: Optional[ReadSettings] = None, nrows=None) -> Reading:
    """Read data files and folders, one table per file.

    A file that can't be read is skipped and named in `skipped`; the others are read.

    Args:
        paths: Files and folders (with their subfolders).
        settings: How to read them.
        nrows: Read only this many rows of each file (0: the headers only).

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
        name = unique_name(file.name, file.name, reading.tables)
        reading.tables[name] = table
        reading.warnings += warnings
    for path, reason in reading.skipped.items():
        logger.info(f"Not read: {path}: {reason}")
    return reading
