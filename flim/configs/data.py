"""Configs of the Data tools."""

from typing import Any, Literal, Optional, Union

from pydantic import model_validator

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

    categories: dict[CategoryColumn, list[Any]] = {}

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

    mode: Literal["vertical", "horizontal"] = "vertical"  # append rows or columns
    numbers_only: bool = False
    source_suffix: bool = True

    @classmethod
    def _from_legacy(cls, params):
        # legacy "type" is the "Horizontal Concatenate" checkbox
        if "type" in params:
            return {"mode": "horizontal" if params.pop("type") else "vertical"}
        return {}

    def _to_legacy(self):
        return {"type": self.mode == "horizontal"}


class RangeFilterSpec(BaseConfig):
    """Keeps the rows whose value in ``column`` lies in [low, high] (if selected)."""

    column: FeatureColumn
    low: float = 0
    high: float = 100
    allowed_min: Optional[float] = None
    allowed_max: Optional[float] = None
    selected: bool = False
    dropna: bool = True

    @model_validator(mode="after")
    def _check_range(self):
        if self.low > self.high:
            raise ValueError(f"{self.column}: low ({self.low}) > high ({self.high})")
        return self

    @classmethod
    def from_legacy(cls, params: dict) -> "RangeFilterSpec":
        return cls(
            column=params["name"],
            low=params.get("rangelow", 0),
            high=params.get("rangehigh", 100),
            allowed_min=params.get("allowedmin"),
            allowed_max=params.get("allowedmax"),
            selected=params.get("selected", False),
            dropna=params.get("dropna", True),
        )

    def to_legacy(self) -> dict:
        return {
            "name": self.column,
            "rangelow": self.low,
            "rangehigh": self.high,
            "allowedmin": self.allowed_min,
            "allowedmax": self.allowed_max,
            "selected": self.selected,
            "dropna": self.dropna,
        }


class FilterConfig(DataTaskConfig):
    legacy_keys = {"range_filters": None}
    legacy_dropped = frozenset({"use", "inplace"})

    # values to keep per category column
    category_filters: dict[CategoryColumn, list[Any]] = {}
    range_filters: list[RangeFilterSpec] = []
    show_dropped: bool = False

    @classmethod
    def _from_legacy(cls, params):
        filters = params.pop("range_filters", []) or []
        return {"range_filters": [RangeFilterSpec.from_legacy(f) for f in filters]}

    def _to_legacy(self):
        return {"range_filters": [f.to_legacy() for f in self.range_filters]}


class MergeConfig(DataTaskConfig):
    legacy_keys = {"how": None, "on": None}
    legacy_dropped = frozenset({"left_index", "right_index"})

    how: Literal["inner", "outer", "left", "right"] = "inner"
    # columns to merge on; None: the category columns both tables have
    on: Optional[list[CategoryColumn]] = None

    @classmethod
    def _from_legacy(cls, params):
        how = params.pop("how", "")
        return {"how": how} if how else {}  # legacy default "" fails in pandas

    def _to_legacy(self):
        return {"how": self.how}


class PivotConfig(DataTaskConfig):
    """Pivots the ``grouping`` columns."""

    grouping: list[CategoryColumn] = ["Treatment"]
    features: Union[list[FeatureColumn], AllFeatures] = "all"


class SortConfig(DataTaskConfig):
    """Sorts by the ``features`` columns."""

    ascending: bool = True
    ignore_index: bool = True


class UnpivotConfig(DataTaskConfig):
    features: Union[list[FeatureColumn], AllFeatures] = "all"
    category_name: str = "Category"
    feature_name: str = "Feature"
