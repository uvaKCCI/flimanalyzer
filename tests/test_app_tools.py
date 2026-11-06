"""Running tools from the application window (registry, generated dialogs, settings)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

from flim.core.registry import tools  # noqa: E402


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
        "Data",
        "Analysis",
        "Plot",
        "Workflow",
        "Window",
        "Help",
    ]
    file_menu = menubar.GetMenu(0)
    EXIT = "Quit" if wx.Platform == "__WXMAC__" else "Exit"  # wx.ID_EXIT's label
    assert [i.GetItemLabelText() for i in file_menu.GetMenuItems() if not i.IsSeparator()] == [
        "Open...", "Import...", "Import Settings...", "Export Settings...", EXIT
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


def test_documentation_of_this_version():
    from flim.gui.app import docs_url

    assert docs_url("0.6.1") == "https://flimanalyzer.readthedocs.io/en/v0.6.1/"
    for development in ("0.6.1.post3+g1a2b3c4", "0.6.1+d20261103", "0.7.0rc1"):
        assert docs_url(development) == "https://flimanalyzer.readthedocs.io/en/latest/"


def test_help_documentation_opens_this_versions_docs(frame, monkeypatch):
    from flim.gui import app

    opened = []
    monkeypatch.setattr(app.wx, "LaunchDefaultBrowser", opened.append)
    frame.OnDocumentation(None)
    assert opened == [app.docs_url()]


@pytest.mark.parametrize("answer, changed", [(wx.ID_CANCEL, False), (wx.ID_OK, True)])
def test_line_color_changes_only_on_ok(frame, monkeypatch, answer, changed):
    # double-clicking a line opens a color dialog; Cancel keeps the color (#188)
    from types import SimpleNamespace

    import matplotlib.figure

    (line,) = matplotlib.figure.Figure().subplots().plot([0, 1], color="blue")
    shown = []

    class Dialog:
        def __init__(self, parent, data):
            self.data = data

        def ShowModal(self):
            self.data.SetColour(wx.Colour(255, 0, 0))
            return answer

        def GetColourData(self):
            return self.data

        def Destroy(self):
            shown.append("destroyed")

    monkeypatch.setattr(wx, "ColourDialog", Dialog)
    event = SimpleNamespace(artist=line, mouseevent=SimpleNamespace(dblclick=True))
    frame.OnPick(event)
    assert (line.get_color() == (1.0, 0.0, 0.0)) == changed
    assert shown == ["destroyed"]
