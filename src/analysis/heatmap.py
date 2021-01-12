#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 1/10/21 5:16 PM
# @Author: Jiaxin_Zhang

import seaborn as sns
from analysis.absanalyzer import AbstractAnalyzer


class Heatmap(AbstractAnalyzer):

    def __init__(self, data, categories, features):
        AbstractAnalyzer.__init__(self, data, categories, features)
        self.name = "Heatmap"

    def __repr__(self):
        return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_required_categories(self):
        return ['any']

    def get_required_features(self):
        return ['any']

    def execute(self):
        data_c = self.data[self.features]
        results = {}
        corr = data_c.corr()
        ax = sns.heatmap(
            corr,
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
        return results
