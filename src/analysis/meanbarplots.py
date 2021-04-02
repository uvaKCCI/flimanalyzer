#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import pandas as pd
from analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt
from gui.dialogs import BasicAnalysisConfigDlg
import wx


class MeanBarPlot(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Mean Bar Plot"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        return wx.Bitmap("resources/meanbar.png")
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def get_default_parameters(self):
        return {
            'display': ['auto','auto'],
            'grouping': [],
            'features': [],
            'ordering': {},
            'orientation': 'vertical',
            'error bar': '+/-',
            'error type': 'std',
        }
                
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
        results = {}
        for feature in sorted(self.params['features']):
            logging.debug (f"\tcreating mean bar plot for {feature}")
            fig,ax = self.grouped_meanbarplot(self.data, feature, categories=self.params['grouping'])
            results[f"Mean Bar Plot: {feature}"] = (fig,ax)
        return results
            
    def grouped_meanbarplot(self, data, feature, title=None, categories=[], dropna=True, pivot_level=1, **kwargs):
        #plt.rcParams.update({'figure.autolayout': True})
        if data is None or not feature in data.columns.values:
            return None, None
        
        fig, ax = plt.subplots(constrained_layout=True)
        if categories is None:
            categories = []
        if len(categories)==0:
            mean = pd.DataFrame(data={'all':[data[feature].mean()]}, index=[feature])#.to_frame()
            std = pd.DataFrame(data={'all':[data[feature].std()]}, index=[feature])#.to_frame()
            ticklabels = ''#mean.index.values
            if self.params['orientation'] == 'horizontal':
                mean.plot.barh(ax=ax, xerr=std, capsize=6)#,figsize=fsize,width=0.8)
            else:
                mean.plot.bar(ax=ax, yerr=std, capsize=6)#,figsize=fsize,width=0.8)            
        else:    
            cols = [c for c in categories]
            cols.append(feature)
            if dropna:
                groupeddata = data[cols].dropna(how='any', subset=[feature]).groupby(categories, observed=True)
            else:    
                groupeddata = data[cols].groupby(categories, observed=True)
    #        groupeddata = data[cols].groupby(groups)
    #        print data.reset_index().set_index(groups).index.unique()
            #df.columns = [' '.join(col).strip() for col in df.columns.values]
            mean = groupeddata.mean()
            std = groupeddata.std()
            no_bars = len(mean)
            if pivot_level < len(categories):
                unstack_level = list(range(pivot_level))
                logging.debug (f"PIVOTING: {pivot_level}, {unstack_level}")
                mean = mean.unstack(unstack_level)
                std = std.unstack(unstack_level)
                mean = mean.dropna(how='all', axis=0)
                std = std.dropna(how='all', axis=0)
            ticklabels = mean.index.values
            bwidth = 0.8# * len(ticklabels)/no_bars 
            fig.set_figheight(1 + no_bars//8)
            fig.set_figwidth(6)
            if self.params['orientation'] == 'horizontal':
                mean.plot.barh(ax=ax, xerr=std, width=bwidth, capsize=0.75*bwidth)           
            else:
                mean.plot.bar(ax=ax, yerr=std, width=bwidth, capsize=6)           
        
        
        if len(categories) > 1:
            # ticklabels is an array of tuples --> convert individual tuples into string 
    #        ticklabels = [', '.join(l) for l in ticklabels]
            ticklabels = [str(l).replace('\'','').replace('(','').replace(')','') for l in ticklabels]
            h, labels = ax.get_legend_handles_labels()
            #labels = [l.encode('ascii','ignore').split(',')[1].strip(' \)') for l in labels]
            labels = [l.replace('\'','').replace('(','').replace(')','') for l in labels]

            if self.params['orientation'] == 'horizontal':
                ax.set_ylabel(', '.join(categories[pivot_level:]))
            else:
                ax.set_xlabel(', '.join(categories[pivot_level:]))            
            no_legendcols = (len(categories)//30 + 1)
            chartbox = ax.get_position()
            ax.set_position([chartbox.x0, chartbox.y0, chartbox.width * (1-0.2 * no_legendcols), chartbox.height])
    #        ax.legend(loc='upper center', labels=grouplabels, bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
            legend = ax.legend(labels=labels,  title=', '.join(categories[0:pivot_level]), loc='upper left', bbox_to_anchor= (1.0, 1.0), fontsize='small', ncol=no_legendcols)
            #legend = ax.legend(labels=labels,  title=', '.join(categories[0:pivot_level]), loc='upper center')
            #ax.add_artist(legend)
        else:
            legend = ax.legend()
            legend.remove()
        if self.params['orientation'] == 'horizontal':
            ax.set_yticklabels(ticklabels)
        else:
            ax.set_xticklabels(ticklabels)        
        if title is None:
            title = feature.replace('\n', ' ') #.encode('utf-8')
            if len(categories) > 0:
                title = f"{title} grouped by {categories}"
        if len(title) > 0:
            ax.set_title(title)
    
        #fig.tight_layout()
        #plt.rcParams.update({'figure.autolayout': False})
        
        self._add_picker(fig)
        return fig,ax
