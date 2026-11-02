import pytest

FEATURES = ["NAD(P)H t1", "NAD(P)H t2", "NAD(P)H a1[%]"]


@pytest.fixture(scope="module")
def wxapp():
    wx = pytest.importorskip("wx")
    try:
        app = wx.App()
    except SystemExit:
        pytest.skip("no display available")
    import flim.gui  # noqa: F401

    yield app
    for window in list(wx.GetTopLevelWindows()):
        # windows already destroyed by a test may still be listed until deleted
        if window and not window.IsBeingDeleted():
            window.Destroy()


def test_dialog_points_controls(wxapp, flim_data):
    from flim.configs import PairPlotConfig
    from flim.core.registry import tools
    from flim.gui.configdialog import ConfigDialog

    config = PairPlotConfig(features=FEATURES, points={"mode": "all", "samples": 5000})
    dlg = ConfigDialog(None, tools.get("Pair Plot"), config, data_choices={"data": flim_data})
    try:
        points = dlg.fields.editors["points"].fields.editors
        assert points["mode"].get() == "all" and points["samples"].get() == 5000
        points["mode"].set("sample")
        points["samples"].set(20000)
        result = dlg.result().config.points
        assert (result.mode, result.samples) == ("sample", 20000)
    finally:
        dlg.Destroy()
