import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FLIM = Path(__file__).resolve().parent.parent / "flim"
SOURCES = sorted(p for p in FLIM.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(FLIM)))
def test_dialogs_with_own_base_params_define_get_base_params(path):
    # BasicAnalysisConfigDlg.get_base_params() returns its own (name-mangled)
    # __base_params, so a subclass table is only used if the subclass also
    # defines get_base_params(); otherwise its settings never reach the dialog
    tree = ast.parse(path.read_text())
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        assigns = {
            t.id
            for n in cls.body
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name)
        }
        methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        if "__base_params" in assigns:
            assert "get_base_params" in methods, (
                f"{cls.name} defines __base_params but not get_base_params()"
            )


@pytest.fixture(scope="module")
def wxapp():
    wx = pytest.importorskip("wx")
    try:
        app = wx.App()
    except SystemExit:  # raised by wx when no display is available
        pytest.skip("no display available")
    import flim.gui  # noqa: F401  (configures wx for the dialogs)

    yield app
    for window in wx.GetTopLevelWindows():
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


def _plugins():
    import flim.plugin as plugin

    return [
        pytest.param(cls, id=f"{group}/{name}")
        for group, plugins in plugin.PLUGINS.items()
        for name, cls in plugins.items()
    ]


@pytest.mark.parametrize("plugin_cls", _plugins())
def test_plugin_configuration_dialog_opens(wxapp, table, monkeypatch, plugin_cls):
    import wx

    shown = []
    monkeypatch.setattr(
        wx.Dialog, "ShowModal", lambda self: shown.append(self) or wx.ID_CANCEL
    )
    plugin = plugin_cls()
    n_inputs = max(1, len(plugin.input_definition()))
    plugin.configure(
        input={f"t{i}": table for i in range(n_inputs)},
        features=["x", "y"],
        grouping=["Treatment"],
    )
    plugin.run_configuration_dialog(None, data_choices={"t0": table, "t1": table})
    assert shown, "no dialog was shown"


def test_filter_dialog_checkboxes(wxapp, table):
    import flim.core.configuration as cfg
    from flim.core.configuration import Config
    from flim.gui.dialogs import ConfigureFiltersDlg

    config = Config()
    config.create_default()
    dlg = ConfigureFiltersDlg(None, config=config.get([cfg.CONFIG_FILTERS]), dataframe=table)
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
    import flim.core.configuration as cfg
    from flim.core.configuration import Config
    from flim.gui.dialogs import ConfigureFiltersDlg

    config = Config()
    config.create_default()
    ConfigureFiltersDlg(None, config=config.get([cfg.CONFIG_FILTERS]), dataframe=table).Destroy()
    assert not [w for w in recwarn if "CheckListCtrlMixin" in str(w.message)]


def test_import_dialog_resize(wxapp):
    import wx
    from flim.core.configuration import Config
    from flim.gui.importdlg import ImportDlg

    config = Config()
    config.create_default()
    dlg = ImportDlg(None, "Import", config)
    try:
        dlg.OnRGridSize(wx.SizeEvent(wx.Size(640, 300)))
    finally:
        dlg.Destroy()
