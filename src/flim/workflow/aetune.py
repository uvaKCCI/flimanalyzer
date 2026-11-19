"""FLIM Data Augmentation Tuning: trains autoencoders, then augments the data."""

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from flim import utils
from flim.configs import (
    AETrainConfig,
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
from flim.core.runner import TaskOutput, select
from flim.core.workflow import Workflow, workflow_input
from flim.core.types import FileType, PlotType, TableType
from flim.tools.autoencoder import AEAugment, AETraining
from flim.tools.data import Concat, Filter, Unpivot
from flim.tools.plot import KDE, BarPlot, Heatmap, LinePlot
from flim.tools.statistics import Summarize

# the columns of the loss tables that name a model's training combination
LOSS_GROUPING = ["Batch Size", "Learning Rate", "Weight Decay"]


def train_models(
    data: TaskOutput,
    training: AETrainConfig,
    model_name: str,
    last_epoch: bool = False,
    step: Optional[str] = None,
) -> list[tuple[str, TaskOutput]]:
    """Add one Autoencoder: Train task per combination of the training settings.

    A combination is one batch size, one learning rate and one weight decay. The
    tasks use `training` with `model_name` and without loss plots. Each task is
    tagged with its combination, e.g. `b128_l1e05_d1e07` (see `utils.clean`), which
    names its results folder: a part of the step `step`.

    Args:
        data: The training table, the output of an earlier step.
        training: The training settings, with the lists of batch sizes, learning
            rates and weight decays.
        model_name: The name of the models, used in their file names.
        last_epoch: If true, the tag also has the number of epochs, e.g. `_e0006`.
            Defaults to False.
        step: The step id of the trainings; None for none.

    Returns:
        The tag and the output of each training task.
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
        trained.append((tag, tool(data, config=config, task_tags=[tag], step=step)))
    return trained


def model_files(output: TaskOutput, epoch: Optional[int] = None) -> list[Path]:
    """Return the model files a training task saved; waits for the task to finish.

    Args:
        output: The output of an Autoencoder: Train task.
        epoch: If set, only the files of that epoch, whose names end with
            `_epoch<epoch, four digits>.model`, e.g. `_epoch0006.model`. Defaults to
            None (all files).

    Returns:
        The files; empty if the task did not complete.
    """
    found = output["Model File"].value() or []
    found = [found] if isinstance(found, str) else found
    return [Path(f) for f in found if epoch is None or str(f).endswith(f"_epoch{epoch:04d}.model")]


def result_name(kind: str, path: str | os.PathLike) -> str:
    """Return the name of a result that an autoencoder tool names after a model file.

    Args:
        kind: The kind of result, e.g. `Features` or `Simulated`.
        path: The model file; only its file name is used.

    Returns:
        `Table: <kind>-<file name>`.
    """
    return f"Table: {kind}-{os.path.basename(str(path))}"


def loss_summary(trained: list[tuple[str, TaskOutput]], first_step: int) -> None:
    """Add tasks for the training and validation losses of the trained models.

    The tasks are: the loss tables of all models concatenated into one table, its
    minimum losses per input and combination, a line plot of both losses per epoch
    and combination, and a bar plot of each loss per epoch and combination. Waits
    for the training tasks to finish. Failed trainings are left out; nothing is added
    if all failed.

    Args:
        trained: The tag and the output of each training task (see `train_models`).
        first_step: The step id of the first task; the others follow it: the
            concatenated table, its summary, the unpivoted table, the line plot and
            the bar plots (a part per loss).
    """
    tables = {}
    for tag, output in trained:
        found = select([output], "^Table: AE Loss")  # waits for the training
        if found:  # not if the training failed
            tables[tag] = found[0]
    if not tables:
        return
    ids = [f"{n:02d}" for n in range(first_step, first_step + 5)]
    losses = Concat()(tables, config=ConcatConfig(), step=ids[0])["Table: Concatenated"]
    Summarize()(
        losses,
        config=SummaryConfig(
            grouping=["Input"] + LOSS_GROUPING,
            features=["Training Loss", "Validation Loss", "Model File"],
            aggs=["min"],
        ),
        step=ids[1],
    )
    long = Unpivot()(
        losses,
        config=UnpivotConfig(
            features=["Training Loss", "Validation Loss"], category_name="Loss Type"
        ),
        step=ids[2],
    )["Table: Unpivoted"]
    LinePlot()(
        long,
        config=LinePlotConfig(
            grouping=["Epoch", "Loss Type"] + LOSS_GROUPING, features=[Unpivot.VALUE]
        ),
        step=ids[3],
    )
    for loss in ("Training Loss", "Validation Loss"):
        BarPlot()(
            losses,
            config=BarPlotConfig(grouping=["Epoch"] + LOSS_GROUPING, features=[loss]),
            step=ids[4],
            task_tags=[loss],
        )


def overview(
    data: TaskOutput,
    features: list[str],
    grouping: str,
    steps: tuple[str, str],
    part: Optional[str] = None,
) -> None:
    """Add tasks for a heatmap of the features' correlations and their KDE plots.

    The heatmap shows the Spearman correlations; the KDE plots show the distribution
    of each feature per value of the column `grouping`.

    Args:
        data: The table, the output of an earlier step.
        features: The features.
        grouping: The grouping column of the KDE plots.
        steps: The step ids of the heatmap and of the KDE plots.
        part: The part of the steps the tasks are, e.g. a model's combination; None
            for none.
    """
    Heatmap()(
        data,
        config=HeatmapConfig(features=features, correlation="spearman"),
        step=steps[0],
        task_tags=[part] if part else None,
    )
    KDE()(
        data,
        config=KDEConfig(grouping=[grouping], features=features),
        step=steps[1],
        task_tags=[part] if part else None,
    )


@register_tool
class AETune(Workflow[AETuneConfig]):
    """Trains autoencoders with each combination of settings, then augments the data."""

    name = "FLIM Data Augmentation Tuning"
    output_types = (TableType, PlotType, FileType)
    description = (
        "Trains an autoencoder for each combination of batch size, learning rate and"
        " weight decay, then augments the data with each model."
    )
    icon = "aetuneworkflow.png"

    def build(self, data: pd.DataFrame, *, config: AETuneConfig) -> None:
        """Call the workflow's steps on the table.

        The steps, by their ids (each saves into `<id>-<tool>`; the calls for each
        model are parts of a step, named by the model's combination):

        - 00: the input table; 01: filter it; 02, 03: the overview of its features
          (see `overview`), per value of the time series column.
        - 04: train a model per combination of the training settings (see
          `train_models`); 05 to 09: summarize their losses (see `loss_summary`).
        - For each model that was trained: 10: augment the filtered table with the
          model's files (Autoencoder: Augment); 11: filter the result; 12, 13: its
          overview; 14: summarize its features (min, max, median, count) per value
          of the time series column, one table per feature.

        Args:
            data: The table.
            config: The features, the time series column, and the settings of the
                training and augmentation steps.
        """
        features = config.features
        # fixed step ids, one per call; the calls for each model are parts of a step
        input = workflow_input(data, step="00")
        filtered = Filter()(input, config=FilterConfig(), step="01")["Table: Filtered"]
        overview(filtered, features, config.timeseries, ("02", "03"))
        trained = train_models(
            filtered, config.training, f"AEAugment-{len(features)}", step="04"
        )
        loss_summary(trained, first_step=5)  # 05 to 09
        for tag, output in trained:
            files = model_files(output)
            if not files:
                continue  # training failed
            augmented = AEAugment()(
                filtered,
                config=config.augment.model_copy(update={"model_files": files}),
                task_tags=[tag],
                after=[output],
                step="10",
            )[result_name("Simulated", files[0])]
            augmented = Filter()(augmented, config=FilterConfig(), task_tags=[tag], step="11")[
                "Table: Filtered"
            ]
            overview(augmented, features, config.timeseries, ("12", "13"), part=tag)
            Summarize()(
                augmented,
                config=SummaryConfig(
                    grouping=[config.timeseries],
                    features=features,
                    single_table=False,
                    aggs=["min", "max", "median", "count"],
                ),
                task_tags=[tag],
                step="14",
            )
