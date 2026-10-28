#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import re
import os
import numpy as np
import numpy.random as random
import pandas as pd
import torch
import torch.nn as nn
from torch.autograd import Variable
import matplotlib.pyplot as plt
from sklearn.impute import SimpleImputer
from sklearn import preprocessing
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files, as_file

import flim.analysis.ml.autoencoder as autoencoder
import flim.resources
from flim.analysis.ml.device import DEFAULT_DEVICE, DEVICES, resolve_device
import flim.tools.autoencoder as ae_tools
from flim.plugin import AbstractPlugin
from flim.plugin import plugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
from flim import utils
from joblib import load


class AEAugmentConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": {},
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "modelfile": "",
        "device": DEFAULT_DEVICE,
        "sets": 1,
        "add_noise": True,
        "snr_db": 0.0,
        "snr_unit": utils.NOISE_UNIT[-1],
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
        data_choices={},
        selectedgrouping=["None"],
        selectedfeatures="All",
        modelfile="",
        device=DEFAULT_DEVICE,
        sets=1,
        add_noise=True,
        snr_db=0.0,
        snr_unit=utils.NOISE_UNIT[-1],
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
        self.sets = sets
        self.add_noise = add_noise
        self.snr_unit = (
            snr_unit if snr_unit in utils.NOISE_UNIT else utils.NOISE_UNIT[-1]
        )
        self.snr = snr_db if self.snr_unit == "dB" else utils.db_to_linear(snr_db)

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )
        super().__init__(parent, **init_params)

    def get_option_panels(self):
        mf = (
            self.modelfile[0]
            if (isinstance(self.modelfile, list) and len(self.modelfile) > 0)
            else self.modelfile
        )
        self.modelfiletxt = wx.StaticText(self.panel, label=mf)
        browsebutton = wx.Button(self.panel, wx.ID_ANY, "Choose...")
        browsebutton.Bind(wx.EVT_BUTTON, self.OnBrowse)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Load Model from File"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(
            browsebutton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.device,
            choices=DEVICES,
        )
        bottom_sizer.Add(
            wx.StaticText(self.panel, label="Device"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        bottom_sizer.Add(
            self.device_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.sets_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, min=1, max=20, initial=self.sets
        )
        bottom_sizer.Add(
            wx.StaticText(self.panel, label="Sets"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        bottom_sizer.Add(
            self.sets_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.noise_checkbox = wx.CheckBox(self.panel, wx.ID_ANY, label="Add noise")
        self.noise_checkbox.SetValue(self.add_noise)
        self.noise_checkbox.Bind(wx.EVT_CHECKBOX, self._add_noise)
        bottom_sizer.Add(
            self.noise_checkbox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.noise_input = NumCtrl(
            self.panel, wx.ID_ANY, min=0.0, value=self.snr, fractionWidth=3
        )
        self.noise_input.SetMin(0.0)
        self.noise_label = wx.StaticText(self.panel, label="Signal-to-Noise Ratio")
        bottom_sizer.Add(self.noise_label, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        bottom_sizer.Add(
            self.noise_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.unit_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.snr_unit,
            choices=utils.NOISE_UNIT,
        )
        self.unit_combobox.Bind(wx.EVT_COMBOBOX, self._update_unit)
        bottom_sizer.Add(
            self.unit_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self._add_noise(None)
        return [timeseries_sizer, bottom_sizer]

    def _add_noise(self, event):
        if self.noise_checkbox.GetValue():
            self.noise_label.Enable()
            self.noise_input.Enable()
            self.unit_combobox.Enable()
        else:
            self.noise_label.Disable()
            self.noise_input.Disable()
            self.unit_combobox.Disable()

    def _update_unit(self, event):
        unit = self.unit_combobox.GetValue()
        if unit != self.snr_unit:
            noise = self.noise_input.GetValue()
            noise = utils.to_db(noise) if unit == "dB" else utils.db_to_linear(noise)
            self.snr_unit = unit
            self.noise_input.SetValue(noise)

    def OnBrowse(self, event):
        if isinstance(self.modelfile, list) and len(self.modelfile) > 0:
            fpath = self.modelfile[0]
            fname = ""
        else:
            fpath = self.modelfile  # self.modelfiletxt.GetLabel()
            _, fname = os.path.split(fpath)
        with wx.FileDialog(
            self, "Model File", style=wx.FD_OPEN | wx.FD_MULTIPLE
        ) as fileDialog:
            fileDialog.SetPath(fpath)
            fileDialog.SetFilename(fname)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            # fname = fileDialog.GetPath()
            self.modelfile = fileDialog.GetPaths()
            self.modelfiletxt.SetLabel(self.modelfile[0])

    def _get_selected(self):
        params = super()._get_selected()
        params["modelfile"] = self.modelfile  # self.modelfiletxt.GetLabel()
        params["device"] = self.device_combobox.GetValue()
        params["sets"] = self.sets_spinner.GetValue()
        params["add_noise"] = self.noise_checkbox.GetValue()
        self.noise_input.Refresh()
        if self.unit_combobox.GetValue() == "dB":
            params["snr_db"] = self.noise_input.GetValue()
        else:
            params["snr_db"] = utils.to_db(self.noise_input.GetValue())
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Analysis")
class AEAugment(AbstractPlugin):
    def __init__(self, name="Autoencoder: Augment Data", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.modelfile = self.params["modelfile"]
        self.device = self.params["device"]
        self.sets = self.params["sets"]
        self.add_noise = self.params["add_noise"]
        self.snr_db = self.params["snr_db"]

    def get_icon(self):
        source = files(flim.resources).joinpath("aeaugment.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_mapped_parameters(self):
        parallel_params = []
        files = self.params["modelfile"]
        if not isinstance(files, list):
            files = [files]
        for mf in files:
            param = self.params.copy()
            param["modelfile"] = [mf]
            parallel_params.append(param)
        return parallel_params

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "modelfile": "",
                "device": DEFAULT_DEVICE,
                "sets": 1,
                "add_noise": True,
                "snr_db": 0.0,  # 0.0 < noise < 1.0
            }
        )
        return params

    def output_definition(self):
        return {"Table: Simulated": None}

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(AEAugmentConfigDlg.get_base_params())
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

        dlg = AEAugmentConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_OK:
            params = dlg.get_selected()
            self.params.update(params)
            return self.params
        else:
            return None

    def execute(self):
        return self.run_tool(ae_tools.AEAugment, list(self.input.values())[0])

