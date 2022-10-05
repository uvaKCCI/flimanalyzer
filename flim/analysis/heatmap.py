#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 1/10/21 5:16 PM
# @Author: Jiaxin_Zhang

import seaborn as sns
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt
from importlib_resources import files
import flim.resources
from flim.plugin import plugin

<<<<<<< HEAD
class HeatmapConfigDlg(BasicAnalysisConfigDlg):
    def __init__(self, parent, title, data, selectedgrouping, selectedfeatures, corr_type, numbers):
        self.corr_type = corr_type
        self.numbers = numbers
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures)

    def get_option_panels(self):
        corrsizer = wx.BoxSizer(wx.HORIZONTAL)
        correlation_opts = ['pearson', 'kendall', 'spearman']
        sel_corr = self.corr_type
        if sel_corr not in correlation_opts:
            sel_corr = correlation_opts[0]
        self.correlation_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_corr, choices=correlation_opts)
        corrsizer.Add(wx.StaticText(self.panel, label="Correlation Method "), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        corrsizer.Add(self.correlation_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        colorsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.num_checkbox = wx.CheckBox(self.panel, wx.ID_ANY, "Include Numbers ")
        self.num_checkbox.SetValue(self.numbers)
        colorsizer.Add(self.num_checkbox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        return [corrsizer, colorsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params['corr_type'] = self.correlation_combobox.GetValue()
        params['numbers'] = self.num_checkbox.GetValue()
        return params

class Heatmap(AbstractAnalyzer):
=======
>>>>>>> prefect

class HeatmapConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input={},
        selectedgrouping=["None"],
        selectedfeatures="All",
        corr_type="pearson",
        numbers=False,
        autosave=True,
        working_dir="",
    ):
        self.corr_type = corr_type
        self.numbers = numbers
        super().__init__(
            parent,
            title,
            input,
            enablegrouping=False,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            autosave=autosave,
            working_dir=working_dir,
        )

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


@plugin(plugintype="Plot")
class Heatmap(AbstractPlugin):
    def __init__(self, name="Heatmap", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
<<<<<<< HEAD
        source = files(flim.resources).joinpath('heatmap.png')
        return wx.Bitmap(str(source))        
        
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'corr_type': 'pearson',
            'numbers': False
        })
        return params
=======
        source = files(flim.resources).joinpath("heatmap.png")
        return wx.Bitmap(str(source))
>>>>>>> prefect

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
<<<<<<< HEAD
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = HeatmapConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures, corr_type=self.params["corr_type"], numbers=self.params["numbers"])
=======
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]
        dlg = HeatmapConfigDlg(
            parent,
            f"Configuration: {self.name}",
            self.input,
            selectedgrouping=selgrouping,
            selectedfeatures=selfeatures,
            corr_type=self.params["corr_type"],
            numbers=self.params["numbers"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
>>>>>>> prefect
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def execute(self):
        data = list(self.input.values())[0]
        data_c = data[self.params["features"]]

        results = {}
<<<<<<< HEAD
        corr = data_c.corr(method=self.params['corr_type'])
=======
        corr = data_c.corr(method=self.params["corr_type"])
>>>>>>> prefect
        fig, ax = plt.subplots(constrained_layout=True)
        ax = sns.heatmap(
            corr,
            ax=ax,
            vmin=-1,
            vmax=1,
            center=0,
            cmap=sns.diverging_palette(20, 220, n=200),
            square=True,
<<<<<<< HEAD
            annot=self.params['numbers']
=======
            annot=self.params["numbers"],
>>>>>>> prefect
        )
        ax.set_yticklabels(
            ax.get_yticklabels(),
            rotation=0,
        )
        ax.set_xticklabels(
            ax.get_xticklabels(), rotation=45, horizontalalignment="right"
        )
        title = "Data ungrouped"
        if len(self.params["grouping"]) > 0:
            title = f"Data grouped by {self.params['grouping']}"
        ax.set_title(title)
        corr = corr.reset_index()
        corr = corr.rename(columns={"index": "Feature"})
        corr["Feature"] = corr["Feature"].astype("category")

        fig = ax.get_figure()
        results["Plot: Heatmap"] = fig
        results["Table: Heatmap"] = corr

        # self._add_picker(fig)
        return results
