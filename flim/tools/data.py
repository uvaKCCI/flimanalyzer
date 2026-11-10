"""Data tools: reorder, combine, filter and reshape tables."""

import logging

import numpy as np
import pandas as pd

from flim.configs.data import (
    FuseCategoriesConfig,
    SeparateCategoriesConfig,
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
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.tool import Tool
from flim.core.types import InputSpec, OutputSpec, TableType
from flim.tools.common import (
    categories_first,
    category_columns,
    feature_columns,
    first_line,
    selected_features,
    set_lineage,
)

logger = logging.getLogger(__name__)


@register_tool
class CategoryOrder(Tool[CategoryOrderConfig]):
    name = "Order Categories"
    category = "Data"
    description = "Sets the order of category values and sorts the rows by them."
    icon = "order.png"
    outputs = (OutputSpec("Reordered", TableType),)

    def run(self, data, *, config):
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


def _row_mismatch(first: pd.DataFrame, other: pd.DataFrame):
    """The first difference between two tables: their numbers of rows, else the first
    row whose shared category columns differ. None if neither differs (or the tables
    share no category column)."""
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


@register_tool
class Concat(Tool[ConcatConfig]):
    name = "Concatenate"
    former_names = ("Concat Data",)
    category = "Data"
    description = "Appends tables below (rows) or next to (columns) each other."
    icon = "concatenate.png"
    inputs = (InputSpec("tables", TableType, many=True),)
    outputs = (OutputSpec("Concatenated", TableType),)

    def run(self, tables: dict, *, config):
        horizontal = config.mode == "horizontal"
        frames = list(tables.values())
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
            return {"Concatenated": pd.concat(frames, axis=1, copy=True)}
        catcols = list(dict.fromkeys(c for df in frames for c in category_columns(df)))
        concat = pd.concat(
            frames,
            axis=1 if horizontal else 0,
            copy=True,
            keys=list(tables),
            names=["Source", "Old Index"],
        ).reset_index()
        concat = concat.drop("Old Index", axis=1)
        concat[catcols] = concat[catcols].astype("category")
        concat["Source"] = concat["Source"].astype("category")
        return {"Concatenated": concat}


@register_tool
class Filter(Tool[FilterConfig]):
    name = "Filter"
    category = "Data"
    description = "Keeps the rows with selected category values and values in range."
    icon = "filter.png"
    outputs = (OutputSpec("Filtered", TableType),)

    def run(self, data, *, config):
        dropped = []
        for column, keep in config.category_filters.items():
            drop = [v for v in data[column].unique() if v not in keep]
            dropped.append(np.flatnonzero(data[column].isin(drop)))
        numeric = set(feature_columns(data))
        for column, limits in config.range_filters.items():
            if column not in numeric:
                continue
            values = data[column]
            outside = values.isna() if limits.dropna else pd.Series(False, values.index)
            if limits.low is not None:
                outside |= values < limits.low
            if limits.high is not None:
                outside |= values > limits.high
            dropped.append(np.flatnonzero(outside))
        dropped = [rows for rows in dropped if len(rows) > 0]
        if dropped:
            rows = np.unique(np.concatenate(dropped))
            data = data.drop(data.index[rows]).reset_index(drop=True)
        else:
            data = data.copy()
        return {"Filtered": data}

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        schema = inputs[0]
        if schema is None:
            return issues
        for column, keep in config.category_filters.items():
            info = schema.column(column)
            if info is None or info.levels is None:
                continue
            missing = [v for v in keep if v not in info.levels]
            if missing:
                issues.append(
                    Issue(
                        f"category_filters[{column!r}]",
                        f"Values not in '{column}': {missing}",
                        "warning",
                    )
                )
        return issues


@register_tool
class Merge(Tool[MergeConfig]):
    name = "Merge"
    category = "Data"
    description = "Joins two tables on their shared category columns."
    icon = "merge.png"
    inputs = (InputSpec("left", TableType), InputSpec("right", TableType))
    outputs = (OutputSpec("Merged", TableType),)

    def run(self, left, right, *, config):
        on = config.on
        if on is None:
            right_cats = set(category_columns(right))
            on = [c for c in category_columns(left) if c in right_cats]
        merged = pd.merge(left, right, how=config.how, on=on)
        merged[on] = merged[on].astype("category")
        return {"Merged": categories_first(merged)}


@register_tool
class Pivot(Tool[PivotConfig]):
    name = "Pivot"
    category = "Data"
    description = "Turns the values of the grouping columns into columns."
    icon = "pivot.png"
    outputs = (OutputSpec("Pivoted", TableType),)

    def run(self, data, *, config):
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
    def output_schema(cls, config, inputs):
        # "<feature>\n<value>[\n<value>...]" columns come from <feature>
        return set_lineage(super().output_schema(config, inputs), first_line)


@register_tool
class Sort(Tool[SortConfig]):
    name = "Sort"
    category = "Data"
    description = "Sorts the rows by the selected columns."
    icon = "sort.png"
    outputs = (OutputSpec("Sorted", TableType),)

    def run(self, data, *, config):
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
    name = "Split"
    category = "Data"
    description = (
        "Splits the table into one table for each combination of the values of the"
        " selected category columns."
    )
    icon = "split.png"

    @staticmethod
    def table_name(grouping, values) -> str:
        """``Split: Treatment=ctrl, FOV=1``."""
        values = values if isinstance(values, tuple) else (values,)
        return "Split: " + ", ".join(f"{c}={v}" for c, v in zip(grouping, values))

    def run(self, data, *, config):
        grouping = list(config.grouping)
        # in the order of the categories; combinations without rows are left out
        return {
            self.table_name(grouping, values): group.copy()
            for values, group in data.groupby(grouping, observed=True, sort=True)
        }


def unique_name(name: str, default: str, existing) -> str:
    """``name`` (or ``default`` if empty), numbered if it is already taken."""
    name = name or default
    base, i = name, 1
    while name in existing:
        name = f"{base}_{i}"
        i += 1
    return name


@register_tool
class Unpivot(Tool[UnpivotConfig]):
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

    def run(self, data, *, config):
        categories = category_columns(data)
        columns = selected_features(data, config.features)
        if not columns:
            raise ValueError(f"{self.name}: select the columns to unpivot")
        depth = headers.depth(columns)
        if any(len(headers.split(c)) != depth for c in columns):
            raise ValueError(
                f"{self.name}: the columns have different numbers of header lines"
            )
        names = headers.names_for(depth, headers.level_names(data))
        index = headers.level_index(config.level, names)
        category = unique_name(config.category_name or "", names[index], categories)
        # level value -> {value column: input column}, in the columns' order
        values: dict = {}
        for column in columns:
            parts = headers.split(column)
            value = parts.pop(index)
            values.setdefault(value, {})[headers.join(parts) or self.VALUE] = column
        pieces = []
        for value, sources in values.items():
            piece = data[categories].copy()
            piece[category] = value
            for name, column in sources.items():
                piece[name] = data[column]
            pieces.append(piece)
        table = pd.concat(pieces, ignore_index=True)
        table[category] = pd.Categorical(table[category], categories=list(values))
        first = categories + [category]
        table = table[first + [c for c in table if c not in first]]
        rest = names[:index] + names[index + 1 :]
        return {"Unpivoted": headers.set_level_names(table, rest)}


# the line added to the names of scaled columns, per method
SCALED = {"standardize": "standardized", "min-max": "min-max", "robust": "robust"}


def _scaler(method: str):
    """Return a function that scales the columns of a 2D array with a method."""
    if method == "standardize":
        from flim.tools.ml import standardized  # the same as Standardize input

        return standardized
    from sklearn.preprocessing import MinMaxScaler, RobustScaler

    scaler = {"min-max": MinMaxScaler, "robust": RobustScaler}[method]
    return lambda values: scaler().fit_transform(values)


@register_tool
class Scale(Tool[ScaleConfig]):
    name = "Scale"
    category = "Data"
    description = (
        "Scales the selected features: standardize (mean 0, standard deviation 1),"
        " min-max (0 to 1) or robust (median 0, interquartile range 1), over the whole"
        " table or within each group."
    )
    outputs = (OutputSpec("Scaled", TableType),)

    def run(self, data, *, config):
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
        if config.keep_original:
            for feature in features:
                name = f"{feature}\n{suffix}"
                table[name] = result[feature]
        else:  # the scaled columns replace the originals, in their place
            for feature in features:
                table[feature] = result[feature]
            table = table.rename(columns={f: f"{f}\n{suffix}" for f in features})
        return {"Scaled": table}


def _with_columns(data, new: dict, after: str, remove=()) -> pd.DataFrame:
    """Return the table with new columns placed after a column, and some removed.

    New names that are taken get a number (unique_name).
    """
    table = data.copy()
    position = list(table.columns).index(after) + 1
    for offset, (name, values) in enumerate(new.items()):
        taken = [c for c in table.columns if c not in remove]
        table.insert(position + offset, unique_name(name, name, taken), values)
    return table.drop(columns=list(remove))


@register_tool
class FuseCategories(Tool[FuseCategoriesConfig]):
    name = "Fuse Categories"
    category = "Data"
    description = (
        "Joins category columns into one category column, e.g. FOV and Cell into"
        " FOV:Cell; Separate Categories reverses it."
    )
    outputs = (OutputSpec("Fused", TableType),)

    @classmethod
    def example(cls, config, tables):
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
    def validate_data(cls, config, tables):
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

    def run(self, data, *, config):
        from flim.core.categories import fuse

        columns = list(config.grouping)
        result = fuse(data, columns, config.delimiter, config.name)
        for message in result.warnings:
            self.warn(message)
        remove = () if config.keep_original else columns
        return {"Fused": _with_columns(data, result.columns, columns[-1], remove)}


@register_tool
class SeparateCategories(Tool[SeparateCategoriesConfig]):
    name = "Separate Categories"
    category = "Data"
    description = (
        "Separates a category column into several: at delimiters (the reverse of"
        " Fuse Categories), or by patterns, as the filename parser does."
    )
    outputs = (OutputSpec("Separated", TableType),)

    @classmethod
    def _separated(cls, config, data):
        from flim.core.categories import separate, separate_by_patterns

        if config.mode == "patterns":
            patterns = [(p.name, p.regex) for p in config.patterns]
            return separate_by_patterns(data, config.column, patterns, config.part)
        return separate(data, config.column, config.delimiters, config.names, config.part)

    @classmethod
    def _table(cls, config, tables):
        return next(
            (
                t
                for t in tables
                if isinstance(t, pd.DataFrame) and config.column in t.columns
            ),
            None,
        )

    @classmethod
    def example(cls, config, tables):
        table = cls._table(config, tables) if config.column else None
        if table is None or (config.mode == "patterns" and not config.patterns):
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
    def validate_data(cls, config, tables):
        table = cls._table(config, tables) if config.column else None
        if table is None or (config.mode == "patterns" and not config.patterns):
            return []
        field = "patterns" if config.mode == "patterns" else "names"
        distinct = table[[config.column]].drop_duplicates()  # few: category values
        try:
            result = cls._separated(config, distinct)
        except ValueError as err:
            return [Issue(field, str(err))]
        return [Issue(field, message, "warning") for message in result.warnings]

    @classmethod
    def validate(cls, config, schemas=()):
        issues = list(super().validate(config, schemas))
        if config.column is None:
            issues.append(Issue("column", "Select the column to separate"))
        if config.mode == "patterns" and not config.patterns:
            issues.append(Issue("patterns", "Add at least one pattern"))
        return issues

    def run(self, data, *, config):
        from flim.core.categories import separate, separate_by_patterns

        if config.column is None:
            raise ValueError(f"{self.name}: select the column to separate")
        if config.mode == "patterns":
            patterns = [(p.name, p.regex) for p in config.patterns]
            result = separate_by_patterns(data, config.column, patterns, config.part)
        else:
            result = separate(
                data, config.column, config.delimiters, config.names, config.part
            )
        for message in result.warnings:
            self.warn(message)
        remove = () if config.keep_original else [config.column]
        return {"Separated": _with_columns(data, result.columns, config.column, remove)}
