"""Data window and main window features, driven as a user would (file dialogs and
group selections are answered by the test)."""

import pandas as pd
import pytest

wx = pytest.importorskip("wx")

FEATURE = "NAD(P)H t1"


@pytest.fixture
def frame(wxapp, monkeypatch):
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)  # never wait
    frame = AppFrame(FLIMAnalyzer())
    yield frame
    for window in frame.windowframes.values():
        if hasattr(window, "modified"):
            window.modified = False
    frame.OnCloseAll(None)
    frame.Destroy()


def _open(frame, data, title="Data"):
    from flim.gui.events import EVT_DATA_TYPE, DataWindowEvent

    event = DataWindowEvent(EVT_DATA_TYPE, frame.GetId())
    event.SetEventInfo(data, title, "createnew", modified=False)
    frame.GetEventHandler().ProcessEvent(event)
    return frame.windowframes[title]


def _answer_group_dialogs(monkeypatch, *answers):
    """SelectGroupsDlg: OK, with the given selections in order."""
    from flim.gui.dialogs import SelectGroupsDlg

    answers = list(answers)
    monkeypatch.setattr(SelectGroupsDlg, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(SelectGroupsDlg, "get_selected", lambda dlg: list(answers.pop(0)))


def _answer_file_dialog(monkeypatch, path):
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(path))


def _set_import_files(frame, files):
    """Sets the files of the import dialog, as the dialog does (for this session)."""
    imported = frame.settings.import_.model_dump(mode="json", by_alias=True)
    frame.settings_manager.update({"import": {**imported, "include_files": files}}, keep=False)


def _new_windows(frame, before):
    return {t: w for t, w in frame.windowframes.items() if t not in before}


def test_pivot(frame, monkeypatch, flim_data):
    window = _open(frame, flim_data)
    _answer_group_dialogs(monkeypatch, ["Treatment"], [FEATURE])
    before = set(frame.windowframes)
    window.pivot_(window.GetViewData())
    (pivoted,) = _new_windows(frame, before).values()
    table = pivoted.GetViewData()
    assert {f"{FEATURE}\nWT", f"{FEATURE}\nKO"} <= set(table.columns)
    assert len(table) == 30  # one row per FOV and cell


def test_range_filter_and_view_all(frame, flim_data):
    window = _open(frame, flim_data)
    low, high = flim_data[FEATURE].quantile([0.25, 0.75])
    window.apply_filters({FEATURE: {"name": FEATURE, "rangelow": low, "rangehigh": high, "selected": True}})
    expected = flim_data[FEATURE].between(low, high).sum()
    assert len(window.GetViewData()) == expected < len(flim_data)
    assert window.is_modified()
    window.OnViewAll(None)
    assert len(window.GetViewData()) == len(flim_data)


@pytest.mark.parametrize("button", ["Save View", "Save All"])
def test_save_renames_the_window(frame, monkeypatch, tmp_path, flim_data, button):
    window = _open(frame, flim_data.copy())
    window.modified = True
    path = tmp_path / "saved.txt"
    _answer_file_dialog(monkeypatch, path)

    class Button:
        def GetLabel(self):
            return button

    class Event:
        def GetEventObject(self):
            return Button()

    window.OnSave(Event())
    saved = pd.read_table(path)
    assert len(saved) == len(flim_data) and FEATURE in saved.columns
    assert not window.is_modified()
    assert "saved.txt" in frame.windowframes  # renamed after the file


def test_saving_keeps_the_window_columns(frame, monkeypatch, tmp_path, flim_data):
    data = flim_data.rename(columns={FEATURE: "NAD(P)H\nt1"})  # e.g. a pivoted table
    window = _open(frame, data)
    _answer_file_dialog(monkeypatch, tmp_path / "pivot.txt")
    from flim.gui.dialogs import save_dataframe

    save_dataframe(window, "Save", window.data, "pivot.txt")
    assert "NAD(P)H t1" in pd.read_table(tmp_path / "pivot.txt").columns  # one line in the file
    assert "NAD(P)H\nt1" in window.data.columns  # the data shown is unchanged


def test_precision_and_autosize(frame, flim_data):
    window = _open(frame, flim_data)
    window.update_precision(5)
    assert window.precision == 5
    window.OnAutosize(None)
    grid = window.grid
    assert grid.GetNumberCols() == len(flim_data.columns)
    assert all(grid.GetColSize(i) > 0 for i in range(grid.GetNumberCols()))


def test_save_and_load_settings(frame, monkeypatch, tmp_path):
    import json

    from flim.configs import KMeansConfig
    from flim.core.registry import tools
    from flim.core.settings import SETTINGS_VERSION

    path = tmp_path / "settings.json"
    manager = frame.settings_manager
    imported = frame.settings.import_.model_dump(mode="json", by_alias=True)
    manager.update({"import": {**imported, "delimiter": ";"}}, keep=False)
    manager.set_tool(tools.get("K-Means"), KMeansConfig(n_clusters=5))
    _answer_file_dialog(monkeypatch, path)
    frame.OnSaveSettings(None)
    assert json.loads(path.read_text())["schema_version"] == SETTINGS_VERSION

    manager.update({"import": {**imported, "delimiter": "\t"}, "tools": {}}, keep=False)
    manager.set_tool(tools.get("K-Means"), KMeansConfig(n_clusters=2))
    frame.OnLoadSettings(None)
    assert frame.settings.import_.delimiter == ";"
    assert frame.settings.tool_settings.config(tools.get("K-Means")).n_clusters == 5


def test_import_several_files(frame, monkeypatch, tmp_path, flim_data):
    from flim.gui.importdlg import ImportDlg

    files = []
    for name, part in (("Results_FOV1_WT_1.txt", flim_data.iloc[:10]), ("Results_FOV2_KO_2.txt", flim_data.iloc[10:25])):
        path = tmp_path / name
        part.drop(columns=["Treatment", "FOV", "Cell"]).to_csv(path, sep="\t", index=False)
        files.append(str(path))
    _set_import_files(frame, files)
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    before = set(frame.windowframes)
    frame.OnImportData(None)
    (title, window), = _new_windows(frame, before).items()
    assert title == "Imported Data"
    assert len(window.GetViewData()) == 25


def test_import_with_no_readable_files(frame, monkeypatch, tmp_path):
    from flim.gui.importdlg import ImportDlg

    _set_import_files(frame, [str(tmp_path / "gone.txt")])
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    messages = []
    monkeypatch.setattr(wx, "MessageBox", lambda m, *a, **k: messages.append(m))
    before = set(frame.windowframes)
    frame.OnImportData(None)
    assert _new_windows(frame, before) == {} and messages


def test_open_file_of_an_open_windows_name_opens_a_new_window(frame, tmp_path):
    """A file named like an open window (data.txt from another folder) gets its own
    window; the open one keeps its data and unsaved changes (were replaced, R1)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    pd.DataFrame({"x": [1.0, 2.0, 3.0]}).to_csv(tmp_path / "a" / "data.txt", sep="\t", index=False)
    pd.DataFrame({"x": [9.0]}).to_csv(tmp_path / "b" / "data.txt", sep="\t", index=False)
    assert frame.open_data_files([str(tmp_path / "a" / "data.txt")]) == "data.txt"
    first = frame.windowframes["data.txt"]
    first.modified = True  # changed, not saved

    assert frame.open_data_files([str(tmp_path / "b" / "data.txt")]) == "data.txt-1"
    assert frame.windowframes["data.txt"] is first
    assert len(first.GetViewData()) == 3 and first.is_modified()
    assert len(frame.windowframes["data.txt-1"].GetViewData()) == 1
    first.modified = False


def test_import_again_opens_a_new_window(frame, monkeypatch, tmp_path, flim_data):
    from flim.gui.importdlg import ImportDlg

    files = []
    for name, part in (("Results_FOV1_WT_1.txt", flim_data.iloc[:10]), ("Results_FOV2_KO_2.txt", flim_data.iloc[10:25])):
        path = tmp_path / name
        part.drop(columns=["Treatment", "FOV", "Cell"]).to_csv(path, sep="\t", index=False)
        files.append(str(path))
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    _set_import_files(frame, files)
    frame.OnImportData(None)
    first = frame.windowframes["Imported Data"]
    first.modified = True  # changed, not saved
    frame.OnImportData(None)  # the same files again
    assert frame.windowframes["Imported Data"] is first and first.is_modified()
    assert len(frame.windowframes["Imported Data-1"].GetViewData()) == 25


def test_filter_changes_reach_the_user_settings_file(wxapp, monkeypatch, tmp_path, flim_data):
    import json

    from flim.core.settingsmgr import SettingsManager, UserSettingsFile
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)  # never wait
    path = tmp_path / "settings.json"
    frame = AppFrame(FLIMAnalyzer(), SettingsManager(user_file=UserSettingsFile(path)))
    try:
        window = _open(frame, flim_data)

        class Checked:  # the filter checkbox's event: checked
            def GetEventObject(self):
                return self

            def GetValue(self):
                return True

        window.OnFilterData(Checked())
        assert json.loads(path.read_text())["filters"]["use"] is True
        assert frame.settings.filters.use is True
    finally:
        frame.OnCloseAll(None)
        frame.Destroy()
