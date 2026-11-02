"""Schemas of tables: their columns without the data.

Tools compute the schemas of their outputs from those of their inputs
(``Tool.output_schema``), so a workflow's steps can be configured and validated before
anything runs.
"""

from typing import Literal, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from flim.core.headers import HEADER_LEVELS

ColumnKind = Literal["category", "feature", "other"]


class ColumnInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    role: ColumnKind
    dtype: str
    levels: Optional[list] = None  # category values, if known
    derived_from: list[str] = []  # input columns it was computed from (lineage)


class TableSchema(BaseModel):
    columns: list[ColumnInfo] = []
    rows: Optional[int] = None  # usually unknown (filters, grouping)
    complete: bool = True  # False: the table may have columns not listed
    # names of the lines of multi-line headers, see flim.core.headers
    header_levels: list[str] = []

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.columns]

    def column(self, name: str) -> Optional[ColumnInfo]:
        return next((c for c in self.columns if c.name == name), None)

    def by_role(self, role: ColumnKind) -> list[str]:
        return [c.name for c in self.columns if c.role == role]

    @classmethod
    def unknown(cls) -> "TableSchema":
        """A table whose columns are not known before it is computed."""
        return cls(complete=False)

    @classmethod
    def from_frame(
        cls, df: pd.DataFrame, rows: bool = True, inputs: tuple = ()
    ) -> "TableSchema":
        """The schema of a DataFrame.

        Args:
            rows: record the number of rows (False for tables computed from samples).
            inputs: schemas of the tables ``df`` was computed from; a column named like
                an input column is recorded as derived from it.
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
        """A small DataFrame with these columns, for computing output schemas.

        Category columns cycle through their levels, so every level occurs (at least
        ``rows`` rows); features hold distinct numbers.
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
