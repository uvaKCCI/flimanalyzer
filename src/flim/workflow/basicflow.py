"""Basic FLIRR Analysis: summaries, relative changes and plots of the FLIRR features."""

import numpy as np
import pandas as pd

from flim.configs import (
    KDEConfig,
    LinePlotConfig,
    PairPlotConfig,
    RelativeChangeConfig,
    ScatterPlotConfig,
    SummaryConfig,
)
from flim.configs.workflow import BasicFLIRRConfig
from flim.core.registry import register_tool
from flim.core.workflow import Workflow, workflow_input
from flim.core.types import PlotType, TableType
from flim.tools.common import ordered_values
from flim.tools.plot import KDE, LinePlot, PairPlot, ScatterPlot, flirr_columns
from flim.tools.statistics import RelativeChange, Summarize

# many measurements make pair plots slow to draw
PAIR_PLOT_POINTS = {"mode": "sample", "samples": 20000}


@register_tool
class BasicFLIRR(Workflow[BasicFLIRRConfig]):
    """Summaries, relative changes and plots of the FLIRR features of one table."""

    name = "Basic FLIRR Analysis"
    output_types = (TableType, PlotType)
    description = (
        "Summaries and relative changes of the features, grouped by the first grouping"
        " column, with KDE, line, pair and scatter plots."
    )
    icon = "flirrworkflow.png"

    def build(self, data: pd.DataFrame, *, config: BasicFLIRRConfig) -> None:
        """Call the workflow's steps on the table.

        The steps are:

        - Summaries of the features per value of the first grouping column (count,
          median, mean, standard deviation, S.E.M.; prefix `Stats-`), and the count
          of the first feature per group of all grouping columns (prefix `Counts-`).
        - Pair plots of the features whose names contain `FAD`, and of those whose
          names contain `NAD`, per value of the first grouping column, with KDEs on
          the diagonal and a sample of at most 20000 rows.
        - Relative changes: each feature divided by its mean in the rows with the
          reference value of the first grouping column, per group of the other
          grouping columns, and the mean of each `rel <feature>` per group of the
          grouping columns in reverse order (prefix `Relative Stats-`).
        - A scatter plot of FAD a1 % against NAD(P)H a2 %, if both columns are set or
          found by name among the numeric columns.
        - A line plot of each `rel <feature>` per group of the first two grouping
          columns, and a KDE plot of each feature per value of the first grouping
          column.

        Args:
            data: The table.
            config: The grouping columns (at least one), the features, the reference
                value (None: the first value of the first grouping column, in the
                order of its categories) and the FAD a1 % and NAD(P)H a2 % columns
                (None: found by name).
        """
        grouping, features = config.grouping, config.features
        first = grouping[:1]
        rel_features = [f"rel {f}" for f in features]
        input = workflow_input(data)
        Summarize()(
            input,
            config=SummaryConfig(
                grouping=first,
                features=features,
                aggs=["count", "median", "mean", "std", "sem"],
                prefix="Stats-",
            ),
        )
        Summarize()(
            input,
            config=SummaryConfig(
                grouping=grouping, features=features[:1], aggs=["count"], prefix="Counts-"
            ),
        )
        for label, word in (("FAD", "FAD"), ("NADPH", "NAD")):
            PairPlot()(
                input,
                config=PairPlotConfig(
                    grouping=first,
                    x_vars=[f for f in features if word in f],
                    diagonal="KDE",
                    points=PAIR_PLOT_POINTS,
                    prefix=f"{label}-",
                ),
            )
        relative = RelativeChange()(
            input,
            config=RelativeChangeConfig(
                grouping=grouping[1:],
                features=features,
                reference_group=grouping[0],
                reference_value=config.reference_value
                or ordered_values(data[grouping[0]])[0],
                method="mean",
            ),
        )["Table: Relative Change"]
        Summarize()(
            relative,
            config=SummaryConfig(
                grouping=grouping[::-1],
                features=rel_features,
                aggs=["mean"],
                prefix="Relative Stats-",
            ),
        )
        numbers = list(data.select_dtypes(include=np.number))
        _, fad, nadph = flirr_columns(numbers, None, config.fad_a1, config.nadph_a2)
        if fad and nadph:
            ScatterPlot()(
                input,
                config=ScatterPlotConfig(
                    grouping=first, features=[fad, nadph], x_axis=fad
                ),
            )
        for feature in rel_features:
            LinePlot()(
                relative,
                config=LinePlotConfig(grouping=grouping[:2], features=[feature]),
            )
        for feature in features:
            KDE()(input, config=KDEConfig(grouping=first, features=[feature]))
