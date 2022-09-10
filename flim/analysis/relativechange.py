#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

import numpy as np
import pandas as pd
import wx
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
from flim.plugin import plugin


class RelativeChangeConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        method="mean",
        refgroup="",
        refvalue="",
        autosave=True,
        working_dir="",
    ):
        self.data = list(input.values())[0]
        self.method_options = ["mean", "median"]
        self.sel_method = method
        if self.sel_method not in self.method_options:
            self.sel_method = self.method_options[0]

        self.categories = list(self.data.select_dtypes(["category"]).columns.values)
        self.sel_refgroup = refgroup
        if self.sel_refgroup not in self.categories:
            self.sel_refgroup = self.categories[0]

        self.refval_options = self.data[self.sel_refgroup].unique()
        self.sel_refvalue = refvalue
        if self.sel_refvalue not in self.refval_options:
            self.sel_refvalue = self.refval_options[0]
        super().__init__(
            parent,
            title,
            input=input,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=1,
            optgridcols=0,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        #data = list(self.input.values())[0]
        self.aggboxes = {}
        self.refgrp_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.sel_refgroup,
            choices=self.categories,
        )
        self.refgrp_combobox.Bind(wx.EVT_COMBOBOX, self.OnRefGroupChanged)
        rgsizer = wx.BoxSizer(wx.HORIZONTAL)
        rgsizer.Add(
            wx.StaticText(self.panel, label="Reference Group "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        rgsizer.Add(
            self.refgrp_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        dummy = [a for c in self.categories for a in self.data[c].unique()]
        self.refval_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.sel_refvalue,
            choices=dummy,
        )
        self.refval_combobox.SetItems(self.refval_options)
        self.refval_combobox.SetValue(self.sel_refvalue)
        rvsizer = wx.BoxSizer(wx.HORIZONTAL)
        rvsizer.Add(
            wx.StaticText(self.panel, label="Reference Value "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        rvsizer.Add(
            self.refval_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.method_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.sel_method,
            choices=self.method_options,
        )
        msizer = wx.BoxSizer(wx.HORIZONTAL)
        msizer.Add(
            wx.StaticText(self.panel, label="Method "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        msizer.Add(
            self.method_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [rgsizer, rvsizer, msizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["method"] = self.method_combobox.GetValue()
        params["reference_group"] = self.refgrp_combobox.GetValue()
        params["reference_value"] = self.refval_combobox.GetValue()
        return params

    def OnRefGroupChanged(self, event):
        sel_refgroup = self.refgrp_combobox.GetValue()
        self.refval_options = self.data[sel_refgroup].unique()
        self.sel_refvalue = self.refval_options[0]
        self.refval_combobox.SetItems(self.refval_options)
        self.refval_combobox.SetValue(self.sel_refvalue)


@plugin(plugintype="Analysis")
class RelativeChange(AbstractPlugin):
    def __init__(self, name="Relative Change", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("relchange.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "method": "mean",  # 'median'
                "reference_group": "Treatment",
                "reference_value": "Ctrl",
            }
        )
        return params

    def output_definition(self):
        return {"Table: Relative Change": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = RelativeChangeConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            method=self.params["method"],
            refgroup=self.params["reference_group"],
            refvalue=self.params["reference_value"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        parameters = dlg.get_selected()
        self.configure(**parameters)
        return parameters

    def execute(self):
        data = list(self.input.values())[0]
        method = self.params["method"]
        allcategories = list(data.select_dtypes(["category"]).columns.values)
        features = self.params["features"]
        grouping = list(self.params["grouping"])
        refgroup = self.params["reference_group"]
        refvalue = self.params["reference_value"]
        if refgroup not in grouping:
            grouping.insert(0, refgroup)
        cols = allcategories + features
        data = data[cols]

        nonrefcategories = [c for c in allcategories if c != refgroup]

        refdf = data.loc[data[refgroup] == refvalue]
        if method == "median":
            transdf = refdf.groupby(grouping)[features].transform("median")
        else:
            transdf = refdf.groupby(grouping)[features].transform("mean")
        data = data.set_index(allcategories)
        transdf = pd.concat([refdf[nonrefcategories], transdf], axis=1)
        transdf = transdf.drop_duplicates()
        transdf = transdf.set_index(nonrefcategories)
        transdef = transdf.reindex(data.index)
        reldf = data[features].div(transdf).reset_index()
        for ckey in allcategories:
            reldf[ckey] = reldf[ckey].astype("category")
        columnlabels = [
            col if col in allcategories else f"rel {col}"
            for col in reldf.columns.values
        ]
        reldf.columns = columnlabels

        title = f"Table: Relative Change"  # -{method}'
        return {title: reldf}
