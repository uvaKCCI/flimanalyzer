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

    # message dialogs answer No without being shown
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)
    frame = AppFrame(FLIMAnalyzer())
    yield frame
    for window in frame.windows_by_title().values():
        if hasattr(window, "modified"):
            window.modified = False
    frame.OnCloseAll(None)
    frame.Destroy()


def _open(frame, data, title="Data"):
    from flim.gui.events import EVT_DATA_TYPE, DataWindowEvent

    event = DataWindowEvent(EVT_DATA_TYPE, frame.GetId())
    event.SetEventInfo(data, title, "createnew", modified=False)
    frame.GetEventHandler().ProcessEvent(event)
    return frame.windows_by_title()[title]


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
    return {t: w for t, w in frame.windows_by_title().items() if t not in before}


def test_pivot(frame, monkeypatch, flim_data):
    window = _open(frame, flim_data)
    _answer_group_dialogs(monkeypatch, ["Treatment"], [FEATURE])
    before = set(frame.windows_by_title())
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


@pytest.mark.parametrize("button", ["Save Shown Rows...", "Save All Rows..."])
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
    assert "saved.txt" in frame.windows_by_title()  # renamed after the file


def test_saving_keeps_the_window_columns(frame, monkeypatch, tmp_path, flim_data):
    data = flim_data.rename(columns={FEATURE: "NAD(P)H\nt1"})  # e.g. a pivoted table
    window = _open(frame, data)
    _answer_file_dialog(monkeypatch, tmp_path / "pivot.txt")
    from flim.gui.dialogs import save_dataframe

    warned = []

    def save_anyway(dialog):
        warned.append(dialog.GetMessage())
        return wx.ID_YES

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", save_anyway)
    save_dataframe(window, "Save", window.data, "pivot.txt")
    assert "headers of several lines are saved as one line" in warned[0]
    # the file has the header on one line
    assert "NAD(P)H t1" in pd.read_table(tmp_path / "pivot.txt").columns
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
    assert frame.settings.tools.config(tools.get("K-Means")).n_clusters == 5


def test_import_several_files(frame, monkeypatch, tmp_path, flim_data):
    from flim.gui.importdlg import ImportDlg

    files = []
    for name, part in (("Results_FOV1_WT_1.txt", flim_data.iloc[:10]), ("Results_FOV2_KO_2.txt", flim_data.iloc[10:25])):
        path = tmp_path / name
        part.drop(columns=["Treatment", "FOV", "Cell"]).to_csv(path, sep="\t", index=False)
        files.append(str(path))
    _set_import_files(frame, files)
    monkeypatch.setattr(ImportDlg, "ShowModal", lambda dlg: wx.ID_OK)
    before = set(frame.windows_by_title())
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
    before = set(frame.windows_by_title())
    frame.OnImportData(None)
    assert _new_windows(frame, before) == {} and messages


def test_open_file_of_an_open_windows_name_opens_a_new_window(frame, tmp_path):
    """A file named like an open window (data.txt from another folder) gets its own
    window; the open one keeps its data and unsaved changes (before, they were
    replaced)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    pd.DataFrame({"x": [1.0, 2.0, 3.0]}).to_csv(tmp_path / "a" / "data.txt", sep="\t", index=False)
    pd.DataFrame({"x": [9.0]}).to_csv(tmp_path / "b" / "data.txt", sep="\t", index=False)
    assert frame.open_data_files([str(tmp_path / "a" / "data.txt")]) == "data.txt"
    first = frame.windows_by_title()["data.txt"]
    first.modified = True  # changed, not saved

    assert frame.open_data_files([str(tmp_path / "b" / "data.txt")]) == "data.txt-1"
    assert frame.windows_by_title()["data.txt"] is first
    assert len(first.GetViewData()) == 3 and first.is_modified()
    assert len(frame.windows_by_title()["data.txt-1"].GetViewData()) == 1
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
    first = frame.windows_by_title()["Imported Data"]
    first.modified = True  # changed, not saved
    frame.OnImportData(None)  # the same files again
    assert frame.windows_by_title()["Imported Data"] is first and first.is_modified()
    assert len(frame.windows_by_title()["Imported Data-1"].GetViewData()) == 25


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


def test_column_range_filter_reaches_the_user_settings_file(
    wxapp, monkeypatch, tmp_path, flim_data
):
    """A range filter changed through a column label's dialog is reported, like the
    filter checkbox and the Filter Settings dialog."""
    import json

    from flim.core.settingsmgr import SettingsManager, UserSettingsFile
    from flim.core.tools import FLIMAnalyzer
    from flim.gui import datapanel
    from flim.gui.app import AppFrame

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)  # never wait
    path = tmp_path / "settings.json"
    frame = AppFrame(FLIMAnalyzer(), SettingsManager(user_file=UserSettingsFile(path)))
    try:
        window = _open(frame, flim_data)
        column = "FAD a1[%]"
        edited = [{**window._existing_rangefilters([], columns=[column])[0], "rangehigh": 70.0}]

        class Dialog:  # ConfigureFiltersDlg answered with OK and an edited range
            def __init__(self, *args, **kwargs):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetData(self):
                return window.filters.model_copy(update={"range_filters": edited})

        monkeypatch.setattr(datapanel, "ConfigureFiltersDlg", Dialog)
        window.filtercb.SetValue(True)

        class Click:  # a click on the column's label
            def GetCol(self):
                return 1 + list(window.dataview.columns).index(column)

            def GetRow(self):
                return -1

        monkeypatch.setattr(window.grid, "GetColLabelValue", lambda col: column)
        window.OnLabelClick(Click())
        stored = json.loads(path.read_text())["filters"]["range_filters"]
        assert {"name": column, "rangehigh": 70.0}.items() <= next(
            f for f in stored if f["name"] == column
        ).items()
    finally:
        frame.OnCloseAll(None)
        frame.Destroy()




@pytest.mark.parametrize("index, fmt, sep", [(0, "tsv", "\t"), (1, "csv", ",")])
def test_table_formats_in_the_save_dialog(frame, monkeypatch, tmp_path, flim_data, index, fmt, sep):
    from flim.gui.dialogs import save_dataframe

    window = _open(frame, flim_data)
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(tmp_path / "cells"))
    monkeypatch.setattr(wx.FileDialog, "GetFilterIndex", lambda dlg: index)
    path = save_dataframe(window, "Save", window.data, "cells.txt", saveindex=False)
    assert path.endswith(".txt" if fmt == "tsv" else ".csv")  # the ending is added
    assert pd.read_csv(path, sep=sep).shape == flim_data.shape


def test_comma_in_a_header_warns_with_csv(frame, monkeypatch, tmp_path, flim_data):
    from flim.gui.dialogs import save_dataframe

    data = flim_data.rename(columns={FEATURE: "t1, ns"})
    window = _open(frame, data)
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(tmp_path / "cells.csv"))
    monkeypatch.setattr(wx.FileDialog, "GetFilterIndex", lambda dlg: 1)
    warned = []
    monkeypatch.setattr(
        wx.MessageDialog, "ShowModal", lambda dlg: warned.append(dlg.GetMessage()) or wx.ID_NO
    )
    assert save_dataframe(window, "Save", window.data, "cells.txt") is None  # not saved
    assert "t1, ns: contains a comma" in warned[0]
    assert not (tmp_path / "cells.csv").exists()


# --- the windows as views of the DataManager's items ---


def test_windows_are_items_of_the_data_manager(frame, flim_data):
    from flim.core.types import TableType

    window = _open(frame, flim_data, "cells")
    item = frame.data_manager.get(window.item_id)
    assert item.title == "cells" and item.data_type is TableType and item.open
    assert not item.modified
    window.modified = True  # an edit in the window
    assert frame.data_manager.get(window.item_id).modified
    window.modified = False
    window.Close()
    closed = frame.data_manager.get(window.item_id)
    assert not closed.open and frame.windows_by_title() == {}


def test_a_renamed_window_keeps_its_item(frame, monkeypatch, tmp_path, flim_data):
    window = _open(frame, flim_data, "cells")
    _answer_file_dialog(monkeypatch, tmp_path / "saved.txt")
    window.OnSave(type("E", (), {"GetEventObject": lambda self: type(
        "B", (), {"GetLabel": lambda self: "Save All Rows..."})()})())
    item = frame.data_manager.get(window.item_id)
    assert item.title == "saved.txt" and not item.modified
    assert frame.windows_by_title()["saved.txt"] is window
    menu = [m.GetItemLabelText() for m in frame.windowmenu.GetMenuItems()]
    assert "saved.txt" in menu and "cells" not in menu


def test_runs_get_copies_of_the_tables(frame, flim_data):
    window = _open(frame, flim_data, "cells")
    (copy,) = frame.tool_data_choices().values()
    window.data.iloc[0, window.data.columns.get_loc(FEATURE)] = -1.0  # an edit later
    assert copy[FEATURE].iloc[0] != -1.0


def test_plot_windows_track_their_modified_state(frame, monkeypatch, tmp_path):
    import matplotlib.figure

    figure = matplotlib.figure.Figure(figsize=(2, 1))
    figure.add_subplot().plot([0, 1], [0, 1])
    window = frame.open_plot(figure, "Box Plot", modified=True)
    assert frame.data_manager.get(window.item_id).modified
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(tmp_path / "plot"))
    monkeypatch.setattr(wx.FileDialog, "GetFilterIndex", lambda dlg: 0)
    window.toolbar.save_figure()  # saved: no longer modified
    assert not frame.data_manager.get(window.item_id).modified
    frame._plot_edited(figure)  # e.g. a new axis label
    assert frame.data_manager.get(window.item_id).modified
    window.modified = False
    window.Close()
    assert not frame.data_manager.get(window.item_id).open


def test_results_of_a_saved_run_open_as_saved(frame, flim_data, tmp_path):
    import matplotlib.figure

    class Run:  # stands in for a FlowRun
        def __init__(self, autosave_dir):
            self.autosave_dir = autosave_dir

        def results(self):
            return [{"Table: R": flim_data, "Plot: P": matplotlib.figure.Figure()}]

    frame.show_results(Run(tmp_path))
    saved = [frame.data_manager.find(t) for t in ("Table: R", "Plot: P")]
    assert [i.modified for i in saved] == [False, False]
    frame.show_results(Run(None))
    unsaved = [frame.data_manager.find(t) for t in ("Table: R-1", "Plot: P-1")]
    assert [i.modified for i in unsaved] == [True, True]



def test_focus_makes_a_window_the_current_one(frame, flim_data):
    from pubsub import pub

    from flim.gui.events import FOCUSED_DATA_WINDOW

    first = _open(frame, flim_data, "first")
    second = _open(frame, flim_data, "second")
    assert frame.get_currentdata()[0] == "second"
    pub.sendMessage(FOCUSED_DATA_WINDOW, data=first.dataview, frame=first)
    assert frame.get_currentdata()[0] == "first"
    assert frame.window_zorder == [second.item_id, first.item_id]
