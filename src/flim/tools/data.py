"""Data tools: reorder, combine, filter and reshape tables."""

import logging
import re
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING, Any, Optional, Union

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
    CollectFilesConfig,
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
from flim.core.types import FileType, InputSpec, OutputSpec, TableType
from flim.tools.common import (
    categories_first,
    category_columns,
    first_line,
    missing_group_message,
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

    name = "Order Category Values"
    former_names = ("Order Categories",)
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
        configured values first. The column's values that are not configured follow,
        in the column's order (its categories, or for another column the order in
        which the values occur), with a warning that names those that occur in the
        table. The rows are sorted by the columns, in the configured order; the sort is stable, so
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
            present = data[column]
            if isinstance(present.dtype, pd.CategoricalDtype):
                known = list(present.cat.categories)
            else:
                known = list(pd.unique(present.dropna()))
            # values that are not configured follow the configured ones, as in the
            # GUI's editor; a warning names those that occur in the table
            others = [v for v in known if v not in values]
            occurring = set(present.dropna().unique())
            appended = [str(v) for v in others if v in occurring]
            if appended:
                self.warn(
                    f"{column}: values not in the configured order, placed after it:"
                    f" {', '.join(appended)}"
                )
            data[column] = pd.Categorical(
                present, categories=list(values) + others, ordered=True
            )
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
class CollectFiles(Tool[CollectFilesConfig]):
    """Collects the files of several inputs into one table, a row per file."""

    name = "Collect Files"
    category = None  # in no menu: its inputs are files, which the GUI has no windows for
    description = (
        "Collects the files of several inputs (e.g. the models of each training) into"
        " one table: a row per file, with the input it came from."
    )
    inputs = (InputSpec("files", FileType, many=True),)
    outputs = (OutputSpec("Files", TableType),)

    def run(self, files: dict[str, Any], *, config: CollectFilesConfig) -> dict[str, Any]:
        """Return one table of the files, in the order of the inputs.

        Args:
            files: The files by input name; each a path or a list of paths (None for
                an input without files).
            config: The settings (none of its own).

        Returns:
            `Files`: a table with the columns `Input` (the input's name) and `File`
            (the path).
        """
        rows = []
        for name, value in files.items():
            paths = value if isinstance(value, (list, tuple)) else [value]
            rows += [{INPUT: name, "File": str(path)} for path in paths if path is not None]
        return {"Files": pd.DataFrame(rows, columns=[INPUT, "File"])}


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
    """Keeps the rows that the range, category and other filters keep."""

    name = "Filter"
    category = "Data"
    description = (
        "Keeps the rows that the filters keep: values in ranges, category values,"
        " conditions; the table windows use the same range filters."
    )
    icon = "filter.png"
    outputs = (OutputSpec("Filtered", TableType),)
    skippable_fields = ("grouping", "features", "categories", "other")

    def run(self, data: pd.DataFrame, *, config: FilterConfig) -> dict[str, Any]:
        """Keep the rows that every filter in use keeps.

        A filter is used if every switch on its way is on: `enabled`, its part's,
        its groups' and its own (see `flim.core.filtering.apply_filters`). A filter
        on a column the table doesn't have keeps all rows and is reported as a
        skipped entry of its part. The rows each filter drops are logged.

        Args:
            data: The table.
            config: The switch of all filters (`enabled`) and the three parts
                (`features`, `categories`, `other`).

        Returns:
            `Filtered`: the rows kept, numbered from 0.
        """
        from flim.core.filtering import apply_filters, leaf_counts

        if not config.enabled:
            logger.info(f"{self.name}: the filters are switched off (Use filters): all rows kept")
            return {"Filtered": data.reset_index(drop=True).copy()}
        outcome = apply_filters(data, config)
        # entries: a filter on a column the table doesn't have keeps all rows
        self.applied(len(outcome.dropped) - len(outcome.notes))
        for path, note in outcome.notes.items():
            part, index = re.match(r"(\w+)\.filters\[(\d+)\]", path).groups()
            entry = getattr(config, part).filters[int(index)]
            self.skip(f"{path}: {note}", field=part, entry=entry)
        line = leaf_counts(outcome)
        if line:
            logger.info(f"{self.name}: {line}")
        return {"Filtered": outcome.data.copy()}

    @classmethod
    def validate(cls, config: FilterConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Validate the config against the input schema.

        A column of a filter in use that the input doesn't have is a warning (the
        filter keeps all rows); for a filter not in use it is no issue. The filters
        themselves are validated by `flim.core.filtering.validate_filters`. A value
        of a category filter in use that its column doesn't have is a warning.
        """
        from flim.core.filtering import validate_filters

        used = set(_used_paths(config))
        issues = []
        for issue in super().validate(config, inputs):
            node = (issue.field or "").rsplit(".", 1)[0]
            if "is not in the input" in issue.message and _in_parts(node):
                # a filter on a missing column keeps all rows (as up to 0.6)
                if node in used:
                    message = issue.message.replace("is not in the input", "is not in the input: keeps all rows")
                    issues.append(Issue(issue.field, message, "warning"))
                continue
            issues.append(issue)
        schema = inputs[0] if inputs else None
        complete = schema is not None and schema.complete
        columns = schema.names if complete else None
        issues += [Issue(f, m, sev) for f, sev, m in validate_filters(config, columns)]
        if schema is None:
            return issues
        for path, node in _part_leaves(config):
            if node.kind != "category" or path not in used:
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


def _in_parts(path: str) -> bool:
    """Return whether a config path is inside the filter parts, e.g. `other.filters[0]`."""
    from flim.configs.data import FILTER_PARTS

    return path.startswith(tuple(f"{part}.filters[" for part in FILTER_PARTS))


def _part_leaves(config: FilterConfig) -> Iterator[tuple[str, FilterNode]]:
    """Yield (path, node) of every leaf of the three parts, also in groups."""
    from flim.configs.data import FILTER_PARTS

    for part in FILTER_PARTS:
        yield from _leaves(getattr(config, part).filters, f"{part}.filters")


def _used_paths(config: FilterConfig) -> Iterator[str]:
    """Yield the paths of the nodes in use: every switch on their way is on."""
    from flim.configs.data import FILTER_PARTS

    for part in FILTER_PARTS:
        on = config.enabled and getattr(config, part).enabled
        yield from _enabled_paths(getattr(config, part).filters, f"{part}.filters", on)


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

    @staticmethod
    def join_columns(config: MergeConfig, left: Any, right: Any) -> list[str]:
        """Return the columns to join on: `on`, or the category columns both tables have.

        Args:
            config: The config.
            left: The first table: a DataFrame or a `TableSchema`.
            right: The second table, of the same kind.

        Returns:
            The columns, in the order of the first table for automatic selection.
        """
        if config.on is not None:
            return list(config.on)

        def categories(table: Any) -> list[str]:
            if isinstance(table, pd.DataFrame):
                return category_columns(table)
            return [c.name for c in table.columns if c.role == "category"]

        right_categories = set(categories(right))
        return [c for c in categories(left) if c in right_categories]

    @staticmethod
    def no_columns_message(config: MergeConfig) -> str:
        """Return why there are no columns to join on, for an empty `join_columns`."""
        if config.on is not None:
            return "select at least one column to merge on"
        return "the two tables have no shared category columns to merge on"

    @classmethod
    def validate(cls, config: MergeConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Validate the config; no columns to join on is an error.

        The automatic selection is validated only with complete schemas of both
        tables.
        """
        issues = super().validate(config, inputs)
        schemas = list(inputs)
        known = len(schemas) == 2 and all(s is not None and s.complete for s in schemas)
        if config.on is not None:
            empty = not config.on
        else:
            empty = known and not cls.join_columns(config, *schemas)
        if empty:
            message = cls.no_columns_message(config)
            issues.append(Issue("on", message[:1].upper() + message[1:]))
        return issues

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

        A row with a missing value in a column joined on matches no row: with `left`,
        `right` or `outer` it is kept without values of the other table, with
        `inner` it is left out. A warning gives the number of these rows.

        Returns:
            `Merged`: the joined table, its category columns first; the columns
            joined on are category columns.

        Raises:
            ValueError: If there are no columns to join on (none selected, or the
                tables have no category column in common).
        """
        on = self.join_columns(config, left, right)
        if not on:
            raise ValueError(f"{self.name}: {self.no_columns_message(config)}")
        suffixes = (config.suffix_left, config.suffix_right)
        # pandas pairs missing key values with each other: each row with a missing
        # key value gets its own value of an extra key, so that it matches no row
        key = unique_name("row", "row", [*map(str, left.columns), *map(str, right.columns)])
        unmatched = []
        tables = []
        offset = 0
        for table, name, kept in (
            (left, "first", config.how in ("left", "outer")),
            (right, "second", config.how in ("right", "outer")),
        ):
            missing = table[on].isna().any(axis=1).to_numpy()
            ids = np.full(len(table), -1)
            ids[missing] = offset + np.arange(missing.sum())
            offset += int(missing.sum())
            tables.append(table.assign(**{key: ids}))
            if missing.any():
                fate = "kept without a match" if kept else "left out"
                unmatched.append(f"{int(missing.sum())} of the {name} table ({fate})")
        if unmatched:
            self.warn(
                f"rows with no value in a column merged on ({', '.join(on)}) match no"
                f" row: {'; '.join(unmatched)}"
            )
        merged = pd.merge(*tables, how=config.how, on=on + [key], suffixes=suffixes)
        merged = merged.drop(columns=key)
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

    @classmethod
    def example(
        cls, config: PivotConfig, tables: Sequence[Any]
    ) -> Union[str, pd.DataFrame, None]:
        """Return the first rows of the pivoted first table.

        None without a table with rows, or if the settings don't apply to it (shown
        as issues).
        """
        from flim.core.tool import preview

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or table.empty or not config.grouping:
            return None
        try:
            (result,) = preview(cls, config, table).values()
        except (ValueError, KeyError):
            return None
        return _reshaped_example(result, f"the result has {len(result)} rows")

    def run(self, data: pd.DataFrame, *, config: PivotConfig) -> dict[str, Any]:
        """Turn the values of the grouping columns into columns.

        The other category columns are the rows; each row holds the mean of the
        feature over the input rows with the same category values. Without other
        category columns, the result is one row with the means over all rows. A new column's
        header has the feature's lines and a line for the value of each grouping
        column, e.g. `FLIRR` and `ctrl`. Rows and columns without any value are left
        out. Input rows with a missing value in a category column are left out, with
        a warning.

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
        # pandas leaves out rows with a missing value in a column or row key
        message = missing_group_message(data, list(config.grouping) + index, "category")
        if message:
            self.warn(message)
        source = data[features + categories]
        if not index:  # no other category column: one row, keyed by a column dropped below
            index = [unique_name("row", "row", list(map(str, data.columns)))]
            source = source.assign(**{index[0]: 0})
        table = pd.pivot_table(
            source,
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
        if index[0] not in categories:  # the key of the single row
            table = table.drop(columns=index[0])
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
    output_types = (TableType,)
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
            by `table_name`, in the order of the categories. Rows with a missing
            value in a grouping column are in no table, with a warning.
        """
        grouping = list(config.grouping)
        message = missing_group_message(data, grouping)
        if message:  # pandas leaves out rows with a missing grouping value
            self.warn(message)
        # in the order of the categories; combinations without rows are left out
        return {
            self.table_name(grouping, values): group.copy()
            for values, group in data.groupby(grouping, observed=True, sort=True)
        }


def _reshaped_example(result: pd.DataFrame, caption: str) -> pd.DataFrame:
    """Return the first rows and columns of a reshaped table as an example.

    The category columns come first; of the others, at most `EXAMPLE_COLUMNS`.

    Args:
        result: The reshaped table.
        caption: What the rows are, e.g. `the first 2 rows become 8 rows`.

    Returns:
        The example (`flim.core.tool.example_table`), all its columns made by the tool.
    """
    from flim.core.tool import EXAMPLE_COLUMNS, EXAMPLE_ROWS, example_table

    categories = [c for c in result.columns if c in category_columns(result)]
    others = [c for c in result.columns if c not in categories]
    shown = result[categories + others[:EXAMPLE_COLUMNS]].head(EXAMPLE_ROWS)
    more = len(others) - EXAMPLE_COLUMNS
    note = f"; {more} more columns" if more > 0 else ""
    return example_table(pd.DataFrame(), shown, caption + note)


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
        validated.
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

    @classmethod
    def example(
        cls, config: UnpivotConfig, tables: Sequence[Any]
    ) -> Union[str, pd.DataFrame, None]:
        """Return the rows the first two rows of the first table become.

        None without a table with rows, or if the settings don't apply to it (shown
        as issues).
        """
        from flim.core.tool import preview

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or table.empty:
            return None
        rows = table.head(2)
        try:
            result = preview(cls, config, rows)["Unpivoted"]
        except (ValueError, KeyError):
            return None
        caption = f"the first {len(rows)} rows become {len(result)} rows"
        return _reshaped_example(result, caption)

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

    @classmethod
    def example(
        cls, config: ScaleConfig, tables: Sequence[Any]
    ) -> Union[str, pd.DataFrame, None]:
        """Return the first rows of a few features before and after scaling.

        The whole first table is scaled (the statistics are of all its rows, or of
        each group's); at most `EXAMPLE_COLUMNS` features are shown. None without a
        table with rows or features, or if the settings don't apply to it.
        """
        from flim.core.tool import EXAMPLE_COLUMNS, EXAMPLE_ROWS, example_table, preview

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or table.empty:
            return None
        features = selected_features(table, config.features)
        if not features:
            return None
        try:
            result = preview(cls, config, table)["Scaled"]
        except (ValueError, KeyError):
            return None
        shown = features[:EXAMPLE_COLUMNS]
        new = [c for c in result.columns if c not in table.columns]
        made = new[: len(shown)] if new else shown  # replaced in place without new ones
        more = len(features) - len(shown)
        return example_table(
            table[shown].head(EXAMPLE_ROWS),
            result[made].head(EXAMPLE_ROWS),
            f"{more} more features" if more > 0 else "",
        )

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

    The columns are removed first, so that a new column can take the name of a
    removed one. The new columns are where they would be after `after` if the
    removed columns stayed: after the columns before it that are kept. New names
    that are taken get a number (`unique_name`).

    Args:
        data: The table.
        new: The new columns by name, in order.
        after: The column the new columns follow; it may be removed.
        remove: The columns removed.

    Returns:
        The new table.
    """
    columns = list(data.columns)
    before = columns[: columns.index(after) + 1]
    position = len([c for c in before if c not in remove])
    table = data.drop(columns=list(remove))
    for offset, (name, values) in enumerate(new.items()):
        table.insert(position + offset, unique_name(name, name, list(table.columns)), values)
    return table


def _clashes(data: pd.DataFrame, new: Sequence[str], remove: Sequence[str] = ()) -> dict:
    """Return the new columns whose names the table has, and the names they get.

    As `_with_columns` names them: a taken name gets a number (`unique_name`).

    Args:
        data: The table.
        new: The names of the new columns, in order.
        remove: The columns removed, whose names are free.

    Returns:
        Taken name -> the name the new column gets, e.g. `{"FOV": "FOV_1"}`.
    """
    taken = [c for c in data.columns if c not in remove]
    renamed = {}
    for name in new:
        given = unique_name(name, name, taken)
        if given != name:
            renamed[name] = given
        taken.append(given)
    return renamed


def _clash_messages(renamed: dict) -> list[str]:
    """Return a warning for each new column whose name the table has (`_clashes`)."""
    return [
        f"the table already has a column '{name}': the new column is named '{given}'"
        for name, given in renamed.items()
    ]


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
    ) -> Union[str, pd.DataFrame, None]:
        """Return the fusion of a few rows with different values in the columns.

        The columns next to the fused column (`example_table`). None if fewer than
        two columns are selected, the first table lacks one of them, or no row has
        values in all of them.
        """
        from flim.core.categories import fuse
        from flim.core.tool import distinct_rows, example_table

        columns = list(config.grouping)
        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if len(columns) < 2 or table is None or not set(columns) <= set(table.columns):
            return None
        rows = distinct_rows(table, columns)
        if rows.empty:
            return None
        fused = fuse(rows, columns, config.delimiter, config.name).columns
        remove = () if config.keep_original else columns
        renamed = _clashes(table, list(fused), remove)
        return example_table(rows[columns], pd.DataFrame(fused).rename(columns=renamed))

    @classmethod
    def validate_data(
        cls, config: FuseCategoriesConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Warn where the delimiter occurs in the column names or values of a table.

        Then separating the fused column back would be ambiguous. Also warn if the
        table has a column of the new column's name: the new one gets a number
        (`New column`). Tables without all the selected columns, and fewer than two
        columns, are not validated.
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
            result = fuse(combinations, columns, config.delimiter, config.name)
            for message in result.warnings:
                issues.append(Issue("delimiter", message, "warning"))
            remove = () if config.keep_original else columns
            for message in _clash_messages(_clashes(table, list(result.columns), remove)):
                issues.append(Issue("name", message, "warning"))
        return issues

    def run(
        self, data: pd.DataFrame, *, config: FuseCategoriesConfig
    ) -> dict[str, Any]:
        """Join the values of category columns into one category column.

        The values are joined by the delimiter, e.g. `1` and `2` into `1:2`; a row
        with a missing value in one of the columns gets a missing value. A warning
        is reported if the delimiter occurs in the column names or values, and if the
        new column's name is taken.

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
        remove = () if config.keep_original else columns
        for message in result.warnings + _clash_messages(_clashes(data, list(result.columns), remove)):
            self.warn(message)
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
        """Return whether the mode's settings are empty (nothing to show or validate)."""
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
    ) -> Union[str, pd.DataFrame, None]:
        """Return how a few different values of the column are separated.

        The column next to the new columns (`example_table`). An invalid setting
        (e.g. a pattern) gives a line with the first value and the error message.
        None if no table has the column, the column has no values, or the mode's
        settings are empty.
        """
        from flim.core.tool import distinct_rows, example_table

        table = cls._table(config, tables) if config.column else None
        if table is None or cls._incomplete(config):
            return None
        rows = distinct_rows(table, [config.column])
        if rows.empty:
            return None
        try:
            result = cls._separated(config, rows)
        except ValueError as err:  # e.g. an invalid pattern: shown as an issue
            return f"{rows[config.column].iloc[0]} \u2192 {err}"
        remove = () if config.keep_original else [config.column]
        renamed = _clashes(table, list(result.columns), remove)
        new = pd.DataFrame(result.columns).rename(columns=renamed)
        return example_table(rows[[config.column]], new)

    @classmethod
    def validate_data(
        cls, config: SeparateCategoriesConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Separate the column's distinct values and return the problems found.

        An invalid setting is an error, the separation's warnings (e.g. values that
        could not be separated) are warnings, on the mode's field: `names`,
        `patterns` or `template`; so is a new column whose name the table has (the
        new one gets a number).
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
        remove = () if config.keep_original else [config.column]
        messages = result.warnings + _clash_messages(_clashes(table, list(result.columns), remove))
        return [Issue(field, message, "warning") for message in messages]

    @classmethod
    def validate(
        cls, config: SeparateCategoriesConfig, schemas: Sequence[Any] = ()
    ) -> list[Issue]:
        """Validate the config: a column, a pattern or a valid template is needed.

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

        The separation's warnings are reported, and a new column whose name the table
        has (it gets a number).

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
        remove = () if config.keep_original else [config.column]
        for message in result.warnings + _clash_messages(_clashes(data, list(result.columns), remove)):
            self.warn(message)
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
    skippable_fields = ("grouping", "features", "replacements")
    never_guessed = ("replacements",)

    @classmethod
    def example(
        cls, config: RenameColumnsConfig, tables: Sequence[Any]
    ) -> Union[str, pd.DataFrame, None]:
        """Return the columns of the first table that are renamed, and their new names.

        At most `EXAMPLE_ROWS` columns; the caption says how many more are renamed.
        `no column name changes` if no name changes; None without a table.
        """
        from flim.core.columns import renamed_columns
        from flim.core.tool import EXAMPLE_ROWS, example_table

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return None
        pairs = [(r.part, r.new) for r in config.replacements]
        changed = [
            (str(old), new)
            for old, new in zip(table.columns, renamed_columns(table.columns, pairs))
            if str(old) != new
        ]
        if not changed:
            return "no column name changes"
        shown = changed[:EXAMPLE_ROWS]
        more = len(changed) - len(shown)
        return example_table(
            pd.DataFrame({"Column": [o for o, _ in shown]}),
            pd.DataFrame({"New name": [n for _, n in shown]}),
            f"and {more} more columns" if more else "",
        )

    def run(
        self, data: pd.DataFrame, *, config: RenameColumnsConfig
    ) -> dict[str, Any]:
        """Replace parts of the column names, in the order of the replacements.

        A replacement whose part occurs in no column name, as the replacements
        before it left the names, is reported as a skipped part of the settings.

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

        names = [str(c) for c in data.columns]
        # entries: a replacement whose part occurs in none of the names that the
        # replacements before it produced is skipped
        for replacement in config.replacements:
            if any(replacement.part in n for n in names):
                self.applied()
            else:
                self.skip(f"no column name contains '{replacement.part}'", entry=replacement)
            names = renamed_columns(names, [(replacement.part, replacement.new)])
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
    skippable_fields = ("grouping", "features", "drop")
    never_guessed = ("drop",)

    @classmethod
    def example(
        cls, config: DropColumnsConfig, tables: Sequence[Any]
    ) -> Union[str, pd.DataFrame, None]:
        """Return the columns of the first table that are dropped.

        At most `EXAMPLE_ROWS` columns; the caption says how many more are dropped.
        `no columns dropped` if none is dropped; None without a table.
        """
        from flim.core.columns import columns_to_drop
        from flim.core.tool import EXAMPLE_ROWS, example_table

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return None
        dropped = columns_to_drop(table.columns, [(r.text, r.match) for r in config.drop])
        if not dropped:
            return "no columns dropped"
        dropped = [n if n.strip() else "(empty header)" for n in dropped]
        more = len(dropped) - EXAMPLE_ROWS
        return example_table(
            pd.DataFrame({"Dropped column": dropped[:EXAMPLE_ROWS]}),
            pd.DataFrame(),
            f"and {more} more columns" if more > 0 else "",
        )

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
        # entries: a rule that matches no column is skipped
        for rule in config.drop:
            if columns_to_drop(data.columns, [(rule.text, rule.match)], drop_empty=False):
                self.applied()
            else:
                self.skip(f"no column name {rule.match} '{rule.text}'", entry=rule)
        return {"Columns Dropped": data.drop(columns=dropped)}


def calculation_example(
    calculations: Sequence[Any], rows: pd.DataFrame, most: int
) -> Union[str, pd.DataFrame]:
    """Return calculated columns for a few rows, next to the columns they use.

    Args:
        calculations: The calculations (`CalculationEntry`), in order.
        rows: The rows to calculate.
        most: The most calculated columns shown; the caption says how many more.

    Returns:
        The table (`flim.core.tool.example_table`); `nothing calculated` if no kept
        column is calculated.

    Raises:
        ValueError: If a calculation is not valid (see `flim.core.calculate.calculate`).
    """
    from flim.core.calculate import calculate, needed_columns
    from flim.core.tool import example_table

    outcome = calculate(rows, list(calculations))
    made = [n for n in outcome.calculated if n in outcome.data.columns]
    if not made:
        return "nothing calculated"
    used: list = []
    for calculation in calculations:
        if calculation.enabled and calculation.name in made[:most]:
            try:
                names = needed_columns(calculation, rows.columns)
            except ValueError:
                names = []
            used += [n for n in names if n in rows.columns and n not in used]
    more = len(made) - most
    return example_table(
        rows[used],
        outcome.data[made[:most]],
        f"and {more} more calculated columns" if more > 0 else "",
    )


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
    skippable_fields = ("grouping", "features", "calculations")

    @classmethod
    def dialog_config(cls, config: CalculateConfig) -> CalculateConfig:
        """Return the config the dialog opens with: the stored one, no calculations.

        A run from the dialog makes only the calculations set up in it; the stored
        ones are offered as presets.
        """
        return config.model_copy(update={"calculations": []})

    @classmethod
    def _issues(cls, problems: Sequence[tuple[int, str, str, str]]) -> list[Issue]:
        """Return `flim.core.calculate.validate_calculations`'s problems as issues on their fields."""
        return [
            Issue(f"calculations[{i}].{field}", message, severity)
            for i, field, severity, message in problems
        ]

    @classmethod
    def validate(
        cls, config: CalculateConfig, schemas: Sequence[Any] = ()
    ) -> list[Issue]:
        """Validate the config; calculations that can't run are errors.

        For example a missing name, a name used twice, an invalid expression, or an
        unknown function. Columns missing from the input are validated by
        `validate_data`.
        """
        from flim.core.calculate import validate_calculations

        issues = list(super().validate(config, schemas))
        # with the input's columns, names may be typed without backticks; the columns
        # used are validated against the tables (validate_data)
        schema = schemas[0] if schemas else None
        columns = schema.names if schema is not None and schema.complete else None
        problems = validate_calculations(config.calculations, columns)
        return issues + cls._issues([p for p in problems if p[2] == "error"])

    @classmethod
    def validate_data(
        cls, config: CalculateConfig, tables: Sequence[Any]
    ) -> list[Issue]:
        """Warn about calculations that would be skipped for the first table.

        For example a calculation that uses a column that is neither in the table
        nor calculated before (see `flim.core.calculate.validate_calculations`).
        """
        from flim.core.calculate import validate_calculations

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None:
            return []
        problems = validate_calculations(config.calculations, list(table.columns))
        return cls._issues([p for p in problems if p[2] == "warning"])

    @classmethod
    def example(
        cls, config: CalculateConfig, tables: Sequence[Any]
    ) -> Union[str, pd.DataFrame, None]:
        """Return the calculated columns for the first rows, next to the columns used.

        At most `EXAMPLE_COLUMNS` calculated columns, and the columns they use; the
        caption says how many more are calculated. `nothing calculated` if no kept
        column is calculated; None without a table or row, or if the calculation
        raises a ValueError.
        """
        from flim.core.tool import EXAMPLE_COLUMNS, EXAMPLE_ROWS

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or table.empty:
            return None
        try:
            return calculation_example(
                config.calculations, table.head(EXAMPLE_ROWS), EXAMPLE_COLUMNS
            )
        except ValueError:
            return None  # shown as an issue

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
        entries = {c.name: c for c in config.calculations}
        for name, reason in outcome.skipped.items():
            self.skip(f"{name} skipped: {reason}", warn=True, entry=entries.get(name))
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
        """Validate the config; an input without `Directory` or `File` is an error."""
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
    ) -> Union[str, pd.DataFrame, None]:
        """Return the `Source` of a few rows with different files, next to the columns.

        Long values are shortened in the middle (`shortened`). None without a table
        with rows and both columns, or if no row has both values.
        """
        from flim.core.paths import path_uri
        from flim.core.tool import distinct_rows, example_table

        table = next((t for t in tables if isinstance(t, pd.DataFrame)), None)
        if table is None or not {"Directory", "File"} <= set(table.columns) or table.empty:
            return None
        rows = distinct_rows(table, ["Directory", "File"])
        if rows.empty:
            return None
        uris = [path_uri(str(d), str(f)) for d, f in zip(rows["Directory"], rows["File"])]
        before = rows[["Directory", "File"]].map(lambda v: shortened(str(v)))
        return example_table(before, pd.DataFrame({"Source": [shortened(u) for u in uris]}))

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
