#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

import numpy as np
import pandas as pd
import wx
from analysis.absanalyzer import AbstractAnalyzer
from gui.dialogs import SelectGroupsDlg

def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)
    percentile_.__name__ = '%s percentile' % n
    return percentile_    



class SummaryStats(AbstractAnalyzer):
    
    agg_functions = {'count':'count', 'min':'min', 'max':'max', 'mean':'mean', 'std':'std', 'median':'median', 'percentile(25)':percentile(25), 'percentile(75)':percentile(75)}
    
    def __init__(self, data, categories, features, aggs=['count', 'min', 'max', 'mean', 'std', 'median', percentile(25), percentile(75)], singledf=True, flattenindex=True, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories, features, aggs=aggs, singledf=singledf, flattenindex=flattenindex)
        self.name = "Summary Table"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
    
    def run_configuration_dialog(self, parent):
        dlg = SelectGroupsDlg(parent, title='Summary: aggregation functions', groups=self.agg_functions)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        parameters = {'aggs': dlg.get_selected()}      
        self.configure(**parameters)
        return parameters
    
    def execute(self):
        titleprefix = 'Summary'
        summaries = {}
        sel_functions = [self.agg_functions[f] for f in self.params['aggs']]
        if self.features is None or len(self.features) == 0:
            return summaries
        for header in self.features:
            #categories = [col for col in self.flimanalyzer.get_importer().get_parser().get_regexpatterns()]
            allcats = [x for x in self.categories]
            allcats.append(header)
            dftitle = ": ".join([titleprefix,header.replace('\n',' ')])
            if self.categories is None or len(self.categories) == 0:
                # create fake group by --> creates 'index' column that needs to removed from aggregate results
                summary = self.data[allcats].groupby(lambda _ : True, group_keys=False).agg(sel_functions)
            else:                
                #data = data.copy()
                #data.reset_index(inplace=True)
                grouped_data = self.data[allcats].groupby(self.categories, observed=True)
                summary = grouped_data.agg(sel_functions)
                #summary = summary.dropna()
            if self.params['flattenindex']:
                summary.columns = ['\n'.join(col).strip() for col in summary.columns.values]    
            summaries[dftitle] = summary
        if self.params['singledf']:
            concat_df = pd.concat([summaries[key] for key in summaries], axis=1)
            return {f"{titleprefix} - rows={len(self.data)}": concat_df}
        else:
            return summaries
