"""Configs of the Data tools."""

from typing import Annotated, Any, Literal, Optional, Union

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
        description="Append the rows of the tables below each other, or their columns"
        " side by side.",
        json_schema_extra={
            "labels": {
                "vertical": "Rows (stack below)",
                "horizontal": "Columns (side by side)",
            }
        },
    )
    numbers_only: bool = Field(
        default=False,
        title="Numeric columns only",
        description="Columns: append only the numeric columns of the other tables.",
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
    min_features = 1

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


class SplitConfig(DataTaskConfig):
    """Splits a table by the values of the ``grouping`` columns."""

    min_grouping = 1
    hidden_fields = frozenset({"features"})

    grouping: list[CategoryColumn] = Field(
        default=[],
        title="Split by",
        description="A table for each combination of the values of these columns.",
    )


class UnpivotConfig(DataTaskConfig):
    """Moves one level (line) of the columns' headers into a category column: the
    inverse of Pivot. E.g. the level Treatment of ``"FLIRR\\nctrl"``,
    ``"FLIRR\\nDox15"``: a column Treatment (ctrl, Dox15) and a column FLIRR."""
    min_features = 1

    legacy_keys = {"category_name": None}
    # the value columns are named by the other levels
    legacy_dropped = frozenset({"feature_name"})
    hidden_fields = frozenset({"grouping"})

    features: Union[list[FeatureColumn], AllFeatures] = Field(
        default="all", title="Columns", description="The columns to unpivot."
    )
    level: str = Field(
        default="",
        title="Level",
        description=(
            "The header line that becomes a category column; empty: the last. The"
            " other lines name the value columns."
        ),
    )
    category_name: Optional[str] = Field(
        default=None,
        title="Category column",
        description="Name of the new category column; empty: the level's name.",
    )

    @classmethod
    def _from_legacy(cls, params):
        # "Category" (the plugin's default name): the level's name
        name = params.pop("category_name", None)
        return {"category_name": None if name in (None, "", "Category") else name}

    def _to_legacy(self):
        return {"category_name": self.category_name or "Category"}


class ScaleConfig(DataTaskConfig):
    """Scales the selected features, over the whole table or within each group."""

    min_features = 1

    method: Literal["standardize", "min-max", "robust"] = Field(
        default="standardize",
        title="Method",
        description="standardize: mean 0, standard deviation 1 (as Standardize input);"
        " min-max: 0 to 1; robust: median 0, interquartile range 1, less affected by"
        " outliers.",
    )
    keep_original: bool = Field(
        default=True,
        title="Keep the original features",
        description="Add the scaled features as new columns; unchecked: they replace"
        " the original columns.",
    )
    grouping: list[CategoryColumn] = Field(
        default=[],
        title="Grouping",
        description="Scale within each group of these columns, e.g. per FOV; none: over"
        " the whole table.",
    )


class FuseCategoriesConfig(DataTaskConfig):
    """Joins category columns into one category column, e.g. FOV and Cell into
    FOV:Cell."""

    min_grouping = 2
    hidden_fields = frozenset({"features"})

    grouping: list[CategoryColumn] = Field(
        default=[],
        title="Columns to fuse",
        description="The category columns, in the order their values are joined.",
    )
    delimiter: str = Field(
        default=":",
        min_length=1,
        title="Delimiter",
        description="Joins the column names and the values; Separate Categories"
        " reverses it with the same delimiter.",
    )
    name: Optional[str] = Field(
        default=None,
        title="New column",
        description="The new column's name; empty: the column names joined by the"
        " delimiter.",
    )
    keep_original: bool = Field(
        default=True,
        title="Keep the original columns",
        description="Keep the fused columns; unchecked: they are removed.",
    )


class CategoryPattern(BaseConfig):
    """A new category column, taken from the values by a regular expression."""

    name: str = Field(default="", title="Column")
    regex: str = Field(
        default="",
        title="Pattern",
        description="A regular expression; its first group (...) is the value.",
    )


class SeparateCategoriesConfig(DataTaskConfig):
    """Separates a category column into several, at delimiters or by patterns."""

    hidden_fields = frozenset({"features", "grouping"})

    column: Optional[CategoryColumn] = Field(
        default=None, title="Column", description="The category column to separate."
    )
    mode: Literal["delimiters", "patterns"] = Field(
        default="delimiters",
        title="Separate",
        description="delimiters: at the delimiters (the reverse of Fuse Categories);"
        " patterns: take parts by regular expressions, as the filename parser does.",
    )
    part: Literal["value", "file name", "file name without extension"] = Field(
        default="value",
        title="Part",
        description="Which part of the values: the whole value, or the file name of a"
        " path, with or without its extension.",
    )
    delimiters: list[str] = Field(
        default=[":"],
        title="Delimiters",
        description="delimiters mode: any of them separates.",
    )
    names: list[str] = Field(
        default=[],
        title="New columns",
        description="delimiters mode: the new columns' names by position; an empty"
        " name skips that part; none: the column name separated the same way.",
    )
    patterns: list[CategoryPattern] = Field(
        default=[],
        title="Patterns",
        description="patterns mode: a new column per pattern.",
    )
    keep_original: bool = Field(
        default=True,
        title="Keep the original column",
        description="Keep the separated column; unchecked: it is removed.",
    )


class Replacement(BaseConfig):
    """Replaces a part of the column names."""

    part: str = Field(default="", title="Part", description="The text to replace.")
    new: str = Field(default="", title="New text", description="Its replacement.")


def _default_replacements() -> list:
    from flim.core.preprocessor import DEFAULT_RENAME

    return [Replacement(part=p, new=n) for p, n in DEFAULT_RENAME.items()]


class RenameColumnsConfig(DataTaskConfig):
    """Replaces parts of the column names, in order."""

    hidden_fields = frozenset({"features", "grouping"})

    replacements: list[Replacement] = Field(
        default_factory=_default_replacements,
        title="Replace",
        description="In order: each replaces its part in every column name that"
        " contains it; a whole name is replaced if the part is the full name.",
    )

    @field_validator("replacements")
    @classmethod
    def _parts_given(cls, replacements):
        if any(not r.part for r in replacements):
            raise ValueError("a replacement needs the part to replace")
        return replacements


class DropRule(BaseConfig):
    """Drops the columns whose names match a text."""

    text: str = Field(default="", title="Text")
    match: Literal["contains", "starts with", "ends with", "is"] = Field(
        default="contains",
        title="Match",
        description="contains: names that contain the text; is: the whole name.",
    )


def _default_drop_rules() -> list:
    from flim.core.preprocessor import DEFAULT_DROP

    return [DropRule(text=t) for t in DEFAULT_DROP]


class DropColumnsConfig(DataTaskConfig):
    """Drops columns by their names; a column with an empty header too."""

    hidden_fields = frozenset({"features", "grouping"})

    drop: list[DropRule] = Field(
        default_factory=_default_drop_rules,
        title="Drop",
        description="The columns whose names match one of these.",
    )


class Calculation(BaseConfig):
    """A new column calculated from others (base of the calculation kinds)."""

    enabled: bool = Field(default=True, title="Use", description="Unchecked: not calculated.")
    name: str = Field(default="", title="Column", description="The new column's name.")
    kind: str = Field(
        default="expression",
        title="Kind",
        description="expression: a formula; function: a registered function.",
    )
    keep: bool = Field(
        default=True,
        title="Keep",
        description="Unchecked: a helper column, used by later calculations but not"
        " in the result.",
    )
    column_type: Literal["feature", "category"] = Field(
        default="feature", title="Type", description="category: values become categories."
    )
    description: str = Field(default="", title="Description")


class ExpressionCalculation(Calculation):
    """A column calculated by an expression of columns, numbers and math functions."""

    kind: Literal["expression"] = "expression"
    expression: str = Field(
        default="",
        title="Expression",
        description="Arithmetic, comparisons and math functions (log, sqrt, ...);"
        " column names with spaces or other characters in backticks: `FAD tm`.",
    )
    engine: Literal["pandas"] = "pandas"


class FunctionCalculation(Calculation):
    """A column calculated by a registered function, row by row."""

    kind: Literal["function"] = "function"
    function: str = Field(default="", title="Function", description="e.g. tm, ratio.")
    args: list[str] = Field(
        default=[], title="Arguments", description="The columns, in the function's order."
    )
    params: dict[str, float] = Field(
        default={}, title="Parameters", description="Keyword parameters, e.g. const=3100."
    )


CalculationEntry = Annotated[
    Union[ExpressionCalculation, FunctionCalculation], Field(discriminator="kind")
]


def _default_calculations() -> list:
    from flim.core.preprocessor import DEFAULT_CALCULATIONS

    return [
        FunctionCalculation(name=n, function=f, args=list(a))
        for n, f, a in DEFAULT_CALCULATIONS
    ]


class CalculateConfig(DataTaskConfig):
    """Calculates new columns, in order: later ones may use earlier ones' columns."""

    hidden_fields = frozenset({"features", "grouping"})

    calculations: list[CalculationEntry] = Field(
        default_factory=_default_calculations,
        title="Calculations",
        description="In order; a calculation that uses a column the table doesn't"
        " have is skipped.",
    )
