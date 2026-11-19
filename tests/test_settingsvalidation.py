"""The GUI's dialogs about settings files (flim.gui.settingsvalidation): the box that
says why a file is not used, in Settings > Import Settings... and in tool dialogs; the
questions before a tool's settings are saved into an older file; the start dialog."""

import json
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

import flim.tools  # noqa: E402, F401  (registers the tools: tool settings are checked)
from flim.core.settings import validate_settings_file  # noqa: E402
from flim.gui import settingsvalidation  # noqa: E402

MIXED = {
    "schema_version": 1,
    "working_dir": "res",
    "bogus_section": 3,
    "execution": {"executor": "ray"},
    "tools": {"Summarize": {"config": {"aggs": ["count"], "nope": 1}}},
}
CLEAN = {"schema_version": 2, "results_dir": "other"}


@pytest.fixture
def table():
    import pandas as pd

    return pd.DataFrame({"Treatment": pd.Categorical(["Ctrl", "Drug"]), "x": [1.0, 2.0]})


def write(tmp_path, content, name="settings.json"):
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


@pytest.fixture
def answers(monkeypatch, wxapp):
    """Answers the dialogs in order: an option of the choice (or None for Cancel),
    True/False for the confirmation, a path (or None) for the file dialog. Records the
    choices offered."""
    queue, offered = [], []

    class Choice:
        def __init__(self, parent, message, caption, choices):
            offered.append((message, list(choices)))
            self.choices = list(choices)
            self.answer = queue.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ShowModal(self):
            return wx.ID_CANCEL if self.answer is None else wx.ID_OK

        def GetSelection(self):
            return self.choices.index(self.answer)

    monkeypatch.setattr(settingsvalidation.wx, "SingleChoiceDialog", Choice)
    monkeypatch.setattr(settingsvalidation, "_save_file", lambda parent: queue.pop(0))
    return queue, offered


@pytest.fixture
def boxes(monkeypatch, wxapp):
    """The message boxes shown (message, title, style), answered with OK."""
    shown = []
    monkeypatch.setattr(
        settingsvalidation.wx, "MessageBox", lambda message, title, style, parent=None: shown.append((message, title, style))
    )
    return shown


def test_a_file_with_settings_that_cant_be_used_is_a_warning(tmp_path, boxes):
    path = write(tmp_path, MIXED)
    settingsvalidation.show_problems(validate_settings_file(path), outcome="Nothing is loaded.")
    ((message, title, style),) = boxes
    assert "bogus_section" in message and "Nothing is loaded." in message
    assert f"flimsettings app --validate {path} lists every problem" in message
    assert style & wx.ICON_WARNING and not style & wx.ICON_ERROR


def test_the_validate_command_is_that_of_the_file_kind(tmp_path):
    """The box names the command that validates the file."""
    tool_file = tmp_path / "tool.json"
    tool_file.write_text('{"schema_version": 2, "tool": "Summarize", "config": {}}')
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"schema_version": 2, "name": "w", "steps": []}')
    app = write(tmp_path, MIXED)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    for path, kind in ((tool_file, "tool"), (workflow, "workflow"), (app, "app"), (broken, "app")):
        assert settingsvalidation.validate_command(path) == f"flimsettings {kind} --validate {path}"


def test_a_file_that_cant_be_used_is_an_error(tmp_path, boxes):
    settingsvalidation.show_problems(validate_settings_file(write(tmp_path, "{not json")))
    assert boxes[0][2] & wx.ICON_ERROR


# --- where the GUI reads settings files ---


@pytest.fixture
def frame(wxapp, monkeypatch, tmp_path):
    from flim.core.settingsmgr import SettingsManager, UserSettingsFile
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)
    frame = AppFrame(
        FLIMAnalyzer(), SettingsManager(user_file=UserSettingsFile(tmp_path / "user.json"))
    )
    yield frame
    frame.Destroy()


def test_import_settings_refuses_a_file_with_problems(frame, tmp_path, boxes):
    frame.load_settings(write(tmp_path, MIXED))
    assert len(boxes) == 1 and "Nothing is imported." in boxes[0][0]
    assert frame.settings.results_dir is None and frame.settings_manager.source is None


def test_import_settings_without_problems_shows_nothing(frame, tmp_path, boxes):
    frame.load_settings(write(tmp_path, CLEAN))
    assert boxes == [] and frame.settings.results_dir == Path("other")


def test_tool_dialog_refuses_only_for_its_own_problems(dialog, tmp_path, boxes):
    path = write(tmp_path, MIXED)
    # K-Means has no settings in the file: the problems of other sections don't matter
    assert not dialog("K-Means").load_settings(str(path))
    assert boxes == []
    d = dialog("Summarize")
    assert not d.load_settings(str(path))
    assert len(boxes) == 1 and "Nothing is loaded." in boxes[0][0]


# --- a tool dialog's Save Settings... ---

OLD = {"schema_version": 1, "working_dir": "res", "bogus": 1}


def test_tool_save_asks_before_rewriting_an_older_file(dialog, tmp_path, answers):
    queue, offered = answers
    path = write(tmp_path, OLD)
    queue.append(None)  # Cancel
    d = dialog("Summarize")
    assert not d.save_settings(str(path))
    assert json.loads(path.read_text()) == OLD
    queue.append(settingsvalidation.REWRITE)
    assert d.save_settings(str(path))
    data = json.loads(path.read_text())
    assert data["schema_version"] == 2 and data["results_dir"] == "res"
    assert "bogus" not in data and "Summarize" in data["tools"]
    assert "working_dir to results_dir" in offered[0][0]


def test_tool_save_to_another_file(dialog, tmp_path, answers):
    queue, _ = answers
    path = write(tmp_path, OLD)
    other = tmp_path / "other.json"
    queue += [settingsvalidation.SAVE_OTHER, str(other)]
    assert dialog("Summarize").save_settings(str(path))
    assert json.loads(path.read_text()) == OLD
    assert json.loads(other.read_text())["tool"] == "Summarize"  # a new file: a tool file


def test_tool_save_to_a_current_file_does_not_ask(dialog, tmp_path, answers):
    _, offered = answers
    path = write(tmp_path, CLEAN)
    assert dialog("Summarize").save_settings(str(path))
    data = json.loads(path.read_text())
    assert offered == [] and data["results_dir"] == "other" and "Summarize" in data["tools"]


# --- File > Settings... ---


def test_settings_viewer_shows_each_setting(frame):
    from flim.gui.settingsview import COLUMNS, SettingsViewer

    viewer = SettingsViewer(frame, frame.settings_manager)
    try:
        table = viewer.table
        assert table.GetColumnCount() == len(COLUMNS)
        titles = [table.GetItemText(i, 0) for i in range(table.GetItemCount())]
        assert titles == ["Results folder", "Executor", "Prefect server", "Server timeout",
                          "Log folder"]
        assert table.GetItemText(1, 1) == "local, workers: automatic"
        assert table.GetItemText(1, 2) == "built-in default"
        assert "User settings file:" in viewer.files.GetLabel()
    finally:
        viewer.Destroy()


def test_file_menu_has_settings(frame):
    item = frame.GetMenuBar().FindItemById(wx.ID_PREFERENCES)
    assert item is not None and item.GetItemLabelText() == "Settings..."


def _startup_dialog(files, default=None, warning=None):
    return settingsvalidation.StartupSettingsDialog(None, files, default, warning)


def test_startup_dialog_preselects_the_default(wxapp, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    d = _startup_dialog([a, b], default=b)
    try:
        # columns: Default, File, Description, Folder
        assert d.table.GetItemCount() == 2 and d.table.GetColumnCount() == 4
        assert d.rows()[1] == (settingsvalidation.DEFAULT_MARK, "b.json", "", str(tmp_path))
        assert d.selected() == b and d.ok.IsEnabled()
        assert d.GetDefaultItem() is d.ok  # Enter: start with the default
        assert not d.make_default.IsEnabled()  # already the default
        assert d.result(wx.ID_OK) == settingsvalidation.Pick(b, b)
        assert d.result(wx.ID_CANCEL) == settingsvalidation.Pick(None, b)  # skipped
    finally:
        d.Destroy()


def test_startup_dialog_without_default_selects_nothing(wxapp, tmp_path):
    a = tmp_path / "a.json"
    d = _startup_dialog([a])
    try:
        assert d.selected() is None and not d.ok.IsEnabled()
        assert d.GetDefaultItem() is d.skip  # Enter: skip
        assert d.skip.GetLabel() == settingsvalidation.SKIP and d.skip.GetId() == wx.ID_CANCEL
        assert not d.make_default.IsEnabled() and not d.clear.IsEnabled()
        assert d.result(wx.ID_CANCEL) == settingsvalidation.Pick(None, None)
        d.select(0)
        assert d.ok.IsEnabled() and d.result(wx.ID_OK) == settingsvalidation.Pick(a, None)
    finally:
        d.Destroy()


def test_startup_dialog_makes_another_file_the_default(wxapp, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    d = _startup_dialog([a, b], default=b)
    try:
        d.select(0)
        assert d.selected() == a and d.make_default.IsEnabled()
        assert d.result(wx.ID_OK) == settingsvalidation.Pick(a, b)  # selecting: unchanged
        d._on_make_default(None)
        assert [d.table.GetItemText(i, 0) for i in range(2)] == [
            settingsvalidation.DEFAULT_MARK, ""
        ]  # the check mark moves at once
        assert not d.make_default.IsEnabled() and d.selected() == a
        assert d.result(wx.ID_OK) == settingsvalidation.Pick(a, a)
        assert d.result(wx.ID_CANCEL) == settingsvalidation.Pick(None, a)  # also when skipped
    finally:
        d.Destroy()


def test_startup_dialog_clears_the_default(wxapp, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    d = _startup_dialog([a, b], default=b)
    try:
        d._on_clear(None)
        assert not d.clear.IsEnabled() and d.table.GetItemText(1, 0) == ""
        assert d.result(wx.ID_OK) == settingsvalidation.Pick(b, None)
        assert d.result(wx.ID_CANCEL) == settingsvalidation.Pick(None, None)  # also skipped
    finally:
        d.Destroy()


def test_startup_dialog_lists_a_default_outside_the_search_path(wxapp, tmp_path):
    lab = tmp_path / "lab" / "lab.json"
    d = _startup_dialog([tmp_path / "a.json"], default=lab)
    try:
        assert d.files[0] == lab and d.selected() == lab
    finally:
        d.Destroy()


# --- Export Settings...: the folder and the app settings search path ---


@pytest.mark.parametrize("answer, added", [(wx.ID_YES, True), (wx.ID_NO, False)])
def test_export_offers_the_folder_for_the_search_path(frame, tmp_path, monkeypatch, answer, added):
    monkeypatch.delenv("FLIM_APP_SETTINGS_PATH", raising=False)
    asked = []

    def show(dialog):
        asked.append(dialog.GetMessage())
        return answer

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", show)
    path = tmp_path / "lab" / "cells.json"
    path.parent.mkdir()
    frame.save_settings(path)
    assert frame.offer_search_path(path) is added
    assert str(path.parent) in asked[0]
    folders = [p.resolve() for p in frame.settings.appsettings_path]
    assert (path.parent.resolve() in folders) is added
    if added:  # not asked again for a folder already in the search path
        assert not frame.offer_search_path(path) and len(asked) == 1


def test_old_import_settings_are_offered_as_a_workflow_file(wxapp, tmp_path, monkeypatch):
    import json

    from flim.core.registry import tools
    from flim.core.settings import validate_settings_file
    from flim.core.settingsmgr import SettingsManager
    from flim.gui.settingsvalidation import offer_import_workflow

    data = json.loads((Path(__file__).parent / "core" / "data" / "settings_v1.json").read_text())
    path = tmp_path / "lab.json"
    path.write_text(json.dumps(data))
    validation = validate_settings_file(path)
    manager = SettingsManager()
    manager.update({"workflow_paths": [str(tmp_path / "workflows")]})
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)
    assert offer_import_workflow(validation, None, manager) is None  # Don't Save: nothing written
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_YES)
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(tmp_path / "workflows" / "lab-import.json"))
    try:
        saved = offer_import_workflow(validation, None, manager)
        assert saved == tmp_path / "workflows" / "lab-import.json" and saved.exists()
        assert "Import (lab)" in tools  # offered by File > Import Tables... at once
        from flim.tools.readers import ImportTables

        # Import Tables runs it next
        assert manager.settings.tools.config(ImportTables).workflow == "Import (lab)"
    finally:
        tools.unregister("Import (lab)")


def test_startup_dialog_shows_the_descriptions(wxapp, tmp_path):
    import json

    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"schema_version": 2, "description": "Course 2026"}))
    b.write_text("not json")
    d = _startup_dialog([a, b], default=None)
    try:
        column = settingsvalidation.STARTUP_COLUMNS.index("Description")
        assert [d.table.GetItemText(i, column) for i in range(2)] == ["Course 2026", ""]
    finally:
        d.Destroy()


def test_user_settings_file_starts_with_the_version_and_description(tmp_path):
    import json

    from flim.core.settingsmgr import UserSettingsFile

    path = tmp_path / "usersettings.json"
    path.write_text(json.dumps({"tools": {}, "description": "mine", "schema_version": 2}))
    UserSettingsFile(path).merge({"results_dir": "/data"})
    assert list(json.loads(path.read_text()))[:2] == ["schema_version", "description"]


@pytest.mark.parametrize("answer, added", [(wx.ID_YES, True), (wx.ID_NO, False)])
def test_startup_dialog_browses_for_a_file_and_offers_its_folder(wxapp, tmp_path, monkeypatch, answer, added):
    listed, other = tmp_path / "appsettings", tmp_path / "course"
    listed.mkdir()
    other.mkdir()
    a, course = listed / "a.json", other / "course.json"
    d = settingsvalidation.StartupSettingsDialog(None, [a], None, search_path=[listed])
    try:
        monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
        monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(course))
        asked = []
        monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: asked.append(dlg.GetMessage()) or answer)
        d._on_browse(None)
        assert d.files == [a, course] and d.selected() == course and d.ok.IsEnabled()
        assert str(other.resolve()) in asked[0]
        assert d.result(wx.ID_OK) == settingsvalidation.Pick(course, None, other.resolve() if added else None)
        monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(a))
        d._on_browse(None)  # a file in the search path: listed once, no question
        assert d.files == [a, course] and d.selected() == a and len(asked) == 1
    finally:
        d.Destroy()


@pytest.mark.parametrize("answer, updated", [(wx.ID_YES, True), (wx.ID_NO, False)])
def test_offer_update_asks_and_keeps_the_original(tmp_path, monkeypatch, wxapp, answer, updated):
    import shutil

    data = Path(__file__).parent / "core" / "data" / "settings_v1.json"
    path = tmp_path / "lab.json"
    shutil.copy(data, path)
    asked = []
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: asked.append(dlg.GetMessage()) or answer)
    assert settingsvalidation.offer_update(validate_settings_file(path)) is updated
    assert "older FLIMAnalyzer version (schema 1)" in asked[0] and "lab.v1.json" in asked[0]
    assert (tmp_path / "lab.v1.json").exists() is updated
    asked.clear()
    if updated:  # current now: not asked again
        assert not settingsvalidation.offer_update(validate_settings_file(path)) and asked == []
