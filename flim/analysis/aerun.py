#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 03/30/21 10:44 AM
# @Author: Jiaxin_Zhang

import logging
import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.autograd import Variable
import matplotlib.pyplot as plt
from sklearn.impute import SimpleImputer
from sklearn import preprocessing
import wx
from wx.lib.masked import NumCtrl

import flim.tools.autoencoder as ae_tools
from flim.plugin import plugin, AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.analysis.ml.autoencoder as autoencoder
import flim.resources
from flim.analysis.ml.device import DEFAULT_DEVICE, DEVICES, resolve_device
from flim import utils
from importlib_resources import files, as_file
from joblib import load


class AERunningConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": {},
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "modelfile": "",
        "device": DEFAULT_DEVICE,
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
        selectedgrouping=["None"],
        selectedfeatures="All",
        modelfile="",
        device=DEFAULT_DEVICE,
        saveconfig=True,
        config_file="",
        autosave=True,
        working_dir="",
        **kwargs,
    ):
        basic_params = {
            "title": title,
            "input": input,
            "selectedgrouping": selectedgrouping,
            "selectedfeatures": selectedfeatures,
            "optgridrows": 1,
            "optgridcols": 0,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }

        basic_params.update(**kwargs)

        self.modelfile = modelfile
        self.device = device

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )
        super().__init__(parent, **init_params)

    def get_option_panels(self):
        self.modelfiletxt = wx.StaticText(self.panel, label=self.modelfile)
        browsebutton = wx.Button(self.panel, wx.ID_ANY, "Choose...")
        browsebutton.Bind(wx.EVT_BUTTON, self.OnBrowse)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Load Model"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(
            browsebutton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.device,
            choices=DEVICES,
        )
        device_sizer.Add(
            wx.StaticText(self.panel, label="Device"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        device_sizer.Add(
            self.device_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [timeseries_sizer, device_sizer]

    def OnBrowse(self, event):
        fpath = self.modelfiletxt.GetLabel()
        _, fname = os.path.split(fpath)
        with wx.FileDialog(self, "Model File", style=wx.FD_OPEN) as fileDialog:
            fileDialog.SetPath(fpath)
            fileDialog.SetFilename(fname)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.modelfiletxt.SetLabel(fname)

    def _get_selected(self):
        params = super()._get_selected()
        params["modelfile"] = self.modelfiletxt.GetLabel()
        params["device"] = self.device_combobox.GetValue()
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Analysis")
class RunAE(AbstractPlugin):
    def __init__(self, name="Autoencoder: Run", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.modelfile = self.params["modelfile"]
        self.device = self.params["device"]

    def get_icon(self):
        source = files(flim.resources).joinpath("aerun.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "modelfile": "",
                "device": DEFAULT_DEVICE,
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(AERunningConfigDlg.get_base_params())
        dlg_params = utils.update_left(
            merged_base,
            self.params,
        )

        dlg_params.update(
            dict(
                title=f"Configuration: {self.name}",
                input=self.input,
                selectedgrouping=selgrouping,
                selectedfeatures=selfeatures,
            )
        )

        dlg = AERunningConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def output_definition(self):
        return {"Table: Reconstructed": None, "Table: Features": None}

    def execute(self):
        return self.run_tool(ae_tools.RunAE, list(self.input.values())[0])

