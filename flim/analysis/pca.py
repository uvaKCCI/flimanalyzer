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
import flim.tools.ml as ml
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources
from flim import utils
from flim.plugin import plugin


class PCAnalysisConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": None,
        "description": None,
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "keeporig": False,
        "keepstd": True,
        "explainedhisto": False,
        "n_components": None,
        "saveconfig": True,
        "config_file": "",
        "autosave": True,
        "working_dir": "",
    }

    def __init__(
        self,
        parent,
        title,
        input=None,
        description=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        keeporig=False,
        keepstd=True,
        explainedhisto=False,
        n_components=None,
        saveconfig=True,
        config_file="",
        autosave=True,
        working_dir="",
        **kwargs,
    ):
        basic_params = {
            "title": title,
            "input": input,
            "description": description,
            "selectedgrouping": selectedgrouping,
            "selectedfeatures": selectedfeatures,
            "keeporig": keeporig,
            "keepstd": keepstd,
            "explainedhisto": explainedhisto,
            "n_components": n_components,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }

        basic_params.update(**kwargs)

        self.keeporig = keeporig
        self.keepstd = keepstd
        self.explainedhisto = explainedhisto
        self.n_components = n_components

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )
        super().__init__(parent, **init_params)

    def get_option_panels(self):
        data = list(self.input.values())[0]
        allfeatures = data.select_dtypes(
            include=["number"], exclude=["category"]
        ).columns.values
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.n_components_input = NumCtrl(
            self.panel,
            wx.ID_ANY,
            min=0.0,
            max=float(len(allfeatures)),
            value=self.n_components,
            fractionWidth=3,
        )
        sizer.Add(
            wx.StaticText(self.panel, label="N-components"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        sizer.Add(
            self.n_components_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.keeporig_cb = wx.CheckBox(
            self.panel, id=wx.ID_ANY, label="Include original data"
        )
        self.keeporig_cb.SetValue(self.keeporig)
        sizer.Add(self.keeporig_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        self.keepstd_cb = wx.CheckBox(
            self.panel, id=wx.ID_ANY, label="Include standardized data"
        )
        self.keepstd_cb.SetValue(self.keepstd)
        sizer.Add(self.keepstd_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        self.explainedhisto_cb = wx.CheckBox(
            self.panel, id=wx.ID_ANY, label="Explained histogram"
        )
        self.explainedhisto_cb.SetValue(self.explainedhisto)
        sizer.Add(
            self.explainedhisto_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [sizer]

    def _get_selected(self):
        n_comps = self.n_components_input.GetValue()
        if n_comps >= 1.0:
            # convert float to int
            n_comps = int(n_comps)
        params = super()._get_selected()
        params["keeporig"] = self.keeporig_cb.GetValue()
        params["keepstd"] = self.keepstd_cb.GetValue()
        params["n_components"] = n_comps
        params["explainedhisto"] = self.explainedhisto_cb.GetValue()

        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Analysis")
class PCAnalysis(AbstractPlugin):
    def __init__(self, name="PCA", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_description(self):
        return (
            "Specifiy PCA components to retain:\n\tleave empty:   retain all PCA"
            " components.\n\t0.0 < n < 1.0 (float):   retain PCA components that"
            " explain specified fraction of observed variance.\n\t1 <= n <= # features"
            " (integer):   retain first n PCA components."
        )

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("pca.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return ["any", "any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "keeporig": False,
                "keepstd": True,
                "explainedhisto": False,
                "n_components": 0.999,
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(PCAnalysisConfigDlg.get_base_params())
        dlg_params = utils.update_left(
            merged_base,
            self.params,
        )

        dlg_params.update(
            dict(
                title=f"Configuration: {self.name}",
                input=self.input,
                description=self.get_description(),
                selectedgrouping=selgrouping,
                selectedfeatures=selfeatures,
            )
        )

        dlg = PCAnalysisConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def output_definition(self):
        if self.params["explainedhisto"]:
            return {
                "Table: PCA Components": None,
                "Table: PCA explained": None,
                "Plot: PCA Explained": None,
            }
        else:
            return {"Table: PCA Components": None, "Table: PCA explained": None}

    def execute(self):
        return self.run_tool(ml.PCAnalysis, list(self.input.values())[0])
