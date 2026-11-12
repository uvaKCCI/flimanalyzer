import logging
import pandas as pd
import numpy as np
import os
import re
import collections.abc

import wx
import wx.grid
import wx.lib.mixins.gridlabelrenderer as glr
from pubsub import pub

from flim.core.filter import RangeFilter
from flim.core.filtering import new_range, window_filters
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
from flim.gui.dialogs import SelectGroupsDlg, ConfigureFiltersDlg, RenameGroupsDlg

logger = logging.getLogger(__name__)

# the table window's save buttons: all rows (also those hidden by filters), or the rows
# shown
SAVE_ALL_ROWS = "Save All Rows..."
SAVE_SHOWN_ROWS = "Save Shown Rows..."

EVEN_ROW_COLOUR = "#CCE6FF"
GRID_LINE_COLOUR = "#ccc"


class FilterColLabelRenderer(glr.GridLabelRenderer):
    def __init__(self, bgcolor):
        self._bgcolor = bgcolor

    def Draw(self, grid, dc, rect, col):
        dc.SetBrush(wx.Brush(self._bgcolor))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(rect)
        hAlign, vAlign = grid.GetColLabelAlignment()
        text = grid.GetColLabelValue(col)
        self.DrawBorder(grid, dc, rect)
        self.DrawText(grid, dc, rect, text, hAlign, vAlign)


class PandasGrid(wx.grid.Grid, glr.GridWithLabelRenderersMixin):
    def __init__(self, *args, **kw):
        wx.grid.Grid.__init__(self, *args, **kw)
        glr.GridWithLabelRenderersMixin.__init__(self)


class PandasTable(wx.grid.GridTableBase):
    def __init__(self, data=None, showcolindex=False, categories_first=False):
        wx.grid.GridTableBase.__init__(self)
        self.SetData(data, showcolindex, categories_first)

    def SetData(self, data, showcolindex=False, categories_first=False):
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

    def GetData(self):
        return self.data

    def GetFloatCols(self):
        return self.floatcols

    def GetFloatColIdx(self):
        return [
            colindex
            for colindex in range(len(self.colheaders))
            if self.colheaders[colindex] in self.floatcols
        ]

    def GetLongColIdx(self):
        return [
            colindex
            for colindex in range(len(self.colheaders))
            if self.colheaders[colindex] in self.intcols
        ]

    def GetNumberRows(self):
        return len(self.data)

    def GetNumberCols(self):
        if self.showcolindex:
            return len(self.data.columns) + 1
        else:
            return len(self.data.columns)

    def GetTypeName(self, row, col):
        if self.GetColLabelValue(col) in self.floatcols:
            return wx.grid.GRID_VALUE_FLOAT
        elif self.GetColLabelValue(col) in self.intcols:
            return wx.grid.GRID_VALUE_LONG
        else:
            return wx.grid.GRID_VALUE_STRING

    def GetValue(self, row, col):
        if self.showcolindex:
            if col == 0:
                return self.data.index[row]
            return self.data.iloc[row, col - 1]
        else:
            return self.data.iloc[row, col]

    def SetValue(self, row, col, value):
        if self.showcolindex:
            self.data.iloc[row, col - 1] = value
        else:
            self.data.iloc[row, col] = value

    def GetColLabelValue(self, col):
        if self.showcolindex:
            if col == 0:
                if self.data.index.name is None:
                    return "Index"
                else:
                    return "\n".join(self.data.index.names)
            return self.colheaders[col - 1]
        else:
            return self.colheaders[col]

    def GetAttr(self, row, col, prop):
        if self.GetColLabelValue(col) in self.intcols:
            attr = wx.grid.GridCellAttr()
            attr.SetAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
            return attr
        else:
            return wx.grid.GridTableBase.GetAttr(self, row, col, prop)


def category_values(column: pd.Series) -> list:
    """The values in a column: of a category column in its category order (see
    Order Categories), else in the order they occur."""
    present = column.unique()
    if isinstance(column.dtype, pd.CategoricalDtype):
        observed = set(present)
        return [c for c in column.cat.categories if c in observed]
    return list(present)


class PandasFrame(wx.Frame):
    def __init__(
        self,
        parent,
        title,
        filters=None,
        data=None,
        showcolindex=False,
        groups=None,
        analyzable=True,
        savemodified=True,
        precision=3,
        enableclose=True,
        on_filters_changed=None,
        on_run_tool=None,
    ):
        """
        Args:
            filters: WindowFilters (flim.core.filtering), shared by the GUI's data
                windows (default: the built-in defaults, not shared).
            on_filters_changed: called with ``filters`` after the user changes them
                (filter checkbox, Filter Settings dialog).
            on_run_tool: called with a tool's name and this window's title to run
                the tool on this window's table in its dialog (Pivot, Unpivot); None:
                the window has no such buttons.
        """
        super(PandasFrame, self).__init__(parent, wx.ID_ANY, title)
        self.filters = filters if filters is not None else window_filters(AppSettings.default())
        self.on_filters_changed = on_filters_changed
        self.on_run_tool = on_run_tool
        self.enableclose = enableclose
        self.grid = None
        self.SetData(data, showcolindex, groups, analyzable, savemodified, precision)
        self._init_gui()
        self.Layout()

        self.Bind(wx.EVT_CLOSE, self.close_and_destroy)
        self.Bind(wx.EVT_ACTIVATE, self.activate)
        pub.subscribe(self.OnDataWindowRenamed, RENAMED_DATA_WINDOW)

    def activate(self, event):
        if event.GetActive():
            pub.sendMessage(FOCUSED_DATA_WINDOW, data=self.dataview, frame=self)
        event.Skip()

    def SetData(
        self,
        data=None,
        showcolindex=False,
        groups=None,
        analyzable=True,
        savemodified=True,
        precision=3,
    ):
        self.analyzable = analyzable
        self.savemodied = savemodified
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
            groups = list(data.select_dtypes(["category"]).columns.values)
            groups = data.select_dtypes(["category"]).columns.get_level_values(0).values
        self.groups = groups
        self.numcols = data.select_dtypes(["number"]).columns.get_level_values(0).values
        self.popupmenus = {}
        for group in groups:
            self.popupmenus[group] = self.create_popupmenu(group)
        if self.grid is not None:
            logger.debug(
                f"datapanel.PandasFrame.SetData - REFRESHING {self.GetTitle()}"
            )
            self.update_view()
        else:
            logger.debug(
                f"datapanel.PandasFrame.SetData - NOT REFRESHING {self.GetTitle()}"
            )

    def set_header_renderer(self):
        if self.grid is not None:
            categorycols = list(self.data.select_dtypes(["category"]).columns.values)
            for i in range(self.grid.GetNumberCols()):
                collabel = self.grid.GetColLabelValue(i)
                if collabel in categorycols:
                    self.grid.SetColLabelRenderer(i, FilterColLabelRenderer("#d0d0ff"))
                else:
                    self.grid.SetColLabelRenderer(i, glr.GridDefaultColLabelRenderer())

    def GetViewData(self):
        return self.dataview

    def GetData(self):
        return self.data

    def _init_gui(self):
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

        self.filtercb = wx.CheckBox(self, wx.ID_ANY, label="Filter Data")
        self.filtercb.SetValue(self.filters.use)
        self.filtercb.Bind(wx.EVT_CHECKBOX, self.OnFilterData)

        self.filterbutton = wx.Button(self, wx.ID_ANY, "Filter Settings...")
        self.filterbutton.Enable(self.filtercb.GetValue())
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
        toolsizer.Add(self.filtercb, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(self.filterbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(pivotviewbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(self.unpivotbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(saveallbutton, 0, wx.ALL | wx.EXPAND, 5)
        toolsizer.Add(saveviewbutton, 0, wx.ALL | wx.EXPAND, 5)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.grid, 1, wx.EXPAND)
        sizer.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5)
        sizer.Add(toolsizer)

        self.SetSizer(sizer)


    def update_precision(self, precision):
        if precision:
            self.precision = precision
            for colindex in self.grid.GetTable().GetFloatColIdx():
                self.grid.SetColFormatFloat(
                    colindex, width=-1, precision=self.precision
                )

    def is_analyzable(self):
        return self.analyzable

    @property
    def modified(self) -> bool:
        """Whether the table has changes not saved to a file; reported to the window's
        `on_modified` callback (set when the window is registered) when set."""
        return getattr(self, "_modified", True)

    @modified.setter
    def modified(self, value) -> None:
        self._modified = bool(value)
        callback = getattr(self, "on_modified", None)
        if callback is not None:
            callback(self._modified)

    def is_modified(self):
        return self.modified

    def set_modified(self, modified=True):
        self.modified = modified

    def apply_filters(self, filtercfg, showdiscarded=False):
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


    def OnDataWindowRenamed(self, original, new, frame):
        if frame is self:  # by identity: another window may have had the same title
            self.SetTitle(new)

    def OnPrecisionChange(self, event):
        self.update_precision(event.GetEventObject().GetValue())
        self.grid.Refresh()

    def updateusefilter(self, enabled, showdiscarded=False):
        self.filters.use = enabled
        self.filterbutton.Enable(enabled)
        filtercfg = self.filters.range_filters
        if enabled:
            # apply
            self.apply_filters(
                {f["name"]: f for f in filtercfg}, showdiscarded=showdiscarded
            )
        else:
            # clear
            self.apply_filters({})

    def OnFilterData(self, event):
        cb = event.GetEventObject()
        self.updateusefilter(cb.GetValue())
        self._filters_changed()

    def _filters_changed(self):
        if self.on_filters_changed is not None:
            self.on_filters_changed(self.filters)

    def _existing_rangefilters(self, filterlist, columns=None):
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

    def OnFilterSettings(self, event):
        rfilterlist = self.filters.range_filters
        shown = self.filters.model_copy(
            update={"range_filters": self._existing_rangefilters(rfilterlist)}
        )
        # a copy of the dropped rows, so that Cancel leaves droppedrows unchanged
        dlg = ConfigureFiltersDlg(self, shown, self.data, self.droppedrows.copy())
        response = dlg.ShowModal()
        if response == wx.ID_OK:
            edited = dlg.GetData()
            self.filters.range_filters = self._merged_filters(edited.range_filters)
            self.filters.show_dropped = edited.show_dropped
            self.filters.use = edited.use
            self.filtercb.SetValue(edited.use)
            self.updateusefilter(edited.use, showdiscarded=edited.show_dropped)
            self._filters_changed()

    def _merged_filters(self, edited) -> list:
        """The range filters with the edited ones replaced (by column name)."""
        filters = {f["name"]: f for f in self.filters.range_filters}
        filters.update({f["name"]: f for f in edited})
        return list(filters.values())

    def OnPopupItemSelected(self, event):
        item = self.currentpopup.FindItemById(event.GetId())
        value = item.GetText()
        group = item.GetMenu().GetTitle()
        if value in ["All", "None"]:
            for item in self.currentpopup.GetMenuItems():
                label = item.GetLabel()
                if item.IsCheckable():
                    item.Check(value == "All")
                    if value == "All":
                        if self.droppedrows.get((group, label)) is not None:
                            del self.droppedrows[(group, label)]
                            self.modified = True
                    else:  #'None'
                        self.droppedrows[(group, label)] = np.flatnonzero(
                            self.data[group] == label
                        )
                        self.modified = True

        else:
            ischecked = item.IsChecked()
            if ischecked:
                if self.droppedrows.get((group, value)) is not None:
                    del self.droppedrows[(group, value)]
                    self.modified = True
                else:
                    wx.MessageBox(f"View selection for '{group}' out of sync.")
            else:
                self.droppedrows[(group, value)] = np.flatnonzero(
                    self.data[group] == value
                )
                self.modified = True
        self.update_view()

    def _flatten_array(self, arraylist):
        arraylist = [a for a in arraylist if len(a) > 0]
        if len(arraylist) > 0:
            arraylist = np.concatenate(arraylist)
        return np.unique(arraylist)

    def update_view(self, showdiscarded=False):
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
        # get rows dropped by category filters
        catdropped = self._flatten_array(
            [
                self.droppedrows[fname]
                for fname in self.droppedrows
                if fname not in rfilter_names
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
            )
            self.GetEventHandler().ProcessEvent(event)

    def create_popupmenu(self, colheader):
        menu = wx.Menu()
        menu.SetTitle(colheader)
        for item in ["All", "None"]:
            mitem = menu.Append(-1, item)
            self.Bind(wx.EVT_MENU, self.OnPopupItemSelected, mitem)
        for chitem in category_values(self.data[colheader]):
            mitem = menu.AppendCheckItem(-1, str(chitem))
            if mitem is not None:
                mitem.Check(True)
                self.Bind(wx.EVT_MENU, self.OnPopupItemSelected, mitem)
        menu.InsertSeparator(2)
        return menu

    def OnLabelDClick(self, event):
        group = self.grid.GetColLabelValue(event.GetCol())
        if event.GetRow() == -1 and group in self.groups:
            dlg = RenameGroupsDlg(self, title=f"{group}: Pattern Rename")
            if dlg.ShowModal() == wx.ID_CANCEL:
                dlg.Destroy()
                return
            pattern = dlg.patterntxt.GetLineText(0)
            replacement = dlg.replacetxt.GetLineText(0)

            self.data[group] = self.data[group].apply(
                lambda x: re.sub(pattern, replacement, str(x))
            )
            self.data[group] = self.data[group].astype("category")
            self.modified = True
            self.update_view()

    def OnLabelClick(self, event):
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
            self.update_view()
        elif (
            event.GetRow() == -1 and group in self.numcols and self.filtercb.GetValue()
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
                self.droppedrows.copy(),
                showusefilter=False,
            )
            response = dlg.ShowModal()
            if response == wx.ID_OK:
                edited = dlg.GetData().range_filters
                self.filters.range_filters = self._merged_filters(edited)
                self.apply_filters({f["name"]: f for f in edited})
                self._filters_changed()

    def OnAutosize(self, event):
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
            if col not in numericcols.columns.values and (
                isinstance(colseries, (str, bytes, collections.abc.Iterable))
            ):
                # handle strings, categories, objects
                logger.debug(f"AUTOSIZE col {col}")
                rowidx = colseries.map(len).idxmax()
                valuestr = colseries[rowidx]
            else:
                # handle numbers; using numpy min/max is orders of magnitude faster than grid.AutoSize
                minval = mins[col]
                maxval = maxs[col]
                value = maxval
                if len(str(minval)) > len(str(maxval)):
                    value = minval
                if col in floatcols:
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

    def OnUnpivot(self, event):
        """Run the Unpivot tool on this window's table, in the tool's dialog."""
        if self.on_run_tool is not None:
            self.on_run_tool("Unpivot", self.GetTitle())

    def OnPivotView(self, event):
        """Run the Pivot tool on this window's table (the rows it shows), in the
        tool's dialog."""
        if self.on_run_tool is not None:
            self.on_run_tool("Pivot", self.GetTitle())

    def OnViewAll(self, event):
        if len(self.droppedrows) > 0:
            for colheader in self.popupmenus:
                for item in self.popupmenus[colheader].GetMenuItems():
                    if item.IsCheckable():
                        item.Check(True)
            self.droppedrows = {}
            self.modified = True
            self.update_view()

    def OnSave(self, event):
        original = self.GetTitle()
        buttonlabel = event.GetEventObject().GetLabel()
        if buttonlabel == SAVE_ALL_ROWS:
            fname = flim.gui.dialogs.save_dataframe(
                self,
                "Save entire data.",
                self.data,
                original + ".txt",
                saveindex=self.showcolindex,
            )
        elif buttonlabel == SAVE_SHOWN_ROWS:
            fname = flim.gui.dialogs.save_dataframe(
                self,
                "Save current data view",
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

    def OnSaveView(self, event):
        original = self.GetTitle()
        fname = flim.gui.dialogs.save_dataframe(
            self,
            "Save current data view",
            self.dataview,
            original + ".txt",
            saveindex=self.showcolindex,
        )
        if fname:
            self.modified = False
            pub.sendMessage(
                REQUEST_RENAME_DATA_WINDOW, original=original, new=fname, frame=self
            )

    def close_and_destroy(self, event):
        if not self.enableclose:
            wx.MessageBox("This window needs to stay open. It can be minimized.")
            return
        if self.savemodied and self.modified:
            dlg = wx.MessageDialog(
                self,
                "The current view of the data has not been saved.\n\nDo you want to"
                " save the data?\n",
                self.GetLabel(),
                style=wx.YES_NO | wx.CANCEL,
            )
            answer = dlg.ShowModal()
            if answer == wx.ID_YES:
                if flim.gui.dialogs.save_dataframe(
                    self,
                    "Save current data view",
                    self.dataview,
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


class TestApp(wx.App):
    def __init__(self, data):
        self.data = data
        super(TestApp, self).__init__()

    def OnInit(self):
        self.frame = PandasFrame(None, "Test", None, self.data)
        self.frame.Show(True)
        return True


if __name__ == "__main__":
    np.random.seed(0)
    df = pd.DataFrame(np.random.randn(8, 4), columns=["A", "B", "C", "D"])
    app = TestApp(df)
    app.MainLoop()
