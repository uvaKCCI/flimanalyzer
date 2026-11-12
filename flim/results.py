#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Writes analysis results (tables, figures, other objects) to files."""
import os
import logging
import matplotlib.figure
import pandas as pd
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from joblib import dump

if TYPE_CHECKING:
    from flim.core.saving import SaveOptions

logger = logging.getLogger(__name__)


def clean_path_component(name: str) -> str:
    r"""Return a result or tag name changed for use as a file or folder name.

    `%` becomes `pcent`; carriage returns are removed; line breaks become spaces;
    `|`, `/` and `\` become `_`; and a `:` with the whitespace character after it,
    if any, becomes `_`.

    Args:
        name: The name; other values are converted with `str`.

    Returns:
        The changed name.
    """
    name = (
        str(name)
        .replace("%", "pcent")
        .replace("\r", "")
        .replace("\n", " ")
        .replace("|", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )
    return re.sub(r":\s?", "_", name)


def write_table(
    table: pd.DataFrame, path: str | os.PathLike, index: bool = False
) -> None:
    """Write a table as tab-separated text (see `flim.core.saving.write_table`).

    Args:
        table: The table.
        path: The file, with its ending.
        index: Whether to write the row index. Defaults to False.
    """
    from flim.core.saving import write_table as write

    write(table, path, index=index)


def save_results(
    results: Any,
    directory: str | os.PathLike,
    name: str,
    formats: Sequence["SaveOptions"] = (),
) -> None:
    """Save a tool's results in `directory`.

    The result without its figures is pickled to `<directory>/pickled/<name>`
    (nothing is pickled if no other value remains), for reloading results. If the
    result is a dict, each value is also saved as `<key>` with its data type's
    writer, in the formats for its kind (`flim.core.saving.save_value`): tables
    tab-separated as `<key>.txt` and figures as `<key>.png` by default. Values of no
    data type with a writer are pickled as `<key>`. Names and keys are changed for
    use as file names (see `clean_path_component`).

    Figures are not pickled: pickling them is slow for figures with many points, and
    the pickles only work with the matplotlib version that wrote them.

    Args:
        results: The tool's result, usually a dict of tables and figures.
        directory: The target folder, created if it does not exist.
        name: The name of the task that produced the results.
        formats: The formats (`AutosaveConfig.formats`); a kind not listed is saved
            in its default format.
    """
    from flim.core.saving import save_value

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
        dump(to_pickle, os.path.join(pickledir, clean_path_component(name)))
    if not isinstance(results, dict):
        return
    for k, v in results.items():
        basename = os.path.join(directory, clean_path_component(k))
        if not save_value(v, basename, list(formats)):
            dump(v, basename)
