#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import pandas as pd
from analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt


class MeanBarPlots(AbstractAnalyzer):
    
    def __init__(self, data, categories, features, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories, features, **kwargs)
        self.name = "Mean Bar Plots"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def execute(self):
        results = {}
        for feature in sorted(self.features):
            logging.debug (f"\tcreating mean bar plot for {feature}")
            fig,ax = self.grouped_meanbarplot(self.data, feature, categories=self.categories)
            results[f"Mean Bar Plot: {feature}"] = (fig,ax)
        return results
            
    def grouped_meanbarplot(self, data, feature, title=None, categories=[], dropna=True, pivot_level=1, **kwargs):
        plt.rcParams.update({'figure.autolayout': True})
        fig, ax = plt.subplots()
        if data is None or not feature in data.columns.values:
            return None, None
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()    
        
        if categories is None:
            categories = []
        if len(categories)==0:
            mean = pd.DataFrame(data={'all':[data[feature].mean()]}, index=[feature])#.to_frame()
            std = pd.DataFrame(data={'all':[data[feature].std()]}, index=[feature])#.to_frame()
            ticklabels = ''#mean.index.values
            mean.plot.barh(ax=ax, xerr=std)#,figsize=fsize,width=0.8)
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
            mean.plot.barh(ax=ax,xerr=std,width=bwidth)           
        
        
        if len(categories) > 1:
            # ticklabels is an array of tuples --> convert individual tuples into string 
    #        ticklabels = [', '.join(l) for l in ticklabels]
            ticklabels = [str(l).replace('\'','').replace('(','').replace(')','') for l in ticklabels]
            h, labels = ax.get_legend_handles_labels()
            #labels = [l.encode('ascii','ignore').split(',')[1].strip(' \)') for l in labels]
            labels = [l.split(',')[1].strip(' \)') for l in labels]
            ax.set_ylabel = ', '.join(categories[pivot_level:])
            no_legendcols = (len(categories)//30 + 1)
            chartbox = ax.get_position()
            ax.set_position([chartbox.x0, chartbox.y0, chartbox.width * (1-0.2 * no_legendcols), chartbox.height])
    #        ax.legend(loc='upper center', labels=grouplabels, bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
            ax.legend(labels=labels,  title=', '.join(categories[0:pivot_level]), loc='upper center', bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
            legend = ax.get_legend()
            ax.add_artist(legend)
        else:
            legend = ax.legend()
            legend.remove()
        ax.set_yticklabels(ticklabels)
        if title is None:
            title = feature.replace('\n', ' ') #.encode('utf-8')
            if len(categories) > 0:
                title = f"{title} grouped by {categories}"
        if len(title) > 0:
            ax.set_title(title)
    
        #fig.tight_layout(pad=1.5)
        plt.rcParams.update({'figure.autolayout': False})
        return fig,ax
