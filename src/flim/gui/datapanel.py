"""Table windows: a grid that shows a table, with view filters and save buttons."""

import logging
import pandas as pd
import numpy as np
import os
import re
from collections.abc import Callable
from typing import Any, Optional, Union

import wx
import wx.grid
import wx.lib.mixins.gridlabelrenderer as glr
from pubsub import pub

from flim.core.filter import RangeFilter
from flim.core.filtering import WindowFilters, new_range, window_filters
from flim.core.settings import AppSettings
from flim.gui.events import (
    EVT_DATA_TYPE,
    DataWindowEvent,
    FOCUSED_DATA_WINDOW,
    CLOSING_DATA_WINDOW,
    REQUEST_RENAME_DATA_WINDOW,
    RENAMED_DATA_WINDOW,
)
import flim.gui.dialogs
from flim.gui.dialogs import FilterPresets, SelectGroupsDlg, ConfigureFiltersDlg, RenameGroupsDlg

logger = logging.getLogger(__name__)

# the table window's save buttons: all rows (also those hidden by filters), or the rows
# shown
SAVE_ALL_ROWS = "Save All Rows..."
SAVE_SHOWN_ROWS = "Save Shown Rows..."

EVEN_ROW_COLOUR = "#CCE6FF"
GRID_LINE_COLOUR = "#ccc"


class FilterColLabelRenderer(glr.GridLabelRenderer):
    """Column label renderer with a background colour, for category columns."""

    def __init__(self, bgcolor: str) -> None:
        """Create the renderer.

        Args:
            bgcolor: The background colour, e.g. `#d0d0ff`.
        """
        self._bgcolor = bgcolor

    def Draw(self, grid: wx.grid.Grid, dc: wx.DC, rect: wx.Rect, col: int) -> None:
        """Draw the label of column `col` on the background colour, with a border."""
        dc.SetBrush(wx.Brush(self._bgcolor))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(rect)
        hAlign, vAlign = grid.GetColLabelAlignment()
        text = grid.GetColLabelValue(col)
        self.DrawBorder(grid, dc, rect)
        self.DrawText(grid, dc, rect, text, hAlign, vAlign)


class PandasGrid(wx.grid.Grid, glr.GridWithLabelRenderersMixin):
    """Grid whose column labels can have their own renderers."""

    def __init__(self, *args: Any, **kw: Any) -> None:
        """Create the grid; the arguments are passed to `wx.grid.Grid`."""
        wx.grid.Grid.__init__(self, *args, **kw)
        glr.GridWithLabelRenderersMixin.__init__(self)


class PandasTable(wx.grid.GridTableBase):
    """Grid table that shows a `pd.DataFrame`.

    The headers of columns with several levels show one level per line. Float
    columns are shown as floats, integer columns as right-aligned integers, the
    others as strings.
    """

    def __init__(
        self,
        data: Optional[pd.DataFrame] = None,
        showcolindex: bool = False,
        categories_first: bool = False,
    ) -> None:
        """Create the table; see `SetData` for the arguments."""
        wx.grid.GridTableBase.__init__(self)
        self.SetData(data, showcolindex, categories_first)

    def SetData(
        self,
        data: Optional[pd.DataFrame],
        showcolindex: bool = False,
        categories_first: bool = False,
    ) -> None:
        """Set the table to show.

        Args:
            data: The table; None for an empty table.
            showcolindex: Whether the first column shows the row index. Defaults to
                False.
            categories_first: Whether the category columns are shown first, sorted
                by name, then the other columns. Defaults to False.
        """
        self.headerRows = 1
        if data is None:
            data = pd.DataFrame()
        self.data = data
        self.showcolindex = showcolindex

        if categories_first:
            cols = self.data.select_dtypes(["category"])
            cols = sorted(cols)
            othercols = [col for col in self.data.columns.values if col not in cols]
            cols.extend(othercols)
            self.data = self.data[cols]
        if self.data.columns.nlevels == 1:
            self.colheaders = self.data.columns.get_level_values(0).values
        else:
            self.colheaders = ["\n".join(c).strip() for c in self.data.columns.values]
        self.floatcols = [
            col
            for col in self.colheaders
            if col in self.data.select_dtypes(include=[float]).columns.values
        ]
        self.intcols = [
            col
            for col in self.colheaders
            if col in self.data.select_dtypes(include=[np.integer]).columns.values
        ]

    def GetData(self) -> pd.DataFrame:
        """Return the table shown."""
        return self.data

    def GetFloatCols(self) -> list[str]:
        """Return the headers of the float columns."""
        return self.floatcols

    def GetFloatColIdx(self) -> list[int]:
        """Return the positions of the float columns among the table's columns.

        The positions do not count the index column.
        """
        return [
            colindex
            for colindex in range(len(self.colheaders))
            if self.colheaders[colindex] in self.floatcols
        ]

    def GetLongColIdx(self) -> list[int]:
        """Return the positions of the integer columns among the table's columns.

        The positions do not count the index column.
        """
        return [
            colindex
            for colindex in range(len(self.colheaders))
            if self.colheaders[colindex] in self.intcols
        ]

    def GetNumberRows(self) -> int:
        """Return the number of rows."""
        return len(self.data)

    def GetNumberCols(self) -> int:
        """Return the number of columns, including the index column if shown."""
        if self.showcolindex:
            return len(self.data.columns) + 1
        else:
            return len(self.data.columns)

    def GetTypeName(self, row: int, col: int) -> str:
        """Return the grid's type of the cell: float, long or string."""
        if self.GetColLabelValue(col) in self.floatcols:
            return wx.grid.GRID_VALUE_FLOAT
        elif self.GetColLabelValue(col) in self.intcols:
            return wx.grid.GRID_VALUE_LONG
        else:
            return wx.grid.GRID_VALUE_STRING

    def GetValue(self, row: int, col: int) -> Any:
        """Return the value of a cell; in the index column, the row's index."""
        if self.showcolindex:
            if col == 0:
                return self.data.index[row]
            return self.data.iloc[row, col - 1]
        else:
            return self.data.iloc[row, col]

    def SetValue(self, row: int, col: int, value: Any) -> None:
        """Set the value of a cell in the table."""
        if self.showcolindex:
            self.data.iloc[row, col - 1] = value
        else:
            self.data.iloc[row, col] = value

    def GetColLabelValue(self, col: int) -> str:
        """Return the header of column `col`.

        The index column's header is the index's names, one per line, or `Index` if
        the index has no name.
        """
        if self.showcolindex:
            if col == 0:
                if self.data.index.name is None:
                    return "Index"
                else:
                    return "\n".join(self.data.index.names)
            return self.colheaders[col - 1]
        else:
            return self.colheaders[col]

    def GetAttr(
        self, row: int, col: int, prop: wx.grid.GridCellAttr.AttrKind
    ) -> Optional[wx.grid.GridCellAttr]:
        """Return the attributes of a cell; integer cells are right-aligned."""
        if self.GetColLabelValue(col) in self.intcols:
            attr = wx.grid.GridCellAttr()
            attr.SetAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
            return attr
        else:
            return wx.grid.GridTableBase.GetAttr(self, row, col, prop)


def category_values(column: pd.Series) -> list[Any]:
    """Return the values that occur in a column.

    The values of a category column are in its category order (see Order
    Categories), those of other columns in the order they occur.
    """
    present = column.unique()
    if isinstance(column.dtype, pd.CategoricalDtype):
        observed = set(present)
        return [c for c in column.cat.categories if c in observed]
    return list(present)


class PandasFrame(wx.Frame):
    """Table window: a grid with the table and buttons for its view.

    The side bar sets the precision of floats, fits the column widths, turns the
    range filters (`Filter Features`) and the hidden category values (`Filter
    Categories`) on and off, edits the range filters (`Filter Features...`), runs
    the Pivot and Unpivot tools on the table, and saves all rows or the rows shown.
    Right-clicking a category column's header selects the values shown (hiding a
    value switches `Filter Categories` on); double-clicking it renames values with a
    pattern. Right-clicking a numeric column's header, with `Filter Features` on,
    edits the column's range filter.

    Pubsub: sends `FOCUSED_DATA_WINDOW` when activated, `CLOSING_DATA_WINDOW` when
    closed and `REQUEST_RENAME_DATA_WINDOW` after a save; receives
    `RENAMED_DATA_WINDOW`.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        title: str,
        filters: Optional[WindowFilters] = None,
        data: Optional[pd.DataFrame] = None,
        showcolindex: bool = False,
        groups: Optional[Union[list[str], np.ndarray]] = None,
        analyzable: bool = True,
        savemodified: bool = True,
        precision: int = 3,
        enableclose: bool = True,
        on_filters_changed: Optional[Callable[[WindowFilters], None]] = None,
        on_run_tool: Optional[Callable[[str, str], None]] = None,
        filtered: bool = True,
        presets: Optional[FilterPresets] = None,
    ) -> None:
        """Create the window.

        Args:
            parent: The parent window; None for none.
            title: The window title.
            filters: The view filters the window starts with, usually the defaults
                for new tables; the window keeps a copy of its own, so changes apply to
                this table only. Defaults to the built-in defaults.
            data: The table; None for an empty table.
            showcolindex: Whether the first column shows the row index.
            groups: The category columns, which have view filters. Defaults to the
                columns of category type.
            analyzable: Whether the table can be analyzed (`is_analyzable`).
            savemodified: Whether closing the window asks to save a modified table.
            precision: The number of decimals of floats.
            enableclose: Whether the window can be closed; if not, closing it shows
                a message.
            on_filters_changed: Called with the window's filters after the user
                changes them (the filter checkboxes, `Filter Features...`, hidden
                category values).
            on_run_tool: Called with a tool's name and this window's title to run
                the tool on this window's table in its dialog (Pivot, Unpivot); None:
                the window does not show these buttons.
            filtered: Whether the window applies the range filters of `filters`
                when they are on (`filters.features`), also when it opens; False for
                a window of the rows they hide (`Show Dropped`), whose `Filter
                Features` and `Filter Categories` boxes are then unchecked.
            presets: Where `Filter Features...` loads and saves range filters (the
                defaults for new tables, saved presets, files); None for no preset
                buttons.
        """
        super(PandasFrame, self).__init__(parent, wx.ID_ANY, title)
        start = filters if filters is not None else window_filters(AppSettings.default())
        self.filters = start.model_copy(deep=True)  # this table's own
        if not filtered:  # the rows the filters of another window dropped
            self.filters.features.enabled = False
            self.filters.categories.enabled = False
        self.presets = presets
        self.on_filters_changed = on_filters_changed
        self.on_run_tool = on_run_tool
        self.enableclose = enableclose
        self.filtered = filtered
        self.grid = None
        self.SetData(data, showcolindex, groups, analyzable, savemodified, precision)
        self._init_gui()
        if self.filters.features.enabled:
            self.use_features(True)  # the shared range filters, as in the other windows
        self.Layout()

        self.Bind(wx.EVT_CLOSE, self.close_and_destroy)
        self.Bind(wx.EVT_ACTIVATE, self.activate)
        pub.subscribe(self.OnDataWindowRenamed, RENAMED_DATA_WINDOW)

    def activate(self, event: wx.ActivateEvent) -> None:
        """Send `FOCUSED_DATA_WINDOW` when the window is activated."""
        if event.GetActive():
            pub.sendMessage(FOCUSED_DATA_WINDOW, data=self.dataview, frame=self)
        event.Skip()

    def SetData(
        self,
        data: Optional[pd.DataFrame] = None,
        showcolindex: bool = False,
        groups: Optional[Union[list[str], np.ndarray]] = None,
        analyzable: bool = True,
        savemodified: bool = True,
        precision: int = 3,
    ) -> None:
        """Set the table and its view settings, and clear the view filters' rows.

        The table is marked modified. If the grid exists, the view is updated. See
        `__init__` for the arguments.
        """
        self.analyzable = analyzable
        self.savemodified = savemodified
        self.modified = True
        self.precision = precision

        if data is None:
            data = pd.DataFrame()
        self.data = data
        self.droppedrows = {}
        self.dataview = data
        self.showcolindex = showcolindex
        # get all columns that define categories; these are the columns with view filters
        if groups is None:
            groups = data.select_dtypes(["category"]).columns.get_level_values(0).values
        self.groups = groups
        self.numcols = data.select_dtypes(["number"]).columns.get_level_values(0).values
        if self.grid is not None:
            logger.debug(
                f"datapanel.PandasFrame.SetData - REFRESHING {self.GetTitle()}"
            )
            self.update_view()
        else:
            logger.debug(
                f"datapanel.PandasFrame.SetData - NOT REFRESHING {self.GetTitle()}"
            )

    def set_header_renderer(self) -> None:
        """Give the headers of category columns a coloured background."""
        if self.grid is not None:
            categorycols = list(self.data.select_dtypes(["category"]).columns.values)
            for i in range(self.grid.GetNumberCols()):
                collabel = self.grid.GetColLabelValue(i)
                if collabel in categorycols:
                    self.grid.SetColLabelRenderer(i, FilterColLabelRenderer("#d0d0ff"))
                else:
                    self.grid.SetColLabelRenderer(i, glr.GridDefaultColLabelRenderer())

    def GetViewData(self) -> pd.DataFrame:
        """Return the rows shown, those not dropped by the view filters."""
        return self.dataview

    def GetData(self) -> pd.DataFrame:
        """Return the table with all rows."""
        return self.data

    def _init_gui(self) -> None:
        """Create the grid and the buttons."""
        table = PandasTable(self.dataview, showcolindex=self.showcolindex)

        self.grid = PandasGrid(self, wx.ID_ANY)
        self.grid.SetTable(table, takeOwnership=True)
        self.set_header_renderer()
        self.update_precision(self.precision)
        self.grid.EnableEditing(False)
        self.grid.SetColLabelSize(wx.grid.GRID_AUTOSIZE)
        self.grid.EnableDragColSize(True)
        self.grid.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnLabelClick)

        self.grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.OnLabelDClick)

        precisionspinner = wx.SpinCtrl(
            self,
            wx.ID_ANY,
            value=str(self.precision),
            min=1,
            max=10,
            style=wx.TE_PROCESS_ENTER,
            size=(50, -1),
        )
        precisionspinner.Bind(wx.EVT_SPINCTRL, self.OnPrecisionChange)

        autosizebutton = wx.Button(self, wx.ID_ANY, "Autosize Cols")
        autosizebutton.Bind(wx.EVT_BUTTON, self.OnAutosize)

        self.featurescb = wx.CheckBox(self, wx.ID_ANY, label="Filter Features")
        self.featurescb.SetToolTip("Use the range filters of the feature columns")
        self.featurescb.SetValue(self.filters.features.enabled)
        self.featurescb.Bind(wx.EVT_CHECKBOX, self.OnFilterFeatures)

        self.categoriescb = wx.CheckBox(self, wx.ID_ANY, label="Filter Categories")
        self.categoriescb.SetToolTip(
            "Use the category values hidden through a right-click on a column header"
        )
        self.categoriescb.SetValue(self.filters.categories.enabled)
        self.categoriescb.Bind(wx.EVT_CHECKBOX, self.OnFilterCategories)

        self.filterbutton = wx.Button(self, wx.ID_ANY, "Filter Features...")
        self.filterbutton.SetToolTip("Edit the range filters of the feature columns")
        self.filterbutton.Bind(wx.EVT_BUTTON, self.OnFilterSettings)

        pivotviewbutton = wx.Button(self, wx.ID_ANY, "Pivot...")
        pivotviewbutton.SetToolTip("The Pivot tool on this table: category values become columns")
        pivotviewbutton.Bind(wx.EVT_BUTTON, self.OnPivotView)
        pivotviewbutton.Show(self.on_run_tool is not None)

        self.unpivotbutton = wx.Button(self, wx.ID_ANY, "Unpivot...")
        self.unpivotbutton.SetToolTip("The Unpivot tool on this table: a header line becomes a category column")
        self.unpivotbutton.Bind(wx.EVT_BUTTON, self.OnUnpivot)
        self.unpivotbutton.Show(self.on_run_tool is not None)

        saveallbutton = wx.Button(self, wx.ID_ANY, SAVE_ALL_ROWS)
        saveallbutton.Bind(wx.EVT_BUTTON, self.OnSave)

        saveviewbutton = wx.Button(self, wx.ID_ANY, SAVE_SHOWN_ROWS)
        saveviewbutton.Bind(wx.EVT_BUTTON, self.OnSave)

        precisionsizer = wx.FlexGridSizer(1, 2, 0, 0)
        precisionsizer.Add(wx.StaticText(self, wx.ID_ANY, "Precision:"), 0, wx.RIGHT, 5)
        precisionsizer.Add(precisionspinner, 0, wx.LEFT | wx.EXPAND, 0)

        toolsizer = wx.BoxSizer(wx.VERTICAL)
        toolsizer.Add(precisionsizer, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(autosizebutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(self.featurescb, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(self.filterbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(self.categoriescb, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(pivotviewbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(self.unpivotbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(saveallbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(saveviewbutton, 0, wx.ALL | wx.EXPAND, 5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.grid, 1, wx.EXPAND)
        sizer.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5)
        sizer.Add(toolsizer)

        self.SetSizer(sizer)
        self._fit_side_bar(toolsizer)

    def _fit_side_bar(self, side_bar: wx.Sizer) -> None:
        """Make the window at least as high as its side bar, within the screen.

        The window starts at the platform's default size, which is lower than the
        side bar's buttons; the side bar's height is also the window's minimum, so
        that the buttons cannot be cut off. The grid scrolls.
        """
        index = wx.Display.GetFromWindow(self)
        usable = wx.Display(max(index, 0)).GetClientArea()
        side = side_bar.GetMinSize()
        height = min(side.height + 10, usable.height)  # 10: the separator's margins
        self.SetMinClientSize((side.width + 160, height))  # 160: a part of the grid
        client = self.GetClientSize()
        self.SetClientSize((client.width, max(client.height, height)))


    def update_precision(self, precision: int) -> None:
        """Show floats with `precision` decimals; 0 keeps the current precision."""
        if precision:
            self.precision = precision
            for colindex in self.grid.GetTable().GetFloatColIdx():
                self.grid.SetColFormatFloat(
                    colindex, width=-1, precision=self.precision
                )

    def is_analyzable(self) -> bool:
        """Return whether the table can be analyzed."""
        return self.analyzable

    @property
    def modified(self) -> bool:
        """Whether the table has changes not saved to a file.

        Setting it calls the window's `on_modified` callback, if set (when the
        window is registered), with the new value.
        """
        return getattr(self, "_modified", True)

    @modified.setter
    def modified(self, value: bool) -> None:
        self._modified = bool(value)
        callback = getattr(self, "on_modified", None)
        if callback is not None:
            callback(self._modified)

    def is_modified(self) -> bool:
        """Return whether the table has changes not saved to a file."""
        return self.modified

    def set_modified(self, modified: bool = True) -> None:
        """Set whether the table has changes not saved to a file."""
        self.modified = modified

    def apply_filters(
        self, filtercfg: dict[str, dict], showdiscarded: bool = False
    ) -> None:
        """Apply range filters to the view; the table is marked modified.

        Each selected filter's dropped rows are computed again; the rows of filters
        not selected are cleared. An empty `filtercfg` clears the rows of all range
        filters of `filters`.

        Args:
            filtercfg: The `RangeFilter` parameters by column name.
            showdiscarded: Whether a new table window shows the rows the range
                filters drop. Defaults to False.
        """
        if len(filtercfg) == 0:
            filternames = [f["name"] for f in self.filters.range_filters]
            for fname in filternames:
                if self.droppedrows.get(fname) is not None:
                    del self.droppedrows[fname]
        for fname in filtercfg:
            filter = RangeFilter(params=filtercfg[fname])
            if filter.is_selected():
                self.droppedrows[fname] = filter.get_dropped(self.data)
            elif self.droppedrows.get(fname) is not None:
                del self.droppedrows[fname]
        self.modified = True
        self.update_view(showdiscarded=showdiscarded)


    def OnDataWindowRenamed(self, original: str, new: str, frame: wx.Frame) -> None:
        """Pubsub `RENAMED_DATA_WINDOW`: set the title if `frame` is this window."""
        if frame is self:  # by identity: another window may have had the same title
            self.SetTitle(new)

    def OnPrecisionChange(self, event: wx.SpinEvent) -> None:
        """Show floats with the precision set in the spinner."""
        self.update_precision(event.GetEventObject().GetValue())
        self.grid.Refresh()

    def use_features(self, enabled: bool, showdiscarded: bool = False) -> None:
        """Turn the range filters on or off (`Filter Features`) and update the view.

        Args:
            enabled: True to apply the range filters of `filters`, False to keep
                the rows they drop.
            showdiscarded: Whether a new table window shows the rows the range
                filters drop (only when `enabled`). Defaults to False.
        """
        self.filters.features.enabled = enabled
        self.featurescb.SetValue(enabled)
        filtercfg = self.filters.range_filters
        if enabled:
            self.apply_filters(
                {f["name"]: f for f in filtercfg}, showdiscarded=showdiscarded
            )
        else:
            self.apply_filters({})

    def use_categories(self, enabled: bool) -> None:
        """Turn the hidden category values on or off (`Filter Categories`).

        The values hidden in the window are kept while they are off.

        Args:
            enabled: True to hide the rows of the hidden values, False to show them.
        """
        self.filters.categories.enabled = enabled
        self.categoriescb.SetValue(enabled)
        self.update_view()

    def OnFilterFeatures(self, event: wx.CommandEvent) -> None:
        """Turn the range filters on or off with `Filter Features`."""
        self.use_features(event.GetEventObject().GetValue())
        self._filters_changed()

    def OnFilterCategories(self, event: wx.CommandEvent) -> None:
        """Turn the hidden category values on or off with `Filter Categories`."""
        self.use_categories(event.GetEventObject().GetValue())
        self._filters_changed()

    def _filters_changed(self) -> None:
        """Call `on_filters_changed`, if set, with the filters."""
        if self.on_filters_changed is not None:
            self.on_filters_changed(self.filters)

    def _existing_rangefilters(
        self, filterlist: list[dict], columns: Optional[Union[list[str], str]] = None
    ) -> list[dict]:
        """Return the range filters of `columns` (default: the numeric columns)."""
        existingfilters = {rfilter["name"]: rfilter for rfilter in filterlist}
        if columns is None:
            columns = self.data.select_dtypes(include=["number"], exclude=["category"])
        elif not isinstance(columns, list):
            columns = [columns]
        rangefilters = [
            existingfilters[f] if f in existingfilters else new_range(f)
            for f in columns
        ]
        return rangefilters

    def _applied_rows(self) -> dict:
        """Return a copy of the dropped rows, without the hidden category values if off.

        The filter dialog counts the rows its range filters drop from the view.
        """
        if self.filters.categories.enabled:
            return self.droppedrows.copy()
        return {k: v for k, v in self.droppedrows.items() if not isinstance(k, tuple)}

    def OnFilterSettings(self, event: wx.CommandEvent) -> None:
        """Edit the range filters in `Filter Features...` and apply them on OK.

        Checking a range filter in the dialog switches `Filter Features` on there;
        the window's box follows on OK.
        """
        rfilterlist = self.filters.range_filters
        shown = self.filters.model_copy(
            update={
                "range_filters": self._existing_rangefilters(rfilterlist),
                "category_filters": self.category_filters(),
            }
        )
        # a copy of the dropped rows, so that Cancel leaves droppedrows unchanged
        dlg = ConfigureFiltersDlg(
            self, shown, self.data, self._applied_rows(), presets=self.presets
        )
        response = dlg.ShowModal()
        edited = dlg.GetData()
        dlg.Destroy()
        if response == wx.ID_OK:
            self.filters.range_filters = self._merged_filters(edited.range_filters)
            self.filters.show_dropped = edited.show_dropped
            self.use_features(edited.features.enabled, showdiscarded=edited.show_dropped)
            self._filters_changed()

    def view_description(self) -> str:
        """Return how the rows a tool gets differ from the table, for a run summary.

        The window's filter switches, the range filters that are on and the category
        values hidden, and the rows shown of the table's rows, e.g. `view: Filter
        Features on (FLIRR 0-3), Filter Categories on (Treatment hides KO), 18 of 40
        rows`.
        """
        parts = []
        ranges = [
            f"{f['name']} {f.get('rangelow')}-{f.get('rangehigh')}"
            for f in self._existing_rangefilters(self.filters.range_filters)
            if f.get("selected")
        ]
        state = "on" if self.filters.features.enabled else "off"
        parts.append(f"Filter Features {state}" + (f" ({', '.join(ranges)})" if ranges else ""))
        hidden: dict[str, list] = {}
        for key in self.droppedrows:
            if isinstance(key, tuple):
                hidden.setdefault(str(key[0]), []).append(str(key[1]))
        shown = [f"{column} hides {', '.join(values)}" for column, values in hidden.items()]
        state = "on" if self.filters.categories.enabled else "off"
        parts.append(f"Filter Categories {state}" + (f" ({'; '.join(shown)})" if shown else ""))
        parts.append(f"{len(self.dataview)} of {len(self.data)} rows")
        return "view: " + ", ".join(parts)

    def category_filters(self) -> dict[str, list]:
        """Return the values kept of each category column that hides values."""
        hidden: dict[str, set] = {}
        for key in self.droppedrows:
            if isinstance(key, tuple):
                hidden.setdefault(key[0], set()).add(key[1])
        return {
            column: [v for v in category_values(self.data[column]) if v not in values]
            for column, values in hidden.items()
        }

    def set_category_filters(self, kept: dict[str, list]) -> None:
        """Hide the values of category columns that are not kept; show all others.

        Args:
            kept: The values kept, by category column; columns not in it keep all
                values, and columns the table does not have are ignored.
        """
        for key in [k for k in self.droppedrows if isinstance(k, tuple)]:
            del self.droppedrows[key]
        for column, keep in kept.items():
            if column not in self.data.columns:
                continue
            for value in category_values(self.data[column]):
                if value not in keep:
                    self.droppedrows[(column, value)] = np.flatnonzero(self.data[column] == value)
        self.modified = True

    def _merged_filters(self, edited: list[dict]) -> list[dict]:
        """Return the range filters with the edited ones replaced, by column name."""
        filters = {f["name"]: f for f in self.filters.range_filters}
        filters.update({f["name"]: f for f in edited})
        return list(filters.values())

    def _flatten_array(self, arraylist: list[Any]) -> np.ndarray:
        """Return the unique values of the arrays in `arraylist`, sorted."""
        arraylist = [a for a in arraylist if len(a) > 0]
        if len(arraylist) > 0:
            arraylist = np.concatenate(arraylist)
        return np.unique(arraylist)

    def update_view(self, showdiscarded: bool = False) -> None:
        """Show the rows that no view filter drops.

        Args:
            showdiscarded: Whether a new table window shows the rows that the range
                filters drop and the category filters do not. Defaults to False.
        """
        # get RangeFilter names and rows dropped by them
        rfilters = self._existing_rangefilters(self.filters.range_filters)
        rfilter_names = [rfilter["name"] for rfilter in rfilters]
        rfilterdropped = self._flatten_array(
            [
                self.droppedrows[fname]
                for fname in rfilter_names
                if fname in self.droppedrows
            ]
        )
        # get rows dropped by the hidden category values, if Filter Categories is on
        catdropped = self._flatten_array(
            [
                self.droppedrows[key]
                for key in self.droppedrows
                if isinstance(key, tuple) and self.filters.categories.enabled
            ]
        )
        # all dropped rows: the union of rfilterdropped and catdropped
        droppedrows = self._flatten_array([rfilterdropped, catdropped])
        if len(droppedrows) == 0:
            self.dataview = self.data
        else:
            self.dataview = self.data.drop(self.data.index[droppedrows]).reset_index(
                drop=True
            )
        self.groups = (
            self.data.select_dtypes(["category"]).columns.get_level_values(0).values
        )

        colsizes = self.grid.GetColSizes()
        self.grid.SetTable(
            PandasTable(self.dataview, self.showcolindex), takeOwnership=True
        )
        self.update_precision(self.precision)
        self.grid.SetColSizes(colsizes)
        self.set_header_renderer()
        self.grid.Refresh()

        if showdiscarded:
            rangediscarded = np.setdiff1d(rfilterdropped, catdropped)
            windowtitle = f"{self.GetTitle()} - Discarded"
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(
                self.data.iloc[rangediscarded, :],
                windowtitle,
                "createnew",
                showcolindex=False,
                analyzable=True,
                filtered=False,
            )
            self.GetEventHandler().ProcessEvent(event)

    def OnLabelDClick(self, event: wx.grid.GridEvent) -> None:
        """Rename the values of a category column with a pattern and a replacement.

        A pattern or a replacement that is not valid shows a message; the values
        are not changed.
        """
        group = self.grid.GetColLabelValue(event.GetCol())
        if event.GetRow() == -1 and group in self.groups:
            dlg = RenameGroupsDlg(self, title=f"{group}: Pattern Rename")
            if dlg.ShowModal() == wx.ID_CANCEL:
                dlg.Destroy()
                return
            pattern = dlg.patterntxt.GetLineText(0)
            replacement = dlg.replacetxt.GetLineText(0)
            dlg.Destroy()
            try:
                renamed = self.data[group].apply(lambda x: re.sub(pattern, replacement, str(x)))
            except re.error as err:  # e.g. a replacement that names a missing group
                wx.MessageBox(
                    f"The pattern or the replacement is not valid: {err}",
                    f"{group}: Pattern Rename", wx.OK | wx.ICON_WARNING, self,
                )  # fmt: skip
                return
            self.data[group] = renamed.astype("category")
            self.modified = True
            self.update_view()

    def OnLabelClick(self, event: wx.grid.GridEvent) -> None:
        """Select the values shown of a category column, or edit a range filter.

        Hiding a value switches `Filter Categories` on. A numeric column's range
        filter is edited only when `Filter Features` is on.
        """
        group = self.grid.GetColLabelValue(event.GetCol())
        if event.GetRow() == -1 and group in self.groups:
            items = category_values(self.data[group])
            selitems = self.dataview[group].unique().tolist()
            dlg = SelectGroupsDlg(
                self, title=f"{group}: Select Items", groups=items, selected=selitems
            )
            if dlg.ShowModal() == wx.ID_CANCEL:
                dlg.Destroy()
                return
            selitems = dlg.get_selected()
            notselected = [i for i in items if i not in selitems]
            dlg.Destroy()
            for value in selitems:
                if self.droppedrows.get((group, value)) is not None:
                    del self.droppedrows[(group, value)]
            for value in notselected:
                self.droppedrows[(group, value)] = np.flatnonzero(
                    self.data[group] == value
                )
            self.modified = True
            if notselected and not self.filters.categories.enabled:
                # hiding a value is an explicit action: Filter Categories goes on
                self.use_categories(True)
                self._filters_changed()
            else:
                self.update_view()
        elif (
            event.GetRow() == -1
            and group in self.numcols
            and self.filters.features.enabled
        ):
            # the range filter of the current column (group)
            shown = self.filters.model_copy(
                update={
                    "range_filters": self._existing_rangefilters(
                        self.filters.range_filters, columns=[group]
                    )
                }
            )
            dlg = ConfigureFiltersDlg(
                self,
                shown,
                self.data,
                self._applied_rows(),
                show_dropped_option=False,
            )
            response = dlg.ShowModal()
            result = dlg.GetData()
            dlg.Destroy()
            if response == wx.ID_OK:
                edited = result.range_filters
                self.filters.range_filters = self._merged_filters(edited)
                if result.features.enabled:
                    self.apply_filters({f["name"]: f for f in edited})
                else:
                    self.use_features(False)
                self._filters_changed()

    def OnAutosize(self, event: wx.CommandEvent) -> None:
        """Fit the column widths to the headers and the widest values shown."""
        font = self.grid.GetFont()
        dc = wx.ClientDC(self)
        dc.SetFont(font)

        numericcols = self.dataview.select_dtypes(include=[np.number])
        floatcols = self.grid.GetTable().GetFloatCols()
        if self.showcolindex:
            self.grid.AutoSizeColLabelSize(0)
            colindex = 1
        else:
            colindex = 0
        mins = numericcols.min()
        maxs = numericcols.max()
        for col in self.dataview.columns.values:
            # autosize header first and get new col width
            self.grid.AutoSizeColLabelSize(colindex)
            headerwidth = self.grid.GetColSize(colindex)
            # determine best size for values in this col
            colseries = self.dataview[col]
            if col not in numericcols.columns.values:
                # strings, categories, objects: the longest text; missing values and
                # an empty table have none
                texts = colseries.dropna().astype(str)
                valuestr = max(texts, key=len) if len(texts) else ""
            else:
                # handle numbers; using numpy min/max is orders of magnitude faster than grid.AutoSize
                minval = mins[col]
                maxval = maxs[col]
                value = maxval
                if len(str(minval)) > len(str(maxval)):
                    value = minval
                if pd.isna(value):  # an empty table or only missing values
                    valuestr = ""
                elif col in floatcols:
                    valuestr = f"{value:.{self.precision}f}"
                else:
                    valuestr = str(int(value))  # integer part only
                logger.debug(
                    f"minval={minval}, maxval={maxval}, value={value},"
                    f" valuestr={valuestr}"
                )
            width, h = dc.GetTextExtent(valuestr)
            width = max(width, headerwidth)
            self.grid.SetColSize(colindex, width + 20)
            colindex += 1

    def OnUnpivot(self, event: wx.CommandEvent) -> None:
        """Run the Unpivot tool on this window's table, in the tool's dialog."""
        if self.on_run_tool is not None:
            self.on_run_tool("Unpivot", self.GetTitle())

    def OnPivotView(self, event: wx.CommandEvent) -> None:
        """Run the Pivot tool on this window's table, in the tool's dialog."""
        if self.on_run_tool is not None:
            self.on_run_tool("Pivot", self.GetTitle())

    def OnSave(self, event: wx.CommandEvent) -> None:
        """Save all rows or the rows shown, by the button's label.

        After a save, the table is marked not modified and
        `REQUEST_RENAME_DATA_WINDOW` is sent with the file name.
        """
        original = self.GetTitle()
        buttonlabel = event.GetEventObject().GetLabel()
        if buttonlabel == SAVE_ALL_ROWS:
            fname = flim.gui.dialogs.save_dataframe(
                self,
                SAVE_ALL_ROWS.rstrip("."),
                self.data,
                original + ".txt",
                saveindex=self.showcolindex,
            )
        elif buttonlabel == SAVE_SHOWN_ROWS:
            fname = flim.gui.dialogs.save_dataframe(
                self,
                SAVE_SHOWN_ROWS.rstrip("."),
                self.dataview,
                original + ".txt",
                saveindex=self.showcolindex,
            )
        else:
            return
        if fname:
            self.modified = False
            pub.sendMessage(
                REQUEST_RENAME_DATA_WINDOW,
                original=original,
                new=os.path.basename(fname),
                frame=self,
            )

    def close_and_destroy(self, event: wx.CloseEvent) -> None:
        """Close the window, after asking to save a modified table.

        The save saves all rows, also those hidden by filters, as `Save All Rows...`
        and File > Save All Windows... do. A window that cannot be closed shows a
        message instead. Cancel, or a save that is cancelled or fails, keeps the
        window open. Sends
        `CLOSING_DATA_WINDOW` before the window is destroyed.
        """
        if not self.enableclose:
            wx.MessageBox("This window needs to stay open. It can be minimized.")
            return
        if self.savemodified and self.modified:
            dlg = wx.MessageDialog(
                self,
                "The table has not been saved.\n\nSave all its rows, also those"
                " hidden by filters?\n",
                self.GetLabel(),
                style=wx.YES_NO | wx.CANCEL,
            )
            answer = dlg.ShowModal()
            dlg.Destroy()
            if answer == wx.ID_YES:
                if flim.gui.dialogs.save_dataframe(
                    self,
                    SAVE_ALL_ROWS.rstrip("."),
                    self.data,
                    self.GetTitle() + ".txt",
                    saveindex=self.showcolindex,
                ):
                    self.modified = False
                else:
                    # the save dialog was cancelled or saving failed
                    return
            elif answer == wx.ID_CANCEL:
                return
        pub.sendMessage(CLOSING_DATA_WINDOW, data=self.dataview, frame=self)
        self.Destroy()
