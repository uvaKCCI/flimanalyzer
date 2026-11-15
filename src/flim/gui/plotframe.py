"""Window that shows a matplotlib figure inside the GUI.

Plugins draw their figures off-screen (Agg backend), possibly in worker threads;
the GUI shows each result figure in a PlotFrame on the main thread.
"""

import math
from typing import Any, Optional

import matplotlib.pyplot as plt
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
from matplotlib.figure import Figure


def _screen_area(window: Optional[wx.Window] = None) -> wx.Rect:
    """Return the usable area of the screen that shows `window` (or the main one)."""
    index = wx.Display.GetFromWindow(window) if window else wx.NOT_FOUND
    return wx.Display(index if index != wx.NOT_FOUND else 0).GetClientArea()


def fit_to_screen(
    width: float,
    height: float,
    extra_height: float = 0,
    window: Optional[wx.Window] = None,
    fraction: float = 0.9,
) -> tuple[int, int]:
    """Scale a size down, keeping the aspect ratio, so that it fits on the screen.

    Args:
        width: The width, in pixels.
        height: The height, in pixels.
        extra_height: Height in pixels that is added below the size, e.g. a toolbar;
            it must fit as well. Defaults to 0.
        window: The window whose screen is used; None for the main screen.
        fraction: The part of the screen's usable width and height to fit into, from
            0 to 1. Defaults to 0.9.

    Returns:
        The width and height in whole pixels, never larger than the given size.
    """
    area = _screen_area(window)
    max_width = area.width * fraction
    max_height = area.height * fraction - extra_height
    scale = min(1.0, max_width / max(width, 1), max_height / max(height, 1))
    return int(width * scale), int(height * scale)


class PlotToolbar(NavigationToolbar2WxAgg):
    """Matplotlib's navigation toolbar with FLIMAnalyzer's plot formats for saving.

    Its save button offers the plot formats of `flim.gui.dialogs.save_figure`
    instead of all of Matplotlib's.
    """

    def save_figure(self, *args: Any) -> Optional[str]:
        """Ask for a file and save the figure in it.

        A plot window that is saved is no longer marked as modified.

        Args:
            *args: Ignored; Matplotlib passes the button event.

        Returns:
            The path of the saved file, or None if no file was saved.
        """
        from flim.gui.dialogs import save_figure

        window = self.canvas.GetTopLevelParent()
        path = save_figure(window, "Save Plot", self.canvas.figure, window.GetTitle())
        if path and isinstance(window, PlotFrame):
            window.modified = False  # saved
        return path


class PlotFrame(wx.Frame):
    """Top-level window with a figure canvas and the Matplotlib navigation toolbar.

    The window opens at the figure's size, scaled down to fit 90% of the screen;
    the figure then follows the window size.
    """

    @property
    def modified(self) -> bool:
        """Whether the plot has changes not saved to a file.

        Setting it calls the window's `on_modified` callback (set when the window is
        registered) with the new value. True until it is set.
        """
        return getattr(self, "_modified", True)

    @modified.setter
    def modified(self, value: bool) -> None:
        self._modified = bool(value)
        callback = getattr(self, "on_modified", None)
        if callback is not None:
            callback(self._modified)

    def __init__(self, parent: Optional[wx.Window], figure: Figure, title: str) -> None:
        """Create the window for a figure.

        Pyplot's reference to the figure is closed; the window owns the figure.

        Args:
            parent: The parent window; its screen is used to fit the window.
            figure: The figure to show.
            title: The window title.
        """
        super().__init__(parent, wx.ID_ANY, title=title)
        # pyplot keeps a reference to every figure it created; the window owns it now
        plt.close(figure)
        self.figure = figure
        # the canvas resizes the figure to fit, so take the figure's size first
        dpi = figure.dpi  # before the canvas scales it for high-resolution screens
        width, height = (figure.get_size_inches() * dpi).round().astype(int)
        self.canvas = FigureCanvasWxAgg(self, wx.ID_ANY, figure)
        self.toolbar = PlotToolbar(self.canvas)
        self.toolbar.Realize()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        sizer.Add(self.toolbar, 0, wx.EXPAND)
        self.SetSizer(sizer)
        # open at the figure's size, scaled down (same aspect ratio) to fit 90% of
        # the screen; the canvas then follows the window size
        toolbar = self.toolbar.GetBestSize().height
        self.canvas_size = fit_to_screen(width, height, toolbar, parent)
        self.SetClientSize((self.canvas_size[0], self.canvas_size[1] + toolbar))
        self.Layout()
        # half the width scaling (geometric) shrinks the figure, half zooms it out
        # (lower dpi on screen): if it were only shrunk, text would keep its size,
        # and a figure of many plots would leave no room for titles and labels
        zoom = math.sqrt(min(1.0, self.canvas_size[0] / max(width, 1)))
        if zoom < 1:
            # savefig(dpi="figure") uses figure._original_dpi, which this keeps
            figure._set_dpi(figure.dpi * zoom, forward=False)
        # resize the figure now: some window managers deliver the resize event late
        # or not at all before the window is shown
        figure.set_size_inches(
            self.canvas_size[0] / (dpi * zoom),
            self.canvas_size[1] / (dpi * zoom),
            forward=False,
        )
