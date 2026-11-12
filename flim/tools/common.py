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
        The values in the order of the column's categories (see Order Categories) if
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
