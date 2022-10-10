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
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources


class CategorizerConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        header="Category",
        selectedgrouping=["None"],
        selectedfeatures="All",
        categories={},
        default="unassigned",
        mergeinput=True,
        autosave=True,
        working_dir="",
    ):
        self.header = header
        self.categories = categories
        self.default = default
        self.mergeinput = mergeinput
        super().__init__(
            parent,
            title,
            input=input,
            enablegrouping=False,
            enablefeatures=False,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=2,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        helptxt = (
            f"Specifiy PCA components to retain:\n\tleave empty:   retain all PCA"
            f" components.\n\t0.0 < n < 1.0 (float):   retain PCA components that"
            f" explain specified fraction of observed variance.\n\t1 <= n <="
            f" {{len(self.allfeatures)}} (integer):   retain first n PCA components."
        )

        mins = [c["criteria"]["min"] for c in self.categories]
        maxs = [c["criteria"]["max"] for c in self.categories]
        values = [c["value"] for c in self.categories]
        bins = mins
        bins.append(maxs[-1])
        if len(self.selectedfeatures) > 0:
            selectedfeature = list(self.selectedfeatures.keys())[0]
        else:
            selectedfeature = list(self.allfeatures.keys())[0]

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.header_field = wx.TextCtrl(self.panel, value=self.header, size=(500, -1))
        hsizer.Add(
            wx.StaticText(self.panel, label="Category column"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        hsizer.Add(self.header_field, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        fsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.feature_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=selectedfeature,
            choices=list(self.allfeatures.keys()),
        )
        fsizer.Add(
            wx.StaticText(self.panel, label="Feature to categorize"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        fsizer.Add(self.feature_combobox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bin_field = wx.TextCtrl(
            self.panel, value=",".join([str(b) for b in bins]), size=(500, -1)
        )
        bsizer.Add(
            wx.StaticText(self.panel, label="Category bins "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        bsizer.Add(self.bin_field, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        vsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.value_field = wx.TextCtrl(
            self.panel, value=",".join(values), size=(500, -1)
        )
        vsizer.Add(
            wx.StaticText(self.panel, label="Category labels"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        vsizer.Add(self.value_field, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        dsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.default_field = wx.TextCtrl(self.panel, value=self.default, size=(500, -1))
        dsizer.Add(
            wx.StaticText(self.panel, label="Default value"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        dsizer.Add(self.default_field, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        msizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mergeinput_cb = wx.CheckBox(self.panel, id=wx.ID_ANY, label="Merge input")
        self.mergeinput_cb.SetValue(self.mergeinput)
        msizer.Add(
            self.mergeinput_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [hsizer, fsizer, bsizer, vsizer, dsizer, msizer]

    def _get_selected(self):
        params = super()._get_selected()
        bins = self.bin_field.GetValue().split(",")
        values = self.value_field.GetValue().split(",")
        feature = self.allfeatures[self.feature_combobox.GetValue()]
        params["features"] = [feature]
        params["name"] = self.header_field.GetValue()
        params["categories"] = [
            {
                "value": values[i],
                "criteria": {
                    "feature": feature,
                    "min": float(bins[i]),
                    "max": float(bins[i + 1]),
                },
            }
            for i in range(len(values))
        ]
        params["default"] = self.default_field.GetValue()
        params["merge_input"] = self.mergeinput_cb.GetValue()
        return params


@plugin(plugintype="Analysis")
class Categorizer(AbstractPlugin):
    def __init__(self, name="Categorize Data", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("categorize.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "name": "New Cat",
                "categories": [
                    {
                        "value": "negative",
                        "criteria": {
                            "feature": "FLIRR",
                            "min": -100000.0,
                            "max": -0.5,
                        },
                    },
                    {
                        "value": "neutral",
                        "criteria": {
                            "feature": "FLIRR",
                            "min": -0.5,
                            "max": 0.5,
                        },
                    },
                    {
                        "value": "positive",
                        "criteria": {
                            "feature": "FLIRR",
                            "min": 0.5,
                            "max": 100000,
                        },
                    },
                ],
                "default": "unassigned",
                "merge_input": True,
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = CategorizerConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            header=self.params["name"],
            categories=self.params["categories"],
            default=self.params["default"],
            mergeinput=self.params["merge_input"],
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
        colname = self.params["name"]
        categories = self.params["categories"]
        selfeatures = self.params["features"]
        default = self.params["default"]
        mins = [c["criteria"]["min"] for c in categories]
        maxs = [c["criteria"]["max"] for c in categories]
        values = [v["value"] for v in categories]
        bins = mins
        bins.append(maxs[-1])
        feature = categories[0]["criteria"]["feature"]

        catcols = data.select_dtypes("category").columns.values

        if self.params["merge_input"]:
            cat_df = data.copy()
        else:
            cols = list(catcols)
            cols.extend(selfeatures)
            cat_df = data[cols].copy()
        cat_df[colname] = pd.cut(data[feature], bins=bins, labels=values)
        cat_df[colname].cat.add_categories(default, inplace=True)
        cat_df[colname].fillna(default, inplace=True)
        orderedcols = [c for c in cat_df.columns.values if c != colname]
        orderedcols.insert(len(catcols), colname)
        cat_df = cat_df[orderedcols]
        results = {
            "Categorized": cat_df,
        }
        return results
