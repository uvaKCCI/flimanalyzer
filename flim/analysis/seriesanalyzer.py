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
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
import numpy as np

class SeriesAnalyzerConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', seriesmin=True, seriesmax=True, seriesrange=True, seriesmean=True, seriesmedian=True, delta=True, deltamin=True, deltamax=True, deltacum=False, mergeinput=False):
        self.seriesmin = seriesmin
        self.seriesmax = seriesmax
        self.seriesrange = seriesrange
        self.seriesmean = seriesmean
        self.seriesmedian = seriesmedian
        self.delta = delta
        self.deltamax = deltamax
        self.deltamin = deltamin
        self.deltacum = deltacum
        self.mergeinput = mergeinput
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, enablegrouping=False, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=1, optgridcols=0)
		    
    def get_option_panels(self):
        sizer = wx.GridSizer(5,0,0)

        self.seriesmin_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Series min")
        self.seriesmin_cb.SetValue(self.seriesmin)
        sizer.Add(self.seriesmin_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.seriesmax_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Series max")
        self.seriesmax_cb.SetValue(self.seriesmax)
        sizer.Add(self.seriesmax_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.seriesrange_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Series max-min")
        self.seriesrange_cb.SetValue(self.seriesrange)
        sizer.Add(self.seriesrange_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.seriesmean_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Series mean")
        self.seriesmean_cb.SetValue(self.seriesmean)
        sizer.Add(self.seriesmean_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.seriesmedian_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Series median")
        self.seriesmedian_cb.SetValue(self.seriesmedian)
        sizer.Add(self.seriesmedian_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.delta_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Step delta")
        self.delta_cb.SetValue(self.delta)
        sizer.Add(self.delta_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.deltamax_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Step delta min")
        self.deltamax_cb.SetValue(self.deltamin)
        sizer.Add(self.deltamax_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.deltamin_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Step delta max")
        self.deltamin_cb.SetValue(self.deltamax)
        sizer.Add(self.deltamin_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.deltacum_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Cumulative delta")
        self.deltacum_cb.SetValue(self.deltamax)
        sizer.Add(self.deltacum_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.mergeinput_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Merge input")
        self.mergeinput_cb.SetValue(self.mergeinput)
        sizer.Add(self.mergeinput_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [sizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['series_min'] = self.seriesmin_cb.GetValue()
        params['series_max'] = self.seriesmax_cb.GetValue()
        params['series_range'] = self.seriesrange_cb.GetValue()
        params['series_mean'] = self.seriesmean_cb.GetValue()
        params['series_median'] = self.seriesmedian_cb.GetValue()
        params['delta'] = self.delta_cb.GetValue()
        params['delta_min'] = self.deltamin_cb.GetValue()
        params['delta_max'] = self.deltamax_cb.GetValue()
        params['delta_cum'] = self.deltacum_cb.GetValue()
        params['merge_input'] = self.mergeinput_cb.GetValue()        
        return params
        

class SeriesAnalyzer(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Series Analysis"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('seriesanalysis.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any','any']
        
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'series_min': True,
            'series_max': True,
            'series_range': True,
            'series_mean': False,
            'series_median': False,
            'delta': True, 
            'delta_min':True,
            'delta_max':True,
            'delta_cum':False,
            'merge_input':False,
            })
        return params
                
    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        seriesmin = self.params['series_min']
        seriesmax = self.params['series_max']
        seriesrange = self.params['series_range']
        seriesmean = self.params['series_mean']
        seriesmedian = self.params['series_median']
        delta = self.params['delta']
        deltamin = self.params['delta_min']
        deltamax = self.params['delta_max']
        deltacum = self.params['delta_cum']
        mergeinput = self.params['merge_input']
        dlg = SeriesAnalyzerConfigDlg(parent, f'Configuration: {self.name}', self.data, 
        	selectedgrouping=selgrouping, 
        	selectedfeatures=selfeatures, 
        	seriesmin=seriesmin,
        	seriesmax=seriesmax,
        	seriesrange=seriesrange, 
        	seriesmean=seriesmean, 
        	seriesmedian=seriesmedian, 
        	delta=delta,
        	deltamin=deltamin,
        	deltamax=deltamax,
            deltacum=deltacum,
        	mergeinput=mergeinput)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        results = {}
        logging.debug (f"\tcreating series analysis for {self.params['features']}")
        categories = self.data.select_dtypes('category').columns.values
        features = self.params['features']
        sfeatures = [f.split("\n") for f in features]
        common = set(sfeatures[0]).intersection(*sfeatures[1:])
        uniquef = ['\n'.join([f for f in s if f not in common]) for s in sfeatures]
        label = '\n'.join(common)
        if self.params['merge_input']:
            cols = list(categories)
            cols.extend(features)
            df = self.data[cols].copy()
        else:
            df = self.data[categories].copy()
        if self.params['series_min']:
            df[f'{label}\nSeries min'] = self.data[features].min(axis=1)
        if self.params['series_max']:
            df[f'{label}\nSeries max'] = self.data[features].max(axis=1)
        if self.params['series_range']:
            df[f'{label}\nSeries max-min'] = self.data[features].max(axis=1)-self.data[features].min(axis=1)
        if self.params['series_mean']:
            df[f'{label}\nSeries mean'] = self.data[features].mean(axis=1)
        if self.params['series_median']:
            df[f'{label}\nSeries median'] = self.data[features].median(axis=1)
        if self.params['delta'] or self.params['delta_max'] or self.params['delta_min']:
            dfdelta = self.data[features].diff(axis=1)
            dfcum = dfdelta.cumsum(axis=1)
            uniquef.insert(0,'None')
            dcolheaders = [f'{label}\ndelta {uniquef[i]}:{uniquef[i+1]}' for i in range(len(uniquef)-1)]
            ccolheaders = [f'{label}\ncumulative delta {uniquef[1]}:{uniquef[i+1]}' for i in range(len(uniquef)-1)]
            dfdelta.columns = dcolheaders
            dfcum.columns = ccolheaders
            if self.params['delta']:
                df = df.join(dfdelta.iloc[:,1:])
            if self.params['delta_cum']:
                df = df.join(dfcum.iloc[:,1:])
            if self.params['delta_min']:
                df[f'{label}\nDelta min'] = dfdelta.iloc[:,1:].min(axis=1)
            if self.params['delta_max']:
                df[f'{label}\nDelta max'] = dfdelta.iloc[:,1:].max(axis=1)
        results["Series Analysis"] = df
        return results
            

