"""The editors of tools that need more than the generated dialog (flim/gui/dialogs)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

import flim.gui.dialogs.autoencoder  # noqa: E402,F401  (register the editors)
import flim.gui.dialogs.categoryorder  # noqa: E402,F401
import flim.gui.dialogs.filter  # noqa: E402,F401
import flim.gui.dialogs.unpivot  # noqa: E402,F401
import flim.tools  # noqa: E402,F401
import flim.workflow  # noqa: E402,F401  (registers the workflows)
from flim.configs import (  # noqa: E402
    AETrainConfig,
    CategoryOrderConfig,
    FilterConfig,
    HistogramConfig,
)
from flim.configs.data import RangeSettings  # noqa: E402
from flim.configs.plot import HistogramRange  # noqa: E402
from flim.core.registry import tools  # noqa: E402


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


def _with_cell_editor(grid, row, col, use):
    """Return `use(editor)` for a cell's editor, then release the editor.

    `GetCellEditor` returns a new reference; one not released keeps the editor
    beyond its grid, and wx later asserts that its control still has the grid's
    event handler pushed ("any pushed event handlers must have been removed").
    """
    editor = grid.GetCellEditor(row, col)
    try:
        return use(editor)
    finally:
        editor.DecRef()


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


def _ranges(config) -> dict:
    """The used top-level range filters of a FilterConfig, by column."""
    return {
        f.column: RangeSettings(low=f.low, high=f.high, dropna=f.dropna)
        for f in config.filters
        if f.kind == "range" and f.enabled
    }


def _categories(config) -> dict:
    return {f.column: f.keep for f in config.filters if f.kind == "category" and f.enabled}


def test_category_filters(dialog):
    d = dialog("Filter")
    editor = d.fields.editors["filters"].categories
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
    assert _categories(d.result().config) == {"FOV": ["1"]}


def test_range_filters_table(dialog, table):
    config = FilterConfig(range_filters={"t1": RangeSettings(low=120, high=180)})
    d = dialog("Filter", config)
    editor = d.fields.editors["filters"].ranges
    assert editor.features == ["t1", "t2"]  # a row for each numeric column
    assert [editor.is_used(r) for r in range(2)] == [True, False]
    editor.use(1)  # checking fills in the data's range
    filters = _ranges(d.result().config)
    assert filters["t1"] == RangeSettings(low=120, high=180)  # kept as configured
    assert filters["t2"].low == pytest.approx(table["t2"].min(), rel=1e-5)
    assert filters["t2"].high == pytest.approx(table["t2"].max(), rel=1e-5)
    editor.grid.SetCellValue(1, 2, "3")  # t2: low > high
    editor.grid.SetCellValue(1, 3, "1")
    d.validate()
    assert editor.marks == {1: "error"}  # the t2 row


# --- settings files ---


def test_save_and_load_feature_settings(dialog, tmp_path):
    import json

    path = tmp_path / "ranges.json"
    d = dialog("Filter", FilterConfig(range_filters={"t1": {"low": 120, "high": 180}}))
    d.fields.editors["filters"].ranges.save_settings(path)
    assert json.loads(path.read_text()) == {
        "t1": {"low": 120, "high": 180, "dropna": True}
    }

    other = dialog("Filter")
    editor = other.fields.editors["filters"].ranges
    applied, skipped = editor.load_settings(path)
    assert (applied, skipped) == (["t1"], [])
    assert _ranges(other.result().config) == {}  # applied, but not checked
    editor.use(0)
    assert _ranges(other.result().config)["t1"] == RangeSettings(low=120, high=180)


def test_feature_settings_that_cannot_be_saved_give_a_message(dialog, tmp_path):
    d = dialog("Filter", FilterConfig(range_filters={"t1": {"low": 120, "high": 180}}))
    editor = d.fields.editors["filters"].ranges
    editor.save_settings(tmp_path / "missing folder" / "ranges.json")  # no error raised
    assert editor.message.GetLabel().startswith("Could not save ranges.json:")


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
    editor = filters.fields.editors["filters"].ranges
    assert editor.load_settings(path) == (["t2"], ["gone"])
    assert "1 are not in the table" in editor.message.GetLabel()
    assert _ranges(filters.result().config)["t2"] == RangeSettings(
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


def test_ok_takes_the_value_of_a_cell_still_being_edited(dialog):
    d = dialog("Frequency Histogram")
    editor = d.fields.editors["features"]
    editor.use(0)
    d.validate()
    grid = editor.grid
    grid.SetGridCursor(0, 4)  # bins
    grid.EnableCellEditControl()
    _with_cell_editor(grid, 0, 4, lambda e: e.GetControl().SetValue("12"))  # typed, cell not left
    closing = []  # the click reaches the dialog, which then closes
    d.Bind(wx.EVT_BUTTON, lambda e: closing.append(e.GetId()), id=wx.ID_OK)
    click = wx.CommandEvent(wx.EVT_BUTTON.typeId, wx.ID_OK)
    click.SetEventObject(d.ok_button)
    d.ok_button.GetEventHandler().ProcessEvent(click)
    assert not grid.IsCellEditControlEnabled()
    assert closing == [wx.ID_OK]
    assert d.result().config.features["t1"].bins == 12


def test_every_dialog_loads_and_saves_its_tool_settings(dialog, tmp_path):
    import json

    from flim.configs import SummaryConfig
    from flim.core.settings import AppSettings, load_settings, save_settings

    path = tmp_path / "settings.json"
    app = AppSettings.default()
    app.filters.use = True
    save_settings(app, path)  # an application settings file
    d = dialog("Summarize")
    d.fields.editors["aggs"].set(["max"])
    d.autosave.SetValue(True)
    d.folder.SetPath(str(tmp_path))
    assert d.save_settings(str(path))
    saved = load_settings(path)
    assert saved.filters.use  # the other sections are kept
    entry = saved.tools.entry(tools.get("Summarize"))
    assert entry.config["aggs"] == ["max"] and entry.autosave.enabled
    # the app settings' tools (Filter) and the dialog's
    assert list(json.loads(path.read_text())["tools"]) == ["Filter", "Summarize"]

    again = dialog("Summarize", SummaryConfig(aggs=["min"]))
    assert again.load_settings(str(path))
    assert again.result().config.aggs == ["max"]
    assert str(again.result().execution.autosave.results_dir) == str(tmp_path)
    other = dialog("Sort")
    assert not other.load_settings(str(path))
    assert "No Sort settings" in other.settings_message.GetLabel()


def test_tab_stays_in_the_features_table(dialog):
    d = dialog("Frequency Histogram")
    editor = d.fields.editors["features"]
    editor.use(0)
    editor.use(1)
    grid = editor.grid

    def tab(row, col, shift=False):
        event = wx.grid.GridEvent(
            wx.ID_ANY,
            wx.grid.wxEVT_GRID_TABBING,
            grid,
            row,
            col,
            kbd=wx.KeyboardState(shiftDown=shift),
        )
        grid.GetEventHandler().ProcessEvent(event)
        return grid.GetGridCursorRow(), grid.GetGridCursorCol()

    assert tab(0, 2) == (0, 3)  # min -> max
    assert tab(0, 4) == (1, 2)  # bins -> the next row's min
    assert tab(1, 4) == (0, 2)  # last cell: back to the first
    assert tab(1, 2, shift=True) == (0, 4)
    d.fields.editors["auto_range"].set(True)
    d.fields.refresh()  # min and max greyed out: skipped
    assert tab(0, 4) == (1, 4)
    assert d.fields.value_of("sync_bins") is False


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
    assert d.fields.markers["features"].IsShown() and not d.ok_button.IsEnabled()
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
    at = names.index("features")
    assert names[at - 2 : at + 1] == ["auto_range", "sync_bins", "features"]
    # then the figure's layout
    assert names[at + 1 :] == ["single_figure", "plots_per_row", "legend_position"]
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


# --- Categorize Data ---


def test_categorize_rules_table(dialog):
    d = dialog("Categorize Data")
    editor = d.fields.editors["rules"]
    labels = [
        w.GetLabel()
        for w in editor.control.GetChildren()
        if isinstance(w, wx.Button)
    ]
    assert labels[:2] == ["Add Rule", "Remove Rules"]
    # the feature column: a drop-down of the input's features
    col = [c.name for c in editor.columns].index("feature")
    assert _with_cell_editor(editor.grid, 0, col, lambda e: isinstance(e, wx.grid.GridCellChoiceEditor))
    editor.grid.SetGridCursor(0, col)
    editor.grid.EnableCellEditControl()
    items = _with_cell_editor(editor.grid, 0, col, lambda e: e.GetControl().GetItems())
    assert items == ["t1", "t2"]
    editor.grid.DisableCellEditControl()


def test_categorize_features_only_without_the_input(dialog):
    d = dialog("Categorize Data")
    features = d.fields.widgets["features"][0]
    assert not features.IsShown()  # all input columns are kept
    d.fields.editors["merge_input"].set(False)
    d.fields.refresh()
    assert features.IsShown()


# --- Unpivot ---


def test_unpivot_offers_the_levels_of_the_headers(dialog, table):
    from flim.configs import PivotConfig
    from flim.tools.data import Pivot

    pivoted = Pivot().run(table, config=PivotConfig(grouping=["Treatment"]))["Pivoted"]
    d = dialog("Unpivot", data_choices={"Table: pivoted": pivoted})
    level = d.fields.editors["level"]
    # each line with its name and values; the last line selected
    assert level.control.GetStrings() == [
        "Feature: t1, t2",
        "Treatment: Ctrl, Drug, Placebo",
    ]
    assert level.control.GetSelection() == 1
    assert d.result().config.level == ""  # the last
    level.control.SetSelection(0)
    level._on_choice(wx.CommandEvent())
    assert d.result().config.level == "Feature"
    # single-line columns: one level, the feature
    level.show_levels(["t1"])
    assert level.control.GetStrings() == ["Feature: t1"]


# --- feature lists ---


def test_features_of_another_table_are_not_listed(dialog, table):
    """Settings of a run on the raw data, opened on its summary: the summary's
    features only; saved features the input lacks are ignored, not kept."""
    from flim.configs import SummaryConfig
    from flim.tools.statistics import Summarize

    summary = Summarize().run(
        table,
        config=SummaryConfig(grouping=["Treatment"], features=["t1"], aggs=["mean"]),
    )["Summary"]
    d = dialog(
        "Summarize",
        SummaryConfig(features=["t1", "t2"]),
        data_choices={"Table: Summary": summary, "Table: data": table},
    )
    features = d.fields.editors["features"]
    assert features.items == ["t1\nmean"]
    assert features.get() == []
    features.list.Check(0)
    features._on_check(wx.CommandEvent())
    d.input_controls[0].SetSelection(1)  # the raw data
    d._update_inputs()
    assert features.items == ["t1", "t2"]
    assert features.get() == []  # the summary's feature is not in the raw data


# --- Concatenate ---


def test_concatenate_shows_the_settings_of_its_direction(dialog):
    d = dialog("Concatenate")
    shown = lambda name: d.fields.widgets[name][0].IsShown()  # noqa: E731
    assert shown("add_input") and not shown("numbers_only")  # rows (default)
    d.fields.editors["mode"].set("horizontal")
    d.fields.refresh()
    assert shown("numbers_only") and not shown("add_input") and not shown("clash_name")


# --- Scatter Plot ---


def test_scatter_plot_x_axis_with_two_features(dialog):
    d = dialog("Scatter Plot")
    x_axis = d.fields.editors["x_axis"]
    hidden = lambda: not d.fields.widgets["x_axis"][0].IsShown()  # noqa: E731
    assert hidden()  # no features checked
    d.fields.editors["features"].set(["t1", "t2"])
    d.fields.refresh()
    assert not hidden()
    assert x_axis.control.GetItems() == ["t1", "t2"]
    assert d.result().config.x_axis == "t1"
    x_axis.control.SetValue("t2")
    assert d.result().config.x_axis == "t2"
    d.fields.editors["features"].set(["t1"])
    d.fields.refresh()
    assert hidden()


# --- workflows ---


def test_basic_flirr_reference_value_of_the_first_grouping_column(dialog):
    d = dialog("Basic FLIRR Analysis")
    d.fields.editors["grouping"].set(["FOV", "Treatment"])
    d.fields.refresh()
    reference = d.fields.editors["reference_value"]
    assert reference.control.GetItems() == ["1", "2"]  # FOV's
    assert d.result().config.reference_value is None  # empty: the first value


# --- the features and statistics a tool needs ---


def test_no_features_disable_ok(dialog):
    from flim.configs.analysis import SummaryConfig

    d = dialog("Summarize", SummaryConfig(grouping=["Treatment"], features=[]))
    d.validate()
    assert d.fields.markers["features"].IsShown() and not d.ok_button.IsEnabled()


def test_no_statistics_disable_ok(dialog):
    from flim.configs.analysis import SummaryConfig

    d = dialog("Summarize", SummaryConfig(grouping=["Treatment"], features=["t1"]))
    d.validate()
    assert d.ok_button.IsEnabled()
    d.fields.editors["aggs"].check_all(False)  # every statistic unchecked
    d.validate()
    assert not d.ok_button.IsEnabled()


def test_filter_dialog_keeps_the_whole_tree(dialog, table):
    from flim.configs.data import (
        CategoryFilterNode as Category,
        ExpressionFilterNode as Expression,
        FilterGroup,
        RangeFilterNode as Range,
    )

    config = FilterConfig(
        filters=[
            Range(column="t1", low=120, high=180),
            Range(column="t2", low=0, high=1, enabled=False),  # shown unchecked
            Range(column="gone", high=3, enabled=False),  # not in the table: kept
            Category(column="Treatment", keep=["Ctrl"]),
            Expression(expression="t1 > 100"),
            FilterGroup(kind="any", filters=[Range(column="t2", high=5), Expression(expression="t1 < 3")]),
            Range(column="t1", high=500),  # a second range on t1
        ]
    )
    d = dialog("Filter", config)
    editor = d.fields.editors["filters"]
    assert [editor.ranges.is_used(r) for r in range(2)] == [True, False]
    assert editor.ranges.grid.GetCellValue(1, 3) == "1"  # t2's unused range is shown
    others = editor.others
    assert others.grid.GetNumberRows() == 3  # the expression, the group, the second t1
    kind = others._kind_column()
    assert others.grid.GetCellValue(1, kind) == "any" and others.grid.IsReadOnly(1, kind)
    assert "any" not in others.columns[kind - others.offset].choices  # no new groups
    result = d.result().config.filters
    assert sorted(map(repr, result)) == sorted(map(repr, config.filters))


def test_source_dialog_shows_the_rename_only_for_a_source_column(dialog):
    from flim.tools.data import SourceFromPath

    plain = pd.DataFrame({"Directory": ["/d"], "File": ["a.txt"], "t1": [1.0]})
    d = dialog("Directory/File to Source", data_choices={"Table: plain": plain})
    d.validate()
    assert not d.fields.editors["clash_name"].control.IsShown()  # nothing to rename
    assert SourceFromPath.example(d.current_config()[0], [plain]) == "/d + a.txt \u2192 file:///d/a.txt"
    taken = plain.assign(Source=["mine"])
    d = dialog("Directory/File to Source", data_choices={"Table: taken": taken})
    d.validate()
    assert d.fields.editors["clash_name"].control.IsShown()


def test_concatenate_shows_the_rename_only_for_an_input_column(dialog):
    a = pd.DataFrame({"t1": [1.0]})
    d = dialog("Concatenate", data_choices={"Table: a": a, "Table: b": a.copy()})
    d.validate()
    assert not d.fields.editors["clash_name"].control.IsShown()
    d = dialog("Concatenate", data_choices={"Table: a": a.assign(Input=["x"]), "Table: b": a})
    d.validate()
    assert d.fields.editors["clash_name"].control.IsShown()


def test_saved_grouping_columns_the_table_lacks_are_not_offered(dialog, table):
    from flim.configs import SummaryConfig

    # e.g. a column fused in an earlier session, saved with the settings
    config = SummaryConfig(grouping=["FOV:Cell", "Treatment"], features=["t1"], aggs=["mean"])
    d = dialog("Summarize", config)
    editor = d.fields.editors["grouping"]
    listed = [editor.rearrange.GetList().GetString(i) for i in range(editor.rearrange.GetList().GetCount())]
    assert "FOV:Cell" not in listed
    assert editor.get() == ["Treatment"]  # only the table's columns are used
    assert d.result().config.grouping == ["Treatment"]


class _Choose:
    """wx.MultiChoiceDialog answered with OK and the first item."""

    offered: list = []

    def __init__(self, parent, message, title, labels):
        _Choose.offered = list(labels)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ShowModal(self):
        return wx.ID_OK

    def GetSelections(self):
        return [0]


def test_calculation_editor_shows_only_the_kinds_fields(wxapp, table):
    from flim.core.schema import TableSchema
    from flim.gui.dialogs.calculate import CalculationDialog

    schema = TableSchema.from_frame(table)
    d = CalculationDialog(None, None, list(table.columns), schema, [table])
    try:
        assert set(d.fields.editors) == {"enabled", "name", "keep", "description", "expression"}
        d.fields.editors["name"].control.SetValue("ratio")
        d.fields.editors["expression"].control.SetValue("t1 / t2")  # no backticks needed
        assert d.validate() and d.example.GetLabel().startswith("Example: ratio = ")
        d.fields.editors["expression"].control.SetValue("t1 / t22")
        assert not d.validate()  # OK disabled
        assert "'t22' (did you mean 't2'?)" in d.message.GetLabel()
        # a function: its own parameters only
        d.kind.SetSelection(1)
        d._on_kind(None)
        assert {"function", "args", "params"} <= set(d.fields.editors) and "expression" not in d.fields.editors
        d.fields.editors["function"].set("trp_Eperc_1")
        d.fields.refresh()
        params = d.fields.editors["params"]
        assert params.fields is not None and set(params.fields.editors) == {"const"}
        assert params.get() == {"const": 3100.0}
        d.fields.editors["function"].set("ratio")
        d.fields.refresh()
        assert params.fields is None  # ratio has no parameters
    finally:
        d.Destroy()


def test_calculate_dialog_is_a_read_only_table_with_presets(dialog, table, monkeypatch):
    from flim.configs import CalculateConfig
    from flim.configs.data import ExpressionCalculation
    from flim.core.settingsmgr import SettingsManager
    from flim.gui.dialogs import calculate
    from flim.tools.data import Calculate

    calculate.bind(SettingsManager())
    stored = CalculateConfig(calculations=[ExpressionCalculation(name="old", expression="t1 * 2")])
    d = dialog("Calculate", Calculate.dialog_config(stored))
    editor = d.fields.editors["calculations"]
    assert editor.grid.GetNumberRows() == 0  # nothing from earlier runs
    assert not editor.grid.IsEditable()
    new = ExpressionCalculation(name="ratio", expression="t1 / t2")
    monkeypatch.setattr(calculate, "edit_calculation", lambda *a, **k: new)
    editor._on_add(None)  # the calculation editor answers with `new`
    assert editor.grid.GetCellValue(0, 0) == "ratio" and editor.grid.GetCellValue(0, 1) == "t1 / t2"
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.OK)
    editor.grid.SetGridCursor(0, 0)
    editor._on_save_presets(None)
    assert [p.name for p in calculate.saved_presets()] == ["ratio"]
    editor._on_remove(None)
    monkeypatch.setattr(wx, "MultiChoiceDialog", _Choose)
    editor._on_load_presets(None)
    assert _Choose.offered == ["ratio = t1 / t2  (saved)"]  # built-in ones don't apply
    assert d.result().config.calculations[0].name == "ratio"
    editor._on_remove_presets(None)
    assert calculate.saved_presets() == []



def test_calculation_editor_example_without_use_or_keep(wxapp, table):
    from flim.core.schema import TableSchema
    from flim.gui.dialogs.calculate import CalculationDialog

    d = CalculationDialog(None, None, list(table.columns), TableSchema.from_frame(table), [table])
    try:
        d.fields.editors["expression"].control.SetValue("t1 * 2")
        d.fields.editors["enabled"].set(False)  # Use unchecked, no name: no error
        d.validate()
        assert "Not used" in d.message.GetLabel()
        d.fields.editors["enabled"].set(True)
        d.fields.editors["name"].control.SetValue("helper")
        d.fields.editors["keep"].set(False)  # a helper column: its example is shown
        assert d.validate() and d.example.GetLabel().startswith("Example: helper = ")
    finally:
        d.Destroy()


def test_separate_categories_presets(wxapp, monkeypatch):
    """Load Preset... fills the settings of a built-in or saved preset; Save as
    Preset... and Remove Presets... change only the saved ones."""
    import flim.gui.dialogs.separate as separate
    from flim.core.registry import tools
    from flim.core.settingsmgr import SettingsManager
    from flim.gui.configdialog import dialog_class

    source = pd.DataFrame({"Source": ["file:///data/Results_a_ctrl_1.txt"], "t1": [1.0]})
    manager = SettingsManager()
    separate.bind(manager)
    tool = tools.get("Separate Categories")
    d = dialog_class(tool.config_class)(None, tool, data_choices={"Table: data": source})
    try:
        assert isinstance(d, separate.SeparateDialog)
        # Load Preset...: the 0.6 parser FOV, Treatment, Cell
        monkeypatch.setattr(wx.SingleChoiceDialog, "ShowModal", lambda dlg: wx.ID_OK)
        built_in = [p["name"] for p in separate.separate_presets()]
        index = built_in.index("FOV, Treatment, Cell")
        monkeypatch.setattr(wx.SingleChoiceDialog, "GetSelection", lambda dlg: index)
        d._on_load_preset(None)
        config, _ = d.current_config()
        assert config.mode == "pattern" and [p.name for p in config.patterns] == ["FOV", "Treatment", "Cell"]
        # Save as Preset...: in the user settings, under its name; a built-in name is refused
        monkeypatch.setattr(wx.TextEntryDialog, "ShowModal", lambda dlg: wx.ID_OK)
        monkeypatch.setattr(wx.TextEntryDialog, "GetValue", lambda dlg: "Mine")
        d._on_save_preset(None)
        (saved,) = manager.settings.separate_presets
        assert saved["name"] == "Mine" and saved["settings"]["column"] == "Source"
        assert set(saved["settings"]) == set(separate.PRESET_FIELDS)
        messages = []
        monkeypatch.setattr(wx, "MessageBox", lambda m, *a, **k: messages.append(m))
        monkeypatch.setattr(wx.TextEntryDialog, "GetValue", lambda dlg: "Treatment, Time")
        d._on_save_preset(None)
        assert "built-in" in messages[0] and len(manager.settings.separate_presets) == 1
        # the saved one is offered after the built-in ones
        assert [p["name"] for p in separate.saved_presets()] == ["Mine"]
        # Remove Presets...
        monkeypatch.setattr(wx.MultiChoiceDialog, "ShowModal", lambda dlg: wx.ID_OK)
        monkeypatch.setattr(wx.MultiChoiceDialog, "GetSelections", lambda dlg: [0])
        d._on_remove_presets(None)
        assert manager.settings.separate_presets == []
    finally:
        d.Destroy()
        separate.bind(None)


def test_separate_shows_only_the_modes_fields(wxapp):
    from flim.configs.data import SeparateCategoriesConfig
    from flim.core.registry import tools
    from flim.gui.configdialog import dialog_class

    source = pd.DataFrame({"Source": ["file:///data/Results-a-ctrl_1.txt"], "t1": [1.0]})
    tool = tools.get("Separate Categories")
    d = dialog_class(tool.config_class)(None, tool, data_choices={"Table: data": source})
    try:
        fields = d.fields

        def shown():
            names = ("delimiters", "names", "patterns", "template")
            return {n for n in names if fields.editors[n].control.IsShown()}

        assert shown() == {"delimiters", "names"}  # the default mode: delimiter
        for mode, expected in (("template", {"template"}), ("pattern", {"patterns"})):
            d.set_values(SeparateCategoriesConfig(column="Source", mode=mode))
            assert shown() == expected, mode
        # hidden fields keep their values
        d.set_values(SeparateCategoriesConfig(column="Source", mode="pattern", template="{A}"))
        assert fields.editors["template"].get() == "{A}"
    finally:
        d.Destroy()


def test_spaces_in_values_are_kept(wxapp):
    """Rename's new texts ('trp ') and Fuse's delimiter (' - ') keep their spaces; the
    dialog trimmed them, which renamed Exc1_-Ch1-_t1 to trpt1."""
    from flim.configs.data import FuseCategoriesConfig, RenameColumnsConfig
    from flim.core.fields import describe
    from flim.core.registry import tools
    from flim.gui.configdialog import dialog_class
    from flim.gui.editors import editor_for

    tool = tools.get("Rename Columns")
    data = pd.DataFrame({"Exc1_-Ch1-_t1": [1.0]})
    d = dialog_class(tool.config_class)(None, tool, data_choices={"Table: d": data})
    try:
        config, _ = d.current_config()
        assert config.replacements == RenameColumnsConfig().replacements
        assert config.replacements[0].new == "trp "
    finally:
        d.Destroy()
    frame = wx.Frame(None)
    try:
        spec = next(s for s in describe(FuseCategoriesConfig) if s.name == "delimiter")
        editor = editor_for(FuseCategoriesConfig, spec)(frame, spec)
        editor.control.SetValue(" - ")
        assert editor.get() == " - "
    finally:
        frame.Destroy()
