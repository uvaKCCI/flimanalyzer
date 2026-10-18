import numpy as np
import pytest
import seaborn as sns

from flim.analysis.pairplots import PairPlot

FEATURES = ["NAD(P)H t1", "NAD(P)H t2", "NAD(P)H a1[%]"]


def _pairplot(flim_data, **params):
    tool = PairPlot()
    tool.configure(
        input={"data": flim_data}, grouping=["Treatment"], features=FEATURES, diag_kind="KDE", **params
    )
    (fig,) = tool.execute().values()
    return fig


def _points_per_panel(fig):
    """Number of scatter points in each off-diagonal panel."""
    counts = []
    n = len(FEATURES)
    for i, ax in enumerate(fig.axes[: n * n]):
        if i // n != i % n:
            counts.append(sum(len(c.get_offsets()) for c in ax.collections))
    return counts


def _notes(fig):
    return [t.get_text() for t in fig.texts if "measurements shown" in t.get_text()]


def test_all_measurements_by_default(flim_data):
    fig = _pairplot(flim_data)
    assert set(_points_per_panel(fig)) == {len(flim_data)}
    assert _notes(fig) == []


def test_random_sample_in_scatter_panels(flim_data, monkeypatch):
    diagonal_sizes = []
    kdeplot = sns.kdeplot

    def recording_kdeplot(*args, **kwargs):
        x = kwargs.get("x", args[0] if args else None)
        diagonal_sizes.append(len(x))
        return kdeplot(*args, **kwargs)

    monkeypatch.setattr(sns, "kdeplot", recording_kdeplot)
    fig = _pairplot(flim_data, plotting="sample", samples=20)
    assert set(_points_per_panel(fig)) == {20}
    # the diagonals use all measurements (seaborn draws them per Treatment group)
    assert sum(diagonal_sizes) == len(FEATURES) * len(flim_data)
    assert _notes(fig) == [f"20 samples of {len(flim_data)} measurements shown"]


def test_sample_is_the_same_on_every_run(flim_data):
    def offsets(fig):
        return np.concatenate([c.get_offsets() for ax in fig.axes for c in ax.collections if len(c.get_offsets())])

    a = offsets(_pairplot(flim_data, plotting="sample", samples=20))
    b = offsets(_pairplot(flim_data, plotting="sample", samples=20))
    np.testing.assert_array_equal(a, b)


def test_sample_larger_than_the_data_plots_all(flim_data):
    fig = _pairplot(flim_data, plotting="sample", samples=10 * len(flim_data))
    assert set(_points_per_panel(fig)) == {len(flim_data)}
    assert _notes(fig) == []


def test_all_ignores_samples(flim_data):
    fig = _pairplot(flim_data, plotting="all", samples=20)
    assert set(_points_per_panel(fig)) == {len(flim_data)}


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
    from flim.analysis.pairplots import PairPlotConfigDlg

    dlg = PairPlotConfigDlg(
        None, "Pair Plot", input={"data": flim_data}, selectedfeatures=FEATURES, plotting="all", samples=5000
    )
    try:
        assert dlg.plot_all_rb.GetValue() and not dlg.samples_spinner.IsEnabled()
        params = dlg._get_selected()
        assert params["plotting"] == "all" and params["samples"] == 5000

        dlg.plot_sample_rb.SetValue(True)
        dlg.samples_spinner.SetValue(20000)
        params = dlg._get_selected()
        assert params["plotting"] == "sample" and params["samples"] == 20000
    finally:
        dlg.Destroy()

    dlg = PairPlotConfigDlg(
        None, "Pair Plot", input={"data": flim_data}, selectedfeatures=FEATURES, plotting="sample", samples=300
    )
    try:
        assert dlg.plot_sample_rb.GetValue() and dlg.samples_spinner.IsEnabled()
        assert dlg.samples_spinner.GetValue() == 300
    finally:
        dlg.Destroy()
