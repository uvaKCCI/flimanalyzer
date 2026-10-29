import pathlib
import sys

import matplotlib.figure
import numpy as np
import pandas as pd

from flim.core.types import (
    DataType,
    FileType,
    ImageType,
    InputSpec,
    OutputSpec,
    PlotType,
    TableType,
)


def test_accepts():
    assert TableType.accepts(pd.DataFrame())
    assert TableType.accepts(pd.Series(dtype=float))
    assert not TableType.accepts(np.zeros(3))
    assert ImageType.accepts(np.zeros((2, 2)))
    assert PlotType.accepts(matplotlib.figure.Figure())
    assert FileType.accepts(pathlib.Path("a.csv"))
    assert not FileType.accepts("a.csv")


def test_of():
    assert DataType.of(pd.DataFrame()) is TableType
    assert DataType.of(np.zeros(1)) is ImageType
    assert DataType.of(42) is None


def test_of_prefers_most_specific_type():
    class LabelImageType(ImageType):
        pretty_name = "Labels"

    try:
        assert DataType.of(np.zeros(1)) is LabelImageType
    finally:
        # forget the test type so it does not leak into other tests
        del LabelImageType
        import gc

        gc.collect()


def test_unloaded_modules_are_not_imported(monkeypatch):
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    monkeypatch.setattr(ImageType, "pytypes", ("torch.Tensor", "numpy.ndarray"))
    assert ImageType.python_classes() == (np.ndarray,)
    assert "torch" not in sys.modules


def test_missing_class_is_skipped(monkeypatch):
    monkeypatch.setattr(
        TableType, "pytypes", ("pandas.NoSuchClass", "pandas.DataFrame")
    )
    assert TableType.python_classes() == (pd.DataFrame,)


def test_display_names():
    assert TableType.display_name("Summary") == "Table: Summary"
    assert OutputSpec("Summary", TableType).display_name == "Table: Summary"
    assert OutputSpec("PCA", PlotType).display_name == "Plot: PCA"
    spec = InputSpec("data", TableType)
    assert not spec.optional and spec.description == ""
