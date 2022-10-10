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
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib.pyplot as plt
import itertools
from importlib_resources import files
import flim.resources

class ScatterPlot(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Scatter Plot"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('scatter.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any', 'any']
        
    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = BasicAnalysisConfigDlg(parent, 'Scatter Plot', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        results = {}
        combs = itertools.combinations(self.params['features'], 2)
        for comb in sorted(combs):
            logging.debug (f"\tcreating scatter plot for {str(comb)}")
            fig = self.grouped_scatterplot(self.data, comb, categories=self.params['grouping'], marker='o', s=10)#, facecolors='none', edgecolors='r')
            results[f"Scatter Plot: {comb}"] = fig
        return results
    
    def grouped_scatterplot(self, data, combination,  title=None, categories=[], dropna=True, pivot_level=1, **kwargs):
        #plt.rcParams.update({'figure.autolayout': True})
        col1 = combination[0]
        col2 = combination[1]
        if data is None or not col1 in data.columns.values or not col2 in data.columns.values:
            return None, None
            
        if categories is None:
            categories = []
        fig, ax = plt.subplots(constrained_layout=True)
        
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
            #chartbox = ax.get_position()
            #ax.set_position([chartbox.x0, chartbox.y0, chartbox.width* (1-0.2 * no_legendcols), chartbox.height])
            no_legendcols = (len(categories)//30 + 1)
            ax.legend(labels=labels, loc='upper left', title=', '.join(categories), bbox_to_anchor= (1.0, 1.0), fontsize='small', ncol=no_legendcols)
            title = f"Data grouped by {categories}"
            ax.set_title(title)
            
        #plt.rcParams.update({'figure.autolayout': False})
        
        self._add_picker(fig)
        return fig   
