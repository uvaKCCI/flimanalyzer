import matplotlib

# plugins draw figures off-screen, possibly in worker threads; the application
# shows them in its own windows (flim.gui.plotframe.PlotFrame)
matplotlib.use("Agg")

import wx  # noqa: E402

# wxPython 4.1+ rejects sizer flags that wxWidgets ignores anyway (e.g. an
# alignment flag combined with wx.EXPAND); the dialogs were written for older
# versions, so keep the old, lenient behavior
wx.SizerFlags.DisableConsistencyChecks()
