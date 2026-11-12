"""The Settings viewer: the app settings of the session, read-only."""

import wx

from flim.core.settingsmgr import SettingsManager
from flim.core.settingsview import log_files, overview

COLUMNS = ("Setting", "Value", "From", "Change with")
MAX_COLUMN_WIDTH = 320  # pixels; longer values (e.g. paths) are in the tooltip


class SettingsViewer(wx.Dialog):
    """A dialog that shows the app settings of the session, read-only.

    A table shows each app setting with its value, the layer that set it (built-in
    default, user settings file, app settings file, environment, command line) and
    how to change it; below it, the settings files and log files of the session.
    The tooltip of a row shows the setting's full value and its description.
    """

    def __init__(self, parent: wx.Window, manager: SettingsManager) -> None:
        """Create the dialog.

        Args:
            parent: The parent window.
            manager: The settings manager of the session.
        """
        super().__init__(
            parent, title="Settings", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.rows = overview(manager)
        self.table = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for i, title in enumerate(COLUMNS):
            self.table.InsertColumn(i, title)
        for row in self.rows:
            index = self.table.InsertItem(self.table.GetItemCount(), row.title)
            for column, text in enumerate((row.value, row.origin, row.change), start=1):
                self.table.SetItem(index, column, text)
        for i in range(len(COLUMNS)):
            self.table.SetColumnWidth(i, wx.LIST_AUTOSIZE)
            if self.table.GetColumnWidth(i) > MAX_COLUMN_WIDTH:
                self.table.SetColumnWidth(i, MAX_COLUMN_WIDTH)
        self.table.Bind(wx.EVT_MOTION, self._on_motion)

        lines = manager.record() + [f"Log file: {path}" for path in log_files()]
        self.files = wx.StaticText(self, label="\n".join(lines))
        note = wx.StaticText(
            self,
            label="These settings apply when FLIMAnalyzer starts. To change them, start"
            " it with the command-line option, the environment variable, or an app"
            " settings file (-s) that sets them.",
        )
        note.Wrap(600)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.table, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.files, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(note, 0, wx.ALL, 8)
        sizer.Add(self.CreateButtonSizer(wx.CLOSE), 0, wx.EXPAND | wx.ALL, 8)
        self.SetEscapeId(wx.ID_CLOSE)
        self.SetSizerAndFit(sizer)
        width = sum(self.table.GetColumnWidth(i) for i in range(len(COLUMNS))) + 40
        self.SetSize(max(width, self.GetSize().width), self.GetSize().height)

    def _on_motion(self, event: wx.MouseEvent) -> None:
        """Set the table's tooltip to the setting under the mouse."""
        index, _ = self.table.HitTest(event.GetPosition())
        if 0 <= index < len(self.rows):
            row = self.rows[index]
            tip = f"{row.value}\n\n{row.description}\nChange with: {row.change}"
        else:
            tip = ""
        self.table.SetToolTip(tip)
        event.Skip()
