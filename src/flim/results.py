#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Writes analysis results (tables, figures, other objects) to files."""
import os
import logging
import matplotlib.figure
import pandas as pd
from collections.abc import Sequence
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

from joblib import dump

if TYPE_CHECKING:
    from flim.core.saving import SaveOptions

logger = logging.getLogger(__name__)


def clean_path_component(name: str) -> str:
    """Return a name as a file or folder name (deprecated: `flim.core.paths.path_name`).

    Deprecated in 0.7.0, removed in 0.8.0: FLIMAnalyzer names files and folders with
    one rule, `flim.core.paths.path_name`, which this function now calls.

    Args:
        name: The name; other values are converted with `str`.

    Returns:
        The name as `path_name` returns it.
    """
    import warnings

    from flim.core.paths import path_name

    warnings.warn(
        "flim.results.clean_path_component is deprecated and is removed in 0.8.0;"
        " use flim.core.paths.path_name",
        DeprecationWarning,
        stacklevel=2,
    )
    return path_name(name)


def write_table(
    table: pd.DataFrame, path: str | os.PathLike, index: bool = False
) -> None:
    """Write a table as tab-separated text (see `flim.core.saving.write_table`).

    Args:
        table: The table.
        path: The file, with its extension.
        index: Whether to write the row index. Defaults to False.
    """
    from flim.core.saving import write_table as write

    write(table, path, index=index)


def save_results(
    results: Any,
    directory: str | os.PathLike,
    name: str,
    formats: Sequence["SaveOptions"] = (),
    replacements: Optional[Mapping[str, str]] = None,
) -> None:
    """Save a tool's results in `directory`.

    The result without its figures is pickled to `<directory>/pickled/<name>`
    (nothing is pickled if no other value remains), for reloading results. If the
    result is a dict, each value is also saved as `<key>` with its data type's
    writer, in the formats for its kind (`flim.core.saving.save_value`): tables
    tab-separated as `<key>.txt` and figures as `<key>.png` by default. Values of no
    data type with a writer are pickled as `<key>`. Names and keys become file names
    with `flim.core.paths.path_name`.

    Figures are not pickled: pickling them is slow for figures with many points, and
    the pickles only work with the matplotlib version that wrote them.

    Args:
        results: The tool's result, usually a dict of tables and figures.
        directory: The target folder, created if it does not exist.
        name: The name of the task that produced the results.
        formats: The formats (`AutosaveConfig.formats`); a kind not listed is saved
            in its default format.
        replacements: The character replacements of the file names (the task's
            `output.char_replacements`, passed on to a task on a Dask worker); None
            for the defaults (`DEFAULT_CHAR_REPLACEMENTS`).

    Raises:
        ValueError: If two keys become the same file name (ignoring case); nothing
            is saved then.
    """
    from flim.core.paths import path_name, same_names
    from flim.core.saving import save_value

    if isinstance(results, dict):
        clashes = same_names(results, replacements)
        if clashes:
            raise ValueError(
                "results with the same file name: "
                + "; ".join(f"'{a}' and '{b}'" for a, b in clashes)
            )

    os.makedirs(directory, exist_ok=True)
    logger.debug(f"Saving results of {name} to {directory}")
    if isinstance(results, dict):
        to_pickle = {
            k: v for k, v in results.items() if not isinstance(v, matplotlib.figure.Figure)
        }
    else:
        to_pickle = None if isinstance(results, matplotlib.figure.Figure) else results
    if to_pickle is not None and not (isinstance(to_pickle, dict) and not to_pickle):
        pickledir = os.path.join(directory, "pickled")
        os.makedirs(pickledir, exist_ok=True)
        dump(to_pickle, os.path.join(pickledir, path_name(name, replacements)))
    if not isinstance(results, dict):
        return
    for k, v in results.items():
        basename = os.path.join(directory, path_name(k, replacements))
        if not save_value(v, basename, list(formats)):
            dump(v, basename)
