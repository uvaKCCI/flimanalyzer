import threading
import time

import numpy as np
import pandas as pd
import pytest

wx = pytest.importorskip("wx")


@pytest.fixture(scope="module")
def wxapp():
    try:
        app = wx.App()
    except SystemExit:  # raised by wx when no display is available
        pytest.skip("no display available")
    import flim.gui  # noqa: F401  (selects the off-screen backend)

    yield app
    for window in list(wx.GetTopLevelWindows()):
        # windows already destroyed by a test may still be listed until deleted
        if window and not window.IsBeingDeleted():
            window.Destroy()


@pytest.fixture
def table():
    rng = np.random.default_rng(0)
    n = 60
    return pd.DataFrame(
        {
            "Treatment": pd.Categorical(rng.choice(["a", "b"], n)),
            "FOV": pd.Categorical(rng.choice(["1", "2"], n)),
            "Cell": pd.Categorical([str(i) for i in range(n)]),
            "x": rng.random(n),
            "y": rng.random(n),
        }
    )


def test_plugins_draw_off_screen(wxapp):
    import matplotlib

    assert matplotlib.get_backend().lower() == "agg"


def _plots_in_worker_thread(table, names):
    import flim.plugin as plugin

    results, errors = {}, {}

    def work():
        for name in names:
            try:
                tool = plugin.PLUGINS["Plot"][name]()
                tool.configure(input={"t": table}, grouping=["Treatment"], features=["x", "y"])
                results[name] = tool.execute()
            except Exception as e:  # reported by the test below
                errors[name] = repr(e)

    thread = threading.Thread(target=work)
    thread.start()
    thread.join()
    return results, errors


def test_figures_from_worker_thread_open_in_app_windows(wxapp, table):
    import matplotlib.figure

    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame
    from flim.gui.events import EVT_PLOT_TYPE, PlotEvent
    from flim.gui.plotframe import PlotFrame, fit_to_screen

    results, errors = _plots_in_worker_thread(
        table, ["Box Plot", "KDE", "Scatter Plot", "Pair Plot"]
    )
    assert not errors, errors
    figures = [
        (title, obj)
        for res in results.values()
        for title, obj in res.items()
        if isinstance(obj, matplotlib.figure.Figure)
    ]
    assert figures

    frame = AppFrame(FLIMAnalyzer())
    try:
        sizes = {}
        for title, fig in figures:
            sizes[title] = tuple((fig.get_size_inches() * fig.dpi).round().astype(int))
            event = PlotEvent(EVT_PLOT_TYPE, frame.GetId())
            event.SetEventInfo(fig, title, "createnew")
            frame.GetEventHandler().ProcessEvent(event)

        plots = {t: w for t, w in frame.windowframes.items() if isinstance(w, PlotFrame)}
        assert set(plots) == set(sizes), (set(plots), set(sizes))
        # some window managers apply sizes asynchronously: let the resize events run,
        # as the app's event loop would
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and any(
            w.canvas.get_width_height() != w.canvas_size for w in plots.values()
        ):
            wx.Yield()
            time.sleep(0.05)
        menu = [m.GetItemLabelText() for m in frame.windowmenu.GetMenuItems()]
        assert set(plots) <= set(menu)
        for title, window in plots.items():
            # opens at the figure's size, scaled down to fit the screen if needed
            fig_w, fig_h = sizes[title]
            can_w, can_h = window.canvas.get_width_height()
            info = f"{title}: figure {fig_w}x{fig_h}, canvas {can_w}x{can_h}, planned {window.canvas_size}"
            assert window.figure.canvas is window.canvas, info
            assert window.canvas_size == fit_to_screen(
                fig_w, fig_h, window.toolbar.GetBestSize().height, frame
            ), info
            # window managers may round the size by a pixel or two
            assert abs(can_w - window.canvas_size[0]) <= 2, info
            assert abs(can_h - window.canvas_size[1]) <= 2, info
            assert can_w <= fig_w + 2 and can_h <= fig_h + 2, info

        title, window = next(iter(plots.items()))
        window.Close()
        wx.Yield()
        assert title not in frame.windowframes
        assert title not in [m.GetItemLabelText() for m in frame.windowmenu.GetMenuItems()]

        frame.OnCloseAll(None)
        wx.Yield()
        assert not any(isinstance(w, PlotFrame) for w in frame.windowframes.values())
    finally:
        frame.Destroy()


def test_plot_window_fits_a_small_screen_without_resize_events(wxapp, monkeypatch):
    """Like the CI runner: a 1024x768 screen whose window manager delivers no
    resize events while the window is set up."""
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg

    from flim.gui import plotframe

    monkeypatch.setattr(plotframe, "_screen_area", lambda window=None: wx.Rect(0, 0, 1024, 768))
    monkeypatch.setattr(FigureCanvasWxAgg, "_on_size", lambda self, event: None)
    fig, _ = plt.subplots(figsize=(12, 6))  # 1200 x 600 px
    window = plotframe.PlotFrame(None, fig, "big")
    try:
        planned = window.canvas_size
        assert planned == (921, 460)  # 90% of the screen width, same aspect ratio
        can_w, can_h = window.canvas.get_width_height()
        assert abs(can_w - planned[0]) <= 2 and abs(can_h - planned[1]) <= 2, (can_w, can_h)
        client_w, client_h = window.GetClientSize()
        assert client_w == planned[0]
    finally:
        window.Destroy()


def test_big_figure_is_zoomed_out_not_only_shrunk(wxapp, monkeypatch):
    """A figure much larger than the screen: shrunk and zoomed out (lower dpi on
    screen), so that its layout keeps room for titles and labels; saving keeps the
    figure's dpi."""
    import warnings

    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg

    from flim.gui import plotframe

    monkeypatch.setattr(plotframe, "_screen_area", lambda window=None: wx.Rect(0, 0, 1024, 768))
    monkeypatch.setattr(FigureCanvasWxAgg, "_on_size", lambda self, event: None)
    fig, axes = plt.subplots(10, 6, figsize=(30, 50), layout="constrained")
    for ax in axes.flat:
        ax.set_title("title")
        ax.set_xlabel("x label")
    window = plotframe.PlotFrame(None, fig, "tiles")
    try:
        planned = window.canvas_size
        can_w, can_h = window.canvas.get_width_height()
        assert abs(can_w - planned[0]) <= 2 and abs(can_h - planned[1]) <= 2, (can_w, can_h)
        # without the zoom the figure would be about 4 x 6.5 inches
        assert fig.get_size_inches()[1] > 2 * planned[1] / 100
        assert fig._original_dpi == 100
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # e.g. "constrained_layout not applied"
            window.canvas.draw()
    finally:
        window.Destroy()
