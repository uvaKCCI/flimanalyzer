#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx event types and events of the data and plot windows, and pubsub topic names."""

from typing import Any, Optional

import pandas as pd
import wx
from matplotlib.figure import Figure

EVT_DU_TYPE = wx.NewEventType()
EVT_DATAUPDATED = wx.PyEventBinder(EVT_DU_TYPE, 1)

EVT_DATA_TYPE = wx.NewEventType()
EVT_DATA = wx.PyEventBinder(EVT_DATA_TYPE, 1)

EVT_PLOT_TYPE = wx.NewEventType()
EVT_PLOT = wx.PyEventBinder(EVT_PLOT_TYPE, 1)


FOCUSED_DATA_WINDOW = "datawindow.focus"
CLOSING_DATA_WINDOW = "datawindow.closing"
REQUEST_RENAME_DATA_WINDOW = "datawindow.requestrename"
RENAMED_DATA_WINDOW = "datawindow.renamed"

ANALYSIS_BINS_UPDATED = "analysis.bins.updated"
FILTERS_UPDATED = "filters.updated"


class DataUpdatedEvent(wx.PyCommandEvent):
    """An event that carries updated data and its data type."""

    def __init__(self, evtType: int, id: int) -> None:
        """Create the event, without data.

        Args:
            evtType: The event type, e.g. `EVT_DU_TYPE`.
            id: The ID of the window that sends the event.
        """
        super().__init__(evtType, id)
        self.data = None
        self.datatype = None

    def SetUpdatedData(self, data: Any, dtype: Any) -> None:
        """Set the updated data and its data type."""
        self.data = data
        self.datatype = dtype

    def GetUpdatedData(self) -> tuple[Any, Any]:
        """Return the updated data and its data type."""
        return self.data, self.datatype


class DataWindowEvent(wx.PyCommandEvent):
    """A request to the main window to act on a data window, e.g. open a table."""

    def __init__(self, evtType: int, id: int) -> None:
        """Create the event, without data.

        Args:
            evtType: The event type, `EVT_DATA_TYPE`.
            id: The ID of the window that sends the event.
        """
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.data = None
        self.config = None
        self.title = None
        self.action = None
        self.showcolindex = True
        self.groups = None
        self.analyzable = True
        self.savemodified = True
        self.enableclose = True
        self.modified = True
        self.filtered = True

    def SetEventInfo(
        self,
        data: pd.DataFrame,
        title: str,
        action: str,
        config: Any = None,
        showcolindex: bool = False,
        groups: Optional[list[str]] = None,
        analyzable: bool = True,
        savemodified: bool = True,
        enableclose: bool = True,
        modified: bool = True,
        filtered: bool = True,
    ) -> None:
        """Set the table and the options of the data window.

        Args:
            data: The table.
            title: The wanted window title.
            action: What to do; the main window handles `createnew` (open a new
                window).
            config: Any value for the receiver; the main window does not use it.
            showcolindex: Whether the window shows the column index in the headers.
            groups: The category columns; None for the table's category columns.
            analyzable: Whether the table can be analyzed.
            savemodified: Whether the window asks to save its unsaved changes when
                it is closed or the GUI quits.
            enableclose: Whether the window can be closed.
            modified: Whether the data differs from what is saved, e.g. False for
                data just read from a file; closing a modified window asks to save.
            filtered: Whether the window applies the range filters when `Filter
                Data` is on; False for a window of the rows they hide.
        """
        self.data = data
        self.config = config
        self.title = title
        self.action = action
        self.showcolindex = showcolindex
        self.groups = groups
        self.analyzable = analyzable
        self.savemodified = savemodified
        self.enableclose = enableclose
        self.modified = modified
        self.filtered = filtered

    def GetData(self) -> pd.DataFrame:
        """Return the table."""
        return self.data

    def GetConfig(self) -> Any:
        """Return the `config` value."""
        return self.config

    def GetTitle(self) -> str:
        """Return the wanted window title."""
        return self.title

    def ShowColIndex(self) -> bool:
        """Return whether the window shows the column index in the headers."""
        return self.showcolindex

    def GetGroups(self) -> Optional[list[str]]:
        """Return the category columns; None for the table's category columns."""
        return self.groups

    def IsAnalyzable(self) -> bool:
        """Return whether the table can be analyzed."""
        return self.analyzable

    def IsEnableClose(self) -> bool:
        """Return whether the window can be closed."""
        return self.enableclose

    def SaveModified(self) -> bool:
        """Return whether the window asks to save its unsaved changes."""
        return self.savemodified

    def IsModified(self) -> bool:
        """Return whether the data differs from what is saved."""
        return self.modified

    def IsFiltered(self) -> bool:
        """Return whether the window applies the range filters when they are on."""
        return self.filtered

    def GetAction(self) -> str:
        """Return the action, e.g. `createnew`."""
        return self.action


class PlotEvent(wx.PyCommandEvent):
    """A request to the main window to open a figure in a plot window."""

    def __init_(self, evtType: int, id: int) -> None:
        """Set the attributes to None; named `__init_`, so Python does not call it."""
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.figure = None
        self.title = None
        self.action = None

    def SetEventInfo(self, figure: Figure, title: str, action: str) -> None:
        """Set the figure, the wanted window title and the action (`createnew`)."""
        self.figure = figure
        self.title = title
        self.action = action

    def GetFigure(self) -> Figure:
        """Return the figure."""
        return self.figure

    def GetDataId(self) -> int:
        """Return the identity (`id`) of the figure."""
        return id(self.figure)

    def GetTitle(self) -> str:
        """Return the wanted window title."""
        return self.title

    def GetAction(self) -> str:
        """Return the action, e.g. `createnew`."""
        return self.action
