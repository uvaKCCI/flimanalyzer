#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import pandas as pd
import flim.tools.plot as plot
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim import utils
import matplotlib.figure
import matplotlib.pyplot as plt
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
import numpy as np
import matplotlib.ticker as mtick


from flim.tools.plot import grouped_meanbarplot  # noqa: F401  (used by flirr)


class BarPlotConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": {},
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "orientation": "vertical",
        "ordering": [],
        "ebar": "+/-",
        "etype": "std",
        "dropna": True,
        "bartype": "single",
        "saveconfig": True,
        "config_file": "",
        "autosave": True,
        "working_dir": "",
        "legend": True,
    }

    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        orientation="vertical",
        ordering=[],
        ebar="+/-",
        etype="std",
        dropna=True,
        bartype="single",
        saveconfig=True,
        config_file="",
        autosave=True,
        working_dir="",
        legend=True,
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

        self.orientation = orientation
        self.ordering = ordering
        self.ebar = ebar
        self.etype = etype
        self.sel_bartype = bartype
        self.dropna = dropna
        self.legend = legend

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )
        super().__init__(parent, **init_params)

    def get_option_panels(self):
        osizer = wx.BoxSizer(wx.HORIZONTAL)
        orientation_opts = ["vertical", "horizontal"]
        sel_orientation = self.orientation
        if sel_orientation not in orientation_opts:
            sel_orientation = orientation_opts[0]
        self.orientation_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_orientation,
            choices=orientation_opts,
        )
        osizer.Add(
            wx.StaticText(self.panel, label="Orientation "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.orientation_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )

        ssizer = wx.BoxSizer(wx.HORIZONTAL)
        bartype_opts = ["single", "stacked", "100% stacked"]
        sel_bartype = self.sel_bartype
        if sel_bartype not in bartype_opts:
            sel_bartype = bartype_opts[0]
        self.bartype_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_bartype,
            choices=bartype_opts,
        )
        self.dropna_cb = wx.CheckBox(self.panel, id=wx.ID_ANY, label="Drop N/A")
        self.dropna_cb.SetValue(self.dropna)
        ssizer.Add(
            self.bartype_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        ssizer.Add(self.dropna_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        ebar_opts = ["+/-", "+", "None"]
        sel_ebar = self.ebar
        if sel_ebar not in ebar_opts:
            sel_ebar = ebar_opts[0]
        self.ebar_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_ebar,
            choices=ebar_opts,
        )
        self.ebar_combobox.Bind(wx.EVT_COMBOBOX, self.OnErroBarChange)
        bsizer.Add(
            wx.StaticText(self.panel, label="Error Bar"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        bsizer.Add(
            self.ebar_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        tsizer = wx.BoxSizer(wx.HORIZONTAL)
        etype_opts = ["std", "s.e.m."]
        sel_etype = self.etype
        if sel_etype not in sel_etype:
            sel_etype = sel_etype[0]
        self.etype_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_etype,
            choices=etype_opts,
        )
        self.etype_combobox.Enable(sel_ebar != "None")
        tsizer.Add(
            wx.StaticText(self.panel, label="Error Type"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        tsizer.Add(
            self.etype_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [osizer, ssizer, bsizer, tsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["ordering"] = []
        params["orientation"] = self.orientation_combobox.GetValue()
        params["bar_type"] = self.bartype_combobox.GetValue()
        params["dropna"] = self.dropna_cb.GetValue()
        params["error_bar"] = self.ebar_combobox.GetValue()
        params["error_type"] = self.etype_combobox.GetValue()
        params["legend"] = self.legend
        return params

    def OnErroBarChange(self, event):
        ebar = self.ebar_combobox.GetValue()
        self.etype_combobox.Enable(ebar != "None")

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Plot")
class BarPlot(AbstractPlugin):
    def __init__(self, name="Bar Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("barplot.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "display": ["auto", "auto"],
                "grouping": [],
                "features": [],
                "ordering": {},
                "orientation": "vertical",  # 'horizontal'
                "bar_type": "single",  # 'stacked', '100% stacked'
                "dropna": True,
                "error_bar": "+/-",  # '+', 'None'
                "error_type": "std",  # 's.e.m'
                "legend": True,
            }
        )
        return params

    def output_definition(self):
        if self.params["bar_type"] == "single":
            # separate plot for each feature
            return {
                f"Plot: {f}": matplotlib.figure.Figure for f in self.params["features"]
            }
        else:
            # one plot stacked with all features
            return {"Plot": matplotlib.figure.Figure}

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]
        etype = self.params["error_type"]
        ebar = self.params["error_bar"]
        bartype = self.params["bar_type"]

        # TODO change this so that info only in the BasicConfigDlg is passed back
        # possible while maintining current __init__ signature for BarPlot? Probably not, need to add kwargs
        # TODO check by removing save config from BarPlot defaults
        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(BarPlotConfigDlg.get_base_params())
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
                etype=etype,
                ebar=ebar,
                bartype=bartype,
            )
        )

        dlg = BarPlotConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def get_mapped_parameters(self):
        if self.params["bar_type"] == "single":
            parallel_params = []
            for f in self.params["features"]:
                pair_param = self.params.copy()
                pair_param["features"] = [f]
                parallel_params.append(pair_param)
            return parallel_params
        else:
            # stacked plots process all features at once
            return [self.params]

    def execute(self):
        return self.run_tool(plot.BarPlot, list(self.input.values())[0])
