import wx

# wxPython 4.1+ rejects sizer flags that wxWidgets ignores anyway (e.g. an
# alignment flag combined with wx.EXPAND); the dialogs were written for older
# versions, so keep the old, lenient behavior
wx.SizerFlags.DisableConsistencyChecks()
