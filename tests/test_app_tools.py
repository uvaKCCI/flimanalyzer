"""Running tools from the main window (registry, generated dialogs, settings)."""

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")

from flim.core.registry import tools  # noqa: E402
from flim.gui.configdialog import shown_in_gui  # noqa: E402


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

    frame = AppFrame(FLIMAnalyzer())
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
        "Monitor",
        "Window",
        "Help",
    ]
    file_menu = menubar.GetMenu(0)
    EXIT = "Quit" if wx.Platform == "__WXMAC__" else "Exit"  # wx.ID_EXIT's label
    # without the submenus of workflow files that other tests may have registered
    assert [
        i.GetItemLabelText() for i in file_menu.GetMenuItems()
        if not i.IsSeparator() and not i.GetSubMenu()
    ] == [
        "Open Tables...", "Import Tables...", "Save All Windows...", "Import Settings...",
        "Export Settings...", "Favorites...", "Settings...",
        EXIT,
    ]
    data_menu = menubar.GetMenu(titles.index("Data"))
    assert [i.GetItemLabelText() for i in data_menu.GetMenuItems()] == [
        t.name for t in tools.by_category()["Data"]
        if getattr(t, "definition", None) is None and shown_in_gui(t)
    ]
    assert "Import" not in [i.GetItemLabelText() for i in data_menu.GetMenuItems()]


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
    saved = frame.settings.tools.config(tools.get("Summarize"))
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
    assert frame.settings.tools.entry(tools.get("Summarize")) is None


def test_autosave(frame, monkeypatch, prefect_harness, tmp_path):
    def change(dialog):
        dialog.fields.editors["features"].set(["x"])
        dialog.autosave.SetValue(True)
        dialog.use_default.SetValue(False)  # a folder of the tool's own
        dialog._follow_default()
        dialog.folder.SetPath(str(tmp_path))

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Sort"))
    assert any(tmp_path.rglob("*Sort*"))
    entry = frame.settings.tools.entry(tools.get("Sort"))
    assert entry.autosave.enabled and entry.autosave.results_dir == tmp_path


def test_a_tool_follows_the_default_folder(frame, monkeypatch, prefect_harness, tmp_path):
    default = tmp_path / "default"
    frame.make_default_folder(default)

    def change(dialog):
        dialog.fields.editors["features"].set(["x"])
        dialog.autosave.SetValue(True)
        assert dialog.use_default.GetValue() and not dialog.folder.IsEnabled()
        assert dialog.folder.GetPath() == str(default)

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Sort"))
    assert any(default.rglob("*Sort*"))  # saved in the default folder
    entry = frame.settings.tools.entry(tools.get("Sort"))
    assert entry.autosave.enabled and entry.autosave.results_dir is None  # follows it
    # a new default: the tool follows it
    later = tmp_path / "later"
    frame.make_default_folder(later)
    answer_dialog(monkeypatch, lambda dialog: None)
    frame.run_tool(tools.get("Sort"))
    assert any(later.rglob("*Sort*"))


def test_make_default_folder_in_the_dialog(frame, monkeypatch, prefect_harness, tmp_path):
    own = tmp_path / "own"
    own.mkdir()

    def change(dialog):
        dialog.fields.editors["features"].set(["x"])
        dialog.autosave.SetValue(True)
        dialog.use_default.SetValue(False)
        dialog._follow_default()
        dialog.folder.SetPath(str(own))
        dialog.validate()  # as the folder field's change event does
        assert dialog.make_default.IsEnabled()
        dialog._make_default()
        assert dialog.use_default.GetValue() and not dialog.make_default.IsEnabled()

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Sort"))
    assert frame.settings.results_dir == own
    assert frame.settings.tools.entry(tools.get("Sort")).autosave.results_dir is None


def test_run_a_tool_with_a_custom_editor(frame, monkeypatch, prefect_harness):
    def change(dialog):
        dialog.fields.editors["categories"].view.set({"Treatment": ["Ctrl"]})

    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Filter"))
    (results,) = frame.shown
    assert set(results["Table: Filtered"]["Treatment"]) == {"Ctrl"}


def test_a_tools_warnings_are_shown_after_its_run(frame, monkeypatch, prefect_harness):
    # Calculate warns when a calculation replaces an input column
    from flim.configs.data import ExpressionCalculation

    def change(dialog):
        replace_x = ExpressionCalculation(name="x", expression="y * 2")
        dialog.fields.editors["calculations"].set([replace_x])

    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, title, *a, **k: shown.append((title, message)))
    answer_dialog(monkeypatch, change)
    frame.run_tool(tools.get("Calculate"))
    (results,) = frame.shown
    assert list(results["Table: Calculated"]["x"]) == list(results["Table: Calculated"]["y"] * 2)
    assert len(shown) == 1
    title, message = shown[0]
    assert title == "Calculate: warning" and "x: the input column is replaced" in message


def test_documentation_of_this_version():
    from flim.gui.app import docs_url

    assert docs_url("0.6.1") == "https://flimanalyzer.readthedocs.io/en/v0.6.1/"
    for development in ("0.7.0.dev3+g1a2b3c4", "0.6.1.post3+g1a2b3c4", "0.6.1+d20261103", "0.7.0rc1"):
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


def test_axis_dialog_is_destroyed_after_use(frame, monkeypatch):
    from types import SimpleNamespace

    import matplotlib.figure

    import flim.gui.app as app

    ax = matplotlib.figure.Figure().subplots()
    destroyed = []

    class Dialog:
        def __init__(self, parent, title, settings):
            self.settings = settings

        def ShowModal(self):
            return wx.ID_OK

        def get_settings(self):
            return self.settings

        def Destroy(self):
            destroyed.append(True)

    monkeypatch.setattr(app, "ConfigureAxisDlg", Dialog)
    monkeypatch.setattr(frame, "_plot_edited", lambda fig: None)
    for axis in (ax.yaxis, ax.xaxis):
        frame.OnPick(SimpleNamespace(artist=axis, mouseevent=SimpleNamespace(dblclick=True)))
    assert destroyed == [True, True]
