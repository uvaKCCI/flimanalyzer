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
import pandas as pd
from analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt
import itertools


class ScatterPlots(AbstractAnalyzer):
    
    def __init__(self, data, categories, features, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories, features, **kwargs)
        self.name = "Scatter Plots"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def configure(self,params):
        pass

    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any', 'any']
        
    def execute(self):
        results = {}
        combs = itertools.combinations(self.features, 2)
        for comb in sorted(combs):
            logging.debug (f"\tcreating scatter plot for {str(comb)}")
            fig, ax = self.grouped_scatterplot(self.data, comb, categories=self.categories, marker='o', s=10)#, facecolors='none', edgecolors='r')
            results[f"Scatter Plot: {comb}"] = (fig,ax)
        return results
    
    def grouped_scatterplot(self, data, combination,  title=None, categories=[], dropna=True, pivot_level=1, **kwargs):
        plt.rcParams.update({'figure.autolayout': True})
        fig, ax = plt.subplots()
        col1 = combination[0]
        col2 = combination[1]
        if data is None or not col1 in data.columns.values or not col2 in data.columns.values:
            return None, None
            
        if categories is None:
            categories = []
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()    
        
        newkwargs = kwargs.copy()
        newkwargs.update({
            'alpha':0.5})
        cols = [c for c in categories]
        cols.extend(combination)
        if dropna:
            data = data[cols].dropna(how='any', subset=combination)
        fig.set_figheight(6)
        fig.set_figwidth(12)
    
        logging.debug (f"NEWKWARGS: {newkwargs}")
        if len(categories) > 0:
            grouped = data.groupby(categories)
            for name, group in grouped:
                if len(group[col1]) > 0 and len(group[col2] > 0):
                    newkwargs.update({'label':name})
                    ax.scatter(group[col1], group[col2], **newkwargs)
        else:        
            ax.scatter(data[col1], data[col2], **newkwargs)
        
        miny = min(0,data[col1].min()) * 1.05
        maxy = max(0,data[col1].max()) * 1.05
        ax.set_xlim(miny, maxy)
        ax.set_xlabel(col1) # col1.encode('ascii'))
        miny = min(0,data[col2].min()) * 1.05
        maxy = max(0,data[col2].max()) * 1.05
        ax.set_ylim(miny, maxy)
        ax.set_ylabel(col2) # col2.encode('utf-8'))
        
        if len(categories) > 0:
            h, labels = ax.get_legend_handles_labels()
            #labels = [l.encode('ascii','ignore').split(',')[1].strip(' \)') for l in labels]
            labels = [l.replace('\'','').replace('(','').replace(')','') for l in labels]
            no_legendcols = (len(grouped)//30 + 1)
            chartbox = ax.get_position()
            ax.set_position([chartbox.x0, chartbox.y0, chartbox.width* (1-0.2 * no_legendcols), chartbox.height])
            ax.legend(labels=labels, loc='upper center', bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
            title = f"Data grouped by {categories}"
            ax.set_title(title)
            
        plt.rcParams.update({'figure.autolayout': False})
        return fig,ax    