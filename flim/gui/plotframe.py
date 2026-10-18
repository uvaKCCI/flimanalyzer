"""Window that shows a matplotlib figure inside the application.

Plugins draw their figures off-screen (Agg backend), possibly in worker threads;
the application shows each result figure in a PlotFrame on the main thread.
"""

import matplotlib.pyplot as plt
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg


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
        # open at the figure's size; the canvas then follows the window size
        self.SetClientSize((width, height + self.toolbar.GetBestSize().height))
