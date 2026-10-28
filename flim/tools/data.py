"""Data tools: reorder, combine, filter and reshape tables."""

import logging

import numpy as np
import pandas as pd

from flim.configs.data import (
    CategoryOrderConfig,
    ConcatConfig,
    FilterConfig,
    MergeConfig,
    PivotConfig,
    SortConfig,
    UnpivotConfig,
)
from flim.core.config import Issue
from flim.core.filter import RangeFilter
from flim.core.registry import register_tool
from flim.core.tool import Tool
from flim.core.types import InputSpec, OutputSpec, TableType


def category_columns(data: pd.DataFrame) -> list[str]:
    return list(data.select_dtypes("category").columns.values)


def feature_columns(data: pd.DataFrame) -> list[str]:
    """The numeric columns (category columns are never numeric)."""
    return list(data.select_dtypes(np.number).columns.values)


def selected_features(data: pd.DataFrame, features) -> list[str]:
    """The feature columns a config selects; "all" selects every numeric column."""
    return feature_columns(data) if features == "all" else list(features)


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
        # the configured category columns take the places of the existing ones, in the
        # configured order
        new_order = list(categories)
        columns = [new_order.pop(0) if c in categories else c for c in data.columns]
        data = data[columns]
        for column, values in categories.items():
            data[column] = pd.Categorical(data[column], categories=values, ordered=True)
        data = data.sort_values(by=list(categories))
        return {"Reordered": data}


@register_tool
class Concat(Tool[ConcatConfig]):
    name = "Concat Data"
    category = "Data"
    description = "Appends tables below (rows) or next to (columns) each other."
    icon = "concatenate.png"
    inputs = (InputSpec("tables", TableType, many=True),)
    outputs = (OutputSpec("Concatenated", TableType),)

    def run(self, tables: dict, *, config):
        horizontal = config.mode == "horizontal"
        frames = list(tables.values())
        if horizontal and config.numbers_only:
            # the first table keeps all its columns
            frames = [
                df if i == 0 else df.select_dtypes(np.number)
                for i, df in enumerate(frames)
            ]
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
        for spec in config.range_filters:
            if spec.selected and spec.column in numeric:
                dropped.append(RangeFilter(params=spec.to_legacy()).get_dropped(data))
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
        categories = category_columns(merged)
        merged = merged[categories + [c for c in merged.columns if c not in categories]]
        return {"Merged": merged}


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
        logging.debug(f"pivoting {config.grouping}, index {index}")
        table = pd.pivot_table(
            data[features + categories],
            index=index,
            columns=config.grouping,
            observed=False,
        )
        table.columns = ["\n".join(col).strip() for col in table.columns.values]
        return {"Pivoted": table.reset_index()}

    @classmethod
    def output_schema(cls, config, inputs):
        outputs = super().output_schema(config, inputs)
        schema = outputs["Pivoted"].schema
        if schema is not None and schema.complete:
            # "<feature>\n<value>[\n<value>...]" columns come from <feature>
            schema.columns = [
                (
                    c.model_copy(update={"derived_from": [c.name.split("\n")[0]]})
                    if "\n" in c.name
                    else c
                )
                for c in schema.columns
            ]
        return outputs


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
        "Stacks the selected feature columns into one category and one value column."
    )
    icon = "unpivot.png"
    outputs = (OutputSpec("Unpivoted", TableType),)

    def run(self, data, *, config):
        categories = category_columns(data)
        features = selected_features(data, config.features)
        category_name = unique_name(config.category_name, "Category", categories)
        feature_name = unique_name(config.feature_name, "Feature", features)
        table = pd.melt(
            data,
            id_vars=categories,
            value_vars=features,
            var_name=category_name,
            value_name=feature_name,
        )
        # pivoted headers have the form "<feature>\n<category>[\n<category>...]"
        table[category_name] = (
            table[category_name]
            .str.replace(feature_name + "\n", "", regex=False)
            .str.replace("\n", "|", regex=False)
            .astype("category")
        )
        return {"Unpivoted": table}
