"""Bitmaps of tools, from their icon resource names."""

import wx
from importlib_resources import files

import flim.resources


def tool_bitmap(tool) -> wx.Bitmap:
    """The icon of a Tool class (``tool.icon``, a file in flim.resources); a generic
    icon if it has none or the file is missing."""
    if tool.icon:
        path = files(flim.resources).joinpath(tool.icon)
        if path.is_file():
            return wx.Bitmap(str(path))
    return wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE, wx.ART_TOOLBAR, (32, 32))
