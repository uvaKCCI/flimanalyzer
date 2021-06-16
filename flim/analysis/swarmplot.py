#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 16:11:37 2020

@author: khs3z
"""

import logging
import pandas as pd
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt
import seaborn as sns
from importlib_resources import files
import flim.resources

class SwarmPlot(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Swarm Plot"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        try:
           source = files(flim.resources).joinpath('swarmplot.png')
        except:
           return 
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']

    def run_configuration_dialog(self, parent):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        if len(self.data) > 1000:
            wx.MessageBox('Too many data points to plot. Consider aggregating the data in a summary table first.', 'Warning', wx.OK)
            return None
        dlg = BasicAnalysisConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None
        
    def execute(self):
        results = {}
        categories = self.data.select_dtypes('category').columns.values
        data = self.data.copy()
        for c in categories:
            data[c] = data[c].astype('str') 

        for feature in sorted(self.params['features']):
            logging.debug (f"\tcreating {self.name} for {feature}")
            fig = self._grouped_plot(data, feature, categories=self.params['grouping'])
            results[f"{self.name} {feature}"] = fig
        return results
    
    def _grouped_plot(self, data, feature, title=None, categories=[], dropna=True, pivot_level=1, **kwargs):
        if data is None or not feature in data.columns.values:
            return None
        
        fig, ax = plt.subplots()
            
        if categories is None:
            categories = []
        
        cols = [c for c in categories]
        cols.append(feature)
        if dropna:
            data = data[cols].dropna(how='any', subset=[feature])
        else:
            data = data[cols]
            
        if len(categories) == 0:
            #data.boxplot(**newkwargs)
            g = sns.catplot(data=data, y=feature, kind="swarm") #, height=6, aspect=.7)
        elif len(categories) == 1:
            g = sns.catplot(data=data, x=categories[0], y=feature, kind="swarm", color='blue') #, height=6, aspect=.7)
        elif len(categories) == 2:
            g = sns.catplot(data=data, x=categories[0], y=feature, hue=categories[1], kind="swarm") #, height=6, aspect=.7)
        elif len(categories) == 3:
            g = sns.catplot(data=data, x=categories[0], y=feature, hue=categories[1], col=categories[2], kind="swarm") #, height=6, aspect=.7)
        elif len(categories) > 3:
            g = sns.catplot(data=data, x=categories[0], y=feature, hue=categories[1], col=categories[2], row=categories[3], kind="swarm") #, height=6, aspect=.7)
        fig = g.fig
           
        #data.set_index(groups, inplace=True)
        #print (f"index.names={data.index.names}")
        #fig.set_figheight(6)
        #fig.set_figwidth(12)
        #data.boxplot(**newkwargs)
        #grouped = data.groupby(level=list(range(len(groups))))
        #grouped.boxplot(ax=ax, subplots=False)
        
        miny = min(0,data[feature].min()) * 0.95
        maxy = max(0,data[feature].max()) * 1.05
        logging.debug (f'title={title}')
        ax = fig.get_axes()[0]
        ax.set_ylim(miny, maxy)
        # plt.rcParams.update({'figure.autolayout': False})
        
        self._add_picker(fig)

        return fig   
