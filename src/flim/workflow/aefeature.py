"""FLIM Feature Analysis: trains autoencoders and compares their first feature.

The models run on the data, and their first feature is compared with FLIRR and the
first principal component.
"""

import pandas as pd

from flim.configs import (
    BarPlotConfig,
    ConcatConfig,
    FilterConfig,
    KDEConfig,
    KSStatsConfig,
    PCAConfig,
    PivotConfig,
    SeriesAnalysisConfig,
    SortConfig,
    SummaryConfig,
)
from flim.configs.workflow import AEFeatureConfig
from flim.core.registry import register_tool
from flim.core.runner import TaskOutput
from flim.core.types import InputSpec, PlotType, TableType
from flim.core.workflow import Workflow, workflow_input
from flim.tools.autoencoder import RunAE
from flim.tools.common import ordered_values
from flim.tools.data import Concat, Filter, Pivot, Sort
from flim.tools.ml import PCAnalysis
from flim.tools.plot import KDE, BarPlot
from flim.tools.statistics import KSStats, SeriesAnalysis, Summarize
from flim.workflow.aetune import model_files, result_name, train_models


@register_tool
class AEFeature(Workflow[AEFeatureConfig]):
    """Trains autoencoders and compares their first feature with FLIRR and PCA."""

    name = "FLIM Feature Analysis"
    output_types = (TableType, PlotType)
    description = (
        "Trains an autoencoder for each combination of batch size, learning rate and"
        " weight decay on the training data, runs the models of the last epoch on the"
        " data, and compares their first feature with FLIRR and the first principal"
        " component: summaries, normalized changes along the time series, KS"
        " statistics and plots."
    )
    icon = "aefeatureworkflow.png"
    inputs = (
        InputSpec("training data", TableType),
        InputSpec("data", TableType, description="The models run on this table."),
    )

    def build(
        self,
        data_train: pd.DataFrame,
        data_run: pd.DataFrame,
        *,
        config: AEFeatureConfig,
    ) -> None:
        """Call the workflow's steps on the training table and the table to analyze.

        The steps, by their ids (each saves into `<id>-<tool>`; the calls of a loop
        are parts of a step, named by what they analyze):

        - 00: both tables (parts `Input_Train`, `Input_Run`); 01: filter them; 02:
          compute the principal components of the features of the filtered
          `data_run`.
        - 03: train a model per combination of the training settings on the filtered
          `data_train` (see `train_models`); 04: run each trained model of the last
          epoch on the filtered `data_run` (Autoencoder: Run).
        - For FLIRR, the first principal component and the first feature of each
          model (parts `FLIRR`, `PCA` and each model's combination): 05: a KDE plot
          per time point; 06, 07: the mean per group of the other grouping columns
          and time point, pivoted to one column per time point; 08, 09: the
          normalized changes between consecutive time points (Series Analysis),
          sorted by the changes from the time points whose name contains the control
          group (not case-sensitive); 10: shown as stacked bars with S.E.M. per
          group of the other grouping columns; 11: KS statistics between the time
          points, per group of the other grouping columns.
        - 12: concatenate the KS statistics tables into one table.

        The time points are the values of the time series column of `data_train`, in
        the order of its categories.

        Args:
            data_train: The table the models are trained on.
            data_run: The table the models run on.
            config: The features, the grouping columns, the time series column, the
                control group, and the settings of the training and run steps.
        """
        features = config.features
        last_epoch = config.training.epochs
        timeseries = config.timeseries
        # the grouping columns besides the time series, e.g. FOV and Cell (#190)
        cells = [c for c in config.grouping if c != timeseries]
        series = ordered_values(data_train[timeseries])  # the time points
        pairs = list(zip(series, series[1:]))

        # fixed step ids, one per call; the calls of a loop are parts of one step
        def filtered(data: pd.DataFrame, name: str) -> TaskOutput:
            return Filter()(
                workflow_input(data, name, step="00"),
                config=FilterConfig(),
                task_tags=[name],
                step="01",
            )["Table: Filtered"]

        train = filtered(data_train, "Input_Train")
        run = filtered(data_run, "Input_Run")
        pca = PCAnalysis()(run, config=PCAConfig(features=features), step="02")[
            "Table: PCA Components"
        ]
        trained = train_models(
            train, config.training, f"AEFeature-{len(features)}", last_epoch=True, step="03"
        )

        # FLIRR, the first principal component and the first feature of each model
        compared = [("FLIRR", run, "FLIRR", "FLIRR:"), ("PCA", pca, "PC 1", "PCA:")]
        for tag, output in trained:
            files = model_files(output, last_epoch)
            if not files:
                continue  # training failed
            features_table = RunAE()(
                run,
                config=config.run.model_copy(update={"model_files": files}),
                task_tags=[tag],
                after=[output],
                step="04",
            )[result_name("Features", files[0])]
            compared.append((tag, features_table, "Feature 1", f"AERun {tag}:"))

        ks = {}
        for tag, table, feature, prefix in compared:
            KDE()(
                table,
                config=KDEConfig(grouping=[timeseries], features=[feature]),
                task_tags=[tag],
                step="05",
            )
            summary = Summarize()(
                table,
                config=SummaryConfig(
                    grouping=cells[::-1] + [timeseries],
                    features=[feature],
                    aggs=["mean"],
                ),
                task_tags=[tag],
                step="06",
            )["Table: Summary"]
            mean = f"{feature}\nmean"
            pivoted = Pivot()(
                summary,
                config=PivotConfig(grouping=[timeseries], features=[mean]),
                task_tags=[tag],
                step="07",
            )["Table: Pivoted"]
            changes = SeriesAnalysis()(
                pivoted,
                config=SeriesAnalysisConfig(
                    features=[f"{mean}\n{t}" for t in series],
                    statistics={"delta", "delta_cum", "delta_norm"},
                ),
                task_tags=[tag],
                step="08",
            )["Table: Series Analysis"]
            deltas = [f"{mean}\nnormalized delta {a}:{b}" for a, b in pairs]
            control = config.control_group.lower()
            ordered = Sort()(
                changes,
                config=SortConfig(
                    features=[
                        d
                        for d, (a, _) in zip(deltas, pairs)
                        if control in a.lower()
                    ]
                ),
                task_tags=[tag],
                step="09",
            )["Table: Sorted"]
            BarPlot()(
                ordered,
                config=BarPlotConfig(
                    grouping=cells,
                    features=deltas,
                    bar_type="stacked",
                    error_type="s.e.m.",
                ),
                task_tags=[tag],
                step="10",
            )
            ks[tag] = KSStats()(
                table,
                config=KSStatsConfig(
                    comparison=timeseries,
                    grouping=[timeseries] + cells,
                    features=[feature],
                    prefix=prefix,
                ),
                task_tags=[tag],
                step="11",
            )[f"{prefix}Table: KS-stats: {feature}"]
        Concat()(ks, config=ConcatConfig(), step="12")
