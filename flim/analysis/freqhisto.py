#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import numpy as np
import pandas as pd
import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt
from importlib_resources import files
import flim.resources
from flim import utils
from flim.plugin import plugin


default_linestyles = ["-", "--", ":", "-."]


class FreqHistoConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": None,
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "bins": 20,
        "stacked": False,
        "cumulative": False,
        "histtype": "step",
        "datatable": False,
        "featuresettings": {},
        "settingspecs": {},
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
        bins=20,
        stacked=False,
        cumulative=False,
        histtype="step",
        datatable=False,
        featuresettings={},
        settingspecs={},
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
            "bins": bins,
            "stacked": stacked,
            "cumulative": cumulative,
            "histtype": histtype,
            "datatable": datatable,
            "featuresettings": featuresettings,
            "settingspecs": settingspecs,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }

        basic_params.update(**kwargs)

        self.bins = bins
        self.stacked = stacked
        self.cumulative = cumulative
        self.histtype = histtype
        self.datatable = datatable

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )

        super().__init__(parent, **init_params)

    def get_option_panels(self):
        optsizer = wx.BoxSizer(wx.HORIZONTAL)

        histtype_opts = ["bar", "barstacked", "step", "stepfilled"]
        sel_histtype = self.histtype
        if sel_histtype not in histtype_opts:
            sel_histtype = histtype_opts[0]
        self.histtype_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_histtype,
            choices=histtype_opts,
        )
        optsizer.Add(
            wx.StaticText(self.panel, label="Type"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        optsizer.Add(
            self.histtype_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.stacked_cb = wx.CheckBox(self.panel, wx.ID_ANY, label="Stacked")
        self.stacked_cb.SetValue(self.stacked)
        optsizer.Add(
            self.stacked_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.cumulative_cb = wx.CheckBox(self.panel, wx.ID_ANY, label="Cumulative")
        self.cumulative_cb.SetValue(self.cumulative)
        optsizer.Add(
            self.cumulative_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.showdata_cb = wx.CheckBox(self.panel, wx.ID_ANY, label="Binned data table")
        self.showdata_cb.SetValue(self.datatable)
        optsizer.Add(
            self.showdata_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [optsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["stacked"] = self.stacked_cb.GetValue()
        params["cumulative"] = self.cumulative_cb.GetValue()
        params["histtype"] = self.histtype_combobox.GetValue()
        params["datatable"] = self.showdata_cb.GetValue()
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Plot")
class FreqHisto(AbstractPlugin):
    def __init__(self, name="Frequency Histogram", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_icon(self):
        source = files(flim.resources).joinpath("histogram.png")
        return wx.Bitmap(str(source))

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params["bins"] = 30
        params["density"] = False
        params["cumulative"] = False
        params["histtype"] = "step"  # 'bar', 'barstacked', 'step', 'stepfilled'
        params["stacked"] = False
        params["datatable"] = False
        params["featuresettings"] = {
            "trp t1": [0, 8000, 81, ["Treatment"]],
            "trp t2": [0, 8000, 81, ["Treatment"]],
            "trp tm": [0, 4000, 81, ["Treatment"]],
            "trp a1[%]": [0, 100, 21, ["Treatment"]],
            "trp a2[%]": [0, 100, 21, ["Treatment"]],
            "trp a1[%]/a2[%]": [0, 2, 81, ["Treatment"]],
            "trp E%1": [0, 100, 21, ["Treatment"]],
            "trp E%2": [0, 100, 21, ["Treatment"]],
            "trp E%3": [0, 100, 21, ["Treatment"]],
            "trp r1": [0, 100, 21, ["Treatment"]],
            "trp r2": [0, 100, 21, ["Treatment"]],
            "trp r3": [0, 100, 21, ["Treatment"]],
            "trp chi": [0, 4.7, 81, ["Treatment"]],
            "trp photons": [0, 160, 81, ["Treatment"]],
            "NAD(P)H t1": [0, 800, 81, ["Treatment"]],
            "NAD(P)H t2": [0, 400, 81, ["Treatment"]],
            "NAD(P)H tm": [0, 2000, 81, ["Treatment"]],
            "NAD(P)H photons": [0, 2000, 81, ["Treatment"]],
            "NAD(P)H a2[%]": [0, 100, 51, ["Treatment"]],
            #                    'NAD(P)H %': [0,99,34,['Treatment']],
            "NADPH %": [0, 99, 34, ["Treatment"]],
            "NADH %": [0, 100, 51, ["Treatment"]],
            "NAD(P)H/NADH": [0, 3, 31, ["Treatment"]],
            "NAD(P)H chi": [0.7, 4.7, 81, ["Treatment"]],
            "FAD t1": [0, 4000, 81, ["Treatment"]],
            "FAD t2": [1000, 7000, 81, ["Treatment"]],
            "FAD tm": [0, 4000, 81, ["Treatment"]],
            "FAD a1[%]": [0, 100, 51, ["Treatment"]],
            "FAD a2[%]": [0, 100, 21, ["Treatment"]],
            "FAD a1[%]/a2[%]": [0, 16, 81, ["Treatment"]],
            "FAD chi": [0.7, 4.7, 81, ["Treatment"]],
            "FAD photons": [0, 800, 81, ["Treatment"]],
            "FLIRR": [0, 2.4, 81, ["Treatment"]],
            "NADPH a2/FAD a1": [0, 10, 101, ["Treatment"]],
        }
        return params

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def run_configuration_dialog(self, parent, data_choices={}):
        data = list(self.input.values())[0]
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]
        histmax = data.select_dtypes(np.number).max().max()
        # defines how to get input for values
        binspecs = {  # revised bins so that they can accept negative vals
            "bins": [wx.SpinCtrl, {"min": 1, "max": 500, "initial": 30}],
            "min": [
                wx.SpinCtrlDouble,
                {"min": -100, "max": histmax, "initial": 0, "inc": 0.1},
            ],
            "max": [
                wx.SpinCtrlDouble,
                {"min": -100, "max": histmax, "initial": histmax, "inc": 0.1},
            ],
        }

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(FreqHistoConfigDlg.get_base_params())
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
                settingspecs=binspecs,
            )
        )

        dlg = FreqHistoConfigDlg(parent, **dlg_params)

        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def execute(self):
        return self.run_tool(plot.FrequencyHistogram, list(self.input.values())[0])

