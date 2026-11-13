"""How results are saved as files: the save options of each data type, and autosave.

Each data type (flim.core.types) declares its save options and writes its values with
`DataType.save`, so autosave, the windows' save dialogs and flimbatch save a value the
same way. `AutosaveConfig` holds whether and where a run saves its results, and in
which formats.
"""

import logging
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializeAsAny,
    field_validator,
    model_validator,
)

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


class SaveOptions(BaseModel):
    """Base of the save options of a data type: the format and its options.

    `kind` names the data type (e.g. `table`); each subclass fixes it and lists its
    formats. `extensions` maps a format to the file extension it is saved with.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    format: str
    extensions: ClassVar[dict[str, str]] = {}

    @property
    def extension(self) -> str:
        """Return the file extension of the format, e.g. `.txt`."""
        return self.extensions[self.format]


class TableSaveOptions(SaveOptions):
    """Tables: tab-separated (`tsv`, saved as `.txt`, the default) or `csv`."""

    kind: Literal["table"] = "table"
    format: Literal["tsv", "csv"] = Field(default="tsv", title="Format")
    extensions: ClassVar[dict[str, str]] = {"tsv": ".txt", "csv": ".csv"}

    @property
    def separator(self) -> str:
        """Return the column separator of the format: a tab or a comma."""
        return "\t" if self.format == "tsv" else ","


class PlotSaveOptions(SaveOptions):
    """Plots: `png` (default), `svg` or `pdf`; `dpi` applies to `png` only."""

    kind: Literal["plot"] = "plot"
    format: Literal["png", "svg", "pdf"] = Field(default="png", title="Format")
    dpi: Optional[int] = Field(default=300, ge=1, title="Resolution (dpi)")
    extensions: ClassVar[dict[str, str]] = {"png": ".png", "svg": ".svg", "pdf": ".pdf"}

    @model_validator(mode="before")
    @classmethod
    def _dpi_for_raster_only(cls, data: Any) -> Any:
        """Set `dpi` to None for the vector formats."""
        # vector formats have no resolution
        if isinstance(data, dict) and data.get("format", "png") != "png":
            return {**data, "dpi": None}
        return data


def save_options_classes() -> dict[str, type[SaveOptions]]:
    """Return the save options of the registered data types (plugins' too), by kind."""
    from flim.core.types import _all_types

    return {t.kind: t.save_options for t in _all_types() if t.save_options is not None}


def _options(value: Any) -> SaveOptions:
    """Validate one entry of `formats` with the save options of its kind."""
    if isinstance(value, SaveOptions):
        return value
    if not isinstance(value, dict) or "kind" not in value:
        raise ValueError(f"{value!r}: an entry needs a kind, e.g. {{'kind': 'table'}}")
    classes = save_options_classes()
    if value["kind"] not in classes:
        known = ", ".join(sorted(classes))
        raise ValueError(f"unknown kind '{value['kind']}': use {known}")
    return classes[value["kind"]].model_validate(value)


class AutosaveConfig(BaseModel):
    """Whether and where a run saves its results, and in which formats.

    Attributes:
        enabled: Whether the results are saved.
        results_dir: The folder; None for the app's results folder.
        formats: The formats, per kind of output; a kind not listed is saved in its
            default format. Several formats of one kind are allowed (e.g. plots as png
            and svg); duplicates are dropped, and two entries of the same kind and
            format with different options are refused.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    results_dir: Optional[Path] = None
    formats: list[SerializeAsAny[SaveOptions]] = []

    @field_validator("formats", mode="before")
    @classmethod
    def _each_by_kind(cls, value: Any) -> list[SaveOptions]:
        """Validate each entry by its kind and drop duplicates."""
        if not isinstance(value, (list, tuple)):
            raise ValueError("formats must be a list")
        unique: dict[tuple[str, str], SaveOptions] = {}
        for options in (_options(v) for v in value):
            key = (options.kind, options.format)
            if key in unique and unique[key] != options:
                raise ValueError(
                    f"{options.kind} as {options.format} is listed twice with different"
                    " options"
                )
            unique[key] = options
        return list(unique.values())

    def formats_for(self, kind: str) -> list[SaveOptions]:
        """Return the formats a value of a kind is saved in.

        Args:
            kind: The data type's kind, e.g. `plot`.

        Returns:
            The listed formats of the kind, or its default format if none is listed;
            empty if the kind has no save options.
        """
        listed = [f for f in self.formats if f.kind == kind]
        if listed:
            return listed
        options = save_options_classes().get(kind)
        return [options()] if options is not None else []


def save_value(
    value: Any, base: str | Path, formats: Sequence[SaveOptions] = ()
) -> list[Path]:
    """Save a value with its data type's writer, in the formats for its kind.

    Args:
        value: The value, e.g. a DataFrame or a Figure.
        base: The path without the file extension.
        formats: The formats (`AutosaveConfig.formats`); defaults per kind.

    Returns:
        The files written; empty if no data type with save options accepts the value
        (a file, `FileType`, is copied as it is).
    """
    from flim.core.types import DataType

    from flim.core.types import FileType

    data_type = DataType.of(value)
    if data_type is FileType:
        return [FileType.save(value, base)]  # copied as it is
    if data_type is None or data_type.save_options is None:
        return []
    config = AutosaveConfig.model_construct(formats=list(formats))
    return [data_type.save(value, base, options) for options in config.formats_for(data_type.kind)]


def write_table(
    table: "pd.DataFrame | pd.Series",
    path: str | os.PathLike,
    options: Optional["TableSaveOptions"] = None,
    index: bool = False,
) -> None:
    """Write a table as text in a format.

    The row index is left out unless `index`: row numbers carry no meaning in
    FLIMAnalyzer's tables and are out of order after sorting (#119). Line breaks in
    column names (headers of several lines joined into one name) become spaces.

    Args:
        table: A DataFrame or Series.
        path: The file, with its extension.
        options: The format; None for tab-separated.
        index: Whether to write the row index. Defaults to False.
    """
    import pandas as pd

    options = options or TableSaveOptions()
    table = table.to_frame() if isinstance(table, pd.Series) else table
    table = table.rename(columns=lambda c: str(c).replace("\n", " "))
    table.to_csv(path, sep=options.separator, index=index)


def header_problems(columns: Iterable[Any], options: TableSaveOptions) -> list[str]:
    """Return why column names would not survive saving a table in a format.

    Args:
        columns: The column names.
        options: The format.

    Returns:
        One message per problem: names containing the format's separator, or line
        breaks (headers of several lines are joined into one line when saved).
    """
    problems = []
    separator = {"tsv": "a tab", "csv": "a comma"}[options.format]
    with_separator = [str(c) for c in columns if options.separator in str(c)]
    if with_separator:
        problems.append(f"{', '.join(with_separator)}: contains {separator}")
    if any("\n" in str(c) for c in columns):
        problems.append("headers of several lines are saved as one line")
    return problems


# --- the formats as fields of a dialog ---

KIND_TITLES = {"table": "Tables", "plot": "Plots", "image": "Images"}


def _choices(options: type[SaveOptions]) -> tuple[str, ...]:
    """Return the formats a save options class allows."""
    import typing

    return typing.get_args(options.model_fields["format"].annotation)


def formats_model(kinds: Iterable[str]) -> type[BaseModel]:
    """Return a model with the format fields of some kinds, for a dialog.

    Per kind: `<kind>_formats`, the formats to save in (several allowed), and the
    kind's other options as `<kind>_<option>` (e.g. `plot_dpi`).

    Args:
        kinds: The kinds, e.g. those of a tool's outputs.

    Returns:
        The model; its defaults are the kinds' default formats and options.

    Raises:
        KeyError: If a kind has no save options.
    """
    from pydantic import create_model

    classes = save_options_classes()
    fields = {}
    for kind in kinds:
        options = classes[kind]
        default = options()
        title = KIND_TITLES.get(kind, kind.capitalize())
        fields[f"{kind}_formats"] = (
            list[Literal[_choices(options)]],  # type: ignore[valid-type]
            Field(default=[default.format], title=title, description=f"Formats of {title.lower()}"),
        )
        for name, info in options.model_fields.items():
            if name in ("kind", "format"):
                continue
            fields[f"{kind}_{name}"] = (info.annotation, Field(default=getattr(default, name), title=info.title, description=info.description))
    return create_model("SaveFormats", **fields)


def formats_values(
    model: type[BaseModel], formats: Sequence[SaveOptions], kinds: Iterable[str]
) -> BaseModel:
    """Return the values of a `formats_model` for a list of formats.

    Kinds not in `formats` get their default format. Each of a kind's other options
    is taken from the first listed format of the kind that sets it (not None).

    Args:
        model: The model made by `formats_model`.
        formats: The formats, e.g. `AutosaveConfig.formats`.
        kinds: The kinds of the model.

    Returns:
        An instance of the model.
    """
    values = {}
    for kind in kinds:
        listed = [f for f in formats if f.kind == kind]
        if not listed:
            continue
        values[f"{kind}_formats"] = [f.format for f in listed]
        for name in type(listed[0]).model_fields:
            if name not in ("kind", "format"):
                value = next((getattr(f, name) for f in listed if getattr(f, name) is not None), None)
                if value is not None:
                    values[f"{kind}_{name}"] = value
    return model(**values)


def formats_from_values(
    values: dict[str, Any], kinds: Iterable[str]
) -> tuple[list[SaveOptions], dict[str, str]]:
    """Return the formats chosen in the fields of a `formats_model`.

    Args:
        values: The fields' values by name.
        kinds: The kinds of the model.

    Returns:
        The formats; and an error message per field name, e.g. for a kind without a
        format or with an option that is not valid.
    """
    classes = save_options_classes()
    formats, errors = [], {}
    for kind in kinds:
        chosen = values.get(f"{kind}_formats") or []
        if not chosen:
            errors[f"{kind}_formats"] = "Choose at least one format"
            continue
        options = {
            name: values.get(f"{kind}_{name}")
            for name in classes[kind].model_fields
            if name not in ("kind", "format") and f"{kind}_{name}" in values
        }
        for fmt in chosen:
            try:
                formats.append(classes[kind](format=fmt, **options))
            except Exception as err:  # e.g. a resolution below 1
                errors[f"{kind}_formats"] = str(err)
    return formats, errors


# --- saving several values at once (File > Save All Windows...) ---


def unique_file_names(titles: Iterable[str]) -> list[str]:
    """Return file names (without extensions) for titles, unique within the list.

    Titles are cleaned for file names (flim.results.clean_path_component) and
    compared ignoring case, as macOS and Windows do; a later duplicate gets `-2`, `-3`,
    ... added.

    Args:
        titles: The titles, e.g. of the open windows.

    Returns:
        One file name per title, in order; `untitled` for a title that is empty
        once cleaned.
    """
    from flim.results import clean_path_component

    names, taken = [], set()
    for title in titles:
        base = clean_path_component(title) or "untitled"
        name, number = base, 2
        while name.lower() in taken:
            name = f"{base}-{number}"
            number += 1
        taken.add(name.lower())
        names.append(name)
    return names


def save_all(
    entries: Iterable[tuple[str, Any]],
    folder: str | os.PathLike,
    formats: Iterable[SaveOptions] = (),
) -> tuple[Path, list[tuple[str, list[Path]]], list[tuple[str, str]]]:
    """Save several values into a new subfolder, never overwriting a file.

    The subfolder is named after the date and time, made unique as run folders are
    (flim.core.paths.unique_run_folder).

    Args:
        entries: (title, value) pairs, e.g. the open windows' tables and figures.
        folder: The folder to create the subfolder in.
        formats: The formats (`AutosaveConfig.formats`); defaults per kind.

    Returns:
        The subfolder; the saved entries as (title, files); the failed ones as
        (title, error message), also values that no data type can save.
    """
    import datetime

    from flim.core.paths import unique_run_folder

    entries = list(entries)
    target = unique_run_folder(folder, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    saved, failed = [], []
    for (title, value), name in zip(entries, unique_file_names(t for t, _ in entries)):
        try:
            files = save_value(value, target / name, list(formats))
        except Exception as err:
            logger.exception(f"Could not save {title}")
            failed.append((title, str(err)))
            continue
        if files:
            saved.append((title, files))
        else:
            failed.append((title, "this kind of result cannot be saved as a file"))
    return target, saved, failed
