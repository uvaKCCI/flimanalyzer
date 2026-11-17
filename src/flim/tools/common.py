"""Helpers shared by the tools."""

from collections.abc import Iterable
from typing import Callable, Optional, Union

import numpy as np
import pandas as pd

from flim.core.types import OutputSpec


def category_columns(data: pd.DataFrame) -> list[str]:
    """Return the names of the category columns, in table order."""
    return list(data.select_dtypes("category").columns.values)


def ordered_values(column: pd.Series) -> list[str]:
    """Return the values that occur in a column, as strings, without missing values.

    Args:
        column: The column.

    Returns:
        The values in the order of the column's categories (see Order Category Values) if
        it is a category column, else in the order they first occur.
    """
    present = set(column.dropna().unique())
    if isinstance(column.dtype, pd.CategoricalDtype):
        return [str(v) for v in column.cat.categories if v in present]
    return [str(v) for v in column.dropna().unique()]


def feature_columns(data: pd.DataFrame) -> list[str]:
    """Return the names of the numeric columns; category columns are never numeric."""
    return list(data.select_dtypes(np.number).columns.values)


def selected_features(
    data: pd.DataFrame, features: Union[Iterable[str], str]
) -> list[str]:
    """Return the feature columns a config selects.

    Args:
        data: The table.
        features: A list of column names, a dict of per-feature settings keyed by
            column name, or `all`.

    Returns:
        The names in the list or the dict's keys; for `all`, every numeric column of
        `data`.
    """
    return feature_columns(data) if features == "all" else list(features)


def categories_first(data: pd.DataFrame) -> pd.DataFrame:
    """Return `data` with its category columns first, otherwise in the same order."""
    categories = category_columns(data)
    return data[categories + [c for c in data.columns if c not in categories]]


def set_lineage(
    outputs: dict[str, OutputSpec], source: Callable[[str], Optional[str]]
) -> dict[str, OutputSpec]:
    """Record the input column that each output column is derived from.

    The outputs are changed in place. Outputs without a complete table schema are
    left unchanged.

    Args:
        outputs: The outputs, keyed by name.
        source: Returns the input column a column is derived from, given the column's
            name; None keeps the column's own lineage.

    Returns:
        `outputs`.
    """
    for output in outputs.values():
        schema = output.schema
        if schema is None or not schema.complete:
            continue
        columns = []
        for c in schema.columns:
            origin = source(c.name)
            columns.append(
                c.model_copy(update={"derived_from": [origin]}) if origin else c
            )
        schema.columns = columns
    return outputs


def first_line(name: str) -> Optional[str]:
    r"""Return the feature of a pivoted or summary column: the first line of its name.

    Args:
        name: The column name, e.g. `FLIRR\nmean`.

    Returns:
        The first line, e.g. `FLIRR`; None for a name of one line.
    """
    return name.split("\n")[0] if "\n" in name else None


def missing_group_message(
    data: pd.DataFrame, columns: Iterable[str], kind: str = "grouping"
) -> Optional[str]:
    """Return a warning about the rows that a grouping leaves out; None if none.

    pandas leaves out of a grouping each row with a missing value in one of the
    grouping columns.

    Args:
        data: The table.
        columns: The grouping columns.
        kind: The role of the columns in the message, e.g. `grouping` or `category`.
            Defaults to `grouping`.

    Returns:
        For example `3 rows left out: no value in the grouping column 'FOV'`; None
        if every row has a value in all the columns.
    """
    columns = list(columns)
    if not columns:
        return None
    missing = data[columns].isna()
    count = int(missing.any(axis=1).sum())
    if count == 0:
        return None
    named = [c for c in columns if missing[c].any()]
    rows = "1 row" if count == 1 else f"{count} rows"
    noun = f"{kind} column" if len(named) == 1 else f"{kind} columns"
    listed = ", ".join(f"'{c}'" for c in named)
    return f"{rows} left out: no value in the {noun} {listed}"
