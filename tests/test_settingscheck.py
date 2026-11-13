"""The choice the GUI offers when some settings of a settings file cannot be used
(flim.gui.settingscheck), in File > Load Settings... and in tool dialogs."""

import json
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

import flim.tools  # noqa: E402, F401  (registers the tools: tool settings are checked)
from flim.core.settings import check_settings_file  # noqa: E402
from flim.gui import settingscheck  # noqa: E402

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

    monkeypatch.setattr(settingscheck.wx, "SingleChoiceDialog", Choice)
    monkeypatch.setattr(settingscheck, "_confirm_update", lambda check, parent: queue.pop(0))
    monkeypatch.setattr(settingscheck, "_other_file", lambda parent: queue.pop(0))
    monkeypatch.setattr(settingscheck, "_save_file", lambda parent: queue.pop(0))
    return queue, offered


def test_use_what_can_be_used(tmp_path, answers):
    queue, offered = answers
    queue.append(settingscheck.USE)
    check = check_settings_file(write(tmp_path, MIXED))
    assert settingscheck.choose_settings(check) is check
    message, options = offered[0]
    assert "bogus_section" in message and "working_dir to results_dir" in message
    assert options == [settingscheck.USE, settingscheck.IGNORE, settingscheck.UPDATE,
                       settingscheck.OTHER]


@pytest.mark.parametrize("answer", [settingscheck.IGNORE, None])  # None: Cancel
def test_dont_use_the_file(tmp_path, answers, answer):
    queue, _ = answers
    queue.append(answer)
    assert settingscheck.choose_settings(check_settings_file(write(tmp_path, MIXED))) is None


def test_update_the_file_after_confirmation(tmp_path, answers):
    queue, offered = answers
    path = write(tmp_path, MIXED)
    queue += [settingscheck.UPDATE, False, settingscheck.UPDATE, True]
    check = settingscheck.choose_settings(check_settings_file(path))
    assert len(offered) == 2  # not confirmed: asked again
    data = json.loads(path.read_text())
    assert data == {"schema_version": 2, "results_dir": "res", "tools": {}}
    assert check.path == path and not check.problems and check.converted == []


def test_another_file_is_checked_the_same_way(tmp_path, answers):
    queue, offered = answers
    broken = write(tmp_path, "{not json", "broken.json")
    clean = write(tmp_path, CLEAN, "clean.json")
    queue += [settingscheck.OTHER, str(broken), settingscheck.OTHER, None,
              settingscheck.OTHER, str(clean)]
    check = settingscheck.choose_settings(check_settings_file(write(tmp_path, MIXED)))
    assert check.path == clean
    # the broken file offers no settings to use or keep
    assert offered[1][1] == [settingscheck.IGNORE, settingscheck.OTHER]
    assert len(offered) == 3  # file dialog cancelled: asked again


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


def test_load_settings_asks_for_a_file_with_problems(frame, tmp_path, answers):
    queue, offered = answers
    queue.append(settingscheck.USE)
    path = write(tmp_path, MIXED)
    frame.load_settings(path)
    assert len(offered) == 1
    assert frame.settings.results_dir == Path("res")
    assert frame.settings_manager.source == path


def test_load_settings_without_problems_does_not_ask(frame, tmp_path, answers):
    _, offered = answers
    frame.load_settings(write(tmp_path, CLEAN))
    assert offered == [] and frame.settings.results_dir == Path("other")


def test_load_settings_not_used(frame, tmp_path, answers):
    queue, _ = answers
    queue.append(settingscheck.IGNORE)
    frame.load_settings(write(tmp_path, MIXED))
    assert frame.settings.results_dir is None and frame.settings_manager.source is None


def test_tool_dialog_asks_only_for_its_own_problems(dialog, tmp_path, answers):
    queue, offered = answers
    path = write(tmp_path, MIXED)
    # K-Means has no settings in the file: the problems of other sections don't matter
    assert not dialog("K-Means").load_settings(str(path))
    assert offered == []
    queue.append(settingscheck.IGNORE)
    d = dialog("Summarize")
    assert not d.load_settings(str(path))
    assert len(offered) == 1


def test_tool_dialog_uses_another_file(dialog, tmp_path, answers):
    from flim.core.settings import save_sections

    queue, _ = answers
    other = tmp_path / "other.json"
    save_sections(
        {"tools": {"Summarize": {"config": {"aggs": ["count"]}, "autosave": {"enabled": False}}}},
        other,
    )
    queue += [settingscheck.OTHER, str(other)]
    d = dialog("Summarize")
    assert d.load_settings(str(write(tmp_path, MIXED)))
    assert d.result().config.aggs == ["count"]
    assert "other.json" in d.settings_message.GetLabel()


# --- a tool dialog's Save Settings... ---

OLD = {"schema_version": 1, "working_dir": "res", "bogus": 1}


def test_tool_save_asks_before_rewriting_an_older_file(dialog, tmp_path, answers):
    queue, offered = answers
    path = write(tmp_path, OLD)
    queue.append(None)  # Cancel
    d = dialog("Summarize")
    assert not d.save_settings(str(path))
    assert json.loads(path.read_text()) == OLD
    queue.append(settingscheck.REWRITE)
    assert d.save_settings(str(path))
    data = json.loads(path.read_text())
    assert data["schema_version"] == 2 and data["results_dir"] == "res"
    assert "bogus" not in data and "Summarize" in data["tools"]
    assert "working_dir to results_dir" in offered[0][0]


def test_tool_save_to_another_file(dialog, tmp_path, answers):
    queue, _ = answers
    path = write(tmp_path, OLD)
    other = tmp_path / "other.json"
    queue += [settingscheck.SAVE_OTHER, str(other)]
    assert dialog("Summarize").save_settings(str(path))
    assert json.loads(path.read_text()) == OLD
    assert "Summarize" in json.loads(other.read_text())["tools"]


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
        assert titles == ["Results folder", "Executor", "Prefect server", "Log folder",
                          "Workflows: missing columns"]
        assert table.GetItemText(1, 1) == "local, workers: automatic"
        assert table.GetItemText(1, 2) == "built-in default"
        assert "User settings file:" in viewer.files.GetLabel()
    finally:
        viewer.Destroy()


def test_file_menu_has_settings(frame):
    item = frame.GetMenuBar().FindItemById(wx.ID_PREFERENCES)
    assert item is not None and item.GetItemLabelText() == "Settings..."


def _startup_dialog(files, default=None, warning=None):
    return settingscheck.StartupSettingsDialog(None, files, default, warning)


def test_startup_dialog_preselects_the_default(wxapp, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    d = _startup_dialog([a, b], default=b)
    try:
        # columns: Default, File, Description, Folder
        assert d.table.GetItemCount() == 2 and d.table.GetColumnCount() == 4
        assert d.rows()[1] == (settingscheck.DEFAULT_MARK, "b.json", "", str(tmp_path))
        assert d.selected() == b and d.ok.IsEnabled()
        assert d.GetDefaultItem() is d.ok  # Enter: start with the default
        assert not d.make_default.IsEnabled()  # already the default
        assert d.result(wx.ID_OK) == settingscheck.Pick(b, b)
        assert d.result(wx.ID_CANCEL) == settingscheck.Pick(None, b)  # skipped
    finally:
        d.Destroy()


def test_startup_dialog_without_default_selects_nothing(wxapp, tmp_path):
    a = tmp_path / "a.json"
    d = _startup_dialog([a])
    try:
        assert d.selected() is None and not d.ok.IsEnabled()
        assert d.GetDefaultItem() is d.skip  # Enter: skip
        assert d.skip.GetLabel() == settingscheck.SKIP and d.skip.GetId() == wx.ID_CANCEL
        assert not d.make_default.IsEnabled() and not d.clear.IsEnabled()
        assert d.result(wx.ID_CANCEL) == settingscheck.Pick(None, None)
        d.select(0)
        assert d.ok.IsEnabled() and d.result(wx.ID_OK) == settingscheck.Pick(a, None)
    finally:
        d.Destroy()


def test_startup_dialog_makes_another_file_the_default(wxapp, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    d = _startup_dialog([a, b], default=b)
    try:
        d.select(0)
        assert d.selected() == a and d.make_default.IsEnabled()
        assert d.result(wx.ID_OK) == settingscheck.Pick(a, b)  # selecting: unchanged
        d._on_make_default(None)
        assert [d.table.GetItemText(i, 0) for i in range(2)] == [
            settingscheck.DEFAULT_MARK, ""
        ]  # the check mark moves at once
        assert not d.make_default.IsEnabled() and d.selected() == a
        assert d.result(wx.ID_OK) == settingscheck.Pick(a, a)
        assert d.result(wx.ID_CANCEL) == settingscheck.Pick(None, a)  # also when skipped
    finally:
        d.Destroy()


def test_startup_dialog_clears_the_default(wxapp, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    d = _startup_dialog([a, b], default=b)
    try:
        d._on_clear(None)
        assert not d.clear.IsEnabled() and d.table.GetItemText(1, 0) == ""
        assert d.result(wx.ID_OK) == settingscheck.Pick(b, None)
        assert d.result(wx.ID_CANCEL) == settingscheck.Pick(None, None)  # also skipped
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
    from flim.core.settings import check_settings_file
    from flim.core.settingsmgr import SettingsManager
    from flim.gui.settingscheck import offer_import_workflow

    data = json.loads((Path(__file__).parent / "core" / "data" / "settings_v1.json").read_text())
    path = tmp_path / "lab.json"
    path.write_text(json.dumps(data))
    check = check_settings_file(path)
    manager = SettingsManager()
    manager.update({"workflow_paths": [str(tmp_path / "workflows")]})
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)
    assert offer_import_workflow(check, None, manager) is None  # Don't Save: nothing written
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_YES)
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(tmp_path / "workflows" / "lab-import.json"))
    try:
        saved = offer_import_workflow(check, None, manager)
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
        column = settingscheck.STARTUP_COLUMNS.index("Description")
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
