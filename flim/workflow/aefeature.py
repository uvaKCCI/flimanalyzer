"""FLIM Feature Analysis: trains autoencoders, then runs them on the data and compares
their first feature with FLIRR and the first principal component."""

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
from flim.core.types import InputSpec, TableType
from flim.core.workflow import Workflow, workflow_input
from flim.tools.autoencoder import RunAE
from flim.tools.data import Concat, Filter, Pivot, Sort
from flim.tools.ml import PCAnalysis
from flim.tools.plot import KDE, BarPlot
from flim.tools.statistics import KSStats, SeriesAnalysis, Summarize
from flim.workflow.aetune import model_files, result_name, train_models


@register_tool
class AEFeature(Workflow[AEFeatureConfig]):
    name = "FLIM Feature Analysis"
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

    def build(self, data_train, data_run, *, config):
        features = config.features
        last_epoch = config.training.epochs
        timeseries = config.timeseries
        series = [v for v in data_train[timeseries].unique() if "15" not in v]
        pairs = list(zip(series, series[1:]))

        def filtered(data, name):
            return Filter()(
                workflow_input(data, name),
                config=FilterConfig(),
                task_tags=f"{name}_Filtered",
            )["Table: Filtered"]

        train = filtered(data_train, "Input_Train")
        run = filtered(data_run, "Input_Run")
        pca = PCAnalysis()(
            run, config=PCAConfig(features=features), task_tags="PCA"
        )["Table: PCA Components"]
        trained = train_models(
            train, config.training, f"AEFeature-{len(features)}", last_epoch=True
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
                task_tags=tag,
                after=[output],
            )[result_name("Features", files[0])]
            compared.append((tag, features_table, "Feature 1", f"AERun {tag}:"))

        ks = {}
        for tag, table, feature, prefix in compared:
            KDE()(
                table,
                config=KDEConfig(grouping=["Treatment"], features=[feature]),
                task_tags=tag,
            )
            summary = Summarize()(
                table,
                config=SummaryConfig(
                    grouping=["Cell", "FOV", "Treatment"],
                    features=[feature],
                    aggs=["mean"],
                ),
                task_tags=tag,
            )["Table: Summary"]
            mean = f"{feature}\nmean"
            pivoted = Pivot()(
                summary,
                config=PivotConfig(grouping=[timeseries], features=[mean]),
                task_tags=tag,
            )["Table: Pivoted"]
            changes = SeriesAnalysis()(
                pivoted,
                config=SeriesAnalysisConfig(
                    features=[f"{mean}\n{t}" for t in series],
                    statistics={"delta", "delta_cum", "delta_norm"},
                ),
                task_tags=tag,
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
                task_tags=tag,
            )["Table: Sorted"]
            BarPlot()(
                ordered,
                config=BarPlotConfig(
                    grouping=["FOV", "Cell"],
                    features=deltas,
                    bar_type="stacked",
                    error_type="s.e.m.",
                ),
                task_tags=tag,
            )
            ks[tag] = KSStats()(
                table,
                config=KSStatsConfig(
                    comparison="Treatment",
                    grouping=["Treatment", "FOV", "Cell"],
                    features=[feature],
                    prefix=prefix,
                ),
                task_tags=tag,
            )[f"{prefix}Table: KS-stats: {feature}"]
        Concat()(ks, config=ConcatConfig(), task_tags="Summary")
