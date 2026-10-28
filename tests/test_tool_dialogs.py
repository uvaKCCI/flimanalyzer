"""The editors of tools that need more than the generated dialog (flim/gui/dialogs)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

import flim.gui.dialogs.autoencoder  # noqa: E402,F401  (register the editors)
import flim.gui.dialogs.categoryorder  # noqa: E402,F401
import flim.gui.dialogs.filter  # noqa: E402,F401
import flim.tools  # noqa: E402,F401
from flim.configs import (  # noqa: E402
    AETrainConfig,
    CategoryOrderConfig,
    FilterConfig,
    HistogramConfig,
)
from flim.configs.data import RangeSettings  # noqa: E402
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


def test_range_filters_table(dialog, table):
    config = FilterConfig(range_filters={"t1": RangeSettings(low=120, high=180)})
    d = dialog("Filter", config)
    editor = d.fields.editors["range_filters"]
    assert editor.features == ["t1", "t2"]  # a row for each numeric column
    assert [editor.is_used(r) for r in range(2)] == [True, False]
    editor.use(1)  # checking fills in the data's range
    filters = d.result().config.range_filters
    assert filters["t1"] == RangeSettings(low=120, high=180)  # kept as configured
    assert filters["t2"].low == pytest.approx(table["t2"].min(), rel=1e-5)
    assert filters["t2"].high == pytest.approx(table["t2"].max(), rel=1e-5)


# --- settings files ---


def test_save_and_load_feature_settings(dialog, tmp_path):
    import json

    path = tmp_path / "ranges.json"
    d = dialog("Filter", FilterConfig(range_filters={"t1": {"low": 120, "high": 180}}))
    d.fields.editors["range_filters"].save_settings(path)
    assert json.loads(path.read_text()) == {
        "t1": {"low": 120, "high": 180, "dropna": True}
    }

    other = dialog("Filter")
    editor = other.fields.editors["range_filters"]
    applied, skipped = editor.load_settings(path)
    assert (applied, skipped) == (["t1"], [])
    assert other.result().config.range_filters == {}  # applied, but not checked
    editor.use(0)
    assert other.result().config.range_filters["t1"] == RangeSettings(low=120, high=180)


def test_load_settings_from_an_old_settings_file(dialog, tmp_path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "root": {
                    "plugins": {
                        "Filter": {
                            "range_filters": [
                                {"name": "t2", "rangelow": 0.2, "rangehigh": 0.8},
                                {"name": "gone", "rangelow": 0, "rangehigh": 1},
                            ]
                        },
                        "Frequency Histogram": {
                            "featuresettings": {"t1": [100, 200, 20, ["Treatment"]]}
                        },
                    }
                }
            }
        )
    )
    histogram = dialog("Frequency Histogram", HistogramConfig(features=["t1"]))
    applied, _ = histogram.fields.editors["features"].load_settings(path)
    assert applied == ["t1"]
    assert histogram.result().config.features["t1"] == HistogramRange(
        min=100, max=200, bins=20
    )
    filters = dialog("Filter", FilterConfig(range_filters=["t2"]))
    editor = filters.fields.editors["range_filters"]
    assert editor.load_settings(path) == (["t2"], ["gone"])
    assert "1 are not in the table" in editor.message.GetLabel()
    assert filters.result().config.range_filters["t2"] == RangeSettings(
        low=0.2, high=0.8
    )


# --- Frequency Histogram: features with settings ---


def test_histogram_features_table(dialog, table):
    d = dialog("Frequency Histogram")
    editor = d.fields.editors["features"]
    assert editor.features == ["t1", "t2"]  # a row for each feature of the input
    assert editor.get() == {}
    assert d.fields.markers["features"].IsShown()  # none checked: an error
    editor.use(0)  # checking fills in the data's range
    d.validate()
    config = d.result().config
    assert list(config.features) == ["t1"]
    assert config.features["t1"].min == pytest.approx(table["t1"].min(), rel=1e-5)
    assert config.features["t1"].bins == 30  # the default bins
    editor.grid.SetCellValue(0, 4, "12")  # bins
    assert d.result().config.features["t1"].bins == 12


def test_histogram_features_keep_saved_settings(dialog):
    config = HistogramConfig(features={"t2": HistogramRange(min=0, max=1, bins=10)})
    d = dialog("Frequency Histogram", config)
    editor = d.fields.editors["features"]
    assert [editor.is_used(r) for r in range(2)] == [False, True]
    assert d.result().config.features == {"t2": HistogramRange(min=0, max=1, bins=10)}
    editor.use_all(True)
    assert list(d.result().config.features) == ["t1", "t2"]
    editor.use_all(False)
    d.validate()
    assert not d.ok_button.IsEnabled()


def test_histogram_same_bins_for_all(dialog, tmp_path):
    import json

    config = HistogramConfig(features={"t1": {"bins": 10}, "t2": {"bins": 20}})
    d = dialog("Frequency Histogram", config)
    editors = d.fields.editors
    table, bins = editors["features"], 4  # the bins column
    editors["sync_bins"].set(True)
    d.fields.refresh()  # switching it on: all rows get the first checked row's bins
    assert [table.grid.GetCellValue(r, bins) for r in range(2)] == ["10", "10"]
    table.grid.SetCellValue(1, bins, "25")
    event = wx.grid.GridEvent(
        table.grid.GetId(), wx.grid.wxEVT_GRID_CELL_CHANGED, table.grid, row=1, col=bins
    )
    table._on_cell_changed(event)  # editing one row changes all
    assert {r.bins for r in d.result().config.features.values()} == {25}

    # loading settings: each feature its own bins again
    path = tmp_path / "bins.json"
    path.write_text(json.dumps({"t1": {"bins": 7}, "t2": {"bins": 9}}))
    table.load_settings(path)
    assert not editors["sync_bins"].get()
    assert {f: r.bins for f, r in d.result().config.features.items()} == {
        "t1": 7,
        "t2": 9,
    }


def test_histogram_auto_range(dialog, tmp_path):
    import json

    config = HistogramConfig(features={"t1": {"min": 100, "max": 150}})
    d = dialog("Frequency Histogram", config)
    editors = d.fields.editors
    table, low, high = editors["features"], 2, 3  # the min and max columns
    editors["auto_range"].set(True)
    d.fields.refresh()
    assert table.disabled == {"min", "max"}
    assert table.grid.IsReadOnly(0, low) and table.grid.IsReadOnly(0, high)
    table.use(1)  # checking a feature does not fill in a range now
    assert table.grid.GetCellValue(1, low) == ""
    config = d.result().config
    assert config.auto_range and config.features["t1"].min == 100  # kept

    editors["auto_range"].set(False)
    d.fields.refresh()
    assert table.disabled == set() and not table.grid.IsReadOnly(0, low)

    # loading settings: their ranges are used
    editors["auto_range"].set(True)
    d.fields.refresh()
    path = tmp_path / "ranges.json"
    path.write_text(json.dumps({"t1": {"min": 120, "max": 140}}))
    table.load_settings(path)
    assert not editors["auto_range"].get() and table.disabled == set()
    assert d.result().config.features["t1"].min == 120


def test_histogram_range_errors_are_marked(dialog):
    d = dialog("Frequency Histogram", HistogramConfig(features=["t1"]))
    editor = d.fields.editors["features"]
    editor.grid.SetCellValue(0, 2, "5")  # min
    editor.grid.SetCellValue(0, 3, "1")  # max
    d.validate()
    assert d.fields.markers["features"].IsShown() and not d.ok_button.IsEnabled()


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


# --- Pair Plot ---


def test_pair_plot_fields_without_choices_are_hidden(dialog):
    d = dialog("Pair Plot")
    editors, fixed = d.fields.editors, lambda: d.fields.fixed
    assert "features" not in editors  # set from the grid columns and rows
    # symmetric: the rows are the columns, nothing to choose
    # (no grouping: no legend either)
    assert fixed() == {"y_vars", "legend_position"}
    assert not editors["y_vars"].control.IsShown()
    editors["x_vars"].set(["t1", "t2"])
    d.fields.refresh()
    editors["corner"].set(True)
    config = d.result().config
    assert config.x_vars == config.y_vars == config.features == ["t1", "t2"]
    assert config.corner

    editors["symmetric"].set(False)
    d.fields.refresh()
    # rows to choose; a lower half needs a symmetric grid
    assert fixed() == {"corner", "legend_position"}
    assert (
        editors["y_vars"].control.IsShown() and not editors["corner"].control.IsShown()
    )
    editors["y_vars"].set(["t2"])
    config = d.result().config
    assert (config.y_vars, config.features, config.corner) == (
        ["t2"],
        ["t1", "t2"],
        False,
    )


# --- issues marked in the rows of tables ---


def test_feature_rows_with_issues_are_marked(dialog, table):
    d = dialog("Frequency Histogram", HistogramConfig(features=["t1", "t2"]))
    editor = d.fields.editors["features"]
    editor.grid.SetCellValue(0, 2, "5")  # t1: min > max
    editor.grid.SetCellValue(0, 3, "1")
    d.validate()
    assert editor.marks == {0: "error"}
    assert editor.row_messages == {0: ["min (5.0) >= max (1.0)"]}
    editor.grid.SetCellValue(0, 3, "500")
    d.validate()
    assert editor.marks == {}


def test_constant_columns_get_no_range(dialog, table):
    table["constant"] = 1.5
    d = dialog("Frequency Histogram")
    editor = d.fields.editors["features"]
    editor.use_all(True)
    row = editor.features.index("constant")
    assert editor.grid.GetCellValue(row, 2) == ""  # no range: one value only
    d.validate()
    assert d.ok_button.IsEnabled()


def test_filter_rows_with_issues_are_marked(dialog):
    d = dialog("Filter", FilterConfig(range_filters=["t2"]))
    editor = d.fields.editors["range_filters"]
    editor.grid.SetCellValue(1, 2, "3")  # t2: low > high
    editor.grid.SetCellValue(1, 3, "1")
    d.validate()
    assert editor.marks == {1: "error"}  # the t2 row


def test_rule_rows_with_issues_are_marked(dialog):
    from flim.configs import CategorizerConfig

    d = dialog("Categorize Data", CategorizerConfig(features=["t1"]))
    rules = d.fields.editors["rules"]
    rules.grid.SetCellValue(1, 2, "9")  # second rule: min > max
    d.validate()
    assert rules.marks == {1: "error"}


def test_histogram_flags_are_above_the_features_table(dialog):
    d = dialog("Frequency Histogram")
    names = list(d.fields.editors)
    assert names[-3:] == ["auto_range", "sync_bins", "features"]
    labels = [
        w.GetLabel()
        for w in d.fields.widgets["auto_range"]
        if isinstance(w, wx.StaticText)
    ]
    assert labels == ["Auto min/max range"]


def test_same_bins_for_all_takes_the_last_edit(dialog):
    config = HistogramConfig(features={"t1": {"bins": 10}, "t2": {"bins": 20}})
    d = dialog("Frequency Histogram", config)
    editors = d.fields.editors
    table, bins = editors["features"], 4
    table.grid.SetCellValue(1, bins, "15")  # edit t2 (not the first row)
    event = wx.grid.GridEvent(
        table.grid.GetId(), wx.grid.wxEVT_GRID_CELL_CHANGED, table.grid, row=1, col=bins
    )
    table._on_cell_changed(event)
    editors["sync_bins"].set(True)
    d.fields.refresh()  # all rows get the value just entered
    assert {r.bins for r in d.result().config.features.values()} == {15}


def test_settings_of_unchecked_rows_are_not_editable(dialog):
    d = dialog("Frequency Histogram", HistogramConfig(features=["t2"]))
    table = d.fields.editors["features"]
    grey = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
    # t1 unchecked: grey, its min, max and bins read-only; t2 checked: editable
    assert all(table.grid.IsReadOnly(0, col) for col in (2, 3, 4))
    assert table.grid.GetCellTextColour(0, 1) == grey
    assert not any(table.grid.IsReadOnly(1, col) for col in (2, 3, 4))
    table.use(0)
    assert not any(table.grid.IsReadOnly(0, col) for col in (2, 3, 4))
    assert table.grid.GetCellTextColour(0, 1) != grey
    table.use(1, False)
    assert all(table.grid.IsReadOnly(1, col) for col in (2, 3, 4))
    # disabled columns stay read-only in checked rows
    d.fields.editors["auto_range"].set(True)
    d.fields.refresh()
    assert table.grid.IsReadOnly(0, 2) and not table.grid.IsReadOnly(0, 4)
