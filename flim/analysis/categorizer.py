#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources

class CategorizerConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, 
            selectedgrouping=['None'], 
            selectedfeatures='All', 
            categories={}, 
            default='unassigned'):

        self.categories = categories
        self.default = default
        self.allfeatures = data.select_dtypes(include=['number'], exclude=['category']).columns.values
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=2, optgridcols=1)
		    
    def get_option_panels(self):
        helptxt = f'Specifiy PCA components to retain:'\
                                 '\n\tleave empty:   retain all PCA components.'\
                                 '\n\t0.0 < n < 1.0 (float):   retain PCA components that explain specified fraction of observed variance.'\
                                 '\n\t1 <= n <= {len(self.allfeatures)} (integer):   retain first n PCA components.'
        
        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        mins = [c['criteria']['min'] for c in self.categories]
        maxs = [c['criteria']['max'] for c in self.categories]
        labels = [l['label'] for l in self.categories]
        print (labels)
        bins = mins
        bins.append(maxs[-1])
        print (bins)
        self.bin_field = wx.TextCtrl(self, value=','.join([str(b) for b in bins]), size=(500,-1))
        bsizer.Add(wx.StaticText(self, label="Category bins"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        bsizer.Add(self.bin_field, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        lsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.label_field = wx.TextCtrl(self, value=','.join(labels), size=(500,-1))
        lsizer.Add(wx.StaticText(self, label="Category labels"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        lsizer.Add(self.label_field, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
                
        return [bsizer, lsizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['categories'] = [        	    
                {'label':'Cat 1',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': 0.0,
        	         'max': 0.1,},
        	    },
        	    {'label':'Cat 2',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': 0.1,
        	         'max': 1.0,},
        	    }
        ]
        params['default'] = 'unassigned'

        return params


class Categorizer(AbstractAnalyzer):
    
    def __init__(self, data, keeporig=False, keepstd=True, explainedhisto=False, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories={}, default='unassigned')
        self.name = "Categorize Data"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_icon(self):
        source = files(flim.resources).joinpath('categorize.png')
        return wx.Bitmap(str(source))
        
    def get_required_features(self):
        return ['any', 'any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'categories': [ 
        	    {'label':'Cat 1',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': 0.0,
        	         'max': 0.1,},
        	    },
        	    {'label':'Cat 2',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': 0.1,
        	         'max': 1.0,},
        	    }
        	],
        	'default': 'unassigned',
        })
        return params
            
    def run_configuration_dialog(self, parent):
        for k in self.params:
            print (k, self.params[k])
        dlg = CategorizerConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            categories=self.params['categories'], 
            default=self.params['default'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params    
        
    def execute(self):        
        cat_df = pd.DataFrame()
        results = {
            'Categorized': cat_df,
        }
        return results
            
