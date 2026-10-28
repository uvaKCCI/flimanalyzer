"""Configs of the Data tools."""

from typing import Any, Literal, Optional, Union

from pydantic import Field, field_validator, model_validator

from flim.core.config import (
    AllFeatures,
    BaseConfig,
    CategoryColumn,
    FeatureColumn,
    TaskConfig,
)


class DataTaskConfig(TaskConfig):
    pass


class CategoryOrderConfig(DataTaskConfig):
    """Order of the values of category columns; the columns are sorted by them."""

    legacy_keys = {"categories": None}
    legacy_dropped = frozenset({"inplace"})
    hidden_fields = frozenset({"grouping", "features"})

    categories: dict[CategoryColumn, list[Any]] = Field(
        default={},
        title="Value order",
        description="For each category column, its values in the order to use.",
    )

    @classmethod
    def _from_legacy(cls, params):
        # legacy: {column: {"values": [...], "sort": ...}}; only the values are used
        categories = params.pop("categories", {}) or {}
        return {
            "categories": {
                col: list(spec.get("values", [])) for col, spec in categories.items()
            }
        }

    def _to_legacy(self):
        return {
            "categories": {
                col: {"values": list(values), "sort": "custom"}
                for col, values in self.categories.items()
            }
        }


class ConcatConfig(DataTaskConfig):
    legacy_keys = {"mode": None}
    legacy_dropped = frozenset({"source_suffix"})  # unused
    hidden_fields = frozenset({"grouping", "features"})

    mode: Literal["vertical", "horizontal"] = Field(
        default="vertical",
        title="Direction",
        description="vertical: append the rows of the tables; horizontal: their columns.",
    )
    numbers_only: bool = Field(
        default=False,
        title="Numeric columns only",
        description="Horizontal: append only the numeric columns of the other tables.",
    )

    @classmethod
    def _from_legacy(cls, params):
        # legacy "type" is the "Horizontal Concatenate" checkbox
        if "type" in params:
            return {"mode": "horizontal" if params.pop("type") else "vertical"}
        return {}

    def _to_legacy(self):
        return {"type": self.mode == "horizontal"}


def range_of_legacy(spec: dict) -> dict:
    """low, high and dropna of a plugin's range filter; infinite: no limit."""
    low, high = spec.get("rangelow"), spec.get("rangehigh")
    return {
        "low": None if low is None or low == float("-inf") else low,
        "high": None if high is None or high == float("inf") else high,
        "dropna": spec.get("dropna", True),
    }


class RangeSettings(BaseConfig):
    """Rows whose value lies outside [low, high] are dropped; empty: no limit."""

    low: Optional[float] = Field(default=None, title="Low")
    high: Optional[float] = Field(default=None, title="High")
    dropna: bool = Field(
        default=True,
        title="Drop missing",
        description="Also drop rows without a value.",
    )

    @model_validator(mode="after")
    def _check_range(self):
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError(f"low ({self.low}) > high ({self.high})")
        return self


class FilterConfig(DataTaskConfig):
    legacy_keys = {"range_filters": None}
    legacy_dropped = frozenset({"use", "inplace", "show_dropped"})  # unused
    hidden_fields = frozenset({"grouping", "features"})

    category_filters: dict[CategoryColumn, list[Any]] = Field(
        default={},
        title="Category values to keep",
        description="For each category column, the values whose rows are kept.",
    )
    range_filters: dict[FeatureColumn, RangeSettings] = Field(
        default={},
        title="Range filters",
        description=(
            "Check the columns to filter: rows outside [low, high] are dropped (empty:"
            " no limit)."
        ),
    )

    @field_validator("range_filters", mode="before")
    @classmethod
    def _filters_from_list(cls, filters):
        """A list of columns: filters without limits (dropping missing values)."""
        if isinstance(filters, (list, tuple)):
            return {f: {} for f in filters}
        return filters

    @classmethod
    def _from_legacy(cls, params):
        # the plugin: a list of {"name", "rangelow", "rangehigh", "selected", ...};
        # it applied the selected ones
        filters = {}
        for spec in params.pop("range_filters", []) or []:
            if spec.get("selected", True):
                filters[spec["name"]] = RangeSettings(**range_of_legacy(spec))
        return {"range_filters": filters}

    def _to_legacy(self):
        inf = float("inf")
        return {
            "range_filters": [
                {
                    "name": column,
                    "rangelow": -inf if r.low is None else r.low,
                    "rangehigh": inf if r.high is None else r.high,
                    "allowedmin": None,
                    "allowedmax": None,
                    "selected": True,
                    "dropna": r.dropna,
                }
                for column, r in self.range_filters.items()
            ]
        }


class MergeConfig(DataTaskConfig):
    legacy_keys = {"how": None, "on": None}
    legacy_dropped = frozenset({"left_index", "right_index"})
    hidden_fields = frozenset({"grouping", "features"})

    how: Literal["inner", "outer", "left", "right"] = Field(
        default="inner",
        title="Join",
        description=(
            "inner: rows in both tables; outer: in either; left/right: all rows of"
            " that table."
        ),
    )
    on: Optional[list[CategoryColumn]] = Field(
        default=None,
        title="Merge on",
        description="Columns to merge on; automatic: the category columns both have.",
    )

    @classmethod
    def _from_legacy(cls, params):
        how = params.pop("how", "")
        return {"how": how} if how else {}  # legacy default "" fails in pandas

    def _to_legacy(self):
        return {"how": self.how}


class PivotConfig(DataTaskConfig):
    """Pivots the ``grouping`` columns."""

    grouping: list[CategoryColumn] = Field(
        default=["Treatment"],
        title="Columns to pivot",
        description="Their values become columns; the other category columns stay rows.",
    )
    features: Union[list[FeatureColumn], AllFeatures] = Field(
        default="all", title="Features"
    )


class SortConfig(DataTaskConfig):
    """Sorts by the ``features`` columns."""

    hidden_fields = frozenset({"grouping"})

    features: Union[list[FeatureColumn], AllFeatures] = Field(
        default=[], title="Sort by", description="The columns to sort by, in order."
    )
    ascending: bool = Field(default=True, title="Ascending")
    ignore_index: bool = Field(
        default=True,
        title="Renumber rows",
        description="Number the sorted rows 0, 1, ...",
    )


class UnpivotConfig(DataTaskConfig):
    hidden_fields = frozenset({"grouping"})

    features: Union[list[FeatureColumn], AllFeatures] = Field(
        default="all", title="Columns to stack"
    )
    category_name: str = Field(
        default="Category",
        title="New category column",
        description="Holds the names of the stacked columns.",
    )
    feature_name: str = Field(
        default="Feature",
        title="New value column",
        description="Holds the values of the stacked columns.",
    )
