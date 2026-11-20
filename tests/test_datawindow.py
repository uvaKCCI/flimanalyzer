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
    frame.settings.import_.delimiter = ";"  # e.g. by the import dialog
    frame.settings.tool_settings.set(tools.get("K-Means"), KMeansConfig(n_clusters=5))
    _answer_file_dialog(monkeypatch, path)
    frame.OnSaveSettings(None)
    assert json.loads(path.read_text())["schema_version"] == SETTINGS_VERSION

    frame.settings.import_.delimiter = "\t"
    frame.settings.tool_settings.tools.clear()
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
    frame.settings.import_.include_files = files
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    before = set(frame.windowframes)
    frame.OnImportData(None)
    (title, window), = _new_windows(frame, before).items()
    assert title == "Imported Data"
    assert len(window.GetViewData()) == 25


def test_import_with_no_readable_files(frame, monkeypatch, tmp_path):
    from flim.gui.importdlg import ImportDlg

    frame.settings.import_.include_files = [str(tmp_path / "gone.txt")]
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    messages = []
    monkeypatch.setattr(wx, "MessageBox", lambda m, *a, **k: messages.append(m))
    before = set(frame.windowframes)
    frame.OnImportData(None)
    assert _new_windows(frame, before) == {} and messages


def test_save_on_close_suggests_the_window_title(frame, monkeypatch, flim_data):
    """It suggested `frame.txt` (the wx window name)."""
    import flim.gui.dialogs

    window = _open(frame, flim_data, "cells")
    window.modified = True
    suggested = []
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_YES)
    monkeypatch.setattr(
        flim.gui.dialogs, "save_dataframe",
        lambda parent, title, data, name, **k: suggested.append(name) or False,
    )  # fmt: skip
    window.close_and_destroy(None)
    assert suggested == ["cells.txt"]
    window.modified = False


def test_filter_settings_dialog_is_destroyed(frame, monkeypatch, flim_data):
    """Each opening left a dialog that stayed subscribed to FILTERS_UPDATED."""
    from flim.gui.dialogs import ConfigureFiltersDlg

    window = _open(frame, flim_data, "cells")
    destroyed = []
    real = ConfigureFiltersDlg.Destroy
    monkeypatch.setattr(ConfigureFiltersDlg, "ShowModal", lambda dlg: wx.ID_CANCEL)
    monkeypatch.setattr(
        ConfigureFiltersDlg, "Destroy", lambda dlg: destroyed.append(dlg) or real(dlg)
    )
    window.OnFilterSettings(None)
    assert len(destroyed) == 1


def test_a_new_window_applies_the_range_filters_that_are_on(frame, flim_data):
    # until 0.6.2 its Filter Data box was checked, but it showed (and passed on) all rows
    low, high = flim_data[FEATURE].quantile([0.25, 0.75])
    filters = frame.settings.filters  # shared by the windows
    filters.range_filters = [{"name": FEATURE, "rangelow": low, "rangehigh": high, "selected": True}]
    filters.use = True
    expected = flim_data[FEATURE].between(low, high).sum()
    window = _open(frame, flim_data, "New")
    assert window.filtercb.GetValue() and window.filterbutton.IsEnabled()
    assert len(window.GetViewData()) == expected < len(flim_data)
    assert not window.is_modified()  # read from a file: the filters change only the view
    # Show Dropped: the window of the hidden rows shows them all, its filters off
    window.updateusefilter(True, showdiscarded=True)
    discarded = frame.windowframes["New - Discarded"]
    assert len(discarded.GetViewData()) == len(flim_data) - expected
    assert not discarded.filtercb.GetValue()
    filters.use = False
    assert len(_open(frame, flim_data, "Unfiltered").GetViewData()) == len(flim_data)


def test_windows_are_listed_once_and_follow_renames(frame, monkeypatch, flim_data):
    """macOS lists the windows in the Window menu itself: the GUI's own entries made
    each window appear twice there until 0.6.2."""
    import flim.gui.app as app

    for native in (True, False):
        monkeypatch.setattr(app, "NATIVE_WINDOW_LIST", native)
        title = f"native {native}"
        window = _open(frame, flim_data, title)
        labels = [m.GetItemLabelText() for m in frame.windowmenu.GetMenuItems()]
        assert labels.count(title) == (0 if native else 1)
        frame.OnRequestRenameDataWindow(title, f"{title} renamed", window)
        assert f"{title} renamed" in frame.windowframes and title not in frame.windowframes
        assert frame.remove_window_from_menu(f"{title} renamed")
        assert f"{title} renamed" not in frame.windowframes
        labels = [m.GetItemLabelText() for m in frame.windowmenu.GetMenuItems()]
        assert f"{title} renamed" not in labels
        window.Destroy()
