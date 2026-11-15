"""Autoencoder tools: train models, run them on data, augment data with them.

torch is imported when a tool runs, so the tools register (and their schemas and
validation work) without it.
"""

import itertools
import logging
import os
from pathlib import Path
import random
import re
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Union

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from flim.configs.analysis import AEAugmentConfig, AERunConfig, AETrainConfig
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.schema import ColumnInfo, TableSchema
from flim.core.tool import Tool, pyplot_lock
from flim.core.columns import free_names
from flim.core.types import FileType, OutputSpec, PlotType, TableType
from flim.tools.common import category_columns, selected_features

if TYPE_CHECKING:  # torch, scikit-learn and matplotlib are imported when a tool runs
    import torch
    from matplotlib.figure import Figure
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import LabelEncoder, MinMaxScaler

logger = logging.getLogger(__name__)

# size of the encoder output of each architecture (flim.analysis.ml.autoencoder)
ENCODED_SIZE = {
    "AE Simulator 1-6": 6,
    "AE Simulator 1-3": 3,
    "AE Dimensionality Reduction 2-10": 1,
    "AE Dimensionality Reduction 2-5": 1,
}


def combinations(config: AETrainConfig) -> list[tuple]:
    """Return the (batch size, learning rate, weight decay) of each model to train.

    Args:
        config: The config; every combination of its `batch_sizes`,
            `learning_rates` and `weight_decays` is a model.

    Returns:
        The combinations, in the order of the config's lists.
    """
    return list(
        itertools.product(
            config.batch_sizes, config.learning_rates, config.weight_decays
        )
    )


def _train_names(
    categories: Sequence[str], features: Sequence[str], encoded_size: int
) -> tuple[str, list[str], list[str]]:
    """Return the names of AE Train's label, reconstructed and encoded columns.

    A name that a category column has already is numbered (see `free_names`).
    """
    (label,) = free_names(["Autoencoder"], categories)
    taken = list(categories) + [label]
    recon = free_names([f"AE Recon {f}" for f in features], taken)
    encoded = free_names([f"AE Encoded {i}" for i in range(encoded_size)], taken)
    return label, recon, encoded


def _schema_columns(
    categories: Sequence[ColumnInfo], names: Sequence[str], role: str = "feature"
) -> list[ColumnInfo]:
    """Return the category columns, then a float32 column per name, for a schema."""
    category_columns_ = [
        ColumnInfo(name=c.name, role="category", dtype="category", levels=c.levels)
        for c in categories
    ]
    return category_columns_ + [
        ColumnInfo(name=n, role=role, dtype="float32") for n in names
    ]


class _Rows:
    """Rows of features with their labels, for torch's DataLoader."""

    def __init__(self, data: ArrayLike, labels: ArrayLike) -> None:
        self.data = np.asarray(data)
        self.labels = np.asarray(labels)

    def __getitem__(self, index: int) -> tuple[np.ndarray, np.ndarray]:
        return self.data[index], self.labels[index]

    def __len__(self) -> int:
        return len(self.data)


def _torch_device(name: str) -> "torch.device":
    """Return the torch device of a name, e.g. `cpu` or `cuda`; imports torch."""
    import torch

    return torch.device(name)


def _skip_gpu_check_on_cpu(
    optimizer: "torch.optim.Optimizer", device: "torch.device"
) -> "torch.optim.Optimizer":
    """Replace the optimizer's CUDA-graph health check by a no-op on the CPU (#143).

    PyTorch's `optimizer.step()` asks whether a GPU is available for this check,
    whatever device the model is on (PyTorch 2.11: `torch.cuda.is_available()`,
    2.14: `torch.accelerator.current_accelerator(check_available=True)`). On a CUDA
    build that initialises CUDA and can warn although the CPU was selected. On the
    CPU there is no graph to check. The attribute is private PyTorch API: if it is
    renamed, nothing is replaced and `test_cpu_never_touches_cuda` fails.

    Args:
        optimizer: The optimizer, changed in place.
        device: The device of the model.

    Returns:
        `optimizer`.
    """
    if device.type == "cpu" and hasattr(optimizer, "_accelerator_graph_capture_health_check"):
        optimizer._accelerator_graph_capture_health_check = lambda: None
    return optimizer


@register_tool
class AETraining(Tool[AETrainConfig]):
    """Trains autoencoder models of the features and saves them to files."""

    name = "Autoencoder Train Model"
    category = None  # a step of the Autoencoder Train workflow, not in the menus
    # a concurrency limit set on the workflow's names limits the trainings
    extra_tags = ("Autoencoder Train", "Autoencoder: Train")
    description = (
        "Trains and saves autoencoder models of the selected features, one per"
        " combination of batch size, learning rate and weight decay. Training and"
        " validation sets are split randomly by the grouping columns (except the"
        " timeseries column)."
    )
    icon = "aetrain.png"

    def run(self, data: pd.DataFrame, *, config: AETrainConfig) -> dict[str, Any]:
        """Train and save a model for each combination of the training settings.

        The models are saved in the run's results folder, or without one in a new
        temporary folder (with a warning in the log). See `train`.

        Args:
            data: The table.
            config: The features; the grouping columns and the time series column;
                the lists `batch_sizes`, `learning_rates` and `weight_decays`, whose
                combinations are the models; and the training settings (see
                `train`).

        Returns:
            The results of `train` for each model; `Model File` lists the files of
            all models.
        """
        output_dir = self.context.output_dir
        if not output_dir:
            output_dir = Path(tempfile.mkdtemp(prefix="flim-autoencoder-"))
            logger.warning(
                f"{self.name}: no results folder set, saving models in {output_dir}"
            )
        os.makedirs(output_dir, exist_ok=True)
        results = {}
        for batch_size, rate, decay in combinations(config):
            for key, value in self.train(
                data, config, batch_size, rate, decay, output_dir
            ).items():
                if key == "Model File" and key in results:
                    value = results[key] + value
                results[key] = value
        return results

    def map_configs(self, config: AETrainConfig) -> list[AETrainConfig]:
        """Return one config per model, so that the models train as separate tasks."""
        return [
            config.model_copy(
                update={
                    "batch_sizes": [b],
                    "learning_rates": [lr],
                    "weight_decays": [wd],
                }
            )
            for b, lr, wd in combinations(config)
        ]

    @classmethod
    def mappable_output(cls, config: AETrainConfig) -> bool:
        """Return True: one part per combination of settings (one model each)."""
        return True

    @classmethod
    def output_prefix(cls, config: AETrainConfig) -> str:
        """Return a part's combination, `<batch size>-<learning rate>-<weight decay>`.

        As in its results' names (e.g. `AE Loss-32-0.001-0`); empty for a config
        with several combinations.
        """
        found = combinations(config)
        return "-".join(str(v) for v in found[0]) if len(found) == 1 else ""

    def _datasets(
        self, data: pd.DataFrame, config: AETrainConfig, batch_size: int
    ) -> tuple[
        "torch.utils.data.DataLoader",
        "torch.utils.data.DataLoader",
        "MinMaxScaler",
        "SimpleImputer",
        "defaultdict[str, LabelEncoder]",
    ]:
        """Return the training and validation loaders, the scaler, imputer and encoders.

        The groups of the grouping columns (except the time series column), or the
        rows without grouping columns, are split randomly into training and
        validation. The features are scaled to 0..1 and missing values set to 0, both
        fitted on the training rows. The category columns are encoded as integers, the
        loaders' labels.
        """
        import torch
        from sklearn import preprocessing
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import LabelEncoder

        seed = config.random_seed
        categories = category_columns(data)
        features = list(config.features)
        grouping = [g for g in config.grouping if g != config.timeseries]

        # encode the labels of all category columns
        encoders = defaultdict(LabelEncoder)
        data = data.loc[:, categories + features]
        data[categories] = data[categories].apply(
            lambda x: encoders[x.name].fit_transform(x)
        )

        if grouping:
            # split the logical groups (e.g. cells) into training and validation
            groups = data.groupby(grouping)
            keys = sorted(groups.groups.keys())
            train_keys = random.Random(seed).sample(
                keys, k=int(np.around(config.train_size * len(keys)))
            )
            train_df = pd.concat(
                [groups.get_group(k) for k in groups.groups if k in train_keys]
            )
            val_df = pd.concat(
                [groups.get_group(k) for k in groups.groups if k not in train_keys]
            )
        else:
            data = data.reset_index(drop=True)  # unique row labels for the split
            train_df = data.sample(
                n=int(np.around(config.train_size * len(data))), random_state=seed
            )
            val_df = data.drop(index=train_df.index)  # the other rows

        # scale and impute with the training data only, so no information leaks from
        # the validation data
        imputer = SimpleImputer(strategy="constant", fill_value=0)
        scaler = preprocessing.MinMaxScaler()
        train_set = train_df[features].to_numpy(dtype=np.float32)
        scaler = scaler.fit(train_set)
        train_set = scaler.transform(train_set)
        imputer = imputer.fit(train_set)
        train_set = imputer.transform(train_set)
        val_set = imputer.transform(
            scaler.transform(val_df[features].to_numpy(dtype=np.float32))
        )

        generator = torch.Generator()
        if seed is None:
            generator.seed()
        else:
            generator.manual_seed(seed)
        loaders = [
            torch.utils.data.DataLoader(
                dataset=_Rows(values, df[categories]),
                batch_size=batch_size,
                shuffle=True,
                generator=generator,
            )
            for values, df in ((train_set, train_df), (val_set, val_df))
        ]
        return loaders[0], loaders[1], scaler, imputer, encoders

    def _new_model(self, config: AETrainConfig) -> "torch.nn.Module":
        """Return a new model of the config's architecture, seeded by `random_seed`."""
        import torch

        import flim.analysis.ml.autoencoder as autoencoder

        model_class = autoencoder.get_autoencoder_classes()[config.architecture]
        if config.random_seed is None:
            return autoencoder.create_instance(
                model_class, nb_param=len(config.features)
            )
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(config.random_seed)
            return autoencoder.create_instance(
                model_class, nb_param=len(config.features)
            )

    def train(
        self,
        data: pd.DataFrame,
        config: AETrainConfig,
        batch_size: int,
        learning_rate: float,
        weight_decay: float,
        output_dir: str | os.PathLike,
    ) -> dict[str, Any]:
        """Train one model and save its checkpoints.

        The model trains with RMSprop on the mean squared error of the reconstructed
        features, for `epochs` epochs. A checkpoint is saved every
        `checkpoint_interval` epochs and after the last epoch, as a scikit-learn
        pipeline of the scaler, the imputer and the model, in
        `<model_name>_<batch size>_<learning rate>_<weight decay>_epoch<n>.model`.

        Args:
            data: The table.
            config: The features, the grouping and time series columns, `epochs`,
                `architecture`, `train_size`, `checkpoint_interval`, `model_name`,
                `rescale_output`, `create_plots` and `random_seed`.
            batch_size: The number of rows per batch.
            learning_rate: The optimizer's learning rate.
            weight_decay: The optimizer's weight decay.
            output_dir: The folder of the model files.

        Returns:
            With the label `<batch size>-<learning rate>-<weight decay>`:
            `AE Loss-<label>`: the training and validation loss per epoch, and the
            model file of each checkpoint (`---` for other epochs).
            `AE Decoded-<label>`, `AE Encoded-<label>`: the last epoch's
            reconstructed features (rescaled to the input's range if
            `rescale_output`) and encoder outputs, with the category columns and a
            column `Autoencoder` (`training` or `validation`; numbered if a category
            column has the name). With `create_plots`,
            `AE Loss-<label> Plot`. Each checkpoint's pipeline, by file name.
            `Model File`: the paths of the files.
        """
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from joblib import dump
        from sklearn.pipeline import make_pipeline

        train_loader, val_loader, scaler, imputer, encoders = self._datasets(
            data, config, batch_size
        )
        label = f"{batch_size}-{learning_rate}-{weight_decay}"
        device = _torch_device(self.context.device)
        epochs = config.epochs
        logger.info(f"Training {config.architecture} {label} on {device}.")
        ae = self._new_model(config).to(device)
        criterion = nn.MSELoss()
        # with the CPU selected, PyTorch's optimizer must not query CUDA (#143: a CUDA
        # warning although the CPU was selected); guarded by test_cpu_never_touches_cuda.
        # lr and weight_decay named: by position the third argument is RMSprop's alpha
        optimizer = _skip_gpu_check_on_cpu(
            optim.RMSprop(ae.parameters(), lr=learning_rate, weight_decay=weight_decay),
            device,
        )

        loss_train, loss_val = [], []
        labels, decoded, encoded = [], [], []
        checkpoints = []
        train_samples = 0
        for epoch in range(1, epochs + 1):
            self.check_cancelled()
            for split, loader in ((0, train_loader), (1, val_loader)):  # 0: training
                cumulative = 0
                for i, (inputs, batch_labels) in enumerate(loader):
                    inputs = inputs.to(device)
                    if split == 0:
                        encoder_out, decoder_out = ae(inputs)
                    else:
                        with torch.no_grad():
                            encoder_out, decoder_out = ae(inputs)
                    if epoch == epochs:
                        # keep the last epoch's outputs, labelled training/validation
                        n = len(batch_labels)
                        labels.append(
                            np.concatenate(
                                [batch_labels, np.full((n, 1), split)], axis=1
                            )
                        )
                        decoded.append(decoder_out.detach().cpu().numpy())
                        encoded.append(encoder_out.detach().cpu().numpy())
                        if split == 0:
                            train_samples += len(inputs)
                    loss = criterion(decoder_out, inputs)
                    cumulative += loss.data.item()
                    if split == 0:
                        optimizer.zero_grad()
                        loss.backward()
                        optimizer.step()
                (loss_train if split == 0 else loss_val).append(cumulative / (i + 1))
            logger.debug(
                f"Epoch {epoch}: training loss {loss_train[-1]:.4f},"
                f" validation loss {loss_val[-1]:.4f}"
            )
            if epoch == epochs or epoch % config.checkpoint_interval == 0:
                # checkpoints stay on the CPU, so saved models load on any machine
                clone = self._new_model(config)
                clone.load_state_dict(ae.state_dict())
                checkpoints.append((epoch, clone))

        encoded = np.concatenate(encoded)
        decoded = np.concatenate(decoded)
        if config.rescale_output:
            decoded = np.concatenate(
                [
                    scaler.inverse_transform(decoded[:train_samples]),
                    scaler.inverse_transform(decoded[train_samples:]),
                ]
            )
        categories = category_columns(data)
        label_column, recon_names, encoded_names = _train_names(
            categories, config.features, encoded.shape[1]
        )
        label_df = pd.DataFrame(
            np.concatenate(labels), columns=categories + [label_column]
        )
        encoders[label_column].fit(["training", "validation"])
        label_df = label_df.apply(lambda x: encoders[x.name].inverse_transform(x))
        label_df = label_df.astype("category")
        decoded_df = pd.concat(
            [label_df, pd.DataFrame(decoded, columns=recon_names, dtype=np.float32)],
            axis=1,
        )
        encoded_df = pd.concat(
            [label_df, pd.DataFrame(encoded, columns=encoded_names, dtype=np.float32)],
            axis=1,
        )

        results = {}
        model_files = {}
        base = os.path.join(
            output_dir,
            f"{config.model_name}_{batch_size}_{learning_rate}_{weight_decay}",
        )
        for epoch, model in checkpoints:
            path = f"{base}_epoch{epoch:04d}.model"
            # as in training: scale (missing values pass through), then set missing
            # values to 0
            pipeline = make_pipeline(scaler, imputer, model)
            dump(pipeline, filename=path)
            results[os.path.basename(path)] = pipeline
            model_files[epoch] = path

        epoch_labels = [str(e) for e in range(1, epochs + 1)]
        loss_df = pd.DataFrame(
            {
                "Epoch": epoch_labels,
                "Batch Size": [str(batch_size)] * epochs,
                "Learning Rate": [str(learning_rate)] * epochs,
                "Weight Decay": [str(weight_decay)] * epochs,
                "Training Loss": loss_train,
                "Validation Loss": loss_val,
                "Model File": [model_files.get(e, "---") for e in range(1, epochs + 1)],
            }
        )
        for column in ("Epoch", "Batch Size", "Learning Rate", "Weight Decay"):
            loss_df[column] = loss_df[column].astype("category")
        logger.info(f"Training {label} complete.")

        results.update(
            {
                f"AE Loss-{label}": loss_df,
                f"AE Decoded-{label}": decoded_df,
                f"AE Encoded-{label}": encoded_df,
                "Model File": list(model_files.values()),
            }
        )
        if config.create_plots:
            results[f"AE Loss-{label} Plot"] = self.loss_plot(loss_train, loss_val)
        return results

    @staticmethod
    def loss_plot(loss_train: Sequence[float], loss_val: Sequence[float]) -> "Figure":
        """Return a plot of the training and validation loss per epoch.

        Args:
            loss_train: The training loss of each epoch.
            loss_val: The validation loss of each epoch.

        Returns:
            The figure.
        """
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MaxNLocator

        from flim.tools.plot import add_picker

        with pyplot_lock:  # trainings can run concurrently; plotting is serialized
            figure, ax = plt.subplots(constrained_layout=True)
            epochs = range(1, len(loss_train) + 1)
            ax.plot(epochs, loss_train, "b-", label="train-loss")
            ax.plot(epochs, loss_val, "r-", label="val-loss")
            ax.grid("on")
            ax.set_ylabel("loss")
            ax.set_xlabel("epoch")
            ax.legend(["training", "validation"], loc="upper right")
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            add_picker(figure)
        return figure

    @classmethod
    def output_schema(
        cls, config: AETrainConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs of each model without training: see `train`.

        The model files' pipelines are not included. The decoded and encoded tables'
        schemas are complete only if the input schema is.
        """
        schema = inputs[0] if inputs else None
        categories = (
            []
            if schema is None
            else [c for c in schema.columns if c.role == "category"]
        )
        label_column, recon_names, encoded_names = _train_names(
            [c.name for c in categories],
            config.features,
            ENCODED_SIZE[config.architecture],
        )
        autoencoder = ColumnInfo(
            name=label_column,
            role="category",
            dtype="category",
            levels=["training", "validation"],
        )
        complete = schema is not None and schema.complete
        loss_columns = [
            ColumnInfo(name=n, role="category", dtype="category")
            for n in ("Epoch", "Batch Size", "Learning Rate", "Weight Decay")
        ] + [
            ColumnInfo(name="Training Loss", role="feature", dtype="float64"),
            ColumnInfo(name="Validation Loss", role="feature", dtype="float64"),
            ColumnInfo(name="Model File", role="other", dtype="object"),
        ]
        outputs = {}
        for b, lr, wd in combinations(config):
            label = f"{b}-{lr}-{wd}"
            decoded = _schema_columns(categories, recon_names)
            encoded = _schema_columns(categories, encoded_names)
            for name, columns in (
                (f"AE Loss-{label}", loss_columns),
                (
                    f"AE Decoded-{label}",
                    decoded[: len(categories)]
                    + [autoencoder]
                    + decoded[len(categories) :],
                ),
                (
                    f"AE Encoded-{label}",
                    encoded[: len(categories)]
                    + [autoencoder]
                    + encoded[len(categories) :],
                ),
            ):
                complete_table = complete or name.startswith("AE Loss")
                outputs[name] = OutputSpec(
                    name,
                    TableType,
                    schema=TableSchema(columns=columns, complete=complete_table),
                )
            if config.create_plots:
                outputs[f"AE Loss-{label} Plot"] = OutputSpec(
                    f"AE Loss-{label} Plot", PlotType
                )
        outputs["Model File"] = OutputSpec("Model File", FileType)
        return outputs

    @classmethod
    def validate(cls, config: AETrainConfig, inputs: Sequence[Any]) -> list[Issue]:
        """Check the config; the number of features is checked by `Tool.validate`."""
        # too few features: min_features, checked by Tool.validate
        return super().validate(config, inputs)


def _load_model(path: str | os.PathLike, device: "torch.device") -> "Pipeline":
    """Load a model file's pipeline, with the autoencoder on `device`."""
    from joblib import load

    pipeline = load(path)
    pipeline[-1].to(device)  # the autoencoder; transform() returns CPU tensors
    return pipeline


class _ModelTool:
    """Runs once per model file; outputs are named after the files."""

    def map_configs(
        self, config: Union[AERunConfig, AEAugmentConfig]
    ) -> list[Union[AERunConfig, AEAugmentConfig]]:
        """Return one config per model file, so that the files run as separate tasks."""
        return [
            config.model_copy(update={"model_files": [f]}) for f in config.model_files
        ]

    @classmethod
    def mappable_output(cls, config: Union[AERunConfig, AEAugmentConfig]) -> bool:
        """Return True: one part per model file."""
        return True

    @classmethod
    def output_prefix(cls, config: Union[AERunConfig, AEAugmentConfig]) -> str:
        """Return a part's model file name without its extension; else empty."""
        files = config.model_files
        return Path(files[0]).stem if len(files) == 1 else ""

    @classmethod
    def validate(
        cls, config: Union[AERunConfig, AEAugmentConfig], inputs: Sequence[Any]
    ) -> list[Issue]:
        """Check the config; no model file is an error."""
        issues = super().validate(config, inputs)
        if not config.model_files:
            issues.append(Issue("model_files", "Select at least one model file"))
        # too few features: min_features, checked by Tool.validate
        return issues


@register_tool
class RunAE(_ModelTool, Tool[AERunConfig]):
    """Runs trained autoencoder models on the features."""

    name = "Autoencoder Run"
    former_names = ("Autoencoder: Run",)
    category = "Analysis"
    description = "Runs trained autoencoder models on the selected features."
    icon = "aerun.png"

    def run(self, data: pd.DataFrame, *, config: AERunConfig) -> dict[str, Any]:
        """Run each model file on the selected features.

        Args:
            data: The table.
            config: The features, in the order the models were trained with, and the
                model files (`model_files`).

        Returns:
            The results of `run_model` for each model file.
        """
        results = {}
        for path in config.model_files:
            self.check_cancelled()
            results.update(self.run_model(data, config, str(path)))
        return results

    def run_model(
        self, data: pd.DataFrame, config: AERunConfig, path: str
    ) -> dict[str, pd.DataFrame]:
        """Run one model file on the selected features.

        Missing values are set to 0 after scaling, as in training.

        Args:
            data: The table.
            config: The features.
            path: The model file.

        Returns:
            With the file name `<name>`: `Reconstructed-<name>`: the category columns
            and the reconstructed features, `Recon Feature 1`, `Recon Feature 2`, and
            so on, in the model's scaled units. `Features-<name>`: the category
            columns and the encoder outputs, `Feature 1`, `Feature 2`, and so on.
            Names that a category column has already are numbered.
        """
        import torch

        values = data[selected_features(data, config.features)].astype(float)
        pipeline = _load_model(path, _torch_device(self.context.device))
        encoded, reconstructed = pipeline.transform(values.to_numpy(dtype=np.float32))
        encoded = torch.squeeze(encoded).detach().numpy()
        reconstructed = reconstructed.detach().numpy()
        loss = torch.nn.MSELoss()(
            torch.as_tensor(reconstructed),
            torch.as_tensor(values.to_numpy(dtype=np.float32)),
        )
        logger.debug(f"{os.path.basename(path)}: loss {loss.item():.4f}")
        if encoded.ndim == 1:
            encoded = encoded.reshape(-1, 1)
        categories = data[category_columns(data)].reset_index(drop=True)
        name = os.path.basename(path)
        return {
            f"Reconstructed-{name}": pd.concat(
                [
                    categories,
                    pd.DataFrame(
                        reconstructed,
                        columns=free_names(
                            [f"Recon Feature {i}" for i in range(1, reconstructed.shape[1] + 1)],
                            categories.columns,
                        ),
                    ),
                ],
                axis=1,
            ),
            f"Features-{name}": pd.concat(
                [
                    categories,
                    pd.DataFrame(
                        encoded,
                        columns=free_names(
                            [f"Feature {i}" for i in range(1, encoded.shape[1] + 1)],
                            categories.columns,
                        ),
                    ),
                ],
                axis=1,
            ),
        }

    @classmethod
    def output_schema(
        cls, config: AERunConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs of each model file without running the models.

        The encoded table's schema lists only the category columns and is
        incomplete: the number of encoder outputs depends on the model.
        """
        schema = inputs[0] if inputs else None
        categories = (
            []
            if schema is None
            else [c for c in schema.columns if c.role == "category"]
        )
        reconstructed = free_names(
            [f"Recon Feature {i}" for i in range(1, len(config.features) + 1)],
            [c.name for c in categories],
        )
        outputs = {}
        for path in config.model_files:
            name = os.path.basename(str(path))
            complete = schema is not None and schema.complete
            outputs[f"Reconstructed-{name}"] = OutputSpec(
                f"Reconstructed-{name}",
                TableType,
                schema=TableSchema(
                    columns=_schema_columns(categories, reconstructed),
                    complete=complete,
                ),
            )
            # the number of encoded features depends on the model in the file
            outputs[f"Features-{name}"] = OutputSpec(
                f"Features-{name}",
                TableType,
                schema=TableSchema(
                    columns=_schema_columns(categories, []), complete=False
                ),
            )
        return outputs


@register_tool
class AEAugment(_ModelTool, Tool[AEAugmentConfig]):
    """Creates simulated copies of the data with trained autoencoder models."""

    name = "Autoencoder Augment Data"
    former_names = ("Autoencoder: Augment Data",)
    category = "Analysis"
    description = (
        "Creates simulated copies of the data with trained autoencoder models,"
        " optionally adding white noise of the given signal-to-noise ratio first."
        " The last grouping column (e.g. Cell) is renumbered for each copy."
    )
    icon = "aeaugment.png"

    def run(self, data: pd.DataFrame, *, config: AEAugmentConfig) -> dict[str, Any]:
        """Create simulated copies of the data with each model file.

        Args:
            data: The table.
            config: The features; the grouping columns, whose last is renumbered in
                each copy; the model files; the number of copies (`sets`);
                `add_noise` and its signal-to-noise ratio (`snr_db`); and
                `random_seed`.

        Returns:
            The results of `simulate` for each model file.

        Raises:
            ValueError: If no grouping column is selected.
        """
        results = {}
        for path in config.model_files:
            self.check_cancelled()
            results.update(self.simulate(data, config, str(path)))
        return results

    @staticmethod
    def noise_model(
        signal: pd.DataFrame, snr_db: float
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return the mean and standard deviation of white noise, per column.

        Each column's signal power is the mean of its squared values.

        Args:
            signal: The values, a column per feature.
            snr_db: The signal-to-noise ratio, in dB.

        Returns:
            The means (zeros) and the standard deviations, one per column.
        """
        signal_avg_db = 10 * np.log10((signal**2).mean().to_numpy())
        noise_avg_power = 10 ** ((signal_avg_db - snr_db) / 10)
        std_noise = np.sqrt(noise_avg_power)
        return np.zeros(std_noise.shape), std_noise

    def simulate(
        self, data: pd.DataFrame, config: AEAugmentConfig, path: str
    ) -> dict[str, pd.DataFrame]:
        """Create `sets` simulated copies of the data with one model file.

        Each copy is the model's reconstruction of the features, with white noise
        added first if `add_noise`, rescaled to the input's range. The last grouping
        column is renumbered: if its values are integers, copy n (counted from 0)
        adds n times (largest value + 1), otherwise `.<n>` is appended. Amplitude
        columns such as `FAD a1`, `FAD a2` get relative amplitude columns, e.g.
        `FAD a1%`, in percent of their sum; a column of the input whose name contains
        the amplitude's name and `%` but no `/` gives its name.

        Args:
            data: The table.
            config: The features, the grouping columns, `sets`, `add_noise`,
                `snr_db` and `random_seed`.
            path: The model file.

        Returns:
            `Simulated-<file name>`: the copies, one below the other: the category
            columns, then the other columns sorted by name.

        Raises:
            ValueError: If no grouping column is selected.
        """
        if not config.grouping:
            raise ValueError(
                f"{self.name}: select the grouping columns (the last is renumbered)"
            )
        categories = category_columns(data)
        features = selected_features(data, config.features)
        values = data[features]
        cell = config.grouping[-1]
        # amplitude columns ("FAD a1", "FAD a2", ...) per signal ("FAD", ...)
        signals = {re.findall(r"\S+", column)[0] for column in features}
        amplitudes = {
            s: [
                c
                for c in features
                if re.findall(rf"^{re.escape(s)}\sa\d$", c, re.IGNORECASE)
            ]
            for s in signals
        }
        try:
            max_cell = np.amax(data[cell].astype(int).to_numpy())
        except (TypeError, ValueError):
            max_cell = None  # not numbered: suffix the copies' cells instead

        mean_noise, std_noise = self.noise_model(values, config.snr_db)
        pipeline = _load_model(path, _torch_device(self.context.device))
        scaler = pipeline.named_steps["minmaxscaler"]
        copies = []
        rng = np.random.default_rng(config.random_seed)  # None: different every run
        for copy_number in range(config.sets):
            self.check_cancelled()
            noisy = values
            if config.add_noise:
                noisy = values + rng.normal(
                    mean_noise, scale=std_noise, size=values.shape
                )
            _, reconstructed = pipeline.transform(noisy.to_numpy(dtype=np.float32))
            simulated = pd.DataFrame(columns=categories + features)
            simulated[categories] = data[categories]
            if max_cell is not None:
                simulated[cell] = (
                    simulated[cell].astype(int) + (max_cell + 1) * copy_number
                )
            else:
                simulated[cell] = simulated[cell].astype(str) + f".{copy_number}"
            simulated[features] = scaler.inverse_transform(
                reconstructed.detach().numpy()
            )
            copies.append(simulated)
        simulated = pd.concat(copies).reset_index(drop=True)

        # relative amplitudes, e.g. a1%, a2%
        for signal, columns in amplitudes.items():
            total = simulated[columns].sum(axis=1)
            for amplitude in columns:
                percent = [
                    c
                    for c in data.columns
                    if amplitude in c and "%" in c and "/" not in c
                ]
                percent = percent[0] if percent else f"{amplitude}%"
                simulated[percent] = simulated[amplitude] / total * 100.0

        # category columns first, then the other columns sorted by name
        outputs = sorted(c for c in simulated.columns if c not in categories)
        simulated = simulated[categories + outputs]
        simulated[cell] = simulated[cell].astype(str).astype("category")
        return {f"Simulated-{os.path.basename(path)}": simulated}

    @classmethod
    def output_schema(
        cls, config: AEAugmentConfig, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return a table per model file; their schemas are unknown."""
        return {
            f"Simulated-{os.path.basename(str(p))}": OutputSpec(
                f"Simulated-{os.path.basename(str(p))}",
                TableType,
                schema=TableSchema.unknown(),
            )
            for p in config.model_files
        }

    @classmethod
    def validate(
        cls, config: AEAugmentConfig, inputs: Sequence[Any]
    ) -> list[Issue]:
        """Check the config; `Tool.validate` checks the number of grouping columns."""
        # too few grouping columns: min_grouping, checked by Tool.validate
        return super().validate(config, inputs)
