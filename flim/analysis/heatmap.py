#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 1/10/21 5:16 PM
# @Author: Jiaxin_Zhang

import seaborn as sns
import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt
from importlib_resources import files
import flim.resources
from flim import utils
from flim.plugin import plugin


class HeatmapConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": {},
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "corr_type": "pearson",
        "numbers": False,
        "saveconfig": True,
        "config_file": "",
        "autosave": True,
        "working_dir": "",
    }

    def __init__(
        self,
        parent,
        title,
        input={},
        selectedgrouping=["None"],
        selectedfeatures="All",
        corr_type="pearson",
        numbers=False,
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
            "corr_type": corr_type,
            "numbers": numbers,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }

        basic_params.update(**kwargs)

        self.corr_type = corr_type
        self.numbers = numbers

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )

        super().__init__(parent, **init_params)

    def get_option_panels(self):
        corrsizer = wx.BoxSizer(wx.HORIZONTAL)
        correlation_opts = ["pearson", "kendall", "spearman"]
        sel_corr = self.corr_type
        if sel_corr not in correlation_opts:
            sel_corr = correlation_opts[0]
        self.correlation_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_corr,
            choices=correlation_opts,
        )
        corrsizer.Add(
            wx.StaticText(self.panel, label="Correlation Method "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        corrsizer.Add(
            self.correlation_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )

        colorsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.num_checkbox = wx.CheckBox(self.panel, wx.ID_ANY, "Overlay Numbers ")
        self.num_checkbox.SetValue(self.numbers)
        colorsizer.Add(
            self.num_checkbox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [corrsizer, colorsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["corr_type"] = self.correlation_combobox.GetValue()
        params["numbers"] = self.num_checkbox.GetValue()
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Plot")
class Heatmap(AbstractPlugin):
    def __init__(self, name="Heatmap", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("heatmap.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def output_definition(self):
        return {"Plot: Heatmap": None}

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({"corr_type": "pearson", "numbers": False})
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(HeatmapConfigDlg.get_base_params())
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

        dlg = HeatmapConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def execute(self):
        return self.run_tool(plot.Heatmap, list(self.input.values())[0])
