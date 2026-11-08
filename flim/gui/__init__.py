import matplotlib

# plugins draw figures off-screen, possibly in worker threads; the GUI shows
# them in its own windows (flim.gui.plotframe.PlotFrame)
matplotlib.use("Agg")

import wx  # noqa: E402

# wxPython 4.1+ rejects sizer flags that wxWidgets ignores (e.g. an alignment
# flag combined with wx.EXPAND); the dialogs use such flags, so the check is
# turned off
wx.SizerFlags.DisableConsistencyChecks()
