#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List controls with check boxes for analysis bins and range filters.

`AnalysisListCtrl` lists analysis bins, `FilterListCtrl` lists range filters; changes
are published with pubsub.
"""

import logging
from typing import Any, Optional, Union

import numpy as np
import pandas as pd
import wx
import wx.lib.mixins.listctrl as listmix
from pubsub import pub

from flim.core.filter import RangeFilter
from flim.gui.events import FILTERS_UPDATED, ANALYSIS_BINS_UPDATED

logger = logging.getLogger(__name__)

class AnalysisListCtrl(
    wx.ListCtrl,
    listmix.ListCtrlAutoWidthMixin,
    listmix.TextEditMixin,
):
    """Report list with a native checkbox in the first column.

    Cells of the columns marked editable (`SetEditable`) can be edited; column 1
    holds the row's key. Checking an item, by the user or with `CheckItem()`, calls
    `OnCheckItem(index, flag)` once per state change. The data map each key to a list
    of the values of columns 2 and following.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the list; the arguments are passed to `wx.ListCtrl`."""
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

    def OnLeftDown(self, evt: wx.MouseEvent) -> None:
        """Pass clicks on the checkbox column to the list; others to the cell editor.

        `TextEditMixin` opens the editor for a click on the current row and keeps
        the click, so the checkbox of the current row could not be clicked.
        """
        x = evt.GetPosition()[0] + self.GetScrollPos(wx.HORIZONTAL)
        if x < self.GetColumnWidth(0):
            if self.editor.IsShown():
                self.CloseEditor()
            evt.Skip()
            return
        listmix.TextEditMixin.OnLeftDown(self, evt)

    def IsChecked(self, index: int) -> bool:
        """Return whether the item at `index` is checked."""
        return self.IsItemChecked(index)

    def CheckItem(self, index: int, check: bool = True) -> None:
        """Check or uncheck the item at `index`.

        Calls `OnCheckItem` once if the state changes; nothing happens otherwise.

        Args:
            index: The item's index.
            check: True to check, False to uncheck. Defaults to True.
        """
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

    def ToggleItem(self, index: int) -> None:
        """Invert the check state of the item at `index`."""
        self.CheckItem(index, not self.IsItemChecked(index))

    def _on_item_checked(self, event: wx.ListEvent) -> None:
        """Call `OnCheckItem` when the user clicks a checkbox."""
        if not self._checking:
            # checkbox clicked by the user
            self.OnCheckItem(event.GetIndex(), self.IsItemChecked(event.GetIndex()))
        event.Skip()

    def fire_rowsupdated_event(self, items: dict[str, Any]) -> None:
        """Publish `ANALYSIS_BINS_UPDATED` with the changed rows, by key."""
        pub.sendMessage(ANALYSIS_BINS_UPDATED, updateditems=items)

    def GetData(self) -> dict[str, Any]:
        """Return the data: the rows' values by key."""
        return self.data

    def SetData(
        self,
        data: Optional[dict[str, Any]],
        headers: Optional[list[str]] = [],
        types: Optional[list[Any]] = [],
        keep_selection: bool = True,
    ) -> None:
        """Replace the rows with `data`, sorted by key.

        Args:
            data: The values of each row by key. Each row shows the key and as many
                values as `headers` has columns after the first two.
            headers: The column headers, including the checkbox and key columns.
            types: Not used.
            keep_selection: Whether the rows that were checked and whose keys are
                still in the list are checked again. Defaults to True.
        """
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

    def get_index_by_key(self, key: str) -> Optional[int]:
        """Return the index of the row whose key column shows `key`; None if none."""
        keycol = self.get_key_col()
        for idx in range(self.GetItemCount()):
            if self.GetItem(idx, keycol).GetText() == key:
                return idx
        return None

    def SetRow(self, key: str, rowdata: list[Any]) -> None:
        """Show the first two values of `rowdata` in columns 2 and 3 of row `key`.

        A key not in the list is ignored. The data are not changed.
        """
        logger.debug("AnalysisListCtrl.SetRow")
        idx = self.get_index_by_key(key)
        if idx is not None:
            logger.debug(f"Updating index {idx}: {rowdata}")
            self.SetItem(idx, 2, str(rowdata[0]))
            self.SetItem(idx, 3, str(rowdata[1]))
            self.Update()

    def SetEditable(self, editable: Optional[list[bool]]) -> None:
        """Set which columns can be edited, one flag per column.

        The flags are kept unless the current flags are None; then they are reset
        to an empty list and `editable` is not used.
        """
        if self.editable is None:
            self.editable = []
        else:
            self.editable = editable

    def get_checked_indices(self) -> list[int]:
        """Return the indices of the checked rows."""
        checked = []
        for idx in range(self.GetItemCount()):
            if self.IsChecked(idx):
                checked.append(idx)
        return checked

    def check_items(self, items: Optional[Any], enable: bool) -> None:
        """Check or uncheck the rows with the keys `items`, then publish the changes.

        Args:
            items: The keys (an iterable, e.g. a dict); keys not in the list are
                ignored. None does nothing.
            enable: True to check, False to uncheck.
        """
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

    def get_checked_items(self) -> dict[str, Any]:
        """Return the data of the checked rows, by key."""
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

    def BeginLabelEdit(self, event: wx.ListEvent) -> None:
        """Allow editing a cell only in the columns marked editable."""
        col = event.GetColumn()
        if col == 0:
            # column 0 holds the checkbox, which toggles itself when clicked
            event.Veto()
        elif col > len(self.editable) or self.editable[col]:
            event.Skip()
        else:
            event.Veto()

    def get_key_col(self) -> int:
        """Return the index of the column that holds the rows' keys."""
        return 1

    def EndLabelEdit(self, event: wx.ListEvent) -> None:
        """Store an edited value in the data and publish the changed row.

        Values of columns 2 and 3 are stored as float, of column 4 as int.
        """
        idx = event.GetIndex()
        col = event.GetColumn()
        rowkey = self.GetItem(idx, self.get_key_col()).GetText()
        logger.debug(self.data[rowkey])
        newvalue = event.GetItem().GetText()
        if col in [2, 3]:
            newvalue = float(newvalue)
        elif col == 4:
            newvalue = int(newvalue)
        self.data[rowkey][col - 2] = newvalue
        logger.debug(self.data[rowkey])
        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})

    def OnCheckItem(self, index: int, flag: bool) -> None:
        """Publish the row whose check state changed.

        Args:
            index: The row's index.
            flag: The new state: True if checked.
        """
        rowkey = self.GetItem(index, self.get_key_col()).GetText()
        logger.debug(f"OnCheckItem {rowkey}")
        if self.enableevents:
            # looked up by the cell text: a data key that is not a string (e.g. a
            # MultiIndex tuple) raises KeyError
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})


class FilterListCtrl(AnalysisListCtrl):
    """List of range filters with a checkbox to use each filter.

    The columns are the checkbox, the column the filter applies to, the low and high
    end of the range, and (with `showdropped`) the number of rows the filter drops
    from the view. The data map each column name to its `RangeFilter`. Changes are
    published with `FILTERS_UPDATED`.
    """

    def __init__(
        self,
        *args: Any,
        dataframe: Optional[pd.DataFrame] = None,
        dropped: Optional[dict[str, Any]] = None,
        showdropped: bool = True,
        fireevents: bool = True,
        **kwargs: Any,
    ) -> None:
        """Create the list.

        Args:
            *args: Passed to `wx.ListCtrl`.
            dataframe: The table the filters apply to.
            dropped: The row positions each filter drops, by name; filters not in
                the list count as dropped by other filters.
            showdropped: Whether the list shows the number of dropped rows in
                column 4. Defaults to True.
            fireevents: Whether changes are published. Defaults to True.
            **kwargs: Passed to `wx.ListCtrl`.
        """
        AnalysisListCtrl.__init__(self, *args, **kwargs)
        self.dataframe = dataframe
        self.showdropped = showdropped
        self.setdrop(dropped)
        self.fireevents = fireevents
        self.Bind(wx.EVT_LIST_END_LABEL_EDIT, self.EndLabelEdit)

    def setdrop(self, dropped: Optional[dict[str, Any]]) -> None:
        """Set the dropped rows by filter name, and those of filters not listed.

        The rows of the filters not in the list (e.g. category values hidden in the
        table window) are kept as `otherdropped`.
        """
        if dropped is None:
            dropped = {}
        self.dropped = dropped
        rfilter_names = [name for name in self.data]
        non_rfilters = [name for name in dropped if name not in rfilter_names]
        odropped = [dropped[n] for n in non_rfilters]
        if len(odropped) > 0:
            odropped = np.concatenate(odropped)
            self.otherdropped = np.unique(odropped)
        else:
            self.otherdropped = []

    def fire_rowsupdated_event(self, updated: dict[str, Any]) -> None:
        """Publish `FILTERS_UPDATED` with the changed filters and the dropped counts.

        Nothing is published unless `fireevents` is set.
        """
        if self.fireevents:
            pub.sendMessage(
                FILTERS_UPDATED,
                updateditems=updated,
                totaldropped=len(self.get_total_dropped_rows()),
                viewdropped=len(self.get_view_dropped()),
                viewlength=len(self.dataframe) - len(self.otherdropped),
            )

    def SetData(
        self,
        data: Optional[dict[str, RangeFilter]],
        dataframe: Optional[pd.DataFrame] = None,
        dropped: Optional[dict[str, Any]] = None,
        headers: Optional[list[str]] = [],
        types: Optional[list[Any]] = [],
    ) -> None:
        """Replace the filters, sorted by name, and publish them all.

        Each row is checked if its filter is selected.

        Args:
            data: The filters by name.
            dataframe: The table the filters apply to.
            dropped: The row positions each filter drops, by name.
            headers: Not used.
            types: Not used.
        """
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

    def check_items(self, items: Optional[Any], enable: bool) -> None:
        """Check or uncheck the filters `items`, select them, and publish them.

        Args:
            items: The filter names; names not in the list are ignored. None does
                nothing.
            enable: True to check and select, False to uncheck and deselect.
        """
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

    def GetDroppedRows(self, rowkey: str) -> Any:
        """Return the row positions the filter `rowkey` drops; None if not known."""
        return self.dropped.get(rowkey)

    def SetDroppedRows(self, droppedrows: Optional[dict[str, Any]]) -> None:
        """Replace the dropped rows by filter name and show their counts.

        Rows of filters without dropped rows show `---`.
        """
        if droppedrows is None:
            droppedrows = {}
        self.dropped = droppedrows
        logger.debug(f"{len(droppedrows)} filters")
        for idx in range(self.GetItemCount()):
            key = self.GetItem(idx, self.get_key_col()).GetText()
            if key in droppedrows:
                dropped = droppedrows[key]
                no_droppedfromview = len(self.get_view_dropped(key))
                self.SetItem(idx, 4, f"{no_droppedfromview:,}")
                logger.debug(
                    f"\tSetting dropped row, key={key}, index={idx}: {len(dropped)},"
                    f" dropped from view: {no_droppedfromview}"
                )
            else:
                self.SetItem(idx, 4, "---")
                logger.debug(
                    f"\tSetting dropped row, index={idx}, key={key}, dropped=---"
                )
        self.Update()

    def UpdateDroppedRows(self, droppedrows: dict[str, Any]) -> None:
        """Store the dropped rows of the filters in `droppedrows` and show the counts.

        Rows of other filters show `---`. Does nothing unless `showdropped` is set.
        """
        if not self.showdropped:
            return
        logger.debug(f"FilterListCtrl.UpdateDroppedRows, {len(droppedrows)} filters")
        droppedidx = {self.get_index_by_key(key): key for key in droppedrows}
        for idx in range(self.GetItemCount()):
            key = droppedidx.get(idx)
            if key is not None:
                dropped = droppedrows[key]
                self.dropped[key] = dropped
                no_droppedfromview = len(self.get_view_dropped(key))
                self.SetItem(idx, 4, f"{no_droppedfromview:,}")
                logger.debug(
                    f"\tUpdating dropped row (SELECTED), key={key}, index={idx}:"
                    f" {len(dropped)}, dropped from view: {no_droppedfromview}"
                )
            else:
                self.SetItem(idx, 4, "---")
                logger.debug(
                    f"\tUpdating dropped row (NOT SELECTED), key={key}, index={idx}"
                )
        self.Update()

    def get_dropped_str(self, key: str) -> str:
        """Return the number of rows filter `key` drops from the view, or `---`."""
        if key in self.dropped:
            return f"{len(self.get_view_dropped(key)):,}"
        else:
            return "---"

    def get_view_dropped(self, key: Optional[str] = None) -> np.ndarray:
        """Return the row positions dropped from the view.

        These are the rows that filter `key` drops, or all checked filters when
        `key` is None, minus those that filters not in this list drop already.
        """
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

    def get_total_dropped_rows(self) -> Union[np.ndarray, list]:
        """Return the unique row positions that the checked filters drop.

        An empty list if none drop rows.
        """
        alldroppedrows = [
            self.dropped.get(selitem)
            for selitem in self.get_checked_items()
            if self.dropped.get(selitem) is not None
        ]
        if len(alldroppedrows) > 0:
            alldroppedrows = np.concatenate(alldroppedrows)
            alldroppedrows = np.unique(alldroppedrows)
        logger.debug(f"total dropped rows: {len(alldroppedrows)}")
        return alldroppedrows

    def EndLabelEdit(self, event: wx.ListEvent) -> None:
        """Set the edited low (column 2) or high (column 3) end of a filter's range.

        The filter's dropped rows are computed again if it is selected, and the
        changed filter is published. An unchanged value does nothing.
        """
        idx = event.GetIndex()
        col = event.GetColumn()
        rowkey = self.GetItem(idx, self.get_key_col()).GetText()
        filter = self.data[rowkey]
        newvalue = event.GetItem().GetText()
        logger.debug("FilterListCtrl.EndLabelEdit")
        logger.debug(f"\t{self.data[rowkey].get_params()}")
        if col == 2:
            if float(newvalue) == self.data[rowkey].get_rangelow():
                logger.debug("\tnothing to update")
                return
            self.data[rowkey].set_rangelow(float(newvalue))
        elif col == 3:
            if float(newvalue) == self.data[rowkey].get_rangehigh():
                logger.debug("\tnothing to update")
                return
            self.data[rowkey].set_rangehigh(float(newvalue))
        if filter.is_selected():
            self.dropped[rowkey] = filter.get_dropped(self.dataframe)
        elif self.dropped.get(rowkey) is not None:
            del self.dropped[rowkey]
        logger.debug(f"\t{self.data[rowkey].get_params()}")
        self.UpdateDroppedRows(self.dropped)
        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})

    def OnCheckItem(self, index: int, flag: bool) -> None:
        """Select or deselect the row's filter, then update and publish its rows.

        Args:
            index: The row's index.
            flag: The new state: True if checked.
        """
        logger.debug("OnCheckItem")
        rowkey = self.GetItem(index, self.get_key_col()).GetText()
        filter = self.data[rowkey]
        filter.select(flag)
        if filter.is_selected():
            self.dropped[rowkey] = filter.get_dropped(self.dataframe)
        elif self.dropped.get(rowkey) is not None:
            del self.dropped[rowkey]
        logger.debug(f"\t{self.data[rowkey].get_params()}")
        self.UpdateDroppedRows(self.dropped)

        if self.enableevents:
            self.fire_rowsupdated_event({rowkey: self.data[rowkey]})
