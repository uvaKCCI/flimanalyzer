#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/17/20 10:44 AM
# @Author: Jiaxin_Zhang

import copy
import itertools
import logging
import os
import random
from collections import defaultdict

import flim.analysis.ml.autoencoder as autoencoder
from flim.analysis.ml.device import DEFAULT_DEVICE, DEVICES, resolve_device
import flim.resources
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.optim as optim
import torch.utils.data
import wx
from flim import utils
from flim.core.runner import pyplot_lock
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.tools.autoencoder as ae_tools
from flim.plugin import AbstractPlugin, plugin
from importlib_resources import files
from joblib import dump
from matplotlib.ticker import MaxNLocator
from sklearn import preprocessing
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder
from torch.utils.data.dataset import Dataset
from wx.lib.masked import NumCtrl


class datasets(Dataset):
    def __init__(self, data, labels=[]):
        self.data = np.asarray(data)
        self.data_len = len(self.data)
        self.labels = np.asarray(labels)
        # self.transform = transforms.Compose([transforms.ToTensor()])

    def __getitem__(self, index):
        single_item = self.data[index]
        item_label = self.labels[index]
        return single_item, item_label

    def __len__(self):
        return self.data_len


class AETrainingConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": {},
        "description": None,
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "epoches": 20,
        "batch_size": 200,
        "learning_rate": 1e-4,
        "weight_decay": 1e-7,
        "timeseries": "",
        "model": "",
        "modelfile": "",
        "device": DEFAULT_DEVICE,
        "rescale": False,
        "checkpoint_interval": 20,
        "saveconfig": True,
        "config_file": "",
        "autosave": True,
        "working_dir": ""
    }

    def __init__(
        self,
        parent,
        title,
        input={},
        description=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        epoches=20,
        batch_size=200,
        learning_rate=1e-4,
        weight_decay=1e-7,
        timeseries="",
        model="",
        modelfile="",
        device=DEFAULT_DEVICE,
        rescale=False,
        checkpoint_interval=20,
        saveconfig=True,
        config_file="",
        autosave=True,
        working_dir="",
        **kwargs
    ):
        basic_params = {
            "title": title,
            "input": input,
            "description": description,
            "selectedgrouping": selectedgrouping,
            "selectedfeatures": selectedfeatures,
            "epoches": epoches,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "timeseries": timeseries,
            "model": model,
            "modelfile": modelfile,
            "device": device,
            "rescale": rescale,
            "checkpoint_interval": checkpoint_interval,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir
        }

        basic_params.update(**kwargs)

        data = next(iter(input.values()))
        self.timeseries_opts = data.select_dtypes(include=["category"]).columns.values
        self.timeseries = timeseries
        self.epoches = epoches
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.model = model
        self.model_opts = [a for a in autoencoder.get_autoencoder_classes()]
        self.working_dir = working_dir
        self.modelfile = modelfile
        self.device = device
        self.rescale = rescale
        self.checkpoint_interval = checkpoint_interval

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )

        super().__init__(
            parent,
            **init_params)
        self._update_model_info(None)

    def get_option_panels(self):
        epoches_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.epoches_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, min=1, max=500, initial=self.epoches
        )
        epoches_sizer.Add(
            wx.StaticText(self.panel, label="Epoches"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        epoches_sizer.Add(
            self.epoches_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        batch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # self.batchsize_spinner = wx.SpinCtrl(self.panel,wx.ID_ANY,min=1,max=4096,initial=self.batch_size)
        self.batchsize_input = wx.TextCtrl(
            self.panel, wx.ID_ANY, value=utils.to_str_sequence(self.batch_size)
        )  # NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        batch_sizer.Add(
            wx.StaticText(self.panel, label="Batch Size"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        batch_sizer.Add(
            self.batchsize_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        checkpoint_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.checkpoint_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, min=1, max=500, initial=self.checkpoint_interval
        )
        checkpoint_sizer.Add(
            wx.StaticText(self.panel, label="Save interval"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        checkpoint_sizer.Add(
            self.checkpoint_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        spinner_sizer = wx.BoxSizer(wx.VERTICAL)
        spinner_sizer.Add(epoches_sizer)
        spinner_sizer.Add(batch_sizer)
        spinner_sizer.Add(checkpoint_sizer)

        learning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.learning_input = wx.TextCtrl(
            self.panel, wx.ID_ANY, value=utils.to_str_sequence(self.learning_rate)
        )  # NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        learning_sizer.Add(
            wx.StaticText(self.panel, label="Learning Rate"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        learning_sizer.Add(
            self.learning_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        weight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.weight_input = wx.TextCtrl(
            self.panel, wx.ID_ANY, value=utils.to_str_sequence(self.weight_decay)
        )  # NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.weight_decay, fractionWidth=10)
        weight_sizer.Add(
            wx.StaticText(self.panel, label="Weight Decay"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        weight_sizer.Add(
            self.weight_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        float_sizer = wx.BoxSizer(wx.VERTICAL)
        float_sizer.Add(learning_sizer)
        float_sizer.Add(weight_sizer)

        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.device,
            choices=DEVICES,
        )
        self.rescale_checkbox = wx.CheckBox(
            self.panel, wx.ID_ANY, label="Rescale decoded"
        )
        self.rescale_checkbox.SetValue(self.rescale)
        device_sizer.Add(
            wx.StaticText(self.panel, label="Device"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        device_sizer.Add(
            self.device_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        rescale_sizer = wx.BoxSizer(wx.VERTICAL)
        rescale_sizer.Add(device_sizer)
        rescale_sizer.Add(self.rescale_checkbox)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(spinner_sizer)
        top_sizer.Add(float_sizer)
        top_sizer.Add(rescale_sizer)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sel_timeseries = self.timeseries
        if sel_timeseries not in self.timeseries_opts:
            sel_timeseries = self.timeseries_opts[0]
        self.timeseries_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_timeseries,
            choices=self.timeseries_opts,
        )
        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Time Series"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(
            self.timeseries_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )

        sel_model = self.model
        if sel_model not in self.model_opts:
            sel_model = self.model_opts[0]
        self.model_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_model,
            choices=self.model_opts,
        )
        self.model_combobox.Bind(wx.EVT_COMBOBOX, self._update_model_info)

        self.modelfiletxt = wx.StaticText(self.panel, label=self.modelfile)
        browsebutton = wx.Button(self.panel, wx.ID_ANY, "Choose...")
        browsebutton.Bind(wx.EVT_BUTTON, self._on_result_browse)

        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Model Architecture"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(
            self.model_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Save Model"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(
            browsebutton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        descr_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.model_descr = wx.TextCtrl(
            self.panel,
            value="None",
            size=(400, 100),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.SUNKEN_BORDER,
        )
        self.model_layers = wx.TextCtrl(
            self.panel,
            value="None",
            size=(400, 100),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.SUNKEN_BORDER,
        )
        descr_sizer.Add(self.model_descr, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        descr_sizer.Add(
            self.model_layers, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        # descr_sizer.Add(wx.StaticText(self, label="Weight Decay"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        # descr_sizer.Add(self.weight_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        all_sizer = wx.BoxSizer(wx.VERTICAL)
        all_sizer.Add(top_sizer)
        all_sizer.Add(timeseries_sizer)
        all_sizer.Add(descr_sizer)

        return [all_sizer]

    def _on_feature_selection(self, event):
        self._update_model_info(None)

    def OnSelectAll(self, event):
        super().OnSelectAll(event)
        self._update_model_info(None)

    def OnDeselectAll(self, event):
        super().OnDeselectAll(event)
        self._update_model_info(None)

    def _update_model_info(self, event):
        modelname = self.model_combobox.GetValue()
        # batch_size = self.batchsize_spinner.GetValue()
        aeclasses = autoencoder.get_autoencoder_classes()
        sel_features = [
            self.allfeatures[key] for key in self.cboxes if self.cboxes[key].GetValue()
        ]
        ae = autoencoder.create_instance(
            aeclasses[modelname], nb_param=len(sel_features)
        )
        if ae:
            descr = ae.get_description()
            layer_txt = "\n".join(
                str(ae).split("\n")[1:-1]
            )  # strip first and last line
        else:
            descr = "No input features or model defined"
            layer_txt = descr
        self.model_descr.Replace(0, self.model_descr.GetLastPosition(), descr)
        self.model_layers.Replace(0, self.model_layers.GetLastPosition(), layer_txt)

    def _on_result_browse(self, event):
        with wx.FileDialog(
            self, "Model File", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as fileDialog:
            fileDialog.SetPath(self.working_dir)
            fileDialog.SetFilename(self.modelfile)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.working_dir, self.modelfile = os.path.split(fname)
            self.modelfiletxt.SetLabel(self.modelfile)

    def _get_selected(self):
        params = super()._get_selected()
        params["epoches"] = self.epoches_spinner.GetValue()
        params["batch_size"] = [
            int(i) for i in self.batchsize_input.GetValue().split(",")
        ]
        params["learning_rate"] = [
            float(i) for i in self.learning_input.GetValue().split(",")
        ]
        params["weight_decay"] = [
            float(i) for i in self.weight_input.GetValue().split(",")
        ]
        params["timeseries"] = self.timeseries_combobox.GetValue()
        params["working_dir"] = self.working_dir
        params["modelfile"] = self.modelfile
        params["model"] = self.model_combobox.GetValue()
        params["device"] = self.device_combobox.GetValue()
        params["rescale"] = self.rescale_checkbox.GetValue()
        params["checkpoint_interval"] = self.checkpoint_spinner.GetValue()
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Analysis")
class AETraining(AbstractPlugin):
    def __init__(self, name="Autoencoder: Train", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.epoches = self.params["epoches"]
        self.timeseries = self.params["timeseries"]
        self.working_dir = self.params["working_dir"]
        self.modelfile = self.params["modelfile"]
        self.lr = self.params["learning_rate"]
        self.wd = self.params["weight_decay"]
        self.bs = self.params["batch_size"]
        self.device = self.params["device"]
        self.rescale = self.params["rescale"]
        self.checkpoint_interval = self.params["checkpoint_interval"]

    def get_description(self):
        descr = (
            "Train and save a new autoencoder model using selectable input features. "
            + "Training and validation datasets are randomly split based on the"
            " specified Data Grouping. "
            + "Device: auto uses a CUDA GPU or the Apple GPU (mps) if available,"
            " otherwise the CPU."
        )
        return descr

    def get_icon(self):
        source = files(flim.resources).joinpath("aetrain.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_mapped_parameters(self):
        parallel_params = []
        sizes = self.params["batch_size"]
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        combinations = list(itertools.product(sizes, rates, decays))
        for size, rate, decay in combinations:
            param = self.params.copy()
            param["batch_size"] = [size]
            param["learning_rate"] = [rate]
            param["weight_decay"] = [decay]
            parallel_params.append(param)
        return parallel_params

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "epoches": 20,
                "learning_rate": [1e-4],
                "weight_decay": [1e-8],
                "batch_size": [128],
                "timeseries": "Treatment",
                "modelfile": "AEModel",
                "grouping": ["FOV", "Cell"],
                "features": [
                    "FAD a1",
                    "FAD a2",
                    "FAD t1",
                    "FAD t2",
                    "FAD photons",
                    "NAD(P)H a1",
                    "NAD(P)H a2",
                    "NAD(P)H t1",
                    "NAD(P)H t2",
                    "NAD(P)H photons",
                ],
                "model": "AE Dimensionality Reduction 2-10",
                "device": DEFAULT_DEVICE,
                "rescale": False,
                "create_plots": True,
                "train_size": 0.7,  # 0.0 < train_size < 1.0
                "checkpoint_interval": 20,
            }
        )
        return params

    def output_definition(self):
        output = {}
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        sizes = self.params["batch_size"]
        combinations = list(itertools.product(sizes, rates, decays))
        for size, rate, decay in combinations:
            output.update(
                {
                    f"Table: AE Loss-{size}-{rate}-{decay}": pd.DataFrame,
                    f"Table: AE Decoded-{size}-{rate}-{decay}": pd.DataFrame,
                    f"Table: AE Encoded-{size}-{rate}-{decay}": pd.DataFrame,
                    "Model File": str,
                }
            )
            if self.params["create_plots"]:
                output.update(
                    {
                        f"Plot: AE Loss-{size}-{rate}-{decay}": matplotlib.figure.Figure,
                    }
                )
        return output

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(AETrainingConfigDlg.get_base_params())
        dlg_params = utils.update_left(
            merged_base,
            self.params,
        )

        dlg_params.update(
            dict(
                title=f"Configuration: {self.name}",
                input=self.input,
                selectedgrouping=selgrouping,
                selectedfeatures=selfeatures
            )
        )

        dlg = AETrainingConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def execute(self):
        return self.run_tool(ae_tools.AETraining, list(self.input.values())[0])

