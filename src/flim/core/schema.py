"""Schemas of tables: their columns without the data.

Tools compute the schemas of their outputs from those of their inputs
(`Tool.output_schema`), so a workflow's steps can be configured and validated before
anything runs.
"""

from collections.abc import Sequence
from typing import Literal, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from flim.core.headers import HEADER_LEVELS

ColumnKind = Literal["category", "feature", "other"]


class ColumnInfo(BaseModel):
    """The description of one column of a table: name, role, data type and lineage.

    Attributes:
        name: The column header.
        role: `category` for categorical columns, `feature` for numeric non-boolean
            columns, `other` for all other columns.
        dtype: The pandas data type as text, e.g. `float64`.
        levels: The category values, if known; None otherwise.
        derived_from: The names of the input columns it was computed from.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    role: ColumnKind
    dtype: str
    levels: Optional[list] = None  # category values, if known
    derived_from: list[str] = []  # input columns it was computed from (lineage)


class TableSchema(BaseModel):
    """The columns of a table without its data.

    Attributes:
        columns: The columns, in table order.
        rows: The number of rows; None if not known.
        complete: Whether `columns` lists all columns; False if the table may have
            columns that are not listed.
        header_levels: The names of the lines of multi-line headers (see
            `flim.core.headers`).
    """

    columns: list[ColumnInfo] = []
    rows: Optional[int] = None  # usually unknown (filters, grouping)
    complete: bool = True  # False: the table may have columns not listed
    # names of the lines of multi-line headers, see flim.core.headers
    header_levels: list[str] = []

    @property
    def names(self) -> list[str]:
        """The column names, in table order."""
        return [c.name for c in self.columns]

    def column(self, name: str) -> Optional[ColumnInfo]:
        """Return the column named `name`, or None if there is none."""
        return next((c for c in self.columns if c.name == name), None)

    def by_role(self, role: str) -> list[str]:
        """Return the names of the columns of a role.

        Args:
            role: `category`, `feature` or `other`; `label` selects the columns of the
                roles `category` and `other`.

        Returns:
            The column names, in table order.
        """
        roles = ("category", "other") if role == "label" else (role,)
        return [c.name for c in self.columns if c.role in roles]

    @classmethod
    def unknown(cls) -> "TableSchema":
        """Return the schema of a table whose columns are not known before it runs.

        Returns:
            A schema without columns and with `complete` False.
        """
        return cls(complete=False)

    @classmethod
    def from_frame(
        cls, df: pd.DataFrame, rows: bool = True, inputs: Sequence["TableSchema"] = ()
    ) -> "TableSchema":
        """Return the schema of a DataFrame.

        Categorical columns get the role `category` with their categories as levels,
        numeric columns other than boolean ones the role `feature`, all other columns
        the role `other`. Column names are converted to text.

        Args:
            df: The table.
            rows: Whether the number of rows is recorded; False for tables computed
                from samples. Defaults to True.
            inputs: The schemas of the tables `df` was computed from; a column named
                like an input column is recorded as derived from it.

        Returns:
            The schema, with the header levels from `df.attrs`.
        """
        input_names = {name for schema in inputs for name in schema.names}
        columns = []
        for name in df.columns:
            series = df[name]
            name = str(name)
            if isinstance(series.dtype, pd.CategoricalDtype):
                role, levels = "category", list(series.cat.categories)
            elif pd.api.types.is_numeric_dtype(series.dtype) and not (
                pd.api.types.is_bool_dtype(series.dtype)
            ):
                role, levels = "feature", None
            else:
                role, levels = "other", None
            columns.append(
                ColumnInfo(
                    name=name,
                    role=role,
                    dtype=str(series.dtype),
                    levels=levels,
                    derived_from=[name] if name in input_names else [],
                )
            )
        return cls(
            columns=columns,
            rows=len(df) if rows else None,
            header_levels=list(df.attrs.get(HEADER_LEVELS) or []),
        )

    def sample(self, rows: int = 3) -> pd.DataFrame:
        """Return a small DataFrame with these columns, for computing output schemas.

        It has `rows` rows, or more if a category column has more levels, so every
        level occurs. Category columns cycle through their levels (two placeholder
        levels if none are known); features hold distinct numbers, other columns
        text. The header levels are copied to the DataFrame's `attrs`.

        Args:
            rows: The minimum number of rows. Defaults to 3.

        Returns:
            The DataFrame.
        """
        n = max([rows] + [len(c.levels) for c in self.columns if c.levels is not None])
        data = {}
        for i, c in enumerate(self.columns):
            if c.role == "category":
                levels = c.levels if c.levels else [f"{c.name} {j}" for j in (1, 2)]
                values = [levels[j % len(levels)] for j in range(n)]
                data[c.name] = pd.Categorical(values, categories=levels)
            elif c.role == "feature":
                values = np.arange(1, n + 1, dtype=float) * (i + 1)
                try:
                    data[c.name] = values.astype(c.dtype)
                except TypeError:
                    data[c.name] = values
            else:
                data[c.name] = [f"{c.name} {j}" for j in range(n)]
        sample = pd.DataFrame(data, columns=self.names)
        if self.header_levels:
            sample.attrs[HEADER_LEVELS] = list(self.header_levels)
        return sample
