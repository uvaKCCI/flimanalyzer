"""Data window and main window features, driven as a user would (file dialogs and
group selections are answered by the test)."""

import pandas as pd
import pytest

wx = pytest.importorskip("wx")

FEATURE = "NAD(P)H t1"


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


def test_split_by_group(frame, monkeypatch, flim_data):
    window = _open(frame, flim_data)
    _answer_group_dialogs(monkeypatch, ["Treatment"])
    before = set(frame.windowframes)
    window.OnSplit(None)
    new = _new_windows(frame, before)
    assert len(new) == 2
    assert sorted(len(w.GetViewData()) for w in new.values()) == [30, 30]
    assert all(set(w.GetViewData()["Treatment"]) in ({"WT"}, {"KO"}) for w in new.values())


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
    import flim.core.configuration as cfg

    path = tmp_path / "settings.json"
    frame.config.update({cfg.CONFIG_DELIMITER: ";"}, [cfg.CONFIG_ROOT, cfg.CONFIG_IMPORT])
    _answer_file_dialog(monkeypatch, path)
    frame.OnSaveSettings(None)
    assert path.exists()

    frame.config.update({cfg.CONFIG_DELIMITER: "\t"}, [cfg.CONFIG_ROOT, cfg.CONFIG_IMPORT])
    frame.OnLoadSettings(None)
    assert frame.config.get([cfg.CONFIG_DELIMITER]) == ";"


def test_import_several_files(frame, monkeypatch, tmp_path, flim_data):
    import flim.core.configuration as cfg
    from flim.gui.importdlg import ImportDlg

    files = []
    for name, part in (("Results_FOV1_WT_1.txt", flim_data.iloc[:10]), ("Results_FOV2_KO_2.txt", flim_data.iloc[10:25])):
        path = tmp_path / name
        part.drop(columns=["Treatment", "FOV", "Cell"]).to_csv(path, sep="\t", index=False)
        files.append(str(path))
    config = frame.config
    config.update({cfg.CONFIG_INCLUDE_FILES: files}, [cfg.CONFIG_ROOT, cfg.CONFIG_IMPORT])
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(ImportDlg, "get_config", lambda dlg: config)
    before = set(frame.windowframes)
    frame.OnImportData(None)
    (title, window), = _new_windows(frame, before).items()
    assert title == "Imported Data"
    assert len(window.GetViewData()) == 25


def test_import_with_no_readable_files(frame, monkeypatch, tmp_path):
    import flim.core.configuration as cfg
    from flim.gui.importdlg import ImportDlg

    config = frame.config
    config.update({cfg.CONFIG_INCLUDE_FILES: [str(tmp_path / "gone.txt")]}, [cfg.CONFIG_ROOT, cfg.CONFIG_IMPORT])
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(ImportDlg, "get_config", lambda dlg: config)
    messages = []
    monkeypatch.setattr(wx, "MessageBox", lambda m, *a, **k: messages.append(m))
    before = set(frame.windowframes)
    frame.OnImportData(None)
    assert _new_windows(frame, before) == {} and messages
