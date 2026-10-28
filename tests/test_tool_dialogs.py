"""The editors of tools that need more than the generated dialog (flim/gui/dialogs)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

import flim.gui.dialogs.autoencoder  # noqa: E402,F401  (register the editors)
import flim.gui.dialogs.categoryorder  # noqa: E402,F401
import flim.gui.dialogs.filter  # noqa: E402,F401
import flim.gui.dialogs.histogram  # noqa: E402,F401
import flim.tools  # noqa: E402,F401
from flim.configs import (  # noqa: E402
    AETrainConfig,
    CategoryOrderConfig,
    FilterConfig,
    HistogramConfig,
)
from flim.configs.data import RangeFilterSpec  # noqa: E402
from flim.configs.plot import HistogramRange  # noqa: E402
from flim.core.registry import tools  # noqa: E402


@pytest.fixture(scope="module")
def wxapp():
    try:
        app = wx.App()
    except SystemExit:
        pytest.skip("no display available")
    import flim.gui  # noqa: F401

    yield app
    for window in list(wx.GetTopLevelWindows()):
        if window and not window.IsBeingDeleted():
            window.Destroy()


@pytest.fixture
def table():
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "Treatment": pd.Categorical(["Drug", "Ctrl", "Placebo"] * 4),
            "FOV": pd.Categorical(["1", "2"] * 6),
            "t1": rng.uniform(100, 200, 12),
            "t2": rng.uniform(0, 1, 12),
        }
    )


@pytest.fixture
def dialog(wxapp, table):
    from flim.gui.configdialog import ConfigDialog

    dialogs = []

    def make(name, config=None):
        d = ConfigDialog(
            None, tools.get(name), config, data_choices={"Table: data": table}
        )
        dialogs.append(d)
        return d

    yield make
    for d in dialogs:
        d.Destroy()


# --- Order Categories ---


def test_category_order(dialog):
    d = dialog("Order Categories")
    editor = d.fields.editors["categories"]
    assert editor.column_names() == ["Treatment", "FOV"]
    assert editor.get() == {}  # nothing checked: no order set
    editor.columns.SetSelection(0)
    editor._show_values()
    editor.values.SetSelection(2)  # Placebo
    editor._move(-1)
    assert editor.get() == {"Treatment": ["Ctrl", "Placebo", "Drug"]}
    editor._on_sort(None)
    assert editor.get() == {"Treatment": ["Ctrl", "Drug", "Placebo"]}
    result = d.result().config
    assert result.categories == {"Treatment": ["Ctrl", "Drug", "Placebo"]}


def test_category_order_keeps_saved_orders(dialog):
    d = dialog(
        "Order Categories", CategoryOrderConfig(categories={"Treatment": ["Placebo"]})
    )
    editor = d.fields.editors["categories"]
    # the saved values first, then the others of the data
    assert editor.get() == {"Treatment": ["Placebo", "Ctrl", "Drug"]}
    editor._on_reset(None)
    assert editor.get() == {"Treatment": ["Ctrl", "Drug", "Placebo"]}


# --- Filter ---


def test_category_filters(dialog):
    d = dialog("Filter")
    editor = d.fields.editors["category_filters"]
    editor.columns.SetSelection(0)
    editor._show_values()
    editor.values.Check(2, False)  # drop Placebo
    editor._on_check(None)
    assert editor.get() == {"Treatment": ["Ctrl", "Drug"]}
    assert editor.columns.GetString(0) == "Treatment *"  # marked: filters
    editor.values.Check(2, True)
    editor._on_check(None)
    assert editor.get() == {}  # keeps all values: no filter
    editor.set({"FOV": ["1"]})
    assert d.result().config.category_filters == {"FOV": ["1"]}


def test_range_filters_add_features(dialog, table):
    config = FilterConfig(
        range_filters=[RangeFilterSpec(column="t1", low=120, high=180, selected=True)]
    )
    d = dialog("Filter", config)
    editor = d.fields.editors["range_filters"]
    editor._on_add_features()
    filters = d.result().config.range_filters
    assert [f.column for f in filters] == ["t1", "t2"]  # t1 kept as configured
    assert (filters[0].low, filters[0].selected) == (120, True)
    t2 = filters[1]
    assert (t2.low, t2.high, t2.selected) == (
        pytest.approx(table["t2"].min()),
        pytest.approx(table["t2"].max()),
        False,
    )


# --- Frequency Histogram ---


def test_histogram_ranges(dialog, table):
    d = dialog("Frequency Histogram", HistogramConfig(features=["t1"]))
    editor = d.fields.editors["per_feature"]
    assert editor.key_title == "Feature"
    editor._on_add_features()  # the selected features
    ranges = d.result().config.per_feature
    assert list(ranges) == ["t1"]
    assert (
        ranges["t1"].min == pytest.approx(table["t1"].min()) and ranges["t1"].bins == 30
    )
    editor.set({"t2": HistogramRange(min=0, max=1, bins=10)})
    assert d.result().config.per_feature == {
        "t2": HistogramRange(min=0, max=1, bins=10)
    }


def test_histogram_range_errors_are_marked(dialog):
    d = dialog("Frequency Histogram")
    editor = d.fields.editors["per_feature"]
    editor.add_row({"min": 5, "max": 1}, key="t1")
    d.validate()
    shown = d.fields.markers["per_feature"].IsShown()
    assert shown and not d.ok_button.IsEnabled()


# --- Autoencoder: Train ---


def test_architecture(dialog):
    d = dialog(
        "Autoencoder: Train", AETrainConfig(features=["t1", "t2"], grouping=["FOV"])
    )
    editor = d.fields.editors["architecture"]
    editor.set("AE Simulator 1-6")
    assert d.result().config.architecture == "AE Simulator 1-6"
    pytest.importorskip("torch")
    assert editor.description.GetLabel()  # the architecture's description
    assert "in_features=2" in editor.layers.GetValue()  # for the 2 selected features
