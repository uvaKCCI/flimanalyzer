"""Data tools: reorder, combine, filter and reshape tables."""

import logging
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
import pandas as pd

from flim.configs.data import (
    CalculateConfig,
    DropColumnsConfig,
    FilterNode,
    RenameColumnsConfig,
    FuseCategoriesConfig,
    SeparateCategoriesConfig,
    SourceFromPathConfig,
    ScaleConfig,
    CategoryOrderConfig,
    ConcatConfig,
    FilterConfig,
    MergeConfig,
    PivotConfig,
    SortConfig,
    SplitConfig,
    UnpivotConfig,
)
from flim.core import headers
from flim.core.columns import free_names, make_room, unique_name  # noqa: F401  (tests)
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.tool import Tool
from flim.core.types import InputSpec, OutputSpec, TableType
from flim.tools.common import (
    categories_first,
    category_columns,
    first_line,
    selected_features,
    set_lineage,
)

if TYPE_CHECKING:
    from flim.core.categories import Result
    from flim.core.settings import AppSettings

logger = logging.getLogger(__name__)


@register_tool
class CategoryOrder(Tool[CategoryOrderConfig]):
    """Sets the order of the values of category columns and sorts the rows by them."""

    name = "Order Categories"
    category = "Data"
    description = "Sets the order of category values and sorts the rows by them."
    icon = "order.png"
    outputs = (OutputSpec("Reordered", TableType),)

    def run(
        self, data: pd.DataFrame, *, config: CategoryOrderConfig
    ) -> dict[str, Any]:
        """Set the order of the values of the configured category columns.

        The configured columns stay at the positions the table has for them, but in
        the order of the config. Each becomes an ordered category column with the
        configured values; a value that is not configured becomes missing. The rows
        are sorted by the columns, in the configured order; the sort is stable, so
        rows with equal values keep their order. The rows are renumbered from 0.

        Args:
            data: The table.
            config: The category columns and their values in order (`categories`).

        Returns:
            `Reordered`: the table; without configured columns an unchanged copy.
        """
        data = data.copy()
        categories = config.categories
        if not categories:
            return {"Reordered": data}
        # the configured columns keep their positions in the table, filled in the
        # configured order
        new_order = list(categories)
        columns = [new_order.pop(0) if c in categories else c for c in data.columns]
        data = data[columns]
        for column, values in categories.items():
            data[column] = pd.Categorical(data[column], categories=values, ordered=True)
        # stable sort: rows with equal category values keep their previous order;
        # the rows are renumbered in their new order (#119)
        data = data.sort_values(by=list(categories), kind="stable", ignore_index=True)
        return {"Reordered": data}


def _row_mismatch(first: pd.DataFrame, other: pd.DataFrame) -> Optional[str]:
    """Return the first row difference of two tables in words; None if none."""
    if len(first) != len(other):
        return f"{len(first)} and {len(other)} rows"
    shared = [c for c in category_columns(first) if c in category_columns(other)]
    if not shared:
        return None
    a = first[shared].astype(str).reset_index(drop=True)
    b = other[shared].astype(str).reset_index(drop=True)
    differ = (a != b).any(axis=1)
    if not differ.any():
        return None
    row = int(differ.idxmax())
    column = next(c for c in shared if a.at[row, c] != b.at[row, c])
    return f"first difference in row {row + 1}, {column}: {a.at[row, column]} and {b.at[row, column]}"


INPUT = "Input"  # Concatenate's column: the table each row came from
SOURCE = "Source"  # each row's origin, a URI (flim.core.reader.SOURCE)


@register_tool
class Concat(Tool[ConcatConfig]):
    """Appends tables below each other (rows) or next to each other (columns)."""

    name = "Concatenate"
    former_names = ("Concat Data",)
    short_name = "Concat"
    category = "Data"
    description = "Appends tables below (rows) or next to (columns) each other."
    icon = "concatenate.png"
    inputs = (InputSpec("tables", TableType, many=True),)
    outputs = (OutputSpec("Concatenated", TableType),)

    @classmethod
    def inapplicable_fields(
        cls, config: ConcatConfig, tables: Sequence[Any]
    ) -> set[str]:
        """Return `clash_name` if no `Input` column is added or none is in the way.

        No `Input` column is added for columns side by side or without `add_input`;
        with known tables, `clash_name` also doesn't apply if none of them has an
        `Input` column.
        """
        frames = [t for t in tables if isinstance(t, pd.DataFrame)]
        if config.mode == "horizontal" or not config.add_input:
            return {"clash_name"}  # no Input column is added
        if frames and not any(INPUT in t.columns for t in frames):
            return {"clash_name"}  # no table has an Input column to rename
        return set()

    @classmethod
    def validate_data(cls, config: ConcatConfig, tables: Sequence[Any]) -> list[Issue]:
        """Warn that a table's own `Input` column is renamed by `clash_name`.

        One warning at most, for the first such table; none if no `Input` column is
        added.
        """
        if config.mode == "horizontal" or not config.add_input:
            return []
        issues = []
        for i, table in enumerate(tables):
            renames = make_room(
                table.columns, [INPUT], config.clash_name,
                tool=cls.short(), table=f"table {i + 1}",
            )  # fmt: skip
            if renames:
                issues.append(
                    Issue("clash_name", f"a table has an '{INPUT}' column: it is renamed"
                          f" by '{config.clash_name}'", "warning")
                )
                break
        return issues

    def run(
        self, tables: dict[str, pd.DataFrame], *, config: ConcatConfig
    ) -> dict[str, Any]:
        """Append the tables below or next to each other.

        A single table is passed on as a copy, without an `Input` column.

        Rows (`mode` `vertical`): the rows of the tables in order, numbered from 0.
        A column that is a category column in any table is a category column in the
        result. With `add_input`, a first column `Input` holds each row's table name;
        an `Input` column a table already has is renamed by `clash_name`, with a
        warning.

        Columns (`mode` `horizontal`): the columns of the tables side by side; rows
        are paired by position (first with first, and so on). A warning names a table whose number of rows or
        shared category values differ from the first table's. With `numbers_only`,
        only the numeric columns of the other tables are added. A column name that an
        earlier table uses gets the table's name appended: `<column> (<table>)`.

        Args:
            tables: The tables by name, in order.
            config: `mode`, `add_input`, `clash_name` and `numbers_only`.

        Returns:
            `Concatenated`: the table.
        """
        horizontal = config.mode == "horizontal"
        frames = list(tables.values())
        if len(frames) == 1:  # nothing to join: the table as it is (no Input column)
            logger.info(f"{self.name}: one table, passed on unchanged")
            return {"Concatenated": frames[0].copy()}
        if horizontal:
            # side by side, rows are paired by position: warn if the tables' shared
            # category columns don't match row by row (e.g. one was reordered)
            names = list(tables)
            for name, df in zip(names[1:], frames[1:]):
                mismatch = _row_mismatch(frames[0], df)
                if mismatch:
                    self.warn(
                        f"the rows of '{name}' don't match '{names[0]}' ({mismatch});"
                        " rows are paired by position. To pair rows by their"
                        " categories, use Merge."
                    )
            if config.numbers_only:
                # the first table keeps all its columns
                frames = [
                    df if i == 0 else df.select_dtypes(np.number)
                    for i, df in enumerate(frames)
                ]
            # a column name that an earlier table already uses gets the table's name
            # appended, "<column> (<table>)" (#176), also with numeric columns only:
            # two columns of the same name cause errors in the tools that use them
            taken = set()
            for i, (name, df) in enumerate(zip(tables, frames)):
                frames[i] = df.rename(
                    columns={c: f"{c} ({name})" for c in df.columns if c in taken}
                )
                taken.update(frames[i].columns)
            # rows are paired by position: the tables' own row labels (e.g. of rows
            # left after filtering) would pair rows by label and add empty rows
            frames = [df.reset_index(drop=True) for df in frames]
            return {"Concatenated": pd.concat(frames, axis=1, copy=True)}
        # an Input column a table already has (e.g. from an earlier Concatenate) is
        # renamed, by default "Input (<table>)"
        for i, (name, df) in enumerate(zip(tables, frames) if config.add_input else ()):
            renames = make_room(
                df.columns, [INPUT], config.clash_name,
                tool=self.short(), table=name,
            )  # fmt: skip
            if renames:
                frames[i] = df.rename(columns=renames)
                self.warn(f"{name}: the column '{INPUT}' is renamed '{renames[INPUT]}'")
        catcols = list(dict.fromkeys(c for df in frames for c in category_columns(df)))
        concat = pd.concat(frames, axis=0, copy=True, keys=list(tables))
        names = concat.index.get_level_values(0)  # the table of each row
        concat = concat.reset_index(drop=True)
        concat[catcols] = concat[catcols].astype("category")
        if config.add_input:
            concat.insert(0, INPUT, pd.Categorical(names))  # categories sorted, as in 0.6
        return {"Concatenated": concat}


@register_tool
class Filter(Tool[FilterConfig]):
    """Keeps the rows that a tree of filters keeps."""

    name = "Filter"
    category = "Data"
    description = (
        "Keeps the rows that the filters keep: values in ranges, category values,"
        " conditions; the table windows use the same filters."
    )
    icon = "filter.png"
    outputs = (OutputSpec("Filtered", TableType),)

    def run(self, data: pd.DataFrame, *, config: FilterConfig) -> dict[str, Any]:
        """Keep the rows that every top-level filter keeps.

        A filter on a column the table doesn't have keeps all rows and is reported as
        a skipped part of the settings. The rows each filter drops are logged.

        Args:
            data: The table.
            config: The filter tree (`filters`).

        Returns:
            `Filtered`: the rows kept, numbered from 0.
        """
        from flim.core.filtering import apply_filters, leaf_counts

        outcome = apply_filters(data, config.filters)
        # parts: a filter on a column the table doesn't have keeps all rows
        self.applied(len(outcome.dropped) - len(outcome.notes))
        for path, note in outcome.notes.items():
            self.skip(f"{path}: {note}")
        line = leaf_counts(outcome)
        if line:
            logger.info(f"{self.name}: {line}")
        return {"Filtered": outcome.data.copy()}

    @classmethod
    def validate(cls, config: FilterConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config against the input schema.

        A column of an enabled filter that the input doesn't have is a warning (the
        filter keeps all rows); for a disabled filter it is no issue. The filter tree
        itself is checked by `flim.core.filtering.check`. A value of an enabled
        category filter that its column doesn't have is a warning.
        """
        from flim.core.filtering import check

        enabled = set(_enabled_paths(config.filters, "filters"))
        issues = []
        for issue in super().validate(config, inputs):
            node = (issue.field or "").rsplit(".", 1)[0]
            if "is not in the input" in issue.message and node.startswith("filters["):
                # a filter on a missing column keeps all rows (as up to 0.6)
                if node in enabled:
                    message = issue.message.replace("is not in the input", "is not in the input: keeps all rows")
                    issues.append(Issue(issue.field, message, "warning"))
                continue
            issues.append(issue)
        schema = inputs[0] if inputs else None
        complete = schema is not None and schema.complete
        columns = schema.names if complete else None
        issues += [Issue(f, m, sev) for f, sev, m in check(config.filters, columns)]
        if schema is None:
            return issues
        for path, node in _leaves(config.filters, "filters"):
            if node.kind != "category" or not node.enabled:
                continue
            info = schema.column(node.column)
            if info is None or info.levels is None:
                continue
            missing = [v for v in node.keep if v not in info.levels]
            if missing:
                issues.append(
                    Issue(f"{path}.keep", f"Values not in '{node.column}': {missing}", "warning")
                )
        return issues


def _leaves(
    filters: Sequence[FilterNode], path: str
) -> Iterator[tuple[str, FilterNode]]:
    """Yield (path, node) of every leaf of a filter list, also in groups."""
    for i, node in enumerate(filters):
        where = f"{path}[{i}]"
        if node.kind in ("all", "any", "not"):
            yield from _leaves(node.filters, f"{where}.filters")
        else:
            yield where, node


def _enabled_paths(
    filters: Sequence[FilterNode], path: str, enabled: bool = True
) -> Iterator[str]:
    """Yield the paths of the nodes that are enabled, with all groups above them."""
    for i, node in enumerate(filters):
        where = f"{path}[{i}]"
        on = enabled and node.enabled
        if on:
            yield where
        if node.kind in ("all", "any", "not"):
            yield from _enabled_paths(node.filters, f"{where}.filters", on)


@register_tool
class Merge(Tool[MergeConfig]):
    """Joins two tables on category columns."""

    name = "Merge"
    category = "Data"
    description = "Joins two tables on their shared category columns."
    icon = "merge.png"
    inputs = (InputSpec("left", TableType), InputSpec("right", TableType))
    outputs = (OutputSpec("Merged", TableType),)

    def run(
        self, left: pd.DataFrame, right: pd.DataFrame, *, config: MergeConfig
    ) -> dict[str, Any]:
        """Join two tables on category columns.

        Other columns that both tables have get the suffixes. With
        `combine_identical`, such a pair becomes one column if the two have the same
        value in every row where both have one; the missing values of the first are
        taken from the second. A warning names the pairs that keep the suffixes.

        Args:
            left: The first table.
            right: The second table.
            config: The join (`how`: `inner`, `outer`, `left` or `right`), the
                columns to join on (`on`; None: the category columns both tables
                have), `combine_identical`, and the suffixes `suffix_left` and
                `suffix_right`.

        Returns:
            `Merged`: the joined table, its category columns first; the columns
            joined on are category columns.
        """
        on = config.on
        if on is None:
            right_cats = set(category_columns(right))
            on = [c for c in category_columns(left) if c in right_cats]
        suffixes = (config.suffix_left, config.suffix_right)
        merged = pd.merge(left, right, how=config.how, on=on, suffixes=suffixes)
        merged[on] = merged[on].astype("category")
        # columns both tables have (not merged on): one column if they agree
        shared = [c for c in left.columns if c in right.columns and c not in on]
        kept = []
        for column in shared:
            a, b = (merged[f"{column}{s}"] for s in suffixes)
            if config.combine_identical and _agree(a, b):
                position = list(merged.columns).index(a.name)
                values = _combined(a, b)
                merged = merged.drop(columns=[a.name, b.name])
                merged.insert(position, column, values)
            else:
                kept.append(column)
        if kept:
            listed = ", ".join(f"'{c}'" for c in kept[:5]) + (" ..." if len(kept) > 5 else "")
            self.warn(
                f"{len(kept)} column(s) of both tables differ and keep the suffixes"
                f" '{suffixes[0]}', '{suffixes[1]}': {listed}"
            )
        return {"Merged": categories_first(merged)}


def _agree(a: pd.Series, b: pd.Series) -> bool:
    """Return whether two columns agree in every row where both have a value."""
    both = a.notna() & b.notna()
    if not both.any():
        return True
    return bool((a[both].astype(object) == b[both].astype(object)).all())


def _combined(a: pd.Series, b: pd.Series) -> pd.Series:
    """Return column `a` with its missing values taken from `b`, in `a`'s type."""
    fill = a.isna() & b.notna()
    result = a.copy()
    if not fill.any():
        return result
    if isinstance(result.dtype, pd.CategoricalDtype):
        new = [v for v in pd.unique(b[fill]) if v not in result.cat.categories]
        result = result.cat.add_categories(new)
    result[fill] = b[fill]
    return result


@register_tool
class Pivot(Tool[PivotConfig]):
    """Turns the values of category columns into columns."""

    name = "Pivot"
    category = "Data"
    description = "Turns the values of the grouping columns into columns."
    icon = "pivot.png"
    outputs = (OutputSpec("Pivoted", TableType),)

    def run(self, data: pd.DataFrame, *, config: PivotConfig) -> dict[str, Any]:
        """Turn the values of the grouping columns into columns.

        The other category columns are the rows; each row holds the mean of the
        feature over the input rows with the same category values. A new column's
        header has the feature's lines and a line for the value of each grouping
        column, e.g. `FLIRR` and `ctrl`. Rows and columns without any value are left
        out.

        Args:
            data: The table.
            config: The columns to pivot (`grouping`) and the features.

        Returns:
            `Pivoted`: the other category columns, then a column per feature and
            combination of the grouping columns' values. The header level names are
            the features' level names followed by the grouping columns.
        """
        features = selected_features(data, config.features)
        categories = category_columns(data)
        index = [c for c in categories if c not in config.grouping]
        logger.debug(f"pivoting {config.grouping}, index {index}")
        table = pd.pivot_table(
            data[features + categories],
            index=index,
            columns=config.grouping,
            observed=False,
        )
        table.columns = [headers.join(col).strip() for col in table.columns.values]
        # levels: the features' own (e.g. of a summary), then the pivoted columns
        feature_levels = headers.names_for(
            headers.depth(features), headers.level_names(data)
        )
        table = table.reset_index()
        return {
            "Pivoted": headers.set_level_names(
                table, feature_levels + list(config.grouping)
            )
        }

    @classmethod
    def output_schema(
        cls, config: PivotConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs; each pivoted column is derived from its feature."""
        # "<feature>\n<value>[\n<value>...]" columns come from <feature>
        return set_lineage(super().output_schema(config, inputs), first_line)


@register_tool
class Sort(Tool[SortConfig]):
    """Sorts the rows by columns."""

    name = "Sort"
    category = "Data"
    description = "Sorts the rows by the selected columns."
    icon = "sort.png"
    outputs = (OutputSpec("Sorted", TableType),)

    def run(self, data: pd.DataFrame, *, config: SortConfig) -> dict[str, Any]:
        """Sort the rows by the selected columns, in their order.

        Args:
            data: The table.
            config: The columns to sort by (`features`), the direction for all of
                them (`ascending`), and whether the rows are renumbered from 0
                (`ignore_index`).

        Returns:
            `Sorted`: the sorted table.
        """
        features = selected_features(data, config.features)
        return {
            "Sorted": data.sort_values(
                by=features,
                ascending=len(features) * [config.ascending],
                ignore_index=config.ignore_index,
            )
        }


@register_tool
class Split(Tool[SplitConfig]):
    """Splits a table into one table per combination of category values."""

    name = "Split"
    category = "Data"
    description = (
        "Splits the table into one table for each combination of the values of the"
        " selected category columns."
    )
    icon = "split.png"

    @staticmethod
    def table_name(grouping: Sequence[str], values: Any) -> str:
        """Return the name of a split table, e.g. `Split: Treatment=ctrl, FOV=1`.

        Args:
            grouping: The columns split by.
            values: The table's values of these columns: a tuple, or one value.

        Returns:
            The name, made of the columns and their values, for example
            `Split: <column>=<value>, ...`.
        """
        values = values if isinstance(values, tuple) else (values,)
        return "Split: " + ", ".join(f"{c}={v}" for c, v in zip(grouping, values))

    def run(self, data: pd.DataFrame, *, config: SplitConfig) -> dict[str, Any]:
        """Split the table by the values of the grouping columns.

        Args:
            data: The table.
            config: The columns to split by (`grouping`).

        Returns:
            One table per combination of the columns' values that has rows, named as
            by `table_name`, in the order of the categories.
        """
        grouping = list(config.grouping)
        # in the order of the categories; combinations without rows are left out
        return {
            self.table_name(grouping, values): group.copy()
            for values, group in data.groupby(grouping, observed=True, sort=True)
        }


@register_tool
class Unpivot(Tool[UnpivotConfig]):
    """Moves one line of the column headers into a category column."""

    name = "Unpivot"
    category = "Data"
    description = (
        "Moves one level (line) of the selected columns' headers into a category"
        " column; the other lines name the value columns. The inverse of Pivot."
    )
    icon = "unpivot.png"
    outputs = (OutputSpec("Unpivoted", TableType),)

    # the value column of single-line columns (no other level names it)
    VALUE = "Value"

    @staticmethod
    def lines(column: str, depth: int) -> list[str]:
        """Return a column's header lines, padded at the end with empty lines.

        Used for a column with fewer lines than the others, e.g. `FLIRR` next to
        `FLIRR / standardized`.

        Args:
            column: The column name; its lines are separated by line breaks.
            depth: The number of lines to return, at least the column's own.

        Returns:
            The lines.
        """
        parts = headers.split(column)
        return parts + [""] * (depth - len(parts))

    @classmethod
    def validate_data(
        cls, config: UnpivotConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Warn about selected columns whose headers have fewer lines than others.

        Their missing lines count as `missing_label`. Only the first input table is
        checked.
        """
        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return []
        columns = selected_features(table, config.features)
        depth = headers.depth(columns)
        shorter = [c.replace("\n", " / ") for c in columns if len(headers.split(c)) < depth]
        if not shorter:
            return []
        named = ", ".join(f"'{c}'" for c in shorter[:5]) + (", ..." if len(shorter) > 5 else "")
        return [
            Issue(
                "missing_label",
                f"{named} {'has' if len(shorter) == 1 else 'have'} fewer header"
                f" lines than the other columns: the missing lines count as"
                f" '{config.missing_label}'",
                "warning",
            )
        ]

    def run(self, data: pd.DataFrame, *, config: UnpivotConfig) -> dict[str, Any]:
        """Move one line of the selected columns' headers into a category column.

        For each value of the line, the result has a copy of the category columns
        with that value in the new category column, and a value column for each of
        the other header lines' combinations; a column without other lines goes into
        the value column `Value`. An empty line (also a missing one) gets the value
        `missing_label`. A value column name that a category column has is numbered.

        Args:
            data: The table.
            config: The columns to unpivot (`features`), the header line (`level`:
                a level name, a position such as `2` or `Level 2`, or empty for the
                last), the new column's name
                (`category_name`; None: the level's name, numbered if taken) and
                `missing_label`.

        Returns:
            `Unpivoted`: the category columns, the new category column (its
            categories in the order the values occur), then the value columns. The
            header level names are the input's without the moved level.

        Raises:
            ValueError: If no columns are selected, or `level` matches no header
                level.
        """
        categories = category_columns(data)
        columns = selected_features(data, config.features)
        if not columns:
            raise ValueError(f"{self.name}: select the columns to unpivot")
        depth = headers.depth(columns)
        names = headers.names_for(depth, headers.level_names(data))
        index = headers.level_index(config.level, names)
        category = unique_name(config.category_name or "", names[index], categories)
        # level value -> {value column: input column}, in the columns' order
        values: dict = {}
        for column in columns:
            parts = self.lines(column, depth)
            value = parts.pop(index) or config.missing_label
            name = headers.join([p for p in parts if p])
            values.setdefault(value, {})[name or self.VALUE] = column
        # value column names that a category column has are numbered
        wanted = list(dict.fromkeys(n for s in values.values() for n in s))
        value_names = dict(zip(wanted, free_names(wanted, categories + [category])))
        pieces = []
        for value, sources in values.items():
            piece = data[categories].copy()
            piece[category] = value
            for name, column in sources.items():
                piece[value_names[name]] = data[column]
            pieces.append(piece)
        table = pd.concat(pieces, ignore_index=True)
        table[category] = pd.Categorical(table[category], categories=list(values))
        first = categories + [category]
        table = table[first + [c for c in table if c not in first]]
        rest = names[:index] + names[index + 1 :]
        return {"Unpivoted": headers.set_level_names(table, rest)}


# the line added to the names of scaled columns, per method
SCALED = {"standardize": "standardized", "min-max": "min-max", "robust": "robust"}


def _scaler(method: str) -> Callable[[np.ndarray], np.ndarray]:
    """Return a function that scales the columns of a 2D array by a `Scale` method."""
    if method == "standardize":
        from flim.tools.ml import standardized  # the same as Standardize input

        return standardized
    from sklearn.preprocessing import MinMaxScaler, RobustScaler

    scaler = {"min-max": MinMaxScaler, "robust": RobustScaler}[method]
    return lambda values: scaler().fit_transform(values)


@register_tool
class Scale(Tool[ScaleConfig]):
    """Scales features: standardize, min-max or robust, overall or per group."""

    name = "Scale"
    icon = "scale.png"
    category = "Analysis"
    description = (
        "Scales the selected features: standardize (mean 0, standard deviation 1),"
        " min-max (0 to 1) or robust (median 0, interquartile range 1), over the whole"
        " table or within each group."
    )
    outputs = (OutputSpec("Scaled", TableType),)

    def run(self, data: pd.DataFrame, *, config: ScaleConfig) -> dict[str, Any]:
        """Scale the selected features, over the whole table or within each group.

        The methods: `standardize` (mean 0, standard deviation 1), `min-max` (0 to
        1), `robust` (median 0, interquartile range 1). Groups include rows with
        missing grouping values.

        Args:
            data: The table.
            config: The features, `method`, the grouping columns (none: the whole
                table) and `keep_original`.

        Returns:
            `Scaled`: the table with the scaled features, named `<feature>` with a
            line `standardized`, `min-max` or `robust` added, numbered if the name is
            taken. With `keep_original` they are added at the end; otherwise they
            replace the features in their places.

        Raises:
            ValueError: If no features are selected.
        """
        features = selected_features(data, config.features)
        if not features:
            raise ValueError(f"{self.name}: select the features to scale")
        scale = _scaler(config.method)
        values = data[features].astype(float)

        def scaled(frame):
            return pd.DataFrame(scale(frame.to_numpy()), index=frame.index, columns=features)

        if config.grouping:
            groups = values.groupby(
                [data[g] for g in config.grouping], observed=True, dropna=False
            )
            result = pd.concat([scaled(frame) for _, frame in groups]).reindex(data.index)
        else:
            result = scaled(values)
        suffix = SCALED[config.method]
        table = data.copy()
        # generated names the table has (e.g. from scaling before) are numbered
        if config.keep_original:
            names = free_names([f"{f}\n{suffix}" for f in features], table.columns)
            for feature, name in zip(features, names):
                table[name] = result[feature]
        else:  # the scaled columns replace the originals, in their place
            for feature in features:
                table[feature] = result[feature]
            others = [c for c in table.columns if c not in features]
            names = free_names([f"{f}\n{suffix}" for f in features], others)
            table = table.rename(columns=dict(zip(features, names)))
        return {"Scaled": table}


def _with_columns(
    data: pd.DataFrame,
    new: dict[str, Any],
    after: str,
    remove: Sequence[str] = (),
) -> pd.DataFrame:
    """Return the table with new columns after a column, and some columns removed.

    New names that are taken get a number (`unique_name`).
    """
    table = data.copy()
    position = list(table.columns).index(after) + 1
    for offset, (name, values) in enumerate(new.items()):
        taken = [c for c in table.columns if c not in remove]
        table.insert(position + offset, unique_name(name, name, taken), values)
    return table.drop(columns=list(remove))


@register_tool
class FuseCategories(Tool[FuseCategoriesConfig]):
    """Joins category columns into one category column, e.g. FOV and Cell."""

    name = "Fuse Categories"
    icon = "fuse.png"
    category = "Data"
    description = (
        "Joins category columns into one category column, e.g. FOV and Cell into"
        " FOV:Cell; Separate Categories reverses it."
    )
    outputs = (OutputSpec("Fused", TableType),)

    @classmethod
    def example(
        cls, config: FuseCategoriesConfig, tables: Sequence[Any]
    ) -> Optional[str]:
        """Return the fusion of the first row that has values in all the columns.

        For example `FOV 1, Cell 2 → FOV:Cell 1:2`. None if fewer than two columns
        are selected, the first table lacks one of them, or no row has values in all
        of them.
        """
        from flim.core.categories import fuse

        columns = list(config.grouping)
        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if len(columns) < 2 or table is None or not set(columns) <= set(table.columns):
            return None
        rows = table[columns].dropna()
        if rows.empty:
            return None
        first = rows.iloc[[0]]
        ((name, values),) = fuse(first, columns, config.delimiter, config.name).columns.items()
        parts = ", ".join(f"{c} {first[c].iloc[0]}" for c in columns)
        return f"{parts} \u2192 {name} {values[0]}"

    @classmethod
    def validate_data(
        cls, config: FuseCategoriesConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Warn where the delimiter occurs in the column names or values of a table.

        Then separating the fused column back would be ambiguous. Tables without all
        the selected columns, and fewer than two columns, are not checked.
        """
        from flim.core.categories import fuse

        columns = list(config.grouping)
        issues = []
        for table in tables:
            if not isinstance(table, pd.DataFrame) or not set(columns) <= set(table.columns):
                continue
            if len(columns) < 2:
                continue
            combinations = table[columns].drop_duplicates()  # few: category values
            for message in fuse(combinations, columns, config.delimiter).warnings:
                issues.append(Issue("delimiter", message, "warning"))
        return issues

    def run(
        self, data: pd.DataFrame, *, config: FuseCategoriesConfig
    ) -> dict[str, Any]:
        """Join the values of category columns into one category column.

        The values are joined by the delimiter, e.g. `1` and `2` into `1:2`; a row
        with a missing value in one of the columns gets a missing value. A warning
        is reported if the delimiter occurs in the column names or values.

        Args:
            data: The table.
            config: The columns, in the order their values are joined (`grouping`),
                `delimiter`, the new column's name (`name`; None: the column names
                joined by the delimiter) and `keep_original`.

        Returns:
            `Fused`: the table with the new column after the last fused column
            (numbered if its name is taken); without `keep_original` the fused
            columns are removed.
        """
        from flim.core.categories import fuse

        columns = list(config.grouping)
        result = fuse(data, columns, config.delimiter, config.name)
        for message in result.warnings:
            self.warn(message)
        remove = () if config.keep_original else columns
        return {"Fused": _with_columns(data, result.columns, columns[-1], remove)}


@register_tool
class SeparateCategories(Tool[SeparateCategoriesConfig]):
    """Separates a category column into several, at delimiters or by patterns."""

    name = "Separate Categories"
    icon = "separate.png"
    category = "Data"
    description = (
        "Separates a category column into several: at delimiters (the reverse of"
        " Fuse Categories), or by patterns, as the filename parser does."
    )
    outputs = (OutputSpec("Separated", TableType),)

    @classmethod
    def _separated(
        cls, config: SeparateCategoriesConfig, data: pd.DataFrame
    ) -> "Result":
        """Return the new columns and warnings of the config's mode."""
        from flim.core.categories import separate, separate_by_patterns, separate_by_template

        if config.mode == "pattern":
            patterns = [(p.name, p.regex) for p in config.patterns]
            return separate_by_patterns(data, config.column, patterns, config.part)
        if config.mode == "template":
            return separate_by_template(data, config.column, config.template, config.part)
        return separate(data, config.column, config.delimiters, config.names, config.part)

    @staticmethod
    def _incomplete(config: SeparateCategoriesConfig) -> bool:
        """Return whether the mode's settings are empty (nothing to show or check)."""
        return (config.mode == "pattern" and not config.patterns) or (
            config.mode == "template" and not config.template.strip()
        )

    @classmethod
    def _table(
        cls, config: SeparateCategoriesConfig, tables: Sequence[Any]
    ) -> Optional[pd.DataFrame]:
        """Return the first table that has the column to separate; None if none."""
        return next(
            (
                t
                for t in tables
                if isinstance(t, pd.DataFrame) and config.column in t.columns
            ),
            None,
        )

    @classmethod
    def example(
        cls, config: SeparateCategoriesConfig, tables: Sequence[Any]
    ) -> Optional[str]:
        """Return how the column's first value is separated.

        For example `1:2 → FOV 1, Cell 2`. An invalid setting (e.g. a pattern)
        shows its error message after the arrow. None if no table has the column,
        the column has no values, or the mode's settings are empty.
        """
        table = cls._table(config, tables) if config.column else None
        if table is None or cls._incomplete(config):
            return None
        values = table[config.column].dropna()
        if values.empty:
            return None
        first = table.loc[[values.index[0]]]
        try:
            result = cls._separated(config, first)
        except ValueError as err:  # e.g. an invalid pattern: shown as an issue
            return f"{values.iloc[0]} \u2192 {err}"
        parts = [f"{n} {v[0]}" for n, v in result.columns.items() if not pd.isna(v[0])]
        shown = ", ".join(parts) if parts else "not separated"
        return f"{values.iloc[0]} \u2192 {shown}"

    @classmethod
    def validate_data(
        cls, config: SeparateCategoriesConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Separate the column's distinct values and return the problems found.

        An invalid setting is an error, the separation's warnings (e.g. values that
        could not be separated) are warnings, on the mode's field: `names`,
        `patterns` or `template`.
        """
        table = cls._table(config, tables) if config.column else None
        if table is None or cls._incomplete(config):
            return []
        field = {"pattern": "patterns", "template": "template"}.get(config.mode, "names")
        distinct = table[[config.column]].drop_duplicates()  # few: category values
        try:
            result = cls._separated(config, distinct)
        except ValueError as err:
            return [Issue(field, str(err))]
        return [Issue(field, message, "warning") for message in result.warnings]

    @classmethod
    def validate(
        cls, config: SeparateCategoriesConfig, schemas: Sequence[Any] = ()
    ) -> list[Issue]:
        """Check the config: a column, a pattern or a valid template is needed.

        A column must be selected; the pattern mode needs at least one pattern, the
        template mode a valid template.
        """
        issues = list(super().validate(config, schemas))
        if config.column is None:
            issues.append(Issue("column", "Select the column to separate"))
        if config.mode == "pattern" and not config.patterns:
            issues.append(Issue("patterns", "Add at least one pattern"))
        if config.mode == "template":
            from flim.core.categories import template_regex

            try:
                template_regex(config.template)
            except ValueError as err:
                issues.append(Issue("template", str(err)[:1].upper() + str(err)[1:]))
        return issues

    def run(
        self, data: pd.DataFrame, *, config: SeparateCategoriesConfig
    ) -> dict[str, Any]:
        """Separate a category column into several new category columns.

        The separation's warnings are reported.

        Args:
            data: The table.
            config: The column, the part of its values (`part`), the mode and its
                settings: `delimiters` and `names` (`delimiter`), `patterns`
                (`pattern`) or `template` (`template`); and `keep_original`.

        Returns:
            `Separated`: the table with the new columns after the column (numbered
            if their names are taken); without `keep_original` the column is
            removed.

        Raises:
            ValueError: If no column is selected, or the mode's settings are not
                valid (no delimiter, an invalid pattern or template).
        """
        if config.column is None:
            raise ValueError(f"{self.name}: select the column to separate")
        result = self._separated(config, data)
        for message in result.warnings:
            self.warn(message)
        remove = () if config.keep_original else [config.column]
        return {"Separated": _with_columns(data, result.columns, config.column, remove)}


@register_tool
class RenameColumns(Tool[RenameColumnsConfig]):
    """Replaces parts of the column names, in order."""

    name = "Rename Columns"
    icon = "renamecolumns.png"
    category = "Data"
    description = (
        "Replaces parts of the column names, in order, e.g. 'Exc1_-Ch1-_' with 'trp '."
    )
    outputs = (OutputSpec("Renamed", TableType),)

    @classmethod
    def example(
        cls, config: RenameColumnsConfig, tables: Sequence[Any]
    ) -> Optional[str]:
        """Return the first column of the first table that is renamed.

        For example `Exc1_-Ch1-_t1 → trp t1 (and 3 more)`; `no column name changes`
        if no name changes; None without a table.
        """
        from flim.core.columns import renamed_columns

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return None
        pairs = [(r.part, r.new) for r in config.replacements]
        changed = [
            (old, new)
            for old, new in zip(table.columns, renamed_columns(table.columns, pairs))
            if str(old) != new
        ]
        if not changed:
            return "no column name changes"
        old, new = changed[0]
        more = f" (and {len(changed) - 1} more)" if len(changed) > 1 else ""
        return f"{old} \u2192 {new}{more}"

    def run(
        self, data: pd.DataFrame, *, config: RenameColumnsConfig
    ) -> dict[str, Any]:
        """Replace parts of the column names, in the order of the replacements.

        A replacement whose part occurs in no column name is reported as a skipped
        part of the settings.

        Args:
            data: The table.
            config: The replacements (`replacements`): each replaces its `part` by
                `new` (see `flim.core.columns.renamed_columns`).

        Returns:
            `Renamed`: the table with the new column names.

        Raises:
            ValueError: If two columns get the same name.
        """
        from flim.core.columns import renamed_columns

        pairs = [(r.part, r.new) for r in config.replacements]
        names = renamed_columns(data.columns, pairs)
        # parts: a replacement whose part occurs in no column name is skipped
        for part, _ in pairs:
            if any(part in str(c) for c in data.columns):
                self.applied()
            else:
                self.skip(f"no column name contains '{part}'")
        if len(set(names)) < len(names):
            duplicates = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(
                f"{self.name}: the new names are not unique: {', '.join(duplicates)}"
            )
        table = data.copy()
        table.columns = names
        return {"Renamed": table}


@register_tool
class DropColumns(Tool[DropColumnsConfig]):
    """Drops columns by their names, and columns with an empty header."""

    name = "Drop Columns"
    icon = "dropcolumns.png"
    category = "Data"
    description = (
        "Drops the columns whose names contain, start with, end with or are a text;"
        " also a column with an empty header."
    )
    outputs = (OutputSpec("Columns Dropped", TableType),)

    @classmethod
    def example(
        cls, config: DropColumnsConfig, tables: Sequence[Any]
    ) -> Optional[str]:
        """Return the columns of the first table that are dropped, e.g. `drops a, b`.

        At most three are named, then the number of the others; `no columns
        dropped` if none is dropped; None without a table.
        """
        from flim.core.columns import columns_to_drop

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return None
        dropped = columns_to_drop(table.columns, [(r.text, r.match) for r in config.drop])
        if not dropped:
            return "no columns dropped"
        dropped = [n if n.strip() else "(empty header)" for n in dropped]
        shown = ", ".join(dropped[:3]) + (f" and {len(dropped) - 3} more" if len(dropped) > 3 else "")
        return f"drops {shown}"

    def run(self, data: pd.DataFrame, *, config: DropColumnsConfig) -> dict[str, Any]:
        """Drop the columns that a rule matches, and columns with an empty header.

        A rule that matches no column is reported as a skipped part of the settings.

        Args:
            data: The table.
            config: The rules (`drop`): a text and how a name matches it
                (`contains`, `starts with`, `ends with` or `is`; see
                `flim.core.columns.matches`).

        Returns:
            `Columns Dropped`: the table without the columns.
        """
        from flim.core.columns import columns_to_drop

        rules = [(r.text, r.match) for r in config.drop]
        dropped = columns_to_drop(data.columns, rules)
        # parts: a rule that matches no column is skipped
        for text, match in rules:
            if columns_to_drop(data.columns, [(text, match)], drop_empty=False):
                self.applied()
            else:
                self.skip(f"no column name {match} '{text}'")
        return {"Columns Dropped": data.drop(columns=dropped)}


@register_tool
class Calculate(Tool[CalculateConfig]):
    """Calculates new columns from others, by expressions or registered functions."""

    name = "Calculate"
    icon = "calculate.png"
    category = "Analysis"
    description = (
        "Calculates new columns from others, in order: by expressions (arithmetic,"
        " comparisons, math functions) or by registered functions such as tm and"
        " ratio."
    )
    outputs = (OutputSpec("Calculated", TableType),)

    @classmethod
    def dialog_config(cls, config: CalculateConfig) -> CalculateConfig:
        """Return the config the dialog opens with: the stored one, no calculations.

        A run from the dialog makes only the calculations set up in it; the stored
        ones are offered as presets.
        """
        return config.model_copy(update={"calculations": []})

    @classmethod
    def _issues(cls, problems: Sequence[tuple[int, str, str, str]]) -> list[Issue]:
        """Return `flim.core.calculate.check`'s problems as issues on their fields."""
        return [
            Issue(f"calculations[{i}].{field}", message, severity)
            for i, field, severity, message in problems
        ]

    @classmethod
    def validate(
        cls, config: CalculateConfig, schemas: Sequence[Any] = ()
    ) -> list[Issue]:
        """Check the config; calculations that can't run are errors.

        For example a missing name, a name used twice, an invalid expression, or an
        unknown function. Columns missing from the input are checked by
        `validate_data`.
        """
        from flim.core.calculate import check

        issues = list(super().validate(config, schemas))
        # with the input's columns, names may be typed without backticks; the columns
        # used are checked against the tables (validate_data)
        schema = schemas[0] if schemas else None
        columns = schema.names if schema is not None and schema.complete else None
        problems = check(config.calculations, columns)
        return issues + cls._issues([p for p in problems if p[2] == "error"])

    @classmethod
    def validate_data(
        cls, config: CalculateConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Warn about calculations that would be skipped for the first table.

        For example a calculation that uses a column that is neither in the table
        nor calculated before (see `flim.core.calculate.check`).
        """
        from flim.core.calculate import check

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return []
        problems = check(config.calculations, list(table.columns))
        return cls._issues([p for p in problems if p[2] == "warning"])

    @classmethod
    def example(cls, config: CalculateConfig, tables: Sequence[Any]) -> Optional[str]:
        """Return the first calculated value for the first row, e.g. `FLIRR = 0.4521`.

        `nothing calculated` if no kept column is calculated; None without a table
        or row, or if the calculation raises a ValueError.
        """
        from flim.core.calculate import calculate

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or table.empty:
            return None
        try:
            outcome = calculate(table.iloc[:1], config.calculations)
        except ValueError:
            return None  # shown as an issue
        shown = [n for n in outcome.calculated if n in outcome.data.columns]
        if not shown:
            return "nothing calculated"
        value = outcome.data[shown[0]].iloc[0]
        text = f"{value:.4g}" if isinstance(value, float) else str(value)
        more = f" (and {len(shown) - 1} more)" if len(shown) > 1 else ""
        return f"{shown[0]} = {text}{more}"

    def run(self, data: pd.DataFrame, *, config: CalculateConfig) -> dict[str, Any]:
        """Calculate the new columns, in order; later ones may use earlier ones.

        A calculation that uses a column the table doesn't have is skipped, with a
        warning. A calculated column named like an input column replaces it, with a
        warning. Columns of calculations with `keep` False are not in the result.

        Args:
            data: The table.
            config: The calculations (`calculations`); see
                `flim.core.calculate.calculate`.

        Returns:
            `Calculated`: the table with the calculated columns.
        """
        from flim.core.calculate import calculate

        outcome = calculate(data, config.calculations)
        self.applied(len(outcome.calculated))
        for name, reason in outcome.skipped.items():
            self.skip(f"{name} skipped: {reason}", warn=True)  # as since it was added
        for name in outcome.replaced:
            self.warn(f"{name}: the input column is replaced")
        return {"Calculated": outcome.data}


def shortened(text: str, most: int = 40) -> str:
    """Return a text shortened to at most `most` characters, for display.

    A longer text keeps its start and end with `…` between, e.g.
    `/data/KCCI/…/9SR/Results-a.txt`.

    Args:
        text: The text, e.g. a path.
        most: The largest number of characters returned. Defaults to 40.

    Returns:
        The text, or its start, `…` and its end.
    """
    if len(text) <= most:
        return text
    head = (most - 1) // 2
    return text[:head] + "\u2026" + text[len(text) - (most - 1 - head):]


@register_tool
class SourceFromPath(Tool[SourceFromPathConfig]):
    """Adds the `Source` column (file URIs) from the `Directory` and `File` columns."""

    name = "Directory/File to Source"
    icon = "source.png"
    short_name = "Add Source"
    category = "Data"
    description = (
        "Adds the Source column, each row's file as a URI (file:///...), built from"
        " the Directory and File columns. For tables imported with FLIMAnalyzer 0.6 or"
        " earlier, which have no Source column."
    )
    outputs = (OutputSpec("With Source", TableType),)

    @classmethod
    def validate(
        cls, config: SourceFromPathConfig, inputs: Sequence[Any]
    ) -> list[Issue]:
        """Check the config; an input without `Directory` or `File` is an error."""
        issues = list(super().validate(config, inputs))
        schema = inputs[0] if inputs else None
        if schema is not None and schema.complete:
            missing = [c for c in ("Directory", "File") if schema.column(c) is None]
            if missing:
                issues.append(Issue(None, f"The table has no {' or '.join(missing)} column"))
        return issues

    @classmethod
    def _renames(
        cls, config: SourceFromPathConfig, tables: Sequence[Any]
    ) -> dict[str, str]:
        """Return the table's own Source column and its new name; {} if none."""
        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return {}
        return make_room(table.columns, [SOURCE], config.clash_name, tool=cls.short())

    @classmethod
    def inapplicable_fields(
        cls, config: SourceFromPathConfig, tables: Sequence[Any]
    ) -> set[str]:
        """Return `clash_name` if the known table has no `Source` column to rename."""
        if not any(isinstance(t, pd.DataFrame) for t in tables):
            return set()  # the tables are not known
        return set() if cls._renames(config, tables) else {"clash_name"}

    @classmethod
    def validate_data(
        cls, config: SourceFromPathConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Warn that the table's own `Source` column is renamed by `clash_name`."""
        return [
            Issue("clash_name", f"the table has a '{old}' column: it is renamed '{new}'", "warning")
            for old, new in cls._renames(config, tables).items()
        ]

    @classmethod
    def example(
        cls, config: SourceFromPathConfig, tables: Sequence[Any]
    ) -> Optional[str]:
        """Return the first row's directory and file and their URI, shortened.

        For example `/data + a.txt → file:///data/a.txt`. None without a table with
        rows and both columns, or if the first row lacks one of the values.
        """
        from flim.core.paths import path_uri

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or not {"Directory", "File"} <= set(table.columns) or table.empty:
            return None
        directory, file = table["Directory"].iloc[0], table["File"].iloc[0]
        if pd.isna(directory) or pd.isna(file):
            return None
        uri = path_uri(str(directory), str(file))
        return f"{shortened(str(directory))} + {shortened(str(file))} \u2192 {shortened(uri)}"

    def run(
        self, data: pd.DataFrame, *, config: SourceFromPathConfig
    ) -> dict[str, Any]:
        """Add the `Source` column: each row's file as a URI.

        The URI is built from the `Directory` and `File` columns; a row without a
        directory or file gets no value. A `Source` column the table already has is
        renamed by `clash_name`, with a warning.

        Args:
            data: The table.
            config: `clash_name` and `keep_original`.

        Returns:
            `With Source`: the table with the `Source` column at the end; without
            `keep_original` the `Directory` and `File` columns are removed.

        Raises:
            ValueError: If the table has no `Directory` or no `File` column.
        """
        from flim.core.paths import path_uri

        for column in ("Directory", "File"):
            if column not in data.columns:
                raise ValueError(f"{self.name}: the table has no {column} column")
        source = [
            None if pd.isna(d) or pd.isna(f) else path_uri(str(d), str(f))
            for d, f in zip(data["Directory"], data["File"])
        ]
        renames = make_room(
            data.columns, [SOURCE], config.clash_name,
            tool=self.short(),
        )  # fmt: skip
        table = data.rename(columns=renames)
        if renames:
            self.warn(f"the column '{SOURCE}' is renamed '{renames[SOURCE]}'")
        table[SOURCE] = pd.Series(source, index=data.index, dtype="object")
        if not config.keep_original:
            table = table.drop(columns=["Directory", "File"])
        return {"With Source": table}
