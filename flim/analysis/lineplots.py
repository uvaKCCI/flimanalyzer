#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import pandas as pd
from flim.analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter
import seaborn as sns
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources

class LinePlot(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Line Plot"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('lineplot.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'display': ['auto','auto'],
            'grouping': [],
            'features': [],
            'ordering': {},
            'ci': 95, #68, #'sd',
            'err_style': 'bars', #'band'
            'markers': True,
            'x': '',
            'hue': '',
            'style': '',
            'col': '',
        })
        return params
                
    def run_configuration_dialog(self, parent, data_choices={}):
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
        results = {}
        categories = self.data.select_dtypes('category').columns.values
        categories = [c for c in categories if len(self.data[c].unique()) > 1]
        ticklabels = [', '.join(row) for row in self.data[categories].values]
        fig, ax = plt.subplots()
        
        data = self.data.copy()
        for c in categories:
            data[c] = data[c].astype('str') 
        for feature in sorted(self.params['features']):
            logging.debug (f"\tcreating mean bar plot for {feature}")
            fig = self.grouped_lineplot(data, feature, categories=self.params['grouping'], ax=ax, fig=fig)
        #x_formatter = FixedFormatter(ticklabels)
        #x_locator = FixedLocator(range(len(ticklabels)))
        #ax.xaxis.set_major_formatter(x_formatter)
        #ax.xaxis.set_major_locator(x_locator)
        
        #ax.tick_params(axis='x', labelrotation=70)
        #h, labels = ax.get_legend_handles_labels()
        #labels = [l.replace('\n', ', ').replace('\'','').replace('(','').replace(')','') for l in labels]
        #print (f"labels={labels}")
        #legend = ax.legend(loc='upper left', bbox_to_anchor= (1.0, 1.0), fontsize='small', ncol=1)
        results[f"Line Plot: {feature}"] = fig
        return results
            
    def grouped_lineplot(self, data, feature, title=None, categories=[], dropna=True, ax=None, fig=None, **kwargs):
        if data is None or not feature in data.columns.values:
            return None, None
        if categories is None:
            categories = []
        if len(categories)==0:
            data[feature].plot(ax=ax)
        else:    
            cols = [c for c in categories]
            cols.append(feature)
            if len(categories) == 1:
                sns.lineplot(ax=ax, data=data, x=categories[0], y=feature, ci=self.params['ci'], err_style=self.params['err_style'], markers=self.params['markers'])
            elif len(categories) == 2:
                sns.lineplot(ax=ax, data=data, x=categories[0], y=feature, hue=categories[1], ci=self.params['ci'], err_style=self.params['err_style'], markers=self.params['markers'])
            elif len(categories) == 3:
                sns.lineplot(ax=ax, data=data, x=categories[0], y=feature, hue=categories[1], style=categories[2], ci=self.params['ci'], err_style=self.params['err_style'], markers=self.params['markers'])
            elif len(categories) >3 :
                g = sns.relplot(data=data, x=categories[0], y=feature, hue=categories[1], style=categories[2], col=categories[3], ci=self.params['ci'], err_style=self.params['err_style'], markers=self.params['markers'], kind="line")
                fig = g.fig

            #if dropna:
            #    groupeddata = data[cols].dropna(how='any', subset=[feature]).groupby(categories, observed=True)
            #else:    
            #    groupeddata = data[cols].groupby(categories, observed=True)
            #for label, df in groupeddata:
            #    df[feature].plot(ax=ax, label=label)
                
        #if title is None:
        #    title = feature.replace('\n', ' ') #.encode('utf-8')
        #    if len(categories) > 0:
        #        title = f"{title} grouped by {categories}"
        #if len(title) > 0:
        #    ax.set_title(title)
            
        self._add_picker(fig)
        return fig
