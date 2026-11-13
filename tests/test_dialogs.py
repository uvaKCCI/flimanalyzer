import numpy as np
import pandas as pd
import pytest


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


def test_filter_dialog(wxapp, table, recwarn):
    from flim.core.filtering import window_filters
    from flim.core.settings import AppSettings
    from flim.gui.dialogs import ConfigureFiltersDlg

    filters = window_filters(AppSettings.default())
    dlg = ConfigureFiltersDlg(None, filters=filters, dataframe=table)
    try:
        assert not [w for w in recwarn if "CheckListCtrlMixin" in str(w.message)]
        assert dlg.GetTitle() == "Filter Settings"
        filters = dlg.filterlist
        assert filters.GetItemCount() > 0
        checked = filters.IsChecked(0)
        filters.CheckItem(0, not checked)
        assert filters.IsChecked(0) != checked
        dlg.OnFiltersUpdated([], 0, 10, 40)
        assert dlg.dropped_label.GetLabel() == "Dropped from view: 10 (of 40)"
        assert dlg.remaining_label.GetLabel() == "Remaining: 30 (75.00%)"
    finally:
        dlg.Destroy()


def test_filter_dialog_counts_rows_hidden_by_one_category_value(wxapp, table):
    from flim.core.filtering import window_filters
    from flim.core.settings import AppSettings
    from flim.gui.dialogs import ConfigureFiltersDlg

    # one category value hidden in the table window: 20 of the 40 rows
    hidden = {("Treatment", "a"): np.flatnonzero(table["Treatment"] == "a")}
    dlg = ConfigureFiltersDlg(None, window_filters(AppSettings.default()), table, hidden)
    try:
        assert len(dlg.filterlist.otherdropped) == 20  # 0.6.2: ignored with one such filter
        dlg.filterlist.dropped["x"] = np.arange(10)  # rows 0-9; the even ones are hidden already
        assert len(dlg.filterlist.get_view_dropped("x")) == 5
    finally:
        dlg.Destroy()


def test_select_dialog_shows_all_its_buttons(wxapp):
    from flim.gui.dialogs import SelectGroupsDlg

    dlg = SelectGroupsDlg(None, "Select", groups=["a", "b", "c"], selected=["a"])
    try:
        for button in (dlg.selectAllButton, dlg.deselectAllButton, dlg.okButton):
            rect = button.GetRect()
            assert rect.GetRight() <= dlg.GetClientSize().width
            assert rect.GetBottom() <= dlg.GetClientSize().height
    finally:
        dlg.Destroy()


def test_category_values_in_category_order():
    from flim.gui.datapanel import category_values

    column = pd.Series(
        pd.Categorical(["Dox15", "ctrl", "Dox15"], categories=["ctrl", "Dox15", "Dox30"])
    )
    assert category_values(column) == ["ctrl", "Dox15"]  # Dox30 does not occur
    assert category_values(pd.Series(["b", "a", "b"])) == ["b", "a"]


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
        # menu order is kept; the File tools (readers) are the File group's buttons
        assert labels == ["File"] + [c for c in tools.categories() if c != "File"]
        n_tools = sum(
            len([c for c in box.GetChildren() if isinstance(c, wx.BitmapButton)])
            for box in boxes
        )
        # Open and Import, and the tools of the menus; workflow files only as favorites
        in_menus = [
            t for group in tools.by_category().values() for t in group
            if t.in_menus and getattr(t, "definition", None) is None
        ]
        assert n_tools == 2 + len(in_menus)
    finally:
        frame.Destroy()


def test_select_dialog_says_when_nothing_is_selected(wxapp, monkeypatch):
    """OK with nothing checked shows a message (it was created but never shown)."""
    import wx

    from flim.gui.dialogs import SelectGroupsDlg

    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: shown.append(message))
    dlg = SelectGroupsDlg(None, "FOV: Select Items", groups=["a", "b"], selected=[])
    try:
        dlg.OnOK(None)
        assert shown == ["Select at least one."]
    finally:
        dlg.Destroy()


def test_pattern_rename_says_when_the_pattern_is_not_valid(wxapp, monkeypatch):
    import wx

    from flim.gui.dialogs import RenameGroupsDlg

    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: shown.append(message))
    dlg = RenameGroupsDlg(None, "FOV: Pattern Rename")
    try:
        dlg.patterntxt.SetValue("(")
        dlg.OnOK(None)
        assert shown and "Not a valid pattern" in shown[0]
    finally:
        dlg.Destroy()


def test_filter_settings_have_no_load_button(wxapp):
    import wx

    from flim.core.filtering import window_filters
    from flim.core.settings import AppSettings
    from flim.gui.dialogs import ConfigureFiltersDlg

    dlg = ConfigureFiltersDlg(None, filters=window_filters(AppSettings.default()), dataframe=pd.DataFrame({"x": [1.0]}))
    try:
        labels = [c.GetLabel() for c in dlg.panel.GetChildren() if isinstance(c, wx.Button)]
        assert "Load" not in labels and "OK" in labels
    finally:
        dlg.Destroy()
