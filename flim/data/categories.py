#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import wx
import wx.grid
from wx.lib.masked import NumCtrl
import pandas as pd
from importlib_resources import files
from itertools import groupby

import flim.resources
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.datapanel import PandasTable
from flim.gui.dialogs import BasicAnalysisConfigDlg


class TablePanel(wx.Panel):
    def __init__(self, parent, category, values, sort):
        super().__init__(parent)
        self.category = category
        self.catdf = pd.DataFrame({f"{category}_orig": values, category: values})
        table = PandasTable(self.catdf)
        self.grid = wx.grid.Grid(self, -1, size=(400, 200))
        self.grid.SetTable(table, takeOwnership=True)
        self.grid.AutoSizeColumns(setAsMin=True)
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
        for row in range(self.grid.GetNumberRows()):
            self.grid.SetReadOnly(row, 1)
        gridsizer = wx.BoxSizer(wx.VERTICAL)
        gridsizer.Add(self.grid)

        buttonsizer = wx.BoxSizer(wx.VERTICAL)
        bmp = wx.ArtProvider.GetBitmap(wx.ART_GO_UP, wx.ART_MENU)
        up_button = wx.BitmapButton(
            self,
            id=wx.ID_ANY,
            bitmap=bmp,
            size=(bmp.GetWidth() + 10, bmp.GetHeight() + 10),
        )
        up_button.Bind(wx.EVT_BUTTON, self.move_up)
        bmp = wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN, wx.ART_MENU)
        down_button = wx.BitmapButton(
            self,
            id=wx.ID_ANY,
            bitmap=bmp,
            size=(bmp.GetWidth() + 10, bmp.GetHeight() + 10),
        )
        down_button.Bind(wx.EVT_BUTTON, self.move_down)
        buttonsizer.Add(up_button)
        buttonsizer.Add(down_button)

        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(gridsizer)
        mainsizer.Add(buttonsizer)
        self.SetSizer(mainsizer)

    def get_selection(self):
        rows = []
        top_left = self.grid.GetSelectionBlockTopLeft()
        bottom_right = self.grid.GetSelectionBlockBottomRight()
        if len(top_left) > 0 and len(bottom_right) > 0:
            rows.extend(range(top_left[0].GetRow(), bottom_right[0].GetRow() + 1))
        sel_rows = self.grid.GetSelectedRows()
        rows.extend([r for r in sel_rows])
        sel_cells = self.grid.GetSelectedCells()
        if len(sel_cells) > 0:
            rows.extend([gridcoords.GetRow() for gridcoords in sel_cells])
        if len(rows) == 0:
            cursor_row = self.grid.GetGridCursorRow()
            rows.append(cursor_row)
        rows = sorted(set(rows))

        # split blocks of consecutive indices
        rows = [
            [e[1] for e in list(g)]
            for k, g in groupby(enumerate(rows), lambda ix: (ix[1] - ix[0]))
        ]
        return rows

    def update_grid(self, sel_rows):
        colsizes = self.grid.GetColSizes()
        self.grid.SetTable(PandasTable(self.catdf), takeOwnership=True)
        self.grid.SetColSizes(colsizes)
        self.grid.Refresh()
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
        for row in range(self.grid.GetNumberRows()):
            self.grid.SetReadOnly(row, 1)
        for i, row in enumerate(sel_rows):
            self.grid.SelectRow(row, addToSelected=i != 0)

    def move_up(self, evt):
        sel_rows = self.get_selection()
        flat_list = [item for sublist in sel_rows for item in sublist]
        if len(flat_list) == 0 or min(flat_list) < 1:
            return
        for rows in sel_rows:
            above_line = pd.DataFrame(
                [self.catdf.iloc[min(rows) - 1, :]], columns=self.catdf.columns.values
            )
            move_block = self.catdf.iloc[rows, :]
            self.catdf = pd.concat(
                [
                    self.catdf.iloc[: min(rows) - 1],
                    move_block,
                    above_line,
                    self.catdf.iloc[max(rows) + 1 :],
                ]
            ).reset_index(drop=True)
        self.update_grid([r - 1 for r in flat_list])

    def move_down(self, evt):
        sel_rows = self.get_selection()
        flat_list = [item for sublist in sel_rows for item in sublist]
        if len(flat_list) == 0 or max(flat_list) == self.grid.GetNumberRows() - 1:
            return
        for rows in sel_rows[::-1]:
            below_line = pd.DataFrame(
                [self.catdf.iloc[max(rows) + 1, :]], columns=self.catdf.columns.values
            )
            move_block = self.catdf.iloc[rows, :]
            self.catdf = pd.concat(
                [
                    self.catdf.iloc[: min(rows)],
                    below_line,
                    move_block,
                    self.catdf.iloc[max(rows) + 2 :],
                ]
            ).reset_index(drop=True)
        self.update_grid([r + 1 for r in flat_list])

    def get_params(self):
        return {
            self.category: {
                "values": [v for v in self.catdf[self.category].values],
                "sort": "custom",
            }
        }


class CategoryOrderConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input,
        categories={},
        inplace=False,
        autosave=True,
        working_dir="",
    ):
        self.data = next(iter(input.values()))
        self.categories = categories
        self.inplace = inplace

        super().__init__(
            parent,
            title,
            input,
            enablegrouping=False,
            enablefeatures=False,
            optgridrows=0,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        if self.data.select_dtypes(["category"]).columns.nlevels == 1:
            categories = [
                c for c in list(self.data.select_dtypes(["category"]).columns.values)
            ]
        else:
            categories = [
                c
                for c in list(
                    self.data.select_dtypes(["category"])
                    .columns.get_level_values(0)
                    .values
                )
            ]
        combolist = list(itertools.permutations(categories, len(categories)))
        groupings = [", ".join(c) for c in combolist]
        self.order_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=", ".join(categories),
            choices=groupings,
        )

        nb = wx.Notebook(self.panel)
        self.tabpanels = {}
        for cat in self.categories:
            self.tabpanels[cat] = TablePanel(
                nb, cat, self.categories[cat]["values"], self.categories[cat]["sort"]
            )
            nb.AddPage(self.tabpanels[cat], cat)

        gsizer = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self.panel, wx.ID_ANY, "Category order")
        gsizer.Add(label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        gsizer.Add(self.order_combobox, 1, wx.EXPAND, 5)

        fsizer = wx.BoxSizer(wx.VERTICAL)
        fsizer.Add(gsizer)
        fsizer.Add(nb, 1, wx.EXPAND, 5)

        return [fsizer]

    def _get_selected(self):
        params = super()._get_selected()
        catparams = {}
        for cat in self.categories:
            catparams.update(self.tabpanels[cat].get_params())
        corder = self.order_combobox.GetValue().split(", ")
        params["categories"] = {c: catparams[c] for c in corder}
        params["inplace"] = self.inplace  # leave unchanged
        return params


@plugin(plugintype="Data")
class CategoryOrder(AbstractPlugin):
    def __init__(self, name="Order Categories", **kwargs):
        AbstractPlugin.__init__(
            self, name=name, **kwargs
        )  # categories={}, default='unassigned')

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("order.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return []

    def _sort_category(values, sort_algo):
        return values

    def _update_category_params(self, data, catparams={}):
        if data is not None:
            allcats = data.select_dtypes("category").columns.values
            for cat in allcats:
                values = list(data[cat].unique())
                if cat in catparams:
                    sort_algo = catparams[cat].get("sort")
                    if sort_algo == "custom":
                        defined = list(catparams[cat].get("values"))
                        missing = [v for v in values if v not in defined]
                        values = defined + missing
                    else:
                        values = _sort_categories(values, sort_algo)
                missing = [
                    v
                    for v in values
                    if (
                        cat not in catparams
                        or v not in catparams[cat].get("values", [])
                    )
                ]
                catparams[cat] = {
                    "values": values,
                    "sort": "custom",
                }
        return catparams

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "categories": self._update_category_params(None),
                "inplace": False,
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        data = next(iter(self.input.values()))
        categories = self._update_category_params(data, self.params["categories"])

        dlg = CategoryOrderConfigDlg(
            parent,
            f"Order Category Values",
            self.input,
            categories=categories,
            inplace=self.params["inplace"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def execute(self):
        data = list(self.input.values())[0]
        catcols = data.select_dtypes(["category"]).columns.values
        if not self.params["inplace"]:
            data = data.copy()
        results = {}
        # input = self.params['input']
        # data = list(input.values())
        # concat_df = pd.concat(data, axis=0, copy=True)
        # results['Concatenated'] = concat_df
        catparams = self.params["categories"]
        newcatorder = list(catparams.keys())
        neworder = []
        for c in data.columns.values:
            if c in catparams.keys():
                neworder.append(newcatorder.pop(0))
            else:
                neworder.append(c)
        data = data[neworder]
        for cat in catparams:
            data[cat] = pd.Categorical(
                data[cat], categories=catparams[cat]["values"], ordered=True
            )
        data.sort_values(by=list(catparams.keys()), inplace=True)
        results["Reordered"] = data
        return results
