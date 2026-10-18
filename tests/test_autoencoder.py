import joblib
import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("wx")  # the plugins import their configuration dialogs

from flim.analysis.ml import device as dev  # noqa: E402

FEATURES = ["FAD a1", "FAD a2", "FAD t1", "FAD t2"]


def test_resolve_device_auto_picks_an_available_device():
    d = dev.resolve_device("auto")
    assert dev.is_available(d.type)
    expected = next((n for n in ("cuda", "mps") if dev.is_available(n)), "cpu")
    assert d.type == expected


def test_resolve_device_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(dev, "is_available", lambda name: name == "cpu")
    assert dev.resolve_device("cuda").type == "cpu"
    assert dev.resolve_device("mps").type == "cpu"
    assert dev.resolve_device("auto").type == "cpu"
    assert dev.resolve_device("tpu").type == "cpu"
    assert dev.resolve_device(None).type == "cpu"


def test_device_choices_offered_in_dialogs():
    assert dev.DEVICES == ["auto", "cpu", "cuda", "mps"]
    assert dev.DEFAULT_DEVICE == "auto"


@pytest.fixture
def flim_table():
    rng = np.random.default_rng(0)
    n = 120
    return pd.DataFrame(
        {
            "FOV": pd.Categorical(rng.integers(1, 4, n).astype(str)),
            "Cell": pd.Categorical(np.arange(n).astype(str)),
            "Treatment": pd.Categorical(rng.choice(["ctrl", "drug"], n)),
            **{f: rng.random(n).astype(np.float32) for f in FEATURES},
        }
    )


@pytest.mark.parametrize("device", ["auto", "cpu"])
def test_train_run_augment(flim_table, tmp_path, device):
    from flim.analysis.aeaugment import AEAugment
    from flim.analysis.aerun import RunAE
    from flim.analysis.aetraining import AETraining

    common = dict(features=FEATURES, grouping=["FOV", "Cell"], device=device)
    training = AETraining()
    training.configure(
        input={"data": flim_table},
        timeseries="Treatment",
        working_dir=str(tmp_path),
        modelfile="AEModel",
        epoches=2,
        checkpoint_interval=2,
        batch_size=[32],
        create_plots=False,
        **common,
    )
    training.execute()
    (modelfile,) = tmp_path.glob("*.model")

    # saved on the CPU, so the model loads on machines without that GPU
    model = joblib.load(modelfile)[-1]
    assert {p.device.type for p in model.parameters()} == {"cpu"}

    run = RunAE()
    run.configure(input={"data": flim_table}, modelfile=str(modelfile), **common)
    tables = run.execute()
    recon = next(v for k, v in tables.items() if k.startswith("Table: Reconstructed"))
    assert recon.shape == (len(flim_table), 3 + len(FEATURES))

    augment = AEAugment()
    augment.configure(
        input={"data": flim_table}, modelfile=[str(modelfile)], sets=2, **common
    )
    simulated = next(iter(augment.execute().values()))
    assert len(simulated) == 2 * len(flim_table)
    assert np.isfinite(simulated[FEATURES].to_numpy(dtype=float)).all()
