import pytest

torch = pytest.importorskip("torch")

from flim.analysis.ml import device as dev  # noqa: E402


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
