#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

import numpy as np
import pandas as pd
import wx
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources


def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)
    percentile_.__name__ = '%s percentile' % n
    return percentile_    


class SummaryStatsConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', allaggs=[], selectedaggs='All'):
        self.allaggs = allaggs
        self.selectedaggs = selectedaggs
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=1, optgridcols=1)
		    
    def get_option_panels(self):
        self.aggboxes = {}
        aggsizer = wx.GridSizer(4, 0, 0)
        for f in self.allaggs:
            cb = wx.CheckBox(self,wx.ID_ANY,f)
            cb.SetValue((f in self.selectedaggs) or (self.selectedaggs == 'All'))
            self.aggboxes[f] = cb
            aggsizer.Add(cb, 0, wx.ALL, 5)
        return [aggsizer]
        
    def _get_selected(self):
        selaggs = [key for key in self.aggboxes if self.aggboxes[key].GetValue()]
        params = super()._get_selected()
        params['aggs'] = selaggs
        return params


class SummaryStats(AbstractAnalyzer):
    
    agg_functions = {'count':'count', 'min':'min', 'max':'max', 'mean':'mean', 'std':'std', 'sem':'sem', 'median':'median', 'percentile(25)':percentile(25), 'percentile(75)':percentile(75)}
    
    def __init__(self, data, aggs=['count', 'min', 'max', 'mean', 'std', 'sem', 'median', 'percentile(25)', 'percentile(75)'], singledf=True, flattenindex=True, **kwargs):
        AbstractAnalyzer.__init__(self, data, aggs=aggs, singledf=singledf, flattenindex=flattenindex, **kwargs)
        self.name = "Summary Table"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('summary.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'aggs': [n for n in self.agg_functions], 
            'singledf': False, 
            'flattenindex': True})
        return params
        
    def run_configuration_dialog(self, parent):
        dlg = SummaryStatsConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=self.params['grouping'], selectedfeatures=self.params['features'], allaggs=self.agg_functions, selectedaggs=self.params['aggs'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        parameters = dlg.get_selected()  
        self.configure(**parameters)
        return parameters
    
    def execute(self):
        titleprefix = 'Summary'
        summaries = {}
        sel_functions = [self.agg_functions[f] for f in self.params['aggs']]
        if self.params['features'] is None or len(self.params['features']) == 0:
            return summaries
        for header in self.params['features']:
            #categories = [col for col in self.flimanalyzer.get_importer().get_parser().get_regexpatterns()]
            allcats = [x for x in self.params['grouping']]
            allcats.append(header)
            dftitle = ": ".join([titleprefix,header.replace('\n',' ')])
            if self.params['grouping'] is None or len(self.params['grouping']) == 0:
                # create fake group by --> creates 'index' column that needs to removed from aggregate results
                summary = self.data[allcats].groupby(lambda _ : True, group_keys=False).agg(sel_functions)
            else:                
                #data = data.copy()
                #data.reset_index(inplace=True)
                grouped_data = self.data[allcats].groupby(self.params['grouping'], observed=True)
                summary = grouped_data.agg(sel_functions)
                #summary = summary.dropna()
            if self.params['flattenindex']:
                summary.columns = ['\n'.join(col).strip() for col in summary.columns.values]    
            summaries[dftitle] = summary.reset_index()
        if self.params['singledf']:
            concat_df = pd.concat([summaries[key] for key in summaries], axis=1)
            return {f"{titleprefix}": concat_df.reset_index()}
        else:
            return summaries
