"""Running tools from the application window (registry, generated dialogs, settings)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")
from prefect.testing.utilities import prefect_test_harness  # noqa: E402

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
    from flim.core.settings import AppSettings

    frame = AppFrame(FLIMAnalyzer(), AppSettings.default())
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
    saved = frame.settings.tool_settings.config(tools.get("Summarize"))
    assert saved.aggs == ["count", "mean"]
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
    assert frame.settings.tool_settings.entry(tools.get("Summarize")) is None


def test_autosave(frame, monkeypatch, prefect_harness, tmp_path):
    def change(dialog):
        dialog.fields.editors["features"].set(["x"])
        dialog.autosave.SetValue(True)
        dialog.folder.SetPath(str(tmp_path))

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Sort"))
    assert any(tmp_path.rglob("*Sort*"))
    entry = frame.settings.tool_settings.entry(tools.get("Sort"))
    assert entry.autosave and entry.results_dir == str(tmp_path)


def test_run_a_tool_with_a_custom_editor(frame, monkeypatch, prefect_harness):
    def change(dialog):
        dialog.fields.editors["category_filters"].set({"Treatment": ["Ctrl"]})

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Filter"))
    (results,) = frame.shown
    assert set(results["Table: Filtered"]["Treatment"]) == {"Ctrl"}


def test_settings_saved_under_a_former_name(frame, monkeypatch):
    from flim.gui import configdialog

    from flim.core.settings import settings_from_data

    # settings of 0.5: plugin parameters, under the former name
    old = {"root": {"plugins": {"Concat Data": {"type": True, "autosave": False}}}}
    frame.settings.tool_settings = settings_from_data(old).tool_settings
    seen = {}

    def show(dialog):
        seen["mode"] = dialog.fields.editors["mode"].get()
        return wx.ID_CANCEL

    monkeypatch.setattr(configdialog.ConfigDialog, "ShowModal", show)
    frame.run_tool(tools.get("Concatenate"))
    assert seen["mode"] == "horizontal"


def test_save_and_load_settings(frame, monkeypatch, tmp_path):
    import json

    from flim.configs import KMeansConfig
    from flim.core.settings import SETTINGS_VERSION

    frame.settings.tool_settings.set(tools.get("K-Means"), KMeansConfig(n_clusters=5))
    frame.settings.import_.delimiter = ","  # e.g. by the import dialog
    path = tmp_path / "settings.json"
    frame.save_settings(path)
    assert json.loads(path.read_text())["schema_version"] == SETTINGS_VERSION

    frame.settings.tool_settings.tools.clear()
    frame.load_settings(path)
    assert frame.settings.import_.delimiter == ","
    assert frame.settings.tool_settings.config(tools.get("K-Means")).n_clusters == 5
