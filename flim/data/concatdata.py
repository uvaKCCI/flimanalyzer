#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import numpy as np
import pandas as pd
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources


class ConcatenatorConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input={},
        data_choices={},
        type=False,
        numbers_only=False,
        autosave=True,
        working_dir="",
    ):
        self.data_choices = data_choices
        # self.data_selected = data_selected
        self.type = type
        self.numbers_only = numbers_only
        super().__init__(
            parent,
            title,
            input=input,
            data_choices=data_choices,
            enablefeatures=False,
            enablegrouping=False,
            optgridrows=2,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        cfgdata = [
            {"Select": name in self.input.keys(), "Dataset": name}
            for name in self.data_choices
        ]

        fsizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self.panel, wx.ID_ANY, "Select datasets to concatenate:")
        self.catsel = wx.CheckBox(self.panel, wx.ID_ANY, "Horizontal Concatenate ")
        self.catsel.SetValue(self.type)
        self.numbers_only_cb = wx.CheckBox(self.panel, wx.ID_ANY, "Numbers only")
        self.numbers_only_cb.SetValue(self.numbers_only)
        self.cfggrid = wx.grid.Grid(self.panel)
        self.cfggrid.SetDefaultColSize(500, True)
        self.cfgtable = ListTable(cfgdata, headers=["Select", "Dataset"], sort=False)
        self.cfggrid.SetTable(self.cfgtable, takeOwnership=True)
        self.cfggrid.SetRowLabelSize(0)
        self.cfggrid.SetColSize(0, -1)

        fsizer.Add(
            self.catsel, 0, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 5
        )
        fsizer.Add(
            self.numbers_only_cb,
            0,
            wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        fsizer.Add(label, 0, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.cfggrid, 1, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        return [fsizer]

    def _get_selected(self):
        self.cfggrid.EnableEditing(False)
        params = super()._get_selected()
        cfgdata = self.cfgtable.GetData()
        params["input"] = {
            row["Dataset"]: self.data_choices[row["Dataset"]]
            for row in cfgdata
            if row["Select"]
        }
        params["type"] = self.catsel.GetValue()
        params["numbers_only"] = self.numbers_only_cb.GetValue()
        return params

    def OnSelectAll(self, event):
        col = 0
        for row in range(self.cfgtable.GetNumberRows()):
            self.cfgtable.SetValue(row, col, True)
        self.cfggrid.ForceRefresh()

    def OnDeselectAll(self, event):
        col = 0
        for row in range(self.cfgtable.GetNumberRows()):
            self.cfgtable.SetValue(row, col, False)
        self.cfggrid.ForceRefresh()


@plugin(plugintype="Data")
class Concatenator(AbstractPlugin):
    def __init__(self, name="Concat Data", **kwargs):
        AbstractPlugin.__init__(self, name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("concatenate.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return []

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "input": {},
                "type": False,
                "numbers_only": False,
                "source_suffix": True,
            }
        )
        return params

    def input_definition(self):
        return [pd.DataFrame, pd.DataFrame]

    def output_definition(self):
        return {"Table: Concatenated": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        input = self.params["input"]
        type = self.params["type"]
        numbers_only = self.params["numbers_only"]
        # left_on and right_on are str representing dataframe window titles
        if isinstance(input, dict) and len(input) > 0:
            left_on = list(input.keys())[0]
        else:
            left_on = ""
        if isinstance(input, dict) and len(input) > 1:
            right_on = list(input.keys())[1]
        else:
            right_on = ""

        dlg = ConcatenatorConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            data_choices=data_choices,
            # data_selected=input,
            type=type,
            numbers_only=numbers_only,
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def execute(self):
        results = {}
        # input = self.params['input']
        horizontal = self.params["type"]
        caxis = 1 if horizontal else 0
        # if horizontal:
        #    caxis = 1
        # else:
        #    caxis = 0
        if horizontal and self.params["numbers_only"]:
            # for df #2 and higher, select numeric columns only
            data = [
                df.select_dtypes(np.number) if i != 0 else df
                for i, df in enumerate(self.input.values())
            ]
            concat_df = pd.concat(data, axis=caxis, copy=True)
        else:
            # data = [df for df in list(self.input.values())]
            data = list(self.input.values())
            catcols = list(
                dict.fromkeys(
                    [
                        c
                        for d in data
                        for c in d.select_dtypes(["category"]).columns.values
                    ]
                )
            )
            concat_df = pd.concat(
                data,
                axis=caxis,
                copy=True,
                keys=list(self.input.keys()),
                names=["Source", "Old Index"],
            ).reset_index()
            concat_df = concat_df.drop("Old Index", axis=1)
            concat_df[catcols] = concat_df[catcols].astype("category")
            concat_df["Source"] = concat_df["Source"].astype("category")
        results["Table: Concatenated"] = concat_df
        return results
