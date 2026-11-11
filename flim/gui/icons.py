"""Bitmaps of tools, from their icon resource names."""

from typing import Optional

import wx
from importlib.resources import files

import flim.resources


def icon_bitmap(name: str) -> Optional[wx.BitmapBundle]:
    """Return an icon of flim.resources in all its sizes.

    The bundle holds `name` and, if it exists, its high-resolution version
    `name@2x.png`, which wx shows on screens with a device pixel ratio of 2.

    Args:
        name: The file name, e.g. `sort.png`.

    Returns:
        The bundle, or None if the file does not exist.
    """
    path = files(flim.resources).joinpath(name)
    if not path.is_file():
        return None
    return wx.BitmapBundle.FromFiles(str(path.parent), path.stem, "png")


def tool_bitmap(tool) -> wx.BitmapBundle:
    """Return the icon of a Tool class (`tool.icon`, a file in flim.resources); a
    generic icon if it has none or the file is missing."""
    bundle = icon_bitmap(tool.icon) if tool.icon else None
    if bundle is None:
        bundle = wx.ArtProvider.GetBitmapBundle(wx.ART_EXECUTABLE_FILE, wx.ART_TOOLBAR, (32, 32))
    return bundle
