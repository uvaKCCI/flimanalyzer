#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 1/10/21 5:16 PM
# @Author: Jiaxin_Zhang

import seaborn as sns
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt
from importlib_resources import files
import flim.resources

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

    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Heatmap"

    def __repr__(self):
        return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_icon(self):
        source = files(flim.resources).joinpath('heatmap.png')
        return wx.Bitmap(str(source))        
        
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'corr_type': 'pearson',
            'numbers': False
        })
        return params

    def get_required_categories(self):
        return ['any']

    def get_required_features(self):
        return ['any']

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = HeatmapConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures, corr_type=self.params["corr_type"], numbers=self.params["numbers"])
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        data_c = self.data[self.params['features']]
        results = {}
        corr = data_c.corr(method=self.params['corr_type'])
        fig, ax = plt.subplots(constrained_layout=True)
        ax = sns.heatmap(
            corr,
            ax=ax,
            vmin=-1, vmax=1, center=0,
            cmap=sns.diverging_palette(20, 220, n=200),
            square=True,
            annot=self.params['numbers']
        )
        ax.set_yticklabels(
            ax.get_yticklabels(),
            rotation=0,
        )
        ax.set_xticklabels(
            ax.get_xticklabels(),
            rotation=45,
            horizontalalignment='right'
        )
        fig = ax.get_figure()
        results['Heatmap'] = fig

        title = "Data ungrouped"
        if len(self.params['grouping']) > 0:
            title = f"Data grouped by {self.params['grouping']}"
        ax.set_title(title)

        self._add_picker(fig)
        return results
