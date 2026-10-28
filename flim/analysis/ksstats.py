#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import flim.tools.statistics as statistics
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations
from flim import utils
from flim.plugin import plugin


calpha = {0.10: 1.22, 0.05: 1.36, 0.025: 1.48, 0.01: 1.63, 0.005: 1.73, 0.001: 1.95}


class KSStatsConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": None,
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "comparison": "Treatment",
        "alpha": 0.05,
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
        comparison="Treatment",
        alpha=0.05,
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
            "comparison": comparison,
            "alpha": alpha,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }

        basic_params.update(**kwargs)

        self.comparison = comparison
        self.alpha = alpha

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )

        super().__init__(parent, **init_params)

    def get_option_panels(self):
        data = list(self.input.values())[0]
        osizer = wx.BoxSizer(wx.HORIZONTAL)
        comparison_opts = [
            c for c in list(data.select_dtypes(["category"]).columns.values)
        ]
        sel_comparison = self.comparison
        if sel_comparison not in comparison_opts:
            sel_comparison = comparison_opts[0]
        self.comparison_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_comparison,
            choices=comparison_opts,
        )

        alpha_opts = [str(c) for c in calpha]
        sel_alpha = str(self.alpha)
        if sel_alpha not in alpha_opts:
            sel_alpha = alpha_opts[0]
        self.alpha_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_alpha,
            choices=alpha_opts,
        )

        osizer.Add(
            wx.StaticText(self.panel, label="Comparison "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.comparison_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            wx.StaticText(self.panel, label="alpha "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.alpha_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [osizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["comparison"] = self.comparison_combobox.GetValue()
        params["alpha"] = float(self.alpha_combobox.GetValue())
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Analysis")
class KSStats(AbstractPlugin):
    def __init__(self, name="KS-Statistics", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("ks.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "comparison": "Treatment",
                "alpha": 0.05,
            }
        )
        return params

    def output_definition(self):
        return {"Table: KS-Stats": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(KSStatsConfigDlg.get_base_params())
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

        dlg = KSStatsConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        return self.run_tool(statistics.KSStats, list(self.input.values())[0])

