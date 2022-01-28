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

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', allaggs=[], selectedaggs='All', singledf=False):
        self.allaggs = allaggs
        self.selectedaggs = selectedaggs
        self.singledf = singledf
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=0, optgridcols=1)
		    
    def get_option_panels(self):
        self.aggboxes = {}
        ssizer = wx.BoxSizer(wx.HORIZONTAL)
        self.dfoutput_opts = ['Single table', 'One table per feature']
        if self.singledf:
            sel_dfoutput = self.dfoutput_opts[0]
        else:
            sel_dfoutput = self.dfoutput_opts[1]
        self.dfoutput_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=sel_dfoutput, choices=self.dfoutput_opts)
        ssizer.Add(wx.StaticText(self, label="Output "), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        ssizer.Add(self.dfoutput_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        nestsizer = wx.BoxSizer(wx.HORIZONTAL)
        aggsizer = wx.GridSizer(5, 0, 0)
        for f in self.allaggs:
            cb = wx.CheckBox(self,wx.ID_ANY,f)
            cb.SetValue((f in self.selectedaggs) or (self.selectedaggs == 'All'))
            self.aggboxes[f] = cb
            aggsizer.Add(cb, 0, wx.ALL, 5)

        selectsizer = wx.BoxSizer(wx.VERTICAL)
        self.selectAllButton = wx.Button(self, label="Select All")
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.OnSelectAll)
        selectsizer.Add(self.selectAllButton, 0, wx.ALL|wx.EXPAND, 5)
        self.deselectAllButton = wx.Button(self, label="Deselect All")
        self.deselectAllButton.Bind(wx.EVT_BUTTON, self.OnDeselectAll)
        selectsizer.Add(self.deselectAllButton, 0, wx.ALL|wx.EXPAND, 5)
        nestsizer.Add(aggsizer, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL)
        nestsizer.Add(selectsizer, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL)
        return [ssizer,nestsizer]
    
    def OnSelectAll(self, event):
        if self.aggboxes:
            for key in self.aggboxes:
                self.aggboxes[key].SetValue(True)
        
    def OnDeselectAll(self, event):
        if self.aggboxes:
            for key in self.aggboxes:
                self.aggboxes[key].SetValue(False)
    
    def _get_selected(self):
        selaggs = [key for key in self.aggboxes if self.aggboxes[key].GetValue()]
        params = super()._get_selected()
        params['aggs'] = selaggs
        params['singledf'] = self.dfoutput_combobox.GetValue() == self.dfoutput_opts[0]
        return params


class SummaryStats(AbstractAnalyzer):
    
    agg_functions = {'count':'count', 'min':'min', 'max':'max', 'mean':'mean', 'std':'std', 'sem':'sem', 'median':'median', 'percentile(25)':percentile(25), 'percentile(75)':percentile(75), 'sum':'sum'}
    
    def __init__(self, data, aggs=['count', 'min', 'max', 'mean', 'std', 'sem', 'median', 'percentile(25)', 'percentile(75)', 'sum'], singledf=True, flattenindex=True, **kwargs):
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
            'singledf': True, 
            'flattenindex': True})
        return params
        
    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = SummaryStatsConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=self.params['grouping'], selectedfeatures=self.params['features'], allaggs=self.agg_functions, selectedaggs=self.params['aggs'], singledf=self.params['singledf'])
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
                summary.reset_index(inplace=True)
            if self.params['flattenindex']:
                summary.columns = ['\n'.join(col).strip() for col in summary.columns.values]    
            summaries[dftitle] = summary #.reset_index()
        if self.params['singledf']:
            if len(self.params['grouping']) > 0:
                concat_df = pd.concat([summaries[key].set_index(self.params['grouping']) for key in summaries], axis=1).reset_index()
            else:
                concat_df = pd.concat([summaries[key] for key in summaries], axis=1)            
            return {f"{titleprefix}": concat_df}
        else:
            return summaries
