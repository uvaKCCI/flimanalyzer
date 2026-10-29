"""FLIM Data Augmentation Tuning: trains autoencoders, then augments the data."""

import os
from pathlib import Path

from flim import utils
from flim.configs import (
    BarPlotConfig,
    ConcatConfig,
    FilterConfig,
    HeatmapConfig,
    KDEConfig,
    LinePlotConfig,
    SummaryConfig,
    UnpivotConfig,
)
from flim.configs.workflow import AETuneConfig
from flim.core.registry import register_tool
from flim.core.runner import select
from flim.core.workflow import Workflow, workflow_input
from flim.tools.autoencoder import AEAugment, AETraining
from flim.tools.data import Concat, Filter, Unpivot
from flim.tools.plot import KDE, BarPlot, Heatmap, LinePlot
from flim.tools.statistics import Summarize

LOSS_GROUPING = ["Batch Size", "Learning Rate", "Weight Decay"]


def train_models(data, training, model_name: str, last_epoch: bool = False):
    """One training task per combination of batch size, learning rate and weight
    decay, tagged with the combination (its results folder).

    Returns:
        list of (tag, TaskOutput) pairs.
    """
    tool = AETraining()
    training = training.model_copy(
        update={"model_name": model_name, "create_plots": False}
    )
    trained = []
    for config in tool.map_configs(training):
        combination = (
            f"b{config.batch_sizes[0]}",
            f"l{config.learning_rates[0]}",
            f"d{config.weight_decays[0]}",
        )
        tag = str(combination) + (f" e{config.epochs:04d}" if last_epoch else "")
        tag = utils.clean(tag)
        trained.append((tag, tool(data, config=config, task_tags=tag)))
    return trained


def model_files(output, epoch: int = None) -> list[Path]:
    """The model files a training task saved (only that of ``epoch``); waits for it."""
    found = output["Model File"].value() or []
    found = [found] if isinstance(found, str) else found
    return [Path(f) for f in found if epoch is None or f"{epoch:04d}" in str(f)]


def result_name(kind: str, path) -> str:
    """The name of a result an autoencoder tool names after a model file."""
    return f"Table: {kind}-{os.path.basename(str(path))}"


def loss_summary(trained, tags: str):
    """Training and validation losses of all models: table, summary and plots."""
    tables = {}
    for tag, output in trained:
        found = select([output], "^Table: AE Loss")  # waits for the training
        if found:  # not if the training failed
            tables[tag] = found[0]
    if not tables:
        return
    losses = Concat()(
        tables,
        config=ConcatConfig(),
        task_tags=tags,
    )["Table: Concatenated"]
    Summarize()(
        losses,
        config=SummaryConfig(
            grouping=["Source"] + LOSS_GROUPING,
            features=["Training Loss", "Validation Loss", "Model File"],
            aggs=["min"],
        ),
        task_tags=tags,
    )
    long = Unpivot()(
        losses,
        config=UnpivotConfig(
            features=["Training Loss", "Validation Loss"],
            category_name="Loss Type",
            feature_name="Loss Value",
        ),
        task_tags=tags,
    )["Table: Unpivoted"]
    LinePlot()(
        long,
        config=LinePlotConfig(
            grouping=["Epoch", "Loss Type"] + LOSS_GROUPING, features=["Loss Value"]
        ),
        task_tags=tags,
    )
    for loss in ("Training Loss", "Validation Loss"):
        BarPlot()(
            losses,
            config=BarPlotConfig(grouping=["Epoch"] + LOSS_GROUPING, features=[loss]),
            task_tags=tags,
        )


def overview(data, features, tags):
    """Correlations and distributions of the features."""
    Heatmap()(
        data,
        config=HeatmapConfig(features=features, correlation="spearman"),
        task_tags=tags,
    )
    KDE()(data, config=KDEConfig(grouping=["Treatment"], features=features), task_tags=tags)


@register_tool
class AETune(Workflow[AETuneConfig]):
    name = "FLIM Data Augmentation Tuning"
    description = (
        "Trains an autoencoder for each combination of batch size, learning rate and"
        " weight decay, then augments the data with each model."
    )
    icon = "aetuneworkflow.png"

    def build(self, data, *, config):
        features = config.features
        input = workflow_input(data)
        filtered = Filter()(input, config=FilterConfig(), task_tags="Input_Filtered")[
            "Table: Filtered"
        ]
        overview(filtered, features, "Input_Filtered")
        trained = train_models(
            filtered, config.training, f"AEAugment-{len(features)}"
        )
        loss_summary(trained, "AE1_Training_Summary")
        for tag, output in trained:
            files = model_files(output)
            if not files:
                continue  # training failed
            augmented = AEAugment()(
                filtered,
                config=config.augment.model_copy(update={"model_files": files}),
                task_tags=tag,
                after=[output],
            )[result_name("Simulated", files[0])]
            augmented = Filter()(augmented, config=FilterConfig(), task_tags=tag)[
                "Table: Filtered"
            ]
            overview(augmented, features, tag)
            Summarize()(
                augmented,
                config=SummaryConfig(
                    grouping=["Treatment"],
                    features=features,
                    single_table=False,
                    aggs=["min", "max", "median", "count"],
                ),
                task_tags=tag,
            )
