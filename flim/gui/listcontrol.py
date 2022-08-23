#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 20 08:45:35 2018

@author: khs3z
"""

import logging
import numpy as np
import wx
import wx.lib.mixins.listctrl as listmix
from pubsub import pub

from flim.gui.events import FILTERS_UPDATED, ANALYSIS_BINS_UPDATED

# from wx.lib.newevent import NewEvent
# FilterUpdatedEvent, EVT_FILTERUPDATED = NewEvent()

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
    listmix.CheckListCtrlMixin,
    listmix.ListCtrlAutoWidthMixin,
    listmix.TextEditMixin,
):
    def __init__(self, *args, **kwargs):
        wx.ListCtrl.__init__(self, *args, **kwargs)
        listmix.CheckListCtrlMixin.__init__(self)
        listmix.TextEditMixin.__init__(self)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        self.data = {}
        self.editable = []
        self.setResizeColumn(2)
        self.checked_indices = []

        self.enableevents = True
        self.Bind(wx.EVT_LIST_BEGIN_LABEL_EDIT, self.BeginLabelEdit)
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.EndLabelEdit)

    def fire_rowsupdated_event(self, items):
        # event = ListCtrlUpdatedEvent(EVT_AU_TYPE, self.GetId())
        # event.SetUpdatedItems(items)
        # self.GetEventHandler().ProcessEvent(event)
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
            #            self.SetStringItem(idx, 2, str(rowdata[0]))
            ##           self.SetStringItem(idx, 3, str(rowdata[1]))
            self.SetItem(idx, 2, str(rowdata[0]))
            self.SetItem(idx, 3, str(rowdata[1]))
            self.Update()

    def SetEditable(self, editable):
        if self.editable is None:
            self.editable = []
        else:
            self.editable = editable

    #    def set_checkedindices(self,checked):
    #        if checked is None:
    #            self.checked = []
    #        else:
    #            self.checked_indices = sorted(set(checked))

    #    def check_index(self,index,enable=True):
    #        if index < 0 or index >= self.GetItemCount():
    #            return
    #        if enable:
    #            self.checked_indices.append(index)
    #            self.checked_indices = sorted(set(self.checked_indices))
    #        else:
    #            try:
    #                self.checked_indices.remove(index)
    #            except:
    #                pass

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
                #                self.data[item].select(enable)
                changed[item] = self.data[item]
        self.Thaw()
        self.enableevents = True
        self.fire_rowsupdated_event(changed)

    def get_checked_items(self):
        checked = {}
        for idx in range(self.GetItemCount()):
            if self.IsChecked(idx):
                key = self.GetItem(idx, self.get_key_col()).GetText()  # .encode('utf-8')
                # PROBLEM MULTIINDEX
                checked[key] = self.data[key]
        return checked

    def BeginLabelEdit(self, event):
        col = event.GetColumn()
        if col == 0:
            self.ToggleItem(event.GetIndex())
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
        logging.debug(f"OnCheckItem %s" % rowkey)
        #        self.data[rowkey].select(flag)
        if self.enableevents:
            # PROBLEM MULTIINDEX
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})


#    def OpenEditor(self, col, row):
#        if col == 1:
#            listmix.TextEditMixin.OpenEditor(self,col,row)


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
        # event = ListCtrlUpdatedEvent(EVT_FU_TYPE, self.GetId())
        # event.SetUpdatedItems(items)
        # self.GetEventHandler().ProcessEvent(event)
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

        #        for dkey in dropped:
        #            if dkey not in data:
        #                dropped.remove(dkey)
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
        #        event = ListCtrlUpdatedEvent(EVT_FU_TYPE, self.GetId())
        #        event.SetUpdatedItems(self.data)
        #        self.GetEventHandler().ProcessEvent(event)
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
                self.SetItem(idx, 4, f"{no_droppedfromview}:,")
                logging.debug(
                    "\tSetting dropped row, key=%s, index=%d: %d, dropped from view: %d"
                    % (key, idx, len(dropped), no_droppedfromview)
                )
            else:
                self.SetItem(idx, 4, "---")
                logging.debug(
                    "\tSetting dropped row, index=%d, key=%s, droppes=%s"
                    % (idx, key, "---")
                )
        self.Update()

    def UpdateDroppedRows(self, droppedrows):
        if not self.showdropped:
            return
        logging.debug("FilterListCtrl.UpdateDroppedRows, %d filters" % len(droppedrows))
        droppedidx = {self.get_index_by_key(key): key for key in droppedrows}
        for idx in range(self.GetItemCount()):
            key = droppedidx.get(idx)
            if key is not None:  # and if self.data[key].is_selected():
                dropped = droppedrows[key]
                self.dropped[key] = dropped
                no_droppedfromview = len(self.get_view_dropped(key))
                self.SetItem(idx, 4, f"{no_droppedfromview:,}")
                logging.debug(
                    "\tUpdating dropped row (SELECTED), key=%s, index=%d: %d, dropped from view: %d"
                    % (key, idx, len(dropped), no_droppedfromview)
                )
            else:
                self.SetItem(idx, 4, "---")
                logging.debug(
                    "\tUpdating dropped row (NOT SELECTED), key=%s, index=%d" % (key, idx)
                )
        """        
        for key in sorted(droppedrows):
            idx = self.get_index_by_key(key)
            if idx is not None:
                dropped = droppedrows[key]
                self.dropped[key] = dropped
                if self.data[key].is_selected():
                    print "\tUpdating dropped row (SELECTED), key=%s, index=%d: %d" % (key, idx, len(dropped))
#                    self.SetStringItem(idx, 4, str(len(dropped)))
                    self.SetItem(idx, 4, str(len(dropped)))
                else:
                    print "\tUpdating dropped row (NOT SELECTED), key=%s, index=%d: %d" % (key, idx, len(dropped))
                    self.SetItem(idx, 4, "---")
#                    self.SetStringItem(idx, 4, "---")
        """
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
        # get those from alldropped that were not already dropped by view category filter
        # those are the ones dropped by the range filters on the curren view
        viewdropped = np.setdiff1d(rangedropped, self.otherdropped, assume_unique=True)
        return viewdropped

    def get_total_dropped_rows(self):
        # alldroppedrows = []
        # for selitem in self.get_checked_items():
        #    d = self.dropped.get(selitem)
        #   if d is not None:
        #        alldroppedrows.extend(d)
        # alldroppedrows = set(alldroppedrows)
        # print (f"total dropped rows (list): {len(alldroppedrows)}")

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

    #    def fire_rowsupdated_event(self, rfilters):
    #        event = FilterUpdatedEvent(EVT_FU_TYPE, self.GetId())
    #        event.SetFilter(rfilters)
    #        self.GetEventHandler().ProcessEvent(event)

    def EndLabelEdit(self, event):
        idx = event.GetIndex()
        col = event.GetColumn()
        rowkey = self.GetItem(idx, self.get_key_col()).GetText()
        filter = self.data[rowkey]
        newvalue = event.GetItem().GetText()
        logging.debug("FilterListCtrl.EndLabelEdit")
        logging.debug("\t%s" % str(self.data[rowkey].get_params()))
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
        logging.debug("\t%s" % str(self.data[rowkey].get_params()))
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
        logging.debug("\t%s" % str(self.data[rowkey].get_params()))
        self.UpdateDroppedRows(self.dropped)

        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})
