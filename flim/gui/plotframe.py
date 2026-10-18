"""Window that shows a matplotlib figure inside the application.

Plugins draw their figures off-screen (Agg backend), possibly in worker threads;
the application shows each result figure in a PlotFrame on the main thread.
"""

import matplotlib.pyplot as plt
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg


def fit_to_screen(width, height, extra_height=0, window=None, fraction=0.9):
    """Scales (width, height) down, keeping the aspect ratio, so that it fits into
    ``fraction`` of the screen (of ``window``) together with ``extra_height``."""
    index = wx.Display.GetFromWindow(window) if window else wx.NOT_FOUND
    area = wx.Display(index if index != wx.NOT_FOUND else 0).GetClientArea()
    max_width = area.width * fraction
    max_height = area.height * fraction - extra_height
    scale = min(1.0, max_width / max(width, 1), max_height / max(height, 1))
    return int(width * scale), int(height * scale)


class PlotFrame(wx.Frame):
    """Top-level window with a figure canvas and the matplotlib navigation toolbar.

    Args:
        parent: parent window.
        figure (matplotlib.figure.Figure): figure to show.
        title (str): window title.
    """

    def __init__(self, parent, figure, title):
        super().__init__(parent, wx.ID_ANY, title=title)
        # pyplot keeps a reference to every figure it created; the window owns it now
        plt.close(figure)
        self.figure = figure
        # the canvas resizes the figure to fit, so take the figure's size first
        width, height = (figure.get_size_inches() * figure.dpi).round().astype(int)
        self.canvas = FigureCanvasWxAgg(self, wx.ID_ANY, figure)
        self.toolbar = NavigationToolbar2WxAgg(self.canvas)
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
