"""Basic FLIRR Analysis: summaries, relative changes and plots of the FLIRR features."""

import numpy as np

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
from flim.tools.plot import KDE, LinePlot, PairPlot, ScatterPlot
from flim.tools.statistics import RelativeChange, Summarize

# many measurements make pair plots slow to draw
PAIR_PLOT_POINTS = {"mode": "sample", "samples": 20000}


def scatter_features(data) -> list:
    """The FAD a1% and NAD(P)H a2% columns (not FLIRR or ratios)."""
    return [
        c
        for c in data.select_dtypes(include=np.number)
        if "FLIRR" not in c.upper()
        and "/" not in c
        and (
            ("FAD" in c and "a1" in c and "%" in c)
            or ("NAD" in c and "a2" in c and "%" in c)
        )
    ]


@register_tool
class BasicFLIRR(Workflow[BasicFLIRRConfig]):
    name = "Basic FLIRR Analysis"
    description = (
        "Summaries and relative changes of the features, grouped by the first grouping"
        " column, with KDE, line, pair and scatter plots."
    )
    icon = "flirrworkflow.png"

    def build(self, data, *, config):
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
                reference_value=str(data[grouping[0]].unique()[0]),
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
        ScatterPlot()(
            input,
            config=ScatterPlotConfig(grouping=first, features=scatter_features(data)),
        )
        for feature in rel_features:
            LinePlot()(
                relative,
                config=LinePlotConfig(grouping=grouping[:2], features=[feature]),
            )
        for feature in features:
            KDE()(input, config=KDEConfig(grouping=first, features=[feature]))
