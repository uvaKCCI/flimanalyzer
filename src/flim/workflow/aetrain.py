"""Autoencoder Train: trains one autoencoder per combination, then lists the model files."""

import pandas as pd

from flim.configs import AETrainConfig, AETrainWorkflowConfig, CollectFilesConfig
from flim.core.registry import register_tool
from flim.core.workflow import Workflow
from flim.core.types import FileType, PlotType, TableType
from flim.tools.autoencoder import AETraining
from flim.tools.data import CollectFiles


@register_tool
class AETrain(Workflow[AETrainWorkflowConfig]):
    """Trains autoencoder models, one per combination of settings, and lists their files."""

    name = "Autoencoder Train"
    output_types = (TableType, PlotType, FileType)
    former_names = ("Autoencoder: Train",)
    category = "Analysis"
    description = (
        "Trains and saves autoencoder models of the selected features, one per"
        " combination of batch size, learning rate and weight decay, and lists the"
        " model files in one table. Training and validation sets are split randomly by"
        " the grouping columns (except the timeseries column)."
    )
    icon = "aetrain.png"

    def build(self, data: pd.DataFrame, *, config: AETrainWorkflowConfig) -> None:
        """Call the workflow's steps on the table.

        The steps are:

        - 01: Autoencoder Train Model, once per combination of batch size, learning
          rate and weight decay (`map_configs`); each call is a part of the step,
          named by its combination (`output_prefix`, e.g. `32-0.001-0.0`), which
          names its results folder below the step's.
        - 02: Collect Files: the model files of all trainings in one table, a row
          per file with the combination it came from.

        Args:
            data: The table.
            config: The training settings, with the lists of batch sizes, learning
                rates and weight decays.
        """
        # the steps name their own results: the workflow's prefix is not passed on
        training = AETrainConfig.model_validate(
            config.model_dump(exclude={"classname", "prefix"})
        )
        tool = AETraining()
        files = {}
        for part in tool.map_configs(training):
            combination = AETraining.output_prefix(part)
            files[combination] = tool(data, config=part, task_tags=[combination], step="01")[
                "Model File"
            ]
        CollectFiles()(files, config=CollectFilesConfig(), step="02")
