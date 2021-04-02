#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 1/10/21 5:16 PM
# @Author: Jiaxin_Zhang

import seaborn as sns
from analysis.absanalyzer import AbstractAnalyzer
from gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt


class Heatmap(AbstractAnalyzer):

    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Heatmap"

    def __repr__(self):
        return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_icon(self):
        return wx.Bitmap("resources/heatmap.png")
        
    def get_required_categories(self):
        return ['any']

    def get_required_features(self):
        return ['any']

    def run_configuration_dialog(self, parent):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = BasicAnalysisConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        data_c = self.data[self.params['features']]
        results = {}
        corr = data_c.corr()
        fig, ax = plt.subplots(constrained_layout=True)
        ax = sns.heatmap(
            corr,
            ax=ax,
            vmin=-1, vmax=1, center=0,
            cmap=sns.diverging_palette(20, 220, n=200),
            square=True,
            annot=True
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
        results['Heatmap'] = (fig, ax)

        title = "Data ungrouped"
        if len(self.params['grouping']) > 0:
            title = f"Data grouped by {self.params['grouping']}"
        ax.set_title(title)

        self._add_picker(fig)
        return results
