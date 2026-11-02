"""Autoencoder tools: train models, run them on data, augment data with them.

torch is imported when a tool runs, so the tools register (and their schemas and
validation work) without it.
"""

import itertools
import logging
import os
import random
import re
import tempfile
from collections import defaultdict

import numpy as np
import pandas as pd

from flim.configs.analysis import AEAugmentConfig, AERunConfig, AETrainConfig
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.schema import ColumnInfo, TableSchema
from flim.core.tool import Tool, pyplot_lock
from flim.core.types import FileType, OutputSpec, PlotType, TableType
from flim.tools.common import category_columns, selected_features

# size of the encoder output of each architecture (flim.analysis.ml.autoencoder)
ENCODED_SIZE = {
    "AE Simulator 1-6": 6,
    "AE Simulator 1-3": 3,
    "AE Dimensionality Reduction 2-10": 1,
    "AE Dimensionality Reduction 2-5": 1,
}


def combinations(config: AETrainConfig) -> list[tuple]:
    """(batch size, learning rate, weight decay) of each model to train."""
    return list(
        itertools.product(
            config.batch_sizes, config.learning_rates, config.weight_decays
        )
    )


def _schema_columns(categories, names, role="feature"):
    category_columns_ = [
        ColumnInfo(name=c.name, role="category", dtype="category", levels=c.levels)
        for c in categories
    ]
    return category_columns_ + [
        ColumnInfo(name=n, role=role, dtype="float32") for n in names
    ]


class _Rows:
    """Rows of features with their labels, for torch's DataLoader."""

    def __init__(self, data, labels):
        self.data = np.asarray(data)
        self.labels = np.asarray(labels)

    def __getitem__(self, index):
        return self.data[index], self.labels[index]

    def __len__(self):
        return len(self.data)


def _torch_device(name: str):
    import torch

    return torch.device(name)


@register_tool
class AETraining(Tool[AETrainConfig]):
    name = "Autoencoder: Train"
    category = "Analysis"
    description = (
        "Trains and saves autoencoder models of the selected features, one per"
        " combination of batch size, learning rate and weight decay. Training and"
        " validation sets are split randomly by the grouping columns (except the"
        " timeseries column)."
    )
    icon = "aetrain.png"

    def run(self, data, *, config):
        output_dir = self.context.output_dir
        if not output_dir:
            output_dir = tempfile.mkdtemp(prefix="flim-autoencoder-")
            logging.warning(
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

    def map_configs(self, config):
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

    def _datasets(self, data, config, batch_size):
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
            train_df = data.sample(
                n=int(np.around(config.train_size * len(data))), random_state=seed
            )
            val_df = pd.concat([data, train_df, train_df]).drop_duplicates(keep=False)

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

    def _new_model(self, config):
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

    def train(self, data, config, batch_size, learning_rate, weight_decay, output_dir):
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from joblib import dump
        from sklearn.pipeline import make_pipeline

        import flim.analysis.ml.autoencoder as autoencoder

        train_loader, val_loader, scaler, imputer, encoders = self._datasets(
            data, config, batch_size
        )
        label = f"{batch_size}-{learning_rate}-{weight_decay}"
        device = _torch_device(self.context.device)
        epochs = config.epochs
        logging.info(f"Training {config.architecture} {label} on {device}.")
        ae = self._new_model(config).to(device)
        criterion = nn.MSELoss()
        optimizer = optim.RMSprop(ae.parameters(), learning_rate, weight_decay)

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
            logging.debug(
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
        if config.rescale:
            decoded = np.concatenate(
                [
                    scaler.inverse_transform(decoded[:train_samples]),
                    scaler.inverse_transform(decoded[train_samples:]),
                ]
            )
        label_columns = category_columns(data) + ["Autoencoder"]
        label_df = pd.DataFrame(np.concatenate(labels), columns=label_columns)
        encoders["Autoencoder"].fit(["training", "validation"])
        label_df = label_df.apply(lambda x: encoders[x.name].inverse_transform(x))
        label_df = label_df.astype("category")
        decoded_df = pd.concat(
            [
                label_df,
                pd.DataFrame(
                    decoded,
                    columns=[f"AE Recon {f}" for f in config.features],
                    dtype=np.float32,
                ),
            ],
            axis=1,
        )
        encoded_df = pd.concat(
            [
                label_df,
                pd.DataFrame(
                    encoded,
                    columns=[f"AE Encoded {i}" for i in range(encoded.shape[1])],
                    dtype=np.float32,
                ),
            ],
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
            pipeline = make_pipeline(imputer, scaler, model)
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
        logging.info(f"Training {label} complete.")

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
    def loss_plot(loss_train, loss_val):
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MaxNLocator

        from flim.tools.plot import add_picker

        with pyplot_lock:  # training runs concurrently, plotting takes turns
            figure, ax = plt.subplots(constrained_layout=True)
            epochs = range(1, len(loss_train) + 1)
            ax.plot(epochs, loss_train, "b-", label="train-loss")
            ax.plot(epochs, loss_val, "r-", label="val-loss")
            ax.grid("on")
            ax.set_ylabel("loss")
            ax.set_xlabel("epoch")
            ax.legend(["training", "testing"], loc="upper right")
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            add_picker(figure)
        return figure

    @classmethod
    def output_schema(cls, config, inputs):
        schema = inputs[0] if inputs else None
        categories = (
            []
            if schema is None
            else [c for c in schema.columns if c.role == "category"]
        )
        autoencoder = ColumnInfo(
            name="Autoencoder",
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
            decoded = _schema_columns(
                categories, [f"AE Recon {f}" for f in config.features]
            )
            encoded = _schema_columns(
                categories,
                [f"AE Encoded {i}" for i in range(ENCODED_SIZE[config.architecture])],
            )
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
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if not config.features:
            issues.append(Issue("features", "Select the features to train on"))
        return issues


def _load_model(path, device):
    from joblib import load

    pipeline = load(path)
    pipeline[-1].to(device)  # the autoencoder; transform() returns CPU tensors
    return pipeline


class _ModelTool:
    """Runs once per model file; outputs are named after the files."""

    def map_configs(self, config):
        return [
            config.model_copy(update={"model_files": [f]}) for f in config.model_files
        ]

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if not config.model_files:
            issues.append(Issue("model_files", "Select at least one model file"))
        if not config.features:
            issues.append(
                Issue("features", "Select the features the models were trained on")
            )
        return issues


@register_tool
class RunAE(_ModelTool, Tool[AERunConfig]):
    name = "Autoencoder: Run"
    category = "Analysis"
    description = "Runs trained autoencoder models on the selected features."
    icon = "aerun.png"

    def run(self, data, *, config):
        results = {}
        for path in config.model_files:
            self.check_cancelled()
            results.update(self.run_model(data, config, str(path)))
        return results

    def run_model(self, data, config, path):
        import torch

        values = data[list(config.features)].astype(float)
        pipeline = _load_model(path, _torch_device(self.context.device))
        encoded, reconstructed = pipeline.transform(values.to_numpy(dtype=np.float32))
        encoded = torch.squeeze(encoded).detach().numpy()
        reconstructed = reconstructed.detach().numpy()
        loss = torch.nn.MSELoss()(
            torch.as_tensor(reconstructed),
            torch.as_tensor(values.to_numpy(dtype=np.float32)),
        )
        logging.debug(f"{os.path.basename(path)}: loss {loss.item():.4f}")
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
                        columns=[
                            f"Recon Feature {i}"
                            for i in range(1, reconstructed.shape[1] + 1)
                        ],
                    ),
                ],
                axis=1,
            ),
            f"Features-{name}": pd.concat(
                [
                    categories,
                    pd.DataFrame(
                        encoded,
                        columns=[
                            f"Feature {i}" for i in range(1, encoded.shape[1] + 1)
                        ],
                    ),
                ],
                axis=1,
            ),
        }

    @classmethod
    def output_schema(cls, config, inputs):
        schema = inputs[0] if inputs else None
        categories = (
            []
            if schema is None
            else [c for c in schema.columns if c.role == "category"]
        )
        reconstructed = [
            f"Recon Feature {i}" for i in range(1, len(config.features) + 1)
        ]
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
    name = "Autoencoder: Augment Data"
    category = "Analysis"
    description = (
        "Creates simulated copies of the data with trained autoencoder models,"
        " optionally adding white noise of the given signal-to-noise ratio first."
        " The last grouping column (e.g. Cell) is renumbered for each copy."
    )
    icon = "aeaugment.png"

    def run(self, data, *, config):
        results = {}
        for path in config.model_files:
            self.check_cancelled()
            results.update(self.simulate(data, config, str(path)))
        return results

    @staticmethod
    def noise_model(signal, snr_db):
        """Mean and standard deviation of white noise for ``snr_db`` (per column)."""
        signal_avg_db = 10 * np.log10(np.mean(signal**2))
        noise_avg_power = 10 ** ((signal_avg_db - snr_db) / 10)
        std_noise = np.sqrt(noise_avg_power)
        return np.zeros(std_noise.shape), std_noise

    def simulate(self, data, config, path):
        if not config.grouping:
            raise ValueError(
                f"{self.name}: select the grouping columns (the last is renumbered)"
            )
        categories = category_columns(data)
        features = list(config.features)
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
        for copy_number in range(config.sets):
            self.check_cancelled()
            noisy = values
            if config.add_noise:
                noisy = values + np.random.normal(
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

        # features sorted, so feature vectors are applied consistently
        outputs = sorted(c for c in simulated.columns if c not in categories)
        simulated = simulated[categories + outputs]
        simulated[cell] = simulated[cell].astype(str).astype("category")
        return {f"Simulated-{os.path.basename(path)}": simulated}

    @classmethod
    def output_schema(cls, config, inputs):
        return {
            f"Simulated-{os.path.basename(str(p))}": OutputSpec(
                f"Simulated-{os.path.basename(str(p))}",
                TableType,
                schema=TableSchema.unknown(),
            )
            for p in config.model_files
        }

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if not config.grouping:
            issues.append(
                Issue(
                    "grouping", "Select the grouping columns (the last is renumbered)"
                )
            )
        return issues
