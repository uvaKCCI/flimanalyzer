#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List controls with check boxes for analysis bins (AnalysisListCtrl) and range
filters (FilterListCtrl); changes are published with pubsub."""

import logging
import numpy as np
import wx
import wx.lib.mixins.listctrl as listmix
from pubsub import pub

from flim.gui.events import FILTERS_UPDATED, ANALYSIS_BINS_UPDATED

EVT_FU_TYPE = wx.NewEventType()
EVT_FILTERUPDATED = wx.PyEventBinder(EVT_FU_TYPE, 1)

EVT_AU_TYPE = wx.NewEventType()
EVT_ANALYSISUPDATED = wx.PyEventBinder(EVT_AU_TYPE, 1)


class ListCtrlUpdatedEvent(wx.PyCommandEvent):
    def __init__(self, evtType, id):
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.items = None

    def SetUpdatedItems(self, items):
        self.items = items

    def GetUpdatedItems(self):
        return self.items


class AnalysisListCtrl(
    wx.ListCtrl,
    listmix.ListCtrlAutoWidthMixin,
    listmix.TextEditMixin,
):
    """Report list with a native checkbox in the first column; cells of the columns
    marked editable (SetEditable) can be edited.

    Checking an item, by the user or with CheckItem(), calls OnCheckItem(index,
    flag) once per state change.
    """

    def __init__(self, *args, **kwargs):
        wx.ListCtrl.__init__(self, *args, **kwargs)
        listmix.TextEditMixin.__init__(self)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        self.EnableCheckBoxes(True)
        self.data = {}
        self.editable = []
        self.setResizeColumn(2)
        self.checked_indices = []
        self._checking = False

        self.enableevents = True
        self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.BeginLabelEdit)
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.EndLabelEdit)
        self.Bind(wx.EVT_LIST_ITEM_CHECKED, self._on_item_checked)
        self.Bind(wx.EVT_LIST_ITEM_UNCHECKED, self._on_item_checked)

    def IsChecked(self, index):
        return self.IsItemChecked(index)

    def CheckItem(self, index, check=True):
        if self.IsItemChecked(index) == check:
            return
        # the native CheckItem() sends EVT_LIST_ITEM_(UN)CHECKED synchronously;
        # notify OnCheckItem() once, here, instead of from the event handler
        self._checking = True
        try:
            wx.ListCtrl.CheckItem(self, index, check)
        finally:
            self._checking = False
        self.OnCheckItem(index, check)

    def ToggleItem(self, index):
        self.CheckItem(index, not self.IsItemChecked(index))

    def _on_item_checked(self, event):
        if not self._checking:
            # checkbox clicked by the user
            self.OnCheckItem(event.GetIndex(), self.IsItemChecked(event.GetIndex()))
        event.Skip()

    def fire_rowsupdated_event(self, items):
        pub.sendMessage(ANALYSIS_BINS_UPDATED, updateditems=items)

    def GetData(self):
        return self.data

    def SetData(self, data, headers=[], types=[], keep_selection=True):
        current_sel = self.get_checked_items()
        if data is None:
            self.data = {}
        else:
            self.data = data
        if headers is None:
            headers = []
        if types is None:
            types = []
        self.DeleteAllItems()
        for rowheader in sorted(data):
            values = data[rowheader]
            row = [" ", rowheader]
            row.extend(values[: len(headers) - 2])
            self.Append(row)
        if keep_selection:
            self.check_items(current_sel, True)

    def get_index_by_key(self, key):
        keycol = self.get_key_col()
        for idx in range(self.GetItemCount()):
            if self.GetItem(idx, keycol).GetText() == key:
                return idx
        return None

    def SetRow(self, key, rowdata):
        logging.debug("AnalysisListCtrl.SetRow")
        idx = self.get_index_by_key(key)
        if idx is not None:
            logging.debug(f"Updating index {idx}: {rowdata}")
            self.SetItem(idx, 2, str(rowdata[0]))
            self.SetItem(idx, 3, str(rowdata[1]))
            self.Update()

    def SetEditable(self, editable):
        if self.editable is None:
            self.editable = []
        else:
            self.editable = editable

    def get_checked_indices(self):
        checked = []
        for idx in range(self.GetItemCount()):
            if self.IsChecked(idx):
                checked.append(idx)
        return checked

    def check_items(self, items, enable):
        if items is None:
            return
        self.enableevents = False
        self.Freeze()
        changed = {}
        for item in items:
            idx = self.get_index_by_key(item)
            if idx is not None and enable != self.IsChecked(idx):
                self.CheckItem(idx, enable)
                changed[item] = self.data[item]
        self.Thaw()
        self.enableevents = True
        self.fire_rowsupdated_event(changed)

    def get_checked_items(self):
        checked = {}
        for idx in range(self.GetItemCount()):
            if self.IsChecked(idx):
                key = self.GetItem(
                    idx, self.get_key_col()
                ).GetText()
                # looked up by the cell text: a data key that is not a string (e.g.
                # a MultiIndex tuple) raises KeyError
                checked[key] = self.data[key]
        return checked

    def BeginLabelEdit(self, event):
        col = event.GetColumn()
        if col == 0:
            # column 0 holds the checkbox, which toggles itself when clicked
            event.Veto()
        elif col > len(self.editable) or self.editable[col]:
            event.Skip()
        else:
            event.Veto()

    def get_key_col(self):
        return 1

    def EndLabelEdit(self, event):
        idx = event.GetIndex()
        col = event.GetColumn()
        rowkey = self.GetItem(idx, self.get_key_col()).GetText()
        logging.debug(self.data[rowkey])
        newvalue = event.GetItem().GetText()
        if col in [2, 3]:
            newvalue = float(newvalue)
        elif col == 4:
            newvalue = int(newvalue)
        self.data[rowkey][col - 2] = newvalue
        logging.debug(self.data[rowkey])
        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})

    def OnCheckItem(self, index, flag):
        rowkey = self.GetItem(index, self.get_key_col()).GetText()
        logging.debug(f"OnCheckItem {rowkey}")
        if self.enableevents:
            # looked up by the cell text: a data key that is not a string (e.g. a
            # MultiIndex tuple) raises KeyError
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})


class FilterListCtrl(AnalysisListCtrl):
    def __init__(
        self,
        *args,
        dataframe=None,
        dropped=None,
        showdropped=True,
        fireevents=True,
        **kwargs,
    ):
        AnalysisListCtrl.__init__(self, *args, **kwargs)
        self.dataframe = dataframe
        self.showdropped = showdropped
        self.setdrop(dropped)
        self.fireevents = fireevents
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.EndLabelEdit)
        self.Bind(EVT_FILTERUPDATED, self.OnFilterUpdated)

    def setdrop(self, dropped):
        if dropped is None:
            dropped = {}
        self.dropped = dropped
        rfilter_names = [name for name in self.data]
        non_rfilters = [name for name in dropped if name not in rfilter_names]
        odropped = [dropped[n] for n in non_rfilters]
        if len(odropped) > 1:
            odropped = np.concatenate(odropped)
            self.otherdropped = np.unique(odropped)
        else:
            self.otherdropped = []

    def fire_rowsupdated_event(self, updated):
        if self.fireevents:
            pub.sendMessage(
                FILTERS_UPDATED,
                updateditems=updated,
                totaldropped=len(self.get_total_dropped_rows()),
                viewdropped=len(self.get_view_dropped()),
                viewlength=len(self.dataframe) - len(self.otherdropped),
            )

    def SetData(self, data, dataframe=None, dropped=None, headers=[], types=[]):
        if data is None:
            self.data = {}
        else:
            self.data = data
        self.dataframe = dataframe
        if headers is None:
            headers = []
        if types is None:
            types = []
        self.setdrop(dropped)

        self.DeleteAllItems()
        self.enableevents = False
        for rowkey in sorted(data):
            rfilter = data[rowkey]
            if self.showdropped:
                row = [
                    " ",
                    rowkey,
                    rfilter.get_rangelow(),
                    rfilter.get_rangehigh(),
                    self.get_dropped_str(rowkey),
                ]
            else:
                row = [" ", rowkey, rfilter.get_rangelow(), rfilter.get_rangehigh()]
            self.Append(row)
            self.CheckItem(self.GetItemCount() - 1, rfilter.is_selected())
        self.fire_rowsupdated_event(self.data)
        self.enableevents = True

    def check_items(self, items, enable):
        if items is None:
            return
        self.enableevents = False
        self.Freeze()
        changed = {}
        for item in items:
            idx = self.get_index_by_key(item)
            if idx is not None and enable != self.IsChecked(idx):
                self.CheckItem(idx, enable)
                self.data[item].select(enable)
                changed[item] = self.data[item]
        self.Thaw()
        self.enableevents = True
        self.fire_rowsupdated_event(changed)

    def OnFilterUpdated(self, event):
        logging.debug(f"{len(event.GetUpdatedItems())} updated")
        for i in event.GetUpdatedItems():
            logging.debug(i)
        event.Skip()

    def GetDroppedRows(self, rowkey):
        return self.dropped.get(rowkey)

    def SetDroppedRows(self, droppedrows):
        if droppedrows is None:
            droppedrows = {}
        self.dropped = droppedrows
        logging.debug(f"{len(droppedrows)} filters")
        for idx in range(self.GetItemCount()):
            key = self.GetItem(idx, self.get_key_col()).GetText()
            if key in droppedrows:
                dropped = droppedrows[key]
                no_droppedfromview = len(self.get_view_dropped(key))
                self.SetItem(idx, 4, f"{no_droppedfromview:,}")
                logging.debug(
                    f"\tSetting dropped row, key={key}, index={idx}: {len(dropped)},"
                    f" dropped from view: {no_droppedfromview}"
                )
            else:
                self.SetItem(idx, 4, "---")
                logging.debug(
                    f"\tSetting dropped row, index={idx}, key={key}, dropped=---"
                )
        self.Update()

    def UpdateDroppedRows(self, droppedrows):
        if not self.showdropped:
            return
        logging.debug(f"FilterListCtrl.UpdateDroppedRows, {len(droppedrows)} filters")
        droppedidx = {self.get_index_by_key(key): key for key in droppedrows}
        for idx in range(self.GetItemCount()):
            key = droppedidx.get(idx)
            if key is not None:
                dropped = droppedrows[key]
                self.dropped[key] = dropped
                no_droppedfromview = len(self.get_view_dropped(key))
                self.SetItem(idx, 4, f"{no_droppedfromview:,}")
                logging.debug(
                    f"\tUpdating dropped row (SELECTED), key={key}, index={idx}:"
                    f" {len(dropped)}, dropped from view: {no_droppedfromview}"
                )
            else:
                self.SetItem(idx, 4, "---")
                logging.debug(
                    f"\tUpdating dropped row (NOT SELECTED), key={key}, index={idx}"
                )
        self.Update()

    def get_dropped_str(self, key):
        if key in self.dropped:
            return f"{len(self.get_view_dropped(key)):,}"
        else:
            return "---"

    def get_view_dropped(self, key=None):
        if not key:
            rangedropped = self.get_total_dropped_rows()
        else:
            if self.dropped[key] is not None:
                rangedropped = self.dropped[key]
            else:
                rangedropped = []
        # the rows of rangedropped that the filters not in this list (otherdropped)
        # have not dropped already: the rows the range filters drop from the view
        viewdropped = np.setdiff1d(rangedropped, self.otherdropped, assume_unique=True)
        return viewdropped

    def get_total_dropped_rows(self):
        alldroppedrows = [
            self.dropped.get(selitem)
            for selitem in self.get_checked_items()
            if self.dropped.get(selitem) is not None
        ]
        if len(alldroppedrows) > 0:
            alldroppedrows = np.concatenate(alldroppedrows)
            alldroppedrows = np.unique(alldroppedrows)
        logging.debug(f"total dropped rows: {len(alldroppedrows)}")
        return alldroppedrows

    def EndLabelEdit(self, event):
        idx = event.GetIndex()
        col = event.GetColumn()
        rowkey = self.GetItem(idx, self.get_key_col()).GetText()
        filter = self.data[rowkey]
        newvalue = event.GetItem().GetText()
        logging.debug("FilterListCtrl.EndLabelEdit")
        logging.debug(f"\t{self.data[rowkey].get_params()}")
        if col == 2:
            if float(newvalue) == self.data[rowkey].get_rangelow():
                logging.debug("\tnothing to update")
                return
            self.data[rowkey].set_rangelow(float(newvalue))
        elif col == 3:
            if float(newvalue) == self.data[rowkey].get_rangehigh():
                logging.debug("\tnothing to update")
                return
            self.data[rowkey].set_rangehigh(float(newvalue))
        if filter.is_selected():
            self.dropped[rowkey] = filter.get_dropped(self.dataframe)
        elif self.dropped.get(rowkey) is not None:
            del self.dropped[rowkey]
        logging.debug(f"\t{self.data[rowkey].get_params()}")
        self.UpdateDroppedRows(self.dropped)
        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})

    def OnCheckItem(self, index, flag):
        logging.debug("OnCheckItem")
        rowkey = self.GetItem(index, self.get_key_col()).GetText()
        filter = self.data[rowkey]
        filter.select(flag)
        if filter.is_selected():
            self.dropped[rowkey] = filter.get_dropped(self.dataframe)
        elif self.dropped.get(rowkey) is not None:
            del self.dropped[rowkey]
        logging.debug(f"\t{self.data[rowkey].get_params()}")
        self.UpdateDroppedRows(self.dropped)

        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})
