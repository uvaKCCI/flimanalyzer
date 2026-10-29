"""Helpers shared by the tools."""

from typing import Callable, Optional

import numpy as np
import pandas as pd

from flim.core.types import OutputSpec


def category_columns(data: pd.DataFrame) -> list[str]:
    return list(data.select_dtypes("category").columns.values)


def ordered_values(column: pd.Series) -> list[str]:
    """The values that occur in a column, in the order of its categories (see Order
    Categories), else in the order they occur."""
    present = set(column.dropna().unique())
    if isinstance(column.dtype, pd.CategoricalDtype):
        return [str(v) for v in column.cat.categories if v in present]
    return [str(v) for v in column.dropna().unique()]


def feature_columns(data: pd.DataFrame) -> list[str]:
    """The numeric columns (category columns are never numeric)."""
    return list(data.select_dtypes(np.number).columns.values)


def selected_features(data: pd.DataFrame, features) -> list[str]:
    """The feature columns a config selects: a list, the keys of a dict of
    per-feature settings, or "all" (every numeric column)."""
    return feature_columns(data) if features == "all" else list(features)


def categories_first(data: pd.DataFrame) -> pd.DataFrame:
    """``data`` with its category columns first, otherwise in the same order."""
    categories = category_columns(data)
    return data[categories + [c for c in data.columns if c not in categories]]


def set_lineage(
    outputs: dict[str, OutputSpec], source: Callable[[str], Optional[str]]
) -> dict[str, OutputSpec]:
    """Records the input column each output column comes from: ``source(name)``, or
    the column's own lineage if it returns None."""
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
    """``"FLIRR"`` for ``"FLIRR\\nmean"``: the feature of a pivoted or summary column."""
    return name.split("\n")[0] if "\n" in name else None
