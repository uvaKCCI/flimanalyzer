"""Autoencoder tools. Schemas and validation work without torch; training needs it."""

import numpy as np
import pandas as pd
import pytest

from flim.configs import AEAugmentConfig, AERunConfig, AETrainConfig
from flim.core.registry import tools
from flim.core.schema import TableSchema
from flim.core.types import FileType, PlotType
from flim.tools.autoencoder import AEAugment, AETraining, RunAE, combinations

FEATURES = ["FAD a1", "FAD a2", "FAD t1", "FAD t2"]


@pytest.fixture
def needs_torch():
    pytest.importorskip("torch")


@pytest.fixture
def data():
    rng = np.random.default_rng(0)
    n = 120
    return pd.DataFrame(
        {
            "FOV": pd.Categorical(rng.integers(1, 4, n).astype(str)),
            "Cell": pd.Categorical(np.arange(n).astype(str)),
            "Treatment": pd.Categorical(rng.choice(["ctrl", "drug"], n)),
            **{f: rng.uniform(10, 100, n) for f in FEATURES},
        }
    )


def train_config(**changes):
    values = dict(
        features=FEATURES,
        grouping=["FOV", "Cell"],
        epochs=2,
        checkpoint_interval=1,
        batch_sizes=[32],
        create_plots=False,
        resources={"preferred_device": "cpu"},
    )
    return AETrainConfig(**{**values, **changes})


# --- without torch ---


def test_registered():
    for name in ("Autoencoder: Train", "Autoencoder: Run", "Autoencoder: Augment Data"):
        assert name in tools


def test_map_configs():
    config = AETrainConfig(batch_sizes=[32, 64], learning_rates=[1e-4, 1e-3])
    assert combinations(config) == [
        (32, 1e-4, 1e-8),
        (32, 1e-3, 1e-8),
        (64, 1e-4, 1e-8),
        (64, 1e-3, 1e-8),
    ]
    mapped = AETraining().map_configs(config)
    assert [(c.batch_sizes, c.learning_rates) for c in mapped] == [
        ([32], [1e-4]),
        ([32], [1e-3]),
        ([64], [1e-4]),
        ([64], [1e-3]),
    ]
    run = AERunConfig(model_files=["a.model", "b.model"])
    assert [c.model_files for c in RunAE().map_configs(run)] == [
        [p] for p in run.model_files
    ]


def test_training_output_schema(data):
    config = train_config(create_plots=True, architecture="AE Simulator 1-3")
    outputs = AETraining.output_schema(config, [TableSchema.from_frame(data)])
    assert set(outputs) == {
        "AE Loss-32-0.0001-1e-08",
        "AE Decoded-32-0.0001-1e-08",
        "AE Encoded-32-0.0001-1e-08",
        "AE Loss-32-0.0001-1e-08 Plot",
        "Model File",
    }
    assert outputs["Model File"].type is FileType
    assert outputs["AE Loss-32-0.0001-1e-08 Plot"].type is PlotType
    encoded = outputs["AE Encoded-32-0.0001-1e-08"].schema
    assert encoded.names == ["FOV", "Cell", "Treatment", "Autoencoder"] + [
        f"AE Encoded {i}" for i in range(3)
    ]
    decoded = outputs["AE Decoded-32-0.0001-1e-08"].schema
    assert decoded.names[-4:] == [f"AE Recon {f}" for f in FEATURES]


def test_run_and_augment_output_schema(data):
    schema = TableSchema.from_frame(data)
    run = RunAE.output_schema(
        AERunConfig(features=FEATURES, model_files=["/m/x.model"]), [schema]
    )
    assert run["Reconstructed-x.model"].schema.names[-1] == "Recon Feature 4"
    assert not run["Features-x.model"].schema.complete  # depends on the model
    augment = AEAugment.output_schema(
        AEAugmentConfig(model_files=["/m/x.model"]), [schema]
    )
    assert list(augment) == ["Simulated-x.model"]


def test_validate(data):
    schema = TableSchema.from_frame(data)
    assert [
        i.field for i in AETraining.validate(AETrainConfig(features=[]), [schema])
    ] == ["features"]
    issues = AEAugment.validate(AEAugmentConfig(), [schema])
    assert [i.field for i in issues] == ["model_files", "features", "grouping"]


def test_legacy_single_grid_values():
    # workflows map over the combinations and pass one value of each grid
    config = AETrainConfig.from_legacy_params(
        {"learning_rate": 1e-3, "weight_decay": 0.0, "batch_size": 16}
    )
    assert (config.learning_rates, config.weight_decays, config.batch_sizes) == (
        [1e-3],
        [0.0],
        [16],
    )


# --- with torch ---


@pytest.mark.parametrize("device", ["auto", "cpu"])
def test_train_run_augment(needs_torch, data, tmp_path, device):
    import joblib

    resources = {"preferred_device": device}
    training = AETraining()
    training._output_dir = str(tmp_path)
    results = training(
        data,
        config=train_config(
            timeseries="Treatment", model_name="M", resources=resources
        ),
    )
    files = results["Model File"]
    assert [p.split("/")[-1] for p in files] == [
        "M_32_0.0001_1e-08_epoch0001.model",
        "M_32_0.0001_1e-08_epoch0002.model",
    ]
    loss = results["Table: AE Loss-32-0.0001-1e-08"]
    assert loss["Model File"].tolist() == files
    decoded = results["Table: AE Decoded-32-0.0001-1e-08"]
    assert len(decoded) == len(data)
    assert set(decoded["Autoencoder"]) == {"training", "validation"}
    # saved on the CPU, so the models load on machines without that GPU
    model = joblib.load(files[-1])[-1]
    assert {p.device.type for p in model.parameters()} == {"cpu"}

    common = dict(features=FEATURES, resources=resources)
    run = RunAE()(data, config=AERunConfig(model_files=[files[-1]], **common))
    reconstructed = run["Table: Reconstructed-M_32_0.0001_1e-08_epoch0002.model"]
    assert reconstructed.shape == (len(data), 3 + len(FEATURES))
    features = run["Table: Features-M_32_0.0001_1e-08_epoch0002.model"]
    assert list(features.columns[-1:]) == ["Feature 1"]

    augment = AEAugment()(
        data,
        config=AEAugmentConfig(
            model_files=[files[-1]], sets=2, grouping=["FOV", "Cell"], **common
        ),
    )
    (simulated,) = augment.values()
    assert len(simulated) == 2 * len(data)
    assert "index" not in simulated.columns
    assert simulated["Cell"].nunique() == 2 * len(
        data
    )  # the copies' cells are renumbered
    assert np.isfinite(simulated[FEATURES].to_numpy(dtype=float)).all()

    # "All features": the table's feature columns (#177)
    common["features"] = "all"
    assert (
        RunAE()(data, config=AERunConfig(model_files=[files[-1]], **common)).keys()
        == run.keys()
    )
    config = AEAugmentConfig(
        model_files=[files[-1]], grouping=["FOV", "Cell"], **common
    )
    assert len(next(iter(AEAugment()(data, config=config).values()))) == len(data)


def test_training_with_a_seed_is_reproducible(needs_torch, data, tmp_path):
    def loss(folder):
        training = AETraining()
        training._output_dir = str(folder)
        results = training(data, config=train_config(random_seed=3))
        return results["Table: AE Loss-32-0.0001-1e-08"]["Training Loss"].tolist()

    assert loss(tmp_path / "a") == loss(tmp_path / "b")


def test_training_without_a_folder_uses_a_temporary_one(needs_torch, data, caplog):
    results = AETraining()(data, config=train_config())
    assert all(p.endswith(".model") for p in results["Model File"])
    assert "no results folder" in caplog.text


def test_cpu_never_touches_cuda(needs_torch, data, tmp_path, monkeypatch):
    # issue #143: a CUDA warning although the CPU was selected
    import torch

    def no_cuda(*args, **kwargs):
        raise AssertionError("CUDA queried although the CPU was selected")

    for name in ("is_available", "init", "_lazy_init", "device_count"):
        monkeypatch.setattr(torch.cuda, name, no_cuda)
    resources = {"preferred_device": "cpu"}
    training = AETraining()
    training._output_dir = str(tmp_path)
    files = training(data, config=train_config(resources=resources))["Model File"]
    common = dict(features=FEATURES, resources=resources, model_files=[files[-1]])
    RunAE()(data, config=AERunConfig(**common))
    AEAugment()(data, config=AEAugmentConfig(grouping=["FOV", "Cell"], **common))
