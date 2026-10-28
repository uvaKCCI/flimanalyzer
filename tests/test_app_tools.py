"""Running tools from the application window (registry, generated dialogs, settings)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")
from prefect.testing.utilities import prefect_test_harness  # noqa: E402

from flim.configs import KMeansConfig, SummaryConfig  # noqa: E402
from flim.core.execution import ExecutionOptions  # noqa: E402
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


@pytest.fixture(scope="module")
def prefect_harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def table():
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "Treatment": pd.Categorical(["Ctrl", "Drug"] * 10),
            "FOV": pd.Categorical(["1", "2"] * 10),
            "x": rng.random(20),
            "y": rng.random(20),
        }
    )


@pytest.fixture
def frame(wxapp, table, monkeypatch, tmp_path):
    from flim.core.runner import CancelToken
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame
    import flim.core.configuration as cfg

    config = cfg.Config()
    config.create_default()
    frame = AppFrame(FLIMAnalyzer(), config)
    frame.shown = []
    monkeypatch.setattr(frame, "tool_data_choices", lambda: {"Table: data": table})
    # run in this thread, without the progress dialog
    monkeypatch.setattr(
        frame,
        "run_with_progress",
        lambda title, start: start(CancelToken(), lambda *a: None, lambda run: None),
    )
    monkeypatch.setattr(
        frame, "show_results", lambda run: frame.shown.extend(run.results())
    )
    yield frame
    frame.Destroy()


def answer_dialog(monkeypatch, change):
    """Makes the configuration dialog return at once, after ``change(dialog)``."""
    from flim.gui import configdialog

    seen = {}

    def show(dialog):
        change(dialog)
        dialog.validate()
        seen["dialog"] = dialog
        return wx.ID_OK if dialog.ok_button.IsEnabled() else wx.ID_CANCEL

    monkeypatch.setattr(configdialog.ConfigDialog, "ShowModal", show)
    return seen


def test_config_from_settings():
    from flim.gui.app import config_from_settings, settings_from_config

    tool = tools.get("K-Means")
    config = KMeansConfig(features=["x"], n_clusters=3, random_seed=None)
    settings = settings_from_config(
        config, ExecutionOptions(autosave=True, results_dir="/r")
    )
    assert settings["n_clusters"] == 3  # plugin parameters, read by older versions
    assert settings["autosave"] is True and settings["working_dir"] == "/r"
    assert config_from_settings(tool, settings) == config  # incl. fields new in 2.x
    # settings of older versions: plugin parameters only
    legacy = {"n_clusters": 4, "features": ["x"], "autosave": False}
    assert config_from_settings(tool, legacy).n_clusters == 4
    # invalid settings: the defaults
    assert config_from_settings(tool, {"_config": {"n_clusters": 0}}) == KMeansConfig()
    assert config_from_settings(tool, None) == KMeansConfig()


def test_menus_and_tool_panel_from_the_registry(frame):
    menubar = frame.GetMenuBar()
    titles = [menubar.GetMenuLabelText(i) for i in range(menubar.GetMenuCount())]
    assert titles == [
        "File",
        "Settings",
        "Data",
        "Analysis",
        "Plot",
        "Workflow",
        "Window",
    ]
    data_menu = menubar.GetMenu(titles.index("Data"))
    assert [i.GetItemLabelText() for i in data_menu.GetMenuItems()] == [
        t.name for t in tools.by_category()["Data"]
    ]


def test_run_a_tool(frame, monkeypatch, prefect_harness):
    def change(dialog):
        dialog.fields.editors["grouping"].set(["Treatment"])
        dialog.fields.editors["features"].set(["x", "y"])
        dialog.fields.editors["aggs"].set(["count", "mean"])

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Summarize"))
    (results,) = frame.shown
    table = results["Table: Summary"]
    assert list(table.columns) == [
        "Treatment",
        "x\ncount",
        "x\nmean",
        "y\ncount",
        "y\nmean",
    ]

    # the settings were saved, and the next dialog starts from them
    settings = frame.config.get(["plugins", "Summarize"])
    assert settings["aggs"] == ["count", "mean"]
    seen = answer_dialog(monkeypatch, lambda dialog: None)
    frame.run_tool(tools.get("Summarize"))
    assert seen["dialog"].config.features == ["x", "y"]


def test_per_feature_runs(frame, monkeypatch, prefect_harness):
    def change(dialog):
        dialog.fields.editors["features"].set(["x", "y"])

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Box Plot"))
    names = [name for results in frame.shown for name in results]
    assert names == ["Plot: Box Plot x", "Plot: Box Plot y"]  # one task per feature


def test_cancelled_dialog_runs_nothing(frame, monkeypatch):
    from flim.gui import configdialog

    monkeypatch.setattr(
        configdialog.ConfigDialog, "ShowModal", lambda self: wx.ID_CANCEL
    )
    frame.run_tool(tools.get("Summarize"))
    assert frame.shown == []
    assert frame.config.get(["plugins", "Summarize"]).get("_config") is None


def test_autosave(frame, monkeypatch, prefect_harness, tmp_path):
    def change(dialog):
        dialog.fields.editors["features"].set(["x"])
        dialog.autosave.SetValue(True)
        dialog.folder.SetPath(str(tmp_path))

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Sort"))
    assert any(tmp_path.rglob("*Sort*"))
    assert frame.config.get(["plugins", "Sort"])["working_dir"] == str(tmp_path)


def test_run_a_tool_with_a_custom_editor(frame, monkeypatch, prefect_harness):
    def change(dialog):
        dialog.fields.editors["category_filters"].set({"Treatment": ["Ctrl"]})

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Filter"))
    (results,) = frame.shown
    assert set(results["Table: Filtered"]["Treatment"]) == {"Ctrl"}
