"""Configs of the Data tools."""

from typing import Annotated, Any, Literal, Optional, Self, Union

from pydantic import Field, field_validator, model_validator

from flim.core.reader import ReadSettings
from flim.core.config import (
    AllFeatures,
    BaseConfig,
    CategoryColumn,
    FeatureColumn,
    LabelColumn,
    TaskConfig,
)


class DataTaskConfig(TaskConfig):
    """Base config of the Data tools."""


class ProtectedNamesConfig(BaseConfig):
    """Settings of tools that write columns of protected names (Source, Input, ...).

    They set how a tool renames a column the table already has under such a name.
    """

    clash_name: str = Field(
        default="{name} (before {tool})",
        title="Rename existing columns as",
        description="A column the table already has under a name this tool writes"
        " (e.g. Source): {name} is its name, {tool} the tool's short name.",
    )

    @model_validator(mode="before")
    @classmethod
    def _no_renames(cls, data: Any) -> Any:
        """Drop `clash_renames`, a name per column, which older settings files have."""
        if isinstance(data, dict) and "clash_renames" in data:
            data = {k: v for k, v in data.items() if k != "clash_renames"}
        return data

    @field_validator("clash_name")
    @classmethod
    def _template(cls, template: str) -> str:
        """Check the rename template with `flim.core.columns.check_template`."""
        from flim.core.columns import check_template

        return check_template(template)


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
    def _from_legacy(cls, params: dict[str, Any]) -> dict[str, Any]:
        """Convert and pop the legacy `categories`; only their values are used."""
        # legacy: {column: {"values": [...], "sort": ...}}; only the values are used
        categories = params.pop("categories", {}) or {}
        return {
            "categories": {
                col: list(spec.get("values", [])) for col, spec in categories.items()
            }
        }

    def _to_legacy(self) -> dict[str, Any]:
        """Return the value orders as legacy `categories` with custom sorting."""
        return {
            "categories": {
                col: {"values": list(values), "sort": "custom"}
                for col, values in self.categories.items()
            }
        }


class CollectFilesConfig(DataTaskConfig):
    """Config of Collect Files: no settings of its own."""

    hidden_fields = frozenset({"grouping", "features"})


class ConcatConfig(DataTaskConfig, ProtectedNamesConfig):
    """Config of Concatenate: the direction and the columns that are appended."""

    legacy_keys = {
        "mode": None, "clash_name": None, "add_input": None,
    }  # fmt: skip
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
        description="Append only the numeric columns of the other tables.",
        json_schema_extra={"shown_when": {"mode": "horizontal"}},
    )
    add_input: bool = Field(
        default=True,
        title="Add Input column",
        description="A column with the name of each row's table.",
        json_schema_extra={"shown_when": {"mode": "vertical"}},
    )
    clash_name: str = Field(
        default="{name} ({table})",
        title="Rename existing columns as",
        description="Rows: an Input column a table already has (e.g. from an earlier"
        " Concatenate): {name} is its name, {table} the table's.",
    )

    @classmethod
    def _from_legacy(cls, params: dict[str, Any]) -> dict[str, Any]:
        """Convert and pop the legacy `type`, true for horizontal."""
        # legacy "type" is the "Horizontal Concatenate" checkbox
        if "type" in params:
            return {"mode": "horizontal" if params.pop("type") else "vertical"}
        return {}

    def _to_legacy(self) -> dict[str, Any]:
        """Return the legacy `type`, true for horizontal."""
        return {"type": self.mode == "horizontal"}


def range_of_legacy(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the limits of a legacy plugin's range filter.

    Args:
        spec: The legacy range filter, with `rangelow`, `rangehigh` and `dropna`.

    Returns:
        `low`, `high` and `dropna`. A missing or infinite limit is None (no limit);
        `dropna` defaults to True.
    """
    low, high = spec.get("rangelow"), spec.get("rangehigh")
    return {
        "low": None if low is None or low == float("-inf") else low,
        "high": None if high is None or high == float("inf") else high,
        "dropna": spec.get("dropna", True),
    }


class RangeSettings(BaseConfig):
    """A range of values: rows outside [low, high] are dropped; empty: no limit."""

    low: Optional[float] = Field(default=None, title="Low")
    high: Optional[float] = Field(default=None, title="High")
    dropna: bool = Field(
        default=True,
        title="Drop missing",
        description="Also drop rows without a value.",
    )

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        """Reject a range whose `low` is larger than its `high`."""
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError(f"low ({self.low}) > high ({self.high})")
        return self


class FilterNode(BaseConfig):
    """A node of a filter tree (base of the filter kinds)."""

    enabled: bool = Field(default=True, title="Use", description="Unchecked: keeps all rows.")
    kind: str = Field(
        default="range",
        title="Kind",
        description="range: values in [low, high]; category: values to keep;"
        " expression: a condition.",
    )


class RangeFilterNode(FilterNode):
    """A filter that keeps the rows whose value lies in [low, high]; empty: no limit."""

    kind: Literal["range"] = "range"
    column: FeatureColumn = Field(default="", title="Column")
    low: Optional[float] = Field(default=None, title="Low")
    high: Optional[float] = Field(default=None, title="High")
    dropna: bool = Field(
        default=True, title="Drop missing", description="Also drop rows without a value."
    )

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        """Reject a range whose `low` is larger than its `high`."""
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError(f"low ({self.low}) > high ({self.high})")
        return self


class CategoryFilterNode(FilterNode):
    """A filter that keeps the rows whose value is one of `keep`."""

    kind: Literal["category"] = "category"
    column: CategoryColumn = Field(default="", title="Column")
    keep: list[Any] = Field(default=[], title="Values to keep")


class ExpressionFilterNode(FilterNode):
    """A filter that keeps the rows for which a condition is true.

    For example ``FAD tm > 1000``, written as the expressions of Calculate.
    """

    kind: Literal["expression"] = "expression"
    expression: str = Field(
        default="",
        title="Expression",
        description="A condition: comparisons, & (and), | (or), ~ (not), arithmetic"
        " and math functions; column names in backticks.",
    )
    engine: Literal["pandas"] = "pandas"


class FilterGroup(FilterNode):
    """A group of filters, combined by its kind.

    `all` keeps the rows all of them keep, `any` the rows one of them keeps, `not` the
    rows that `all` of them would drop. An empty group keeps all rows.
    """

    kind: Literal["all", "any", "not"] = "all"
    filters: list["FilterEntry"] = Field(default=[], title="Filters")


FilterEntry = Annotated[
    Union[RangeFilterNode, CategoryFilterNode, ExpressionFilterNode, FilterGroup],
    Field(discriminator="kind"),
]
FilterGroup.model_rebuild()


def _filters_of_v1(
    values: dict[str, Any], enabled: bool = True
) -> list[dict[str, Any]]:
    """Return older Filter fields (`category_filters`, `range_filters`) as nodes."""
    nodes = []
    ranges = values.get("range_filters") or {}
    if isinstance(ranges, (list, tuple)):
        # a list: of columns (no limits), or of the plugin's range filters
        ranges = {
            (r["name"] if isinstance(r, dict) else r): (range_of_legacy(r) if isinstance(r, dict) else {})
            for r in ranges
        }
    for column, limits in ranges.items():
        limits = limits.model_dump() if hasattr(limits, "model_dump") else dict(limits or {})
        limits = {k: v for k, v in limits.items() if k in ("low", "high", "dropna")}
        nodes.append({"kind": "range", "column": column, "enabled": enabled, **limits})
    for column, keep in (values.get("category_filters") or {}).items():
        nodes.append({"kind": "category", "column": column, "keep": list(keep), "enabled": enabled})
    return nodes


class FilterConfig(DataTaskConfig):
    """Config of Filter: keeps the rows that the filters keep.

    The filters are a tree whose top level is an `all` group: a row is kept if every
    filter of the list keeps it. A filter is used only if `enabled` (the switch of
    all filters), the `enabled` of each group it is in and its own `enabled` are all
    true.
    """

    legacy_keys = {"filters": None, "enabled": "use"}  # 0.5: `use`, the same switch
    legacy_dropped = frozenset({"inplace", "show_dropped"})  # unused
    hidden_fields = frozenset({"grouping", "features"})

    enabled: bool = Field(
        default=True,
        title="Use filters",
        description="The switch of all filters: off keeps all rows. A filter is used"
        " only if this, the groups it is in and its own Use are all on.",
    )
    filters: list[FilterEntry] = Field(
        default=[],
        title="Filters",
        description="A row is kept if every filter keeps it. A filter on a column the"
        " table doesn't have keeps all rows.",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_v1(cls, values: Any) -> Any:
        """Convert the older fields `category_filters` and `range_filters`."""
        if isinstance(values, dict) and (
            "category_filters" in values or "range_filters" in values
        ):
            values = dict(values)
            old = {k: values.pop(k) for k in ("category_filters", "range_filters") if k in values}
            values["filters"] = list(values.get("filters") or []) + _filters_of_v1(old)
        return values

    @classmethod
    def _from_legacy(cls, params: dict[str, Any]) -> dict[str, Any]:
        """Convert and pop the legacy range and category filters."""
        # the plugin: range_filters, a list of {"name", "rangelow", "rangehigh",
        # "selected", ...} (it applied the selected ones), and category_filters
        filters = []
        for spec in params.pop("range_filters", []) or []:
            if spec.get("selected", True):
                filters.append({"kind": "range", "column": spec["name"], **range_of_legacy(spec)})
        for column, keep in (params.pop("category_filters", {}) or {}).items():
            filters.append({"kind": "category", "column": column, "keep": list(keep)})
        return {"filters": filters}

    def _to_legacy(self) -> dict[str, Any]:
        """Return the enabled top-level range and category filters in legacy form."""
        inf = float("inf")
        return {
            "range_filters": [
                {
                    "name": f.column,
                    "rangelow": -inf if f.low is None else f.low,
                    "rangehigh": inf if f.high is None else f.high,
                    "allowedmin": None,
                    "allowedmax": None,
                    "selected": True,
                    "dropna": f.dropna,
                }
                for f in self.filters
                if f.kind == "range" and f.enabled
            ],
            "category_filters": {
                f.column: list(f.keep)
                for f in self.filters
                if f.kind == "category" and f.enabled
            },
        }


class MergeConfig(DataTaskConfig):
    """Config of Merge: the join, the columns to merge on and the suffixes."""

    legacy_keys = {
        "how": None, "on": None, "suffix_left": None, "suffix_right": None,
        "combine_identical": None,
    }  # fmt: skip
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
    combine_identical: bool = Field(
        default=True,
        title="Combine identical columns",
        description="A column both tables have, with the same values wherever both"
        " have one, becomes one column; other such columns get the suffixes.",
    )
    suffix_left: str = Field(
        default=" (left)",
        title="Suffix of the first table",
        description="Appended to the names of its columns that the other table has too.",
    )
    suffix_right: str = Field(
        default=" (right)",
        title="Suffix of the second table",
        description="Appended to the names of its columns that the first table has too.",
    )

    @model_validator(mode="after")
    def _suffixes_differ(self) -> Self:
        """Reject equal suffixes for the two tables."""
        if self.suffix_left == self.suffix_right:
            raise ValueError("the two suffixes must differ")
        return self

    @classmethod
    def _from_legacy(cls, params: dict[str, Any]) -> dict[str, Any]:
        """Convert and pop the legacy `how`; an empty one gives the default."""
        how = params.pop("how", "")
        return {"how": how} if how else {}  # legacy default "" fails in pandas

    def _to_legacy(self) -> dict[str, Any]:
        """Return the legacy `how`."""
        return {"how": self.how}


class PivotConfig(DataTaskConfig):
    """Config of Pivot: the columns whose values become columns, and the features."""

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
    """Config of Sort: the columns to sort by, in order, and the direction."""

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
    """Config of Split: a table per combination of values of the `grouping` columns."""

    min_grouping = 1
    hidden_fields = frozenset({"features"})

    grouping: list[CategoryColumn] = Field(
        default=[],
        title="Split by",
        description="A table for each combination of the values of these columns.",
    )


class UnpivotConfig(DataTaskConfig):
    r"""Config of Unpivot: moves one header line of the columns into a category column.

    It is the inverse of Pivot. For example, the level Treatment of `"FLIRR\nctrl"`
    and `"FLIRR\nDox15"` gives a column Treatment (ctrl, Dox15) and a column FLIRR.
    """

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
    missing_label: str = Field(
        default="none",
        title="Label for a missing line",
        description="The category value of a column whose header has fewer lines than"
        " the others (e.g. FLIRR next to FLIRR / standardized, after Scale): its"
        " missing last lines count as empty, and an empty level gets this label, e.g."
        " original.",
    )

    @classmethod
    def _from_legacy(cls, params: dict[str, Any]) -> dict[str, Any]:
        """Convert and pop the legacy `category_name`; `Category` means none."""
        # "Category" (the plugin's default name): the level's name
        name = params.pop("category_name", None)
        return {"category_name": None if name in (None, "", "Category") else name}

    def _to_legacy(self) -> dict[str, Any]:
        """Return the legacy `category_name`, `Category` if none is set."""
        return {"category_name": self.category_name or "Category"}


class ScaleConfig(DataTaskConfig):
    """Config of Scale: the method, and whether to scale within groups."""

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
    """Config of Fuse Categories: joins category columns into one category column.

    For example, FOV and Cell become FOV:Cell.
    """

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
        " reverses it with the same delimiter. Spaces count, e.g. ' - '; \\t is a tab.",
        json_schema_extra={"escapes": True},
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
    """Config of Separate Categories: separates a category column into several.

    The column is separated at delimiters, by regular expressions (patterns), or by
    a template of its values.
    """

    hidden_fields = frozenset({"features", "grouping"})

    column: Optional[LabelColumn] = Field(
        default=None, title="Column", description="The category column to separate."
    )
    mode: Literal["delimiter", "pattern", "template"] = Field(
        default="delimiter",
        title="Mode",
        description="delimiter: at the delimiters (the reverse of Fuse Categories);"
        " pattern: take parts by regular expressions, as the filename parsers did;"
        " template: by the layout of the values, e.g. Results-{FOV}-{Treatment}_{Cell}.",
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
        description="Each of these characters separates, e.g. -_ ; \\t is a tab.",
        json_schema_extra={"chars": True, "shown_when": {"mode": "delimiter"}},
    )
    names: list[str] = Field(
        default=[],
        title="New columns",
        description="The new columns' names by position, separated by commas; an empty"
        " name skips that part (e.g. , Treatment, Cell); none: the column name"
        " separated the same way.",
        json_schema_extra={"words": True, "shown_when": {"mode": "delimiter"}},
    )
    patterns: list[CategoryPattern] = Field(
        default=[],
        title="Patterns",
        description="A new column per pattern.",
        json_schema_extra={"shown_when": {"mode": "pattern"}},
    )
    template: str = Field(
        default="",
        title="Template",
        description="The layout of the values, {Name} for a new column, {} for a part"
        " that is not kept; the text between must be as it is, e.g."
        " Results-{FOV}-{Treatment}_{Cell}.",
        json_schema_extra={"wide": True, "shown_when": {"mode": "template"}},
    )
    keep_original: bool = Field(
        default=True,
        title="Keep the original column",
        description="Keep the separated column; unchecked: it is removed.",
    )

    @field_validator("mode", mode="before")
    @classmethod
    def _singular(cls, mode: Any) -> Any:
        """Read the older mode names `delimiters` and `patterns`."""
        return {"delimiters": "delimiter", "patterns": "pattern"}.get(mode, mode)


class Replacement(BaseConfig):
    """A replacement of Rename Columns: a part of the column names and its new text."""

    part: str = Field(
        default="",
        title="Part",
        description="The text to replace; spaces count (\\t: a tab).",
        json_schema_extra={"escapes": True},
    )
    new: str = Field(
        default="",
        title="New text",
        description="Its replacement; spaces count, e.g. 'trp ' gives 'trp t1'.",
        json_schema_extra={"escapes": True},
    )


def _default_replacements() -> list[Replacement]:
    """Return the default replacements, from `flim.core.preprocessor`."""
    from flim.core.preprocessor import DEFAULT_RENAME

    return [Replacement(part=p, new=n) for p, n in DEFAULT_RENAME.items()]


class RenameColumnsConfig(DataTaskConfig):
    """Config of Rename Columns: replaces parts of the column names, in order."""

    hidden_fields = frozenset({"features", "grouping"})

    replacements: list[Replacement] = Field(
        default_factory=_default_replacements,
        title="Replace",
        description="In order: each replaces its part in every column name that"
        " contains it; a whole name is replaced if the part is the full name.",
    )

    @field_validator("replacements")
    @classmethod
    def _parts_given(cls, replacements: list[Replacement]) -> list[Replacement]:
        """Reject a replacement without a part to replace."""
        if any(not r.part for r in replacements):
            raise ValueError("a replacement needs the part to replace")
        return replacements


class DropRule(BaseConfig):
    """A rule of Drop Columns: the columns whose names match a text are dropped."""

    text: str = Field(default="", title="Text")
    match: Literal["contains", "starts with", "ends with", "is"] = Field(
        default="contains",
        title="Match",
        description="contains: names that contain the text; is: the whole name.",
    )


def _default_drop_rules() -> list[DropRule]:
    """Return the default drop rules, from `flim.core.preprocessor`."""
    from flim.core.preprocessor import DEFAULT_DROP

    return [DropRule(text=t) for t in DEFAULT_DROP]


class DropColumnsConfig(DataTaskConfig):
    """Config of Drop Columns: drops columns by their names, and empty headers."""

    hidden_fields = frozenset({"features", "grouping"})

    drop: list[DropRule] = Field(
        default_factory=_default_drop_rules,
        title="Drop",
        description="The columns whose names match one of these.",
    )


class Calculation(BaseConfig):
    """A new column calculated from others (base of the calculation kinds)."""

    enabled: bool = Field(default=True, title="Use", description="Unchecked: not calculated.")
    name: str = Field(default="", title="New Column", description="The new column's name.")
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
    description: str = Field(default="", title="Description")


    @model_validator(mode="before")
    @classmethod
    def _no_column_type(cls, values: Any) -> Any:
        """Drop `column_type`, which older files have; the type follows the values."""
        if isinstance(values, dict) and "column_type" in values:
            values = {k: v for k, v in values.items() if k != "column_type"}
        return values


class ExpressionCalculation(Calculation):
    """A column calculated by an expression of columns, numbers and math functions."""

    kind: Literal["expression"] = "expression"
    expression: str = Field(
        default="",
        title="Expression",
        description="Arithmetic, comparisons and math functions (log, sqrt, ...), with"
        " the column names as in the table, e.g. NAD(P)H tm / FAD tm.",
        json_schema_extra={"wide": True},
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


def _default_calculations() -> list[FunctionCalculation]:
    """Return the default calculations, from `flim.core.preprocessor`."""
    from flim.core.preprocessor import DEFAULT_CALCULATIONS

    return [
        FunctionCalculation(name=n, function=f, args=list(a))
        for n, f, a in DEFAULT_CALCULATIONS
    ]


class CalculateConfig(DataTaskConfig):
    """Config of Calculate: new columns, in order; later ones may use earlier ones."""

    hidden_fields = frozenset({"features", "grouping"})

    calculations: list[CalculationEntry] = Field(
        default_factory=_default_calculations,
        title="Calculations",
        description="In order; a calculation that uses a column the table doesn't"
        " have is skipped.",
    )


class SourceFromPathConfig(DataTaskConfig, ProtectedNamesConfig):
    """Config of Directory/File to Source: the `Source` column from the paths."""

    hidden_fields = frozenset({"features", "grouping"})

    keep_original: bool = Field(
        default=True,
        title="Keep Directory and File",
        description="Unchecked: the Directory and File columns are removed.",
    )


class TableReaderConfig(TaskConfig, ReadSettings):
    """How Open Tables reads data files, one table per file."""

    hidden_fields = frozenset({"grouping", "features", "prefix", "resources"})

    def read_settings(self) -> ReadSettings:
        """Return the read settings alone (for `flim.core.reader`)."""
        return ReadSettings(**{name: getattr(self, name) for name in ReadSettings.model_fields})


class ImportTablesConfig(TableReaderConfig):
    """How Import Tables reads data files, and the workflow it runs on the tables."""

    workflow: Optional[str] = Field(
        default=None,
        title="Workflow",
        description="The workflow run on the tables: the name of a workflow, or the"
        " path of a workflow file. None: the tables are opened as they are read.",
    )
