"""Statistics tools: summaries, KS tests, relative change and series analysis."""

import logging
from collections.abc import Callable, Sequence
from itertools import combinations
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

from flim.configs.analysis import (
    KSStatsConfig,
    RelativeChangeConfig,
    SeriesAnalysisConfig,
    SummaryConfig,
)
from flim.core import headers
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.tool import Tool
from flim.core.types import OutputSpec, TableType
from flim.tools.common import (
    category_columns,
    first_line,
    selected_features,
    set_lineage,
)

logger = logging.getLogger(__name__)


def percentile(n: float) -> Callable[[np.ndarray], float]:
    """Return a function that computes the n-th percentile, ignoring missing values.

    The function is named for the summary's column headers, e.g. `25 percentile`.

    Args:
        n: The percentile, from 0 to 100.

    Returns:
        A function of an array of values.
    """

    def percentile_(x: np.ndarray) -> float:
        return np.nanpercentile(x, n)

    percentile_.__name__ = f"{n} percentile"
    return percentile_


# the levels of the summary's headers, "<feature>\n<aggregate>"
SUMMARY_LEVELS = [headers.FEATURE_LEVEL, "Statistic"]

AGGREGATE_FUNCTIONS = {
    "count": "count",
    "min": "min",
    "max": "max",
    "mean": "mean",
    "std": "std",
    "sem": "sem",
    "median": "median",
    "percentile(25)": percentile(25),
    "percentile(75)": percentile(75),
    "sum": "sum",
}


@register_tool
class Summarize(Tool[SummaryConfig]):
    """Statistics of features per group: count, min, max, mean, median and others."""

    name = "Summarize"
    category = "Analysis"
    description = (
        "Calculates counts, min, max, mean, median (50th percentile), 25th percentile,"
        " and 75th percentile, StDev, S.E.M, of grouped data."
    )
    icon = "summary.png"

    @staticmethod
    def output_name(feature: Optional[str] = None) -> str:
        """Return the name of a summary table.

        Args:
            feature: The feature; None for the table of all features.

        Returns:
            `Summary: <feature>` (line breaks of the name as spaces), or `Summary`.
        """
        return f"Summary: {feature.replace(chr(10), ' ')}" if feature else "Summary"

    def run(self, data: pd.DataFrame, *, config: SummaryConfig) -> dict[str, Any]:
        """Compute the statistics of the selected features per group.

        Args:
            data: The table.
            config: The grouping columns, the features, the statistics (`aggs`), and
                whether all features are summarized in one table (`single_table`).

        Returns:
            One table per feature, named `Summary: <feature>`, or with `single_table`
            one table named `Summary`. Each has a row per group (one row without
            grouping columns) and a column per feature and statistic, whose header has
            two lines: the feature and the statistic.
        """
        functions = [AGGREGATE_FUNCTIONS[a] for a in config.aggs]
        grouping = list(config.grouping)
        summaries = {}
        for feature in selected_features(data, config.features):
            columns = grouping + [feature]
            if grouping:
                summary = data[columns].groupby(grouping, observed=True).agg(functions)
                summary = summary.reset_index()
            else:
                summary = data[columns].groupby(lambda _: True).agg(functions)
            summary.columns = [headers.join(col).strip() for col in summary.columns]
            summaries[self.output_name(feature)] = summary
        for summary in summaries.values():  # "<feature>\n<aggregate>"
            headers.set_level_names(summary, SUMMARY_LEVELS)
        if not config.single_table or not summaries:
            return summaries
        if grouping:
            table = pd.concat(
                [s.set_index(grouping) for s in summaries.values()], axis=1
            ).reset_index()
        else:
            table = pd.concat(list(summaries.values()), axis=1)
        return {self.output_name(): headers.set_level_names(table, SUMMARY_LEVELS)}

    def map_configs(self, config: SummaryConfig) -> list[SummaryConfig]:
        """Return one config per feature, so that the features run as separate tasks.

        With `single_table`, or with all features selected, the config is not split.
        """
        if config.single_table or config.features == "all":
            return [config]
        return [config.model_copy(update={"features": [f]}) for f in config.features]

    @classmethod
    def output_schema(
        cls, config: SummaryConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs; each statistic's column is derived from its feature."""
        return set_lineage(super().output_schema(config, inputs), first_line)


# coefficient c(alpha) of the two-sample KS test's critical value per alpha level:
# D = c(alpha) * sqrt((n1 + n2) / (n1 * n2))
KS_CRITICAL = {0.1: 1.22, 0.05: 1.36, 0.025: 1.48, 0.01: 1.63, 0.005: 1.73, 0.001: 1.95}


@register_tool
class KSStats(Tool[KSStatsConfig]):
    """Two-sample Kolmogorov-Smirnov tests between values of a category column."""

    name = "KS-Statistics"
    category = "Analysis"
    description = (
        "Two-sample Kolmogorov-Smirnov tests between the values of the comparison"
        " column, separately for each group of the other grouping columns."
    )
    icon = "ks.png"

    def run(self, data: pd.DataFrame, *, config: KSStatsConfig) -> dict[str, Any]:
        """Test each selected feature between the values of the comparison column.

        Args:
            data: The table.
            config: The features, the comparison column, the other grouping columns
                (each of their groups is tested separately) and the significance
                level `alpha`.

        Returns:
            One table per feature, named `KS-stats: <feature>` (see `ks_table`).
        """
        return {
            f"KS-stats: {feature}": self.ks_table(data, feature, config)
            for feature in sorted(selected_features(data, config.features))
        }

    def ks_table(
        self, data: pd.DataFrame, feature: str, config: KSStatsConfig
    ) -> pd.DataFrame:
        """Return the tests of one feature, one row per pair of comparison values.

        The pairs are tested in each group of the other grouping columns. A pair is
        dissimilar if the test statistic is larger than the critical value D at
        `alpha` and the p-value is smaller than `alpha`. Groups and values without
        rows are left out.

        Args:
            data: The table.
            feature: The feature.
            config: The comparison column, the grouping columns and `alpha`.

        Returns:
            A table with the group's values (or a column `Grouping` with `none`), the
            two values compared, whether they are dissimilar, the numbers of rows, the
            p-value, the statistic and the critical value D. The columns up to
            the dissimilar column are category columns.
        """
        comparison, alpha = config.comparison, config.alpha
        # the comparison column splits the data; the other groups are tested separately
        groups = [g for g in config.grouping if g != comparison]
        if groups:
            group_values = [name for name, _ in data.groupby(groups, observed=False)]
            columns = list(groups)
        else:
            group_values = [("none",)]
            columns = ["Grouping"]
        dissimilar = f"dissimilar (<{alpha})"
        pair_columns = [
            f"{comparison} 1",
            f"{comparison} 2",
            f"{comparison} 1 & 2",
            dissimilar,
        ]
        categories = columns + pair_columns
        columns = categories + [
            f"n ({comparison} 1)",
            f"n ({comparison} 2)",
            "p-values",
            "statistic",
            f"critical D ({alpha})",
        ]
        rows = []
        for group_value in group_values:
            self.check_cancelled()
            if groups:
                query = " and ".join(
                    f'`{g}` == "{v}"' for g, v in zip(groups, group_value)
                )
                subset = data.query(query)
            else:
                subset = data
            if len(subset) == 0:
                continue
            split = {
                name: values[feature]
                for name, values in subset.groupby(comparison, observed=False)
            }
            for a, b in combinations(split, 2):
                data1, data2 = split[a], split[b]
                if len(data1) == 0 or len(data2) == 0:
                    continue
                ks = stats.ks_2samp(data1, data2)
                critical_d = KS_CRITICAL[alpha] * np.sqrt(
                    (len(data1) + len(data2)) / (len(data1) * len(data2))
                )
                is_dissimilar = ks.statistic > critical_d and ks.pvalue < alpha
                rows.append(
                    list(group_value)
                    + [a, b, f"{a}-{b}", "Yes" if is_dissimilar else "No"]
                    + [len(data1), len(data2), ks.pvalue, ks.statistic, critical_d]
                )
        table = pd.DataFrame(rows, columns=columns)
        for column in categories:
            table[column] = table[column].astype("category")
        return table

    def map_configs(self, config: KSStatsConfig) -> list[KSStatsConfig]:
        """Return one config per feature, so that the features run as separate tasks.

        With all features selected, the config is not split.
        """
        if config.features == "all":
            return [config]
        return [config.model_copy(update={"features": [f]}) for f in config.features]

    @classmethod
    def validate(cls, config: KSStatsConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config: the comparison column needs at least two values."""
        issues = super().validate(config, inputs)
        schema = inputs[0]
        column = schema.column(config.comparison) if schema is not None else None
        if column is not None and column.levels is not None and len(column.levels) < 2:
            issues.append(
                Issue("comparison", f"'{config.comparison}' has fewer than 2 values")
            )
        return issues


@register_tool
class RelativeChange(Tool[RelativeChangeConfig]):
    """Features relative to their mean or median in a reference group."""

    name = "Relative Change"
    category = "Analysis"
    description = (
        "Divides each feature by its mean or median in the reference group"
        " (reference value of the reference column), per group."
    )
    icon = "relchange.png"
    outputs = (OutputSpec("Relative Change", TableType),)

    def run(
        self, data: pd.DataFrame, *, config: RelativeChangeConfig
    ) -> dict[str, Any]:
        """Divide each selected feature by its mean or median in the reference rows.

        The reference rows are the rows whose reference column has the reference
        value. If there are grouping columns besides the reference column, each row is
        divided by the reference rows of its own group. A row whose group has no
        reference rows gets missing values, and a warning in the log names these
        groups.

        Args:
            data: The table.
            config: The features, the grouping columns, the reference column
                (`reference_group`) and value (`reference_value`), and `method`
                (`mean` or `median`).

        Returns:
            `Relative Change`: the category columns, and a column `rel <feature>` for
            each feature.
        """
        categories = category_columns(data)
        features = selected_features(data, config.features)
        reference = config.reference_group
        # rows are matched to the reference rows of their group only (#178)
        keys = [c for c in config.grouping if c != reference]
        reference_rows = data.loc[data[reference] == config.reference_value]
        if keys:
            reference_values = (
                reference_rows.groupby(keys, observed=True)[features]
                .agg(config.method)
                .reset_index()
            )
            matched = data[keys].merge(
                reference_values, on=keys, how="left", indicator=True
            )
            missing = matched.loc[matched["_merge"] == "left_only", keys]
            if len(missing):
                groups = missing.drop_duplicates().astype(str).agg(", ".join, axis=1)
                logger.warning(
                    f"{self.name}: no '{config.reference_value}' rows in"
                    f" {' / '.join(keys)} {'; '.join(groups)}: left empty"
                )
            denominators = matched[features].set_axis(data.index)
        else:
            denominators = reference_rows[features].agg(config.method)
        relative = data[categories].copy()
        for feature in features:
            relative[f"rel {feature}"] = data[feature] / denominators[feature]
        return {"Relative Change": relative}

    @classmethod
    def output_schema(
        cls, config: RelativeChangeConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs; a column `rel <feature>` is derived from `<feature>`."""
        return set_lineage(
            super().output_schema(config, inputs),
            lambda name: name[4:] if name.startswith("rel ") else None,
        )

    @classmethod
    def validate(
        cls, config: RelativeChangeConfig, inputs: Sequence[Any]
    ) -> list[Issue]:
        """Check the config; a reference value the column doesn't have is an error."""
        issues = super().validate(config, inputs)
        schema = inputs[0]
        column = schema.column(config.reference_group) if schema is not None else None
        if (
            column is not None
            and column.levels is not None
            and config.reference_value not in column.levels
        ):
            issues.append(
                Issue(
                    "reference_value",
                    f"'{config.reference_value}' is not a value of"
                    f" '{config.reference_group}'",
                )
            )
        return issues


@register_tool
class SeriesAnalysis(Tool[SeriesAnalysisConfig]):
    """Statistics over a series of features per row, e.g. pivoted time points."""

    name = "Series Analysis"
    category = "Analysis"
    description = (
        "Min, max, range, mean, median and the deltas between consecutive features"
        " of a series (e.g. the pivoted values of a time point column)."
    )
    icon = "seriesanalysis.png"
    outputs = (OutputSpec("Series Analysis", TableType),)

    def run(
        self, data: pd.DataFrame, *, config: SeriesAnalysisConfig
    ) -> dict[str, Any]:
        """Compute statistics over a series of features, per row.

        The features are the steps of the series, for example the pivoted columns
        whose headers have the lines `FLIRR`, `mean` and `Day 1`, `Day 2`, and so on.
        The header lines that all features share (`FLIRR`, `mean`) name the new
        columns; the other lines name the steps.

        Args:
            data: The table.
            config: The features in series order; the statistics: `series_min`,
                `series_max`, `series_range`, `series_mean`, `series_median`, and the
                differences between consecutive steps: `delta`, `delta_cum`,
                `delta_norm`, `delta_min`, `delta_max`, `delta_sum`; and whether the
                features are kept in the result (`merge_input`).

        Returns:
            `Series Analysis`: the category columns, the features if kept, and a
            column per statistic, for example `Series max` or `delta Day 1:Day 2`
            under the shared header lines. A normalized difference is the difference
            divided by the change from the first to the last step.

        Raises:
            ValueError: If no features are selected.
        """
        statistics = config.statistics
        features = selected_features(data, config.features)
        if not features:
            raise ValueError(f"{self.name}: select the features of the series")
        categories = category_columns(data)
        # pivoted features look like "FLIRR\nmean\nDay 1"; the lines all features
        # share label the results, the others name the series' steps
        lines = [f.split("\n") for f in features]
        shared = set(lines[0]).intersection(*lines[1:])
        label = "\n".join(line for line in lines[0] if line in shared)
        steps = ["\n".join(l for l in f if l not in shared) for f in lines]
        logger.debug(f"series {label}: {steps}")

        columns = categories + features if config.merge_input else categories
        table = data[columns].copy()
        values = data[features]
        if "series_min" in statistics:
            table[f"{label}\nSeries min"] = values.min(axis=1)
        if "series_max" in statistics:
            table[f"{label}\nSeries max"] = values.max(axis=1)
        if "series_range" in statistics:
            table[f"{label}\nSeries max-min"] = values.max(axis=1) - values.min(axis=1)
        if "series_mean" in statistics:
            table[f"{label}\nSeries mean"] = values.mean(axis=1)
        if "series_median" in statistics:
            table[f"{label}\nSeries median"] = values.median(axis=1)

        delta_statistics = {
            "delta",
            "delta_min",
            "delta_max",
            "delta_sum",
            "delta_cum",
            "delta_norm",
        }
        if statistics & delta_statistics:
            delta = values.diff(axis=1)
            cumulative = delta.cumsum(axis=1)
            normalized = delta.divide(cumulative.iloc[:, -1], axis=0)
            steps = ["None"] + steps
            pairs = range(len(steps) - 1)
            delta.columns = [f"{label}\ndelta {steps[i]}:{steps[i + 1]}" for i in pairs]
            cumulative.columns = [
                f"{label}\ncumulative delta {steps[1]}:{steps[i + 1]}" for i in pairs
            ]
            normalized.columns = [
                f"{label}\nnormalized delta {steps[i]}:{steps[i + 1]}" for i in pairs
            ]
            # the first column has no predecessor
            if "delta" in statistics:
                table = table.join(delta.iloc[:, 1:])
            if "delta_cum" in statistics:
                table = table.join(cumulative.iloc[:, 1:])
            if "delta_norm" in statistics:
                table = table.join(normalized.iloc[:, 1:])
            if "delta_min" in statistics:
                table[f"{label}\ndelta min"] = delta.iloc[:, 1:].min(axis=1)
            if "delta_max" in statistics:
                table[f"{label}\ndelta max"] = delta.iloc[:, 1:].max(axis=1)
            if "delta_sum" in statistics:
                table[f"{label}\ndelta sum"] = delta.iloc[:, 1:].sum(axis=1)
        return {"Series Analysis": table}

    @classmethod
    def validate(
        cls, config: SeriesAnalysisConfig, inputs: Sequence[Any]
    ) -> list[Issue]:
        """Check the config; the number of features is checked by `Tool.validate`."""
        return super().validate(config, inputs)
