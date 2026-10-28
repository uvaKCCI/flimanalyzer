#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 16:11:28 2020

@author: khs3z
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import numpy as np
import pandas as pd
import seaborn as sns
import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib
import matplotlib.pyplot as plt
import itertools
from importlib_resources import files
import flim.resources
from flim import utils
from flim.plugin import plugin


class PairPlotConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": None,
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "x_vars": [],
        "y_vars": [],
        "diag_kind": "KDE",
        "corner": False,
        "hist_bins": 20,
        "plotting": "all",
        "samples": 20000,
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
        x_vars=[],
        y_vars=[],
        diag_kind="KDE",
        corner=False,
        hist_bins=20,
        plotting="all",
        samples=20000,
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
            "x_vars": x_vars,
            "y_vars": y_vars,
            "diag_kind": diag_kind,
            "corner": corner,
            "hist_bins": hist_bins,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }

        basic_params.update(**kwargs)

        self.x_vars = x_vars
        self.y_vars = y_vars
        self.diag_kind = diag_kind
        self.corner = corner
        self.hist_bins = hist_bins
        self.plotting = plotting
        self.samples = samples

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )

        super().__init__(parent, **init_params)

    def get_option_panels(self):
        data = list(self.input.values())[0]
        osizer = wx.BoxSizer(wx.HORIZONTAL)
        diag_opts = ["KDE", "Histogram"]
        sel_diag = self.diag_kind
        if sel_diag not in diag_opts:
            sel_diag = diag_opts[0]
        self.diag_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_diag,
            choices=diag_opts,
        )
        self.corner_cb = wx.CheckBox(self.panel, id=wx.ID_ANY, label="Corner")
        self.corner_cb.SetValue(bool(self.corner))

        osizer.Add(
            wx.StaticText(self.panel, label="Diagonal Plot"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.diag_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        osizer.Add(self.corner_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        # points in the scatter panels: all measurements or a random sample
        psizer = wx.BoxSizer(wx.HORIZONTAL)
        self.plot_all_rb = wx.RadioButton(
            self.panel, wx.ID_ANY, "All measurements", style=wx.RB_GROUP
        )
        self.plot_sample_rb = wx.RadioButton(self.panel, wx.ID_ANY, "Random sample of")
        self.samples_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, min=100, max=10_000_000, initial=int(self.samples)
        )
        sampled = self.plotting == "sample"
        self.plot_sample_rb.SetValue(sampled)
        self.plot_all_rb.SetValue(not sampled)
        self.samples_spinner.Enable(sampled)
        for rb in (self.plot_all_rb, self.plot_sample_rb):
            rb.Bind(
                wx.EVT_RADIOBUTTON,
                lambda event: self.samples_spinner.Enable(self.plot_sample_rb.GetValue()),
            )
        tip = (
            "Scatter panels show a random sample (the same on every run) for faster "
            "plotting; the diagonals always use all measurements."
        )
        for control in (self.plot_sample_rb, self.samples_spinner):
            control.SetToolTip(tip)
        psizer.Add(
            wx.StaticText(self.panel, label="Points"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5
        )
        for control in (self.plot_all_rb, self.plot_sample_rb, self.samples_spinner):
            psizer.Add(control, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        psizer.Add(
            wx.StaticText(self.panel, label="measurements"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )

        return [osizer, psizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["x_vars"] = self.selectedfeatures  # self.x_vars
        params["y_vars"] = self.selectedfeatures  # self.y_vars
        params["diag_kind"] = self.diag_combobox.GetValue()
        params["corner"] = self.corner_cb.GetValue()
        params["hist_bins"] = self.hist_bins  # self.hist_bins_spinner.GetValue())
        params["plotting"] = "sample" if self.plot_sample_rb.GetValue() else "all"
        params["samples"] = self.samples_spinner.GetValue()
        return params

    @classmethod
    def get_base_params(cls):
        return cls.__base_params


@plugin(plugintype="Plot")
class PairPlot(AbstractPlugin):
    def __init__(self, name="Pair Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("pairplot.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "x_vars": [],  # "KDE"
                "y_vars": [],  # "KDE"
                "diag_kind": "Histogram",  # "KDE"
                "corner": False,
                "hist_bins": 20,
                # scatter panels: "all" measurements or a random "sample" of `samples`
                # (the same on every run); the diagonals always use all measurements
                "plotting": "all",
                "samples": 20000,
                "random_seed": 0,
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(PairPlotConfigDlg.get_base_params())
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
        dlg = PairPlotConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def output_definition(self):
        return {f"Pair Plot: {self.params['grouping']}": matplotlib.figure.Figure}

    def execute(self):
        return self.run_tool(plot.PairPlot, list(self.input.values())[0])

