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


def _sampled(func, keep):
    """Wraps a seaborn plot function to draw only the rows where ``keep`` is True.

    PairGrid passes each panel's x, y and hue columns of the whole table; ``keep``
    is a boolean array over the table's (reset, 0..n-1) index.
    """

    def plot(x, y, hue=None, **kwargs):
        mask = keep[x.index.to_numpy()]
        if hue is not None:
            hue = hue[mask]
        return func(x=x[mask], y=y[mask], hue=hue, **kwargs)

    return plot


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
        data = list(self.input.values())[0]
        features = self.params["features"]
        x_vars = self.params["x_vars"]
        if not x_vars or len(x_vars) == 0:
            x_vars = features
        y_vars = self.params["y_vars"]
        if not y_vars or len(y_vars) == 0:
            y_vars = features
        hue = self.params["grouping"][0] if len(self.params["grouping"]) > 0 else None
        corner = self.params["corner"]
        results = {}
        logging.debug(f"\tcreating pair plot for {features}, grouped by {hue}")
        # fig, ax = plt.subplots()
        fig = self.grouped_pairplot(
            data,
            x_vars=x_vars,
            y_vars=y_vars,
            hue=hue,
            corner=corner,
        )  # , facecolors='none', edgecolors='r')
        results[f"Pair Plot: {self.params['grouping']}"] = fig
        return results

    def grouped_pairplot(
        self,
        data,
        x_vars,
        y_vars,
        hue=None,
        corner=False,
        dropna=True,
    ):
        # g = sns.pairplot(data, x_vars=features, y_vars=features, hue=hue, dropna=dropna)
        columns = list(dict.fromkeys(list(x_vars) + list(y_vars) + ([hue] if hue else [])))
        data = data[columns].reset_index(drop=True)
        total = len(data)
        samples = int(self.params.get("samples", 0) or 0)
        sampled = self.params.get("plotting") == "sample" and 0 < samples < total
        scatter = sns.scatterplot
        if sampled:
            rng = np.random.default_rng(self.params.get("random_seed", 0))
            keep = np.zeros(total, dtype=bool)
            keep[rng.choice(total, size=samples, replace=False)] = True
            scatter = _sampled(sns.scatterplot, keep)
        g = sns.PairGrid(
            data,
            diag_sharey=False,
            x_vars=x_vars,
            y_vars=y_vars,
            hue=hue,
            dropna=dropna,
            corner=corner,
        )
        if self.params["diag_kind"] == "Histogram":
            g.map_diag(sns.histplot, bins=self.params["hist_bins"])
        else:
            g.map_diag(sns.kdeplot)
        g.map_upper(scatter)
        g.map_lower(scatter)  # sns.kdeplot
        g.add_legend()
        if sampled:
            g.figure.text(
                0.5,
                0.005,
                f"{samples:,} samples of {total:,} measurements shown",
                ha="center",
                va="bottom",
                fontsize="small",
                color="0.3",
            )
            # room for the note; keeps the right margin seaborn made for the legend
            g.figure.subplots_adjust(bottom=g.figure.subplotpars.bottom + 0.03)
        return g.fig
