"""The generic configuration dialog (flim.gui.configdialog) and its field editors."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

import flim.tools  # noqa: E402,F401  (registers the tools)
from flim.configs import (  # noqa: E402
    CategorizerConfig,
    KMeansConfig,
    LinePlotConfig,
    RelativeChangeConfig,
)
from flim.core.execution import ExecutionOptions  # noqa: E402
from flim.core.registry import tools  # noqa: E402

TOOLS = [t for group in tools.by_category().values() for t in group]


@pytest.fixture(scope="module")
def wxapp():
    try:
        app = wx.App()
    except SystemExit:  # raised by wx when no display is available
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
            "Treatment": pd.Categorical(["Ctrl", "Drug"] * 10),
            "FOV": pd.Categorical(["1", "2"] * 10),
            "Cell": pd.Categorical([str(i) for i in range(20)]),
            "FLIRR": rng.random(20),
            "x": rng.random(20),
            "y": rng.random(20),
        }
    )


@pytest.fixture
def dialog(wxapp, table):
    from flim.gui.configdialog import ConfigDialog

    dialogs = []

    def make(name, config=None, **kwargs):
        kwargs.setdefault(
            "data_choices",
            {"Table: data": table, "Table: other": table[["Treatment", "x"]]},
        )
        d = ConfigDialog(None, tools.get(name), config, **kwargs)
        dialogs.append(d)
        return d

    yield make
    for d in dialogs:
        d.Destroy()


def marker(d, name):
    m = d.fields.markers[name]
    return m.IsShown(), m.GetToolTipText()


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.name)
def test_every_tool_dialog_builds(dialog, tool):
    d = dialog(tool.name)
    assert d.fields.editors  # something to edit
    d.validate()
    if d.ok_button.IsEnabled():
        assert isinstance(d.result().config, tool.config_class)


def test_edit_and_result(dialog):
    d = dialog("K-Means", KMeansConfig(features=["x"]))
    editors = d.fields.editors
    editors["n_clusters"].set(5)
    editors["features"].set(["x", "FLIRR"])
    editors["init"].set("random")
    editors["random_seed"].set(None)
    d.validate()
    assert d.ok_button.IsEnabled()
    result = d.result()
    config = result.config
    assert (config.n_clusters, config.init, config.random_seed) == (5, "random", None)
    assert config.features == ["FLIRR", "x"]  # in the table's column order
    assert result.input_names == ["Table: data"]
    assert result.inputs[0] is d.data_choices["Table: data"]


def test_grouping_order(dialog):
    d = dialog("Summarize")
    d.fields.editors["grouping"].set(["FOV", "Treatment"])
    assert d.result().config.grouping == ["FOV", "Treatment"]
    d.fields.editors["grouping"].set(["Treatment", "Cell", "FOV"])
    assert d.result().config.grouping == ["Treatment", "Cell", "FOV"]


def test_unused_fields_and_order(dialog):
    d = dialog("K-Means")
    assert "grouping" not in d.fields.editors  # K-Means does not group
    names = list(d.fields.editors)
    # the tool's own settings first, the general ones after
    assert names.index("n_clusters") < names.index("prefix")
    assert names.index("tolerance") < names.index("random_seed")
    label = next(
        w.GetLabel()
        for w in d.fields.GetChildren()
        if isinstance(w, wx.StaticText) and w.GetLabel() == "Clusters"
    )
    assert label == "Clusters"  # the field's title


def test_reference_values_are_offered(dialog):
    d = dialog("Relative Change", RelativeChangeConfig(features=["x"]))
    reference = d.fields.editors["reference_value"]
    assert reference.control.GetItems() == ["Ctrl", "Drug"]
    d.fields.editors["reference_group"].control.SetValue("FOV")
    assert reference.control.GetItems() == ["1", "2"]


def test_invalid_text_marks_the_field(dialog):
    d = dialog("K-Means", KMeansConfig(features=["x"]))
    d.fields.editors["tolerance"].control.SetValue("tiny")
    d.validate()
    assert marker(d, "tolerance") == (True, "'tiny' is not a number")
    assert not d.ok_button.IsEnabled()
    d.fields.editors["tolerance"].control.SetValue("0.001")
    d.validate()
    assert not marker(d, "tolerance")[0]
    assert d.ok_button.IsEnabled()


def test_constraint_violations_mark_the_field(dialog):
    d = dialog("K-Means", KMeansConfig(features=["x"]))
    d.fields.editors["tolerance"].control.SetValue("-1")
    d.validate()
    shown, text = marker(d, "tolerance")
    assert shown and "greater than 0" in text


def test_issues_against_the_input(dialog):
    config = RelativeChangeConfig(features=["x"], reference_value="Placebo")
    d = dialog("Relative Change", config)
    shown, text = marker(d, "reference_value")
    assert shown and "not a value of 'Treatment'" in text
    assert not d.ok_button.IsEnabled()
    d.fields.editors["reference_value"].control.SetValue("Ctrl")
    d.validate()
    assert not marker(d, "reference_value")[0] and d.ok_button.IsEnabled()


def test_columns_follow_the_selected_input(dialog):
    d = dialog("Summarize")
    features = d.fields.editors["features"]
    assert features.items == ["FLIRR", "x", "y"]
    d.input_controls[0].SetStringSelection("Table: other")
    d._on_input(None)
    assert features.items == ["x"]
    grouping = d.fields.editors["grouping"]
    assert grouping.items == ["Treatment"]


def test_missing_columns_are_marked(dialog):
    d = dialog("K-Means", KMeansConfig(features=["gone"]))
    shown, text = marker(d, "features")
    assert shown and "'gone' is not in the input" in text
    assert d.fields.editors["features"].items[-1] == "gone"  # still listed, to uncheck


def test_all_features(dialog):
    d = dialog("Box Plot")
    features = d.fields.editors["features"]
    features.set("all")
    assert not features.list.IsEnabled()
    assert d.result().config.features == "all"


def test_mixed_and_optional_fields(dialog):
    d = dialog("Line Plot", LinePlotConfig(features=["x"]))
    errorbar = d.fields.editors["errorbar"]
    for text, value in (("sd", "sd"), ("68", 68), ("", None)):
        errorbar.control.SetValue(text)
        assert d.result().config.errorbar == value


def test_rules_table(dialog):
    d = dialog("Categorize Data", CategorizerConfig(features=["x"]))
    rules = d.fields.editors["rules"]
    assert rules.grid.GetNumberRows() == 3
    rules.grid.SetCellValue(0, 3, "-0.4")  # overlaps the next rule (-0.5..0.5)
    d.validate()
    shown, text = marker(d, "rules")
    assert shown and "overlap" in text
    rules.grid.SetCellValue(0, 3, "-0.5")
    rules.grid.SetCellValue(0, 1, "x")
    rules.grid.SetCellValue(1, 1, "x")
    rules.grid.SetCellValue(2, 1, "x")
    d.validate()
    assert d.ok_button.IsEnabled()
    assert [r.feature for r in d.result().config.rules] == ["x", "x", "x"]


def test_nested_resources_section(dialog):
    d = dialog("Autoencoder: Train")
    resources = d.fields.editors["resources"]
    resources.fields.editors["preferred_device"].set("cpu")
    resources.fields.editors["preferred_threads"].set(2)
    d.fields.editors["features"].set(["x", "y"])
    d.fields.editors["grouping"].set(["FOV"])
    d.fields.editors["timeseries"].set("Treatment")
    d.validate()
    config = d.result().config
    assert (config.resources.preferred_device, config.resources.preferred_threads) == (
        "cpu",
        2,
    )
    # tools whose resources allow only one value have no resources section
    assert "resources" not in dialog("Sort").fields.editors


def test_model_files(dialog, tmp_path):
    d = dialog("Autoencoder: Run")
    d.fields.editors["model_files"].set([tmp_path / "a.model"])
    d.fields.editors["features"].set(["x"])
    d.validate()
    assert d.result().config.model_files == [tmp_path / "a.model"]


def test_inputs_of_tools_with_several(dialog, table):
    merge = dialog("Merge")
    assert merge.selected_names() == ["Table: data", "Table: other"]
    concat = dialog("Concat Data")
    assert concat.selected_names() == [["Table: data", "Table: other"]]
    assert set(concat.result().inputs[0]) == {"Table: data", "Table: other"}


def test_execution_options(dialog, tmp_path):
    d = dialog("Sort", execution=ExecutionOptions(executor="local", num_workers=3))
    d.autosave.SetValue(True)
    d.validate()
    assert not d.ok_button.IsEnabled()
    assert "Choose the folder" in d.status.GetLabel()
    d.folder.SetPath(str(tmp_path))
    d.validate()
    execution = d.result().execution
    assert execution.autosave and execution.results_dir == Path(tmp_path)
    assert execution.num_workers == 3  # other options are kept


def test_autosave_locked(dialog, tmp_path):
    options = ExecutionOptions(autosave=False)
    d = dialog("Sort", execution=options, autosave_locked=True)
    assert d.autosave.GetValue() and not d.autosave.IsEnabled()


def test_registered_dialog_and_open(wxapp, table, monkeypatch):
    from flim.gui import configdialog

    class SortDialog(configdialog.ConfigDialog):
        pass

    from flim.configs import SortConfig

    configdialog.register_dialog(SortConfig)(SortDialog)
    try:
        assert configdialog.dialog_class(SortConfig) is SortDialog
        assert configdialog.dialog_class(KMeansConfig) is configdialog.ConfigDialog
        monkeypatch.setattr(SortDialog, "ShowModal", lambda self: wx.ID_OK)
        result = configdialog.open_config_dialog(
            None,
            tools.get("Sort"),
            SortConfig(features=["x"]),
            data_choices={"t": table},
        )
        assert result.config.features == ["x"]
        monkeypatch.setattr(SortDialog, "ShowModal", lambda self: wx.ID_CANCEL)
        assert (
            configdialog.open_config_dialog(
                None, tools.get("Sort"), data_choices={"t": table}
            )
            is None
        )
    finally:
        configdialog._DIALOGS.pop(SortConfig)


def test_registered_field_editor(dialog):
    from flim.gui import editors

    class Upper(editors.TextEditor):
        def get(self):
            return super().get().upper()

    editors.register_editor(KMeansConfig, "cluster_prefix")(Upper)
    try:
        d = dialog("K-Means", KMeansConfig(features=["x"]))
        assert isinstance(d.fields.editors["cluster_prefix"], Upper)
        assert d.result().config.cluster_prefix == "CLUSTER"
    finally:
        editors._FIELD_EDITORS.pop((KMeansConfig, "cluster_prefix"))


def test_all_features_checks_every_feature(dialog):
    d = dialog("Box Plot")
    features = d.fields.editors["features"]
    features.set(["x"])
    features.all.SetValue(True)
    features._on_all(wx.CommandEvent())
    assert features.checked() == features.items == ["FLIRR", "x", "y"]
    assert not features.list.IsEnabled() and not features.buttons[0].IsEnabled()
    assert d.result().config.features == "all"
    # unchecked again: the selection made before
    features.all.SetValue(False)
    features._on_all(wx.CommandEvent())
    assert features.checked() == ["x"] and features.list.IsEnabled()
    assert d.result().config.features == ["x"]


def test_all_features_from_a_config_and_new_inputs(dialog):
    from flim.configs import BoxPlotConfig

    d = dialog("Box Plot", BoxPlotConfig(features="all"))
    features = d.fields.editors["features"]
    assert features.checked() == ["FLIRR", "x", "y"]
    d.input_controls[0].SetStringSelection("Table: other")
    d._on_input(None)
    assert features.checked() == ["x"]  # all features of the other table
    features.all.SetValue(False)
    features._on_all(wx.CommandEvent())  # no selection before: all stay checked
    assert features.checked() == ["x"]


def test_nested_settings_are_inline_and_advanced_ones_collapsed(dialog):
    d = dialog("Scatter Plot")
    points = d.fields.editors["points"]
    assert not isinstance(points.control, wx.CollapsiblePane)  # no extra click
    points.fields.editors["mode"].set("sample")
    points.fields.refresh()
    assert points.fields.editors["samples"].control.IsShown()
    training = dialog("Autoencoder: Train")
    assert isinstance(training.fields.editors["resources"].control, wx.CollapsiblePane)
