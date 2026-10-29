import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def wxapp():
    wx = pytest.importorskip("wx")
    try:
        app = wx.App()
    except SystemExit:  # raised by wx when no display is available
        pytest.skip("no display available")
    import flim.gui  # noqa: F401  (configures wx for the dialogs)

    yield app
    for window in list(wx.GetTopLevelWindows()):
        # windows already destroyed by a test may still be listed until deleted
        if window and not window.IsBeingDeleted():
            window.Destroy()


@pytest.fixture
def table():
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "Treatment": pd.Categorical(["a", "b"] * 20),
            "FOV": pd.Categorical(["1", "2", "3", "4"] * 10),
            "Cell": pd.Categorical([str(i) for i in range(40)]),
            "FLIRR": rng.random(40),
            "x": rng.random(40),
            "y": rng.random(40),
        }
    )


def test_filter_dialog_checkboxes(wxapp, table):
    from flim.core.settings import AppSettings
    from flim.gui.dialogs import ConfigureFiltersDlg

    filters = AppSettings.default().filters
    dlg = ConfigureFiltersDlg(None, filters=filters, dataframe=table)
    try:
        filters = dlg.filterlist
        assert filters.GetItemCount() > 0
        checked = filters.IsChecked(0)
        filters.CheckItem(0, not checked)
        assert filters.IsChecked(0) != checked
    finally:
        dlg.Destroy()


def test_list_checkboxes_notify_once_per_change(wxapp):
    import wx
    from flim.gui.listcontrol import AnalysisListCtrl

    frame = wx.Frame(None)
    try:
        lc = AnalysisListCtrl(frame, style=wx.LC_REPORT)
        for header in ("", "name", "low", "high"):
            lc.AppendColumn(header)
        lc.Append([" ", "a", "0", "1"])
        lc.Append([" ", "b", "0", "1"])
        calls = []
        lc.OnCheckItem = lambda index, flag: calls.append((index, flag))

        lc.CheckItem(0, True)
        lc.CheckItem(0, True)  # no change, no notification
        lc.ToggleItem(1)
        assert calls == [(0, True), (1, True)]
        assert lc.IsChecked(0) and lc.IsChecked(1)

        # a click on the checkbox reaches the control as a native state change
        wx.ListCtrl.CheckItem(lc, 0, False)
        assert calls[-1] == (0, False) and not lc.IsChecked(0)
    finally:
        frame.Destroy()


def test_filter_dialog_has_no_deprecated_checklist_mixin(wxapp, table, recwarn):
    from flim.core.settings import AppSettings
    from flim.gui.dialogs import ConfigureFiltersDlg

    filters = AppSettings.default().filters
    ConfigureFiltersDlg(None, filters=filters, dataframe=table).Destroy()
    assert not [w for w in recwarn if "CheckListCtrlMixin" in str(w.message)]


def test_import_dialog_resize(wxapp):
    import wx
    from flim.core.settings import AppSettings
    from flim.gui.importdlg import ImportDlg

    dlg = ImportDlg(None, "Import", AppSettings.default())
    try:
        dlg.OnRGridSize(wx.SizeEvent(wx.Size(640, 300)))
    finally:
        dlg.Destroy()


def test_tool_panel_two_rows_groups_on_one_line(wxapp):
    import wx
    from flim.core.registry import tools
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    frame = AppFrame(FLIMAnalyzer())
    try:
        frame.Layout()
        boxes = [c for c in frame.toolpanel.GetChildren() if isinstance(c, wx.StaticBox)]
        rows = {}
        for box in boxes:
            buttons = [c for c in box.GetChildren() if isinstance(c, wx.BitmapButton)]
            # all buttons of a group on the same line
            assert len({b.GetPosition().y for b in buttons}) == 1, box.GetLabel()
            rows.setdefault(box.GetPosition().y, []).append(box.GetLabel())
        assert len(rows) == 2
        labels = [label for y in sorted(rows) for label in rows[y]]
        assert labels == ["File"] + tools.categories()  # menu order is kept
        n_tools = sum(
            len([c for c in box.GetChildren() if isinstance(c, wx.BitmapButton)])
            for box in boxes
        )
        assert n_tools == 2 + len(tools)
    finally:
        frame.Destroy()
