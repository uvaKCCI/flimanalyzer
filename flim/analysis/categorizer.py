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
            header='Category',
            selectedgrouping=['None'], 
            selectedfeatures='All', 
            categories={}, 
            default='unassigned',
            mergeinput=True):
        self.header = header
        self.categories = categories
        self.default = default
        self.mergeinput = mergeinput
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, enablegrouping=False, enablefeatures=False, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=2, optgridcols=1)
		    
    def get_option_panels(self):
        helptxt = f'Specifiy PCA components to retain:'\
                                 '\n\tleave empty:   retain all PCA components.'\
                                 '\n\t0.0 < n < 1.0 (float):   retain PCA components that explain specified fraction of observed variance.'\
                                 '\n\t1 <= n <= {len(self.allfeatures)} (integer):   retain first n PCA components.'
        
        mins = [c['criteria']['min'] for c in self.categories]
        maxs = [c['criteria']['max'] for c in self.categories]
        values = [c['value'] for c in self.categories]
        print (values)
        bins = mins
        bins.append(maxs[-1])
        print (bins)
        if len(self.selectedfeatures) > 0:
            selectedfeature = list(self.selectedfeatures.keys())[0] 
        else:
            selectedfeature = list(self.allfeatures.keys())[0]

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.header_field = wx.TextCtrl(self, value=self.header, size=(500,-1))
        hsizer.Add(wx.StaticText(self, label="Category column header"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        hsizer.Add(self.header_field, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
                
        fsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.feature_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=selectedfeature, choices=list(self.allfeatures.keys()))
        fsizer.Add(wx.StaticText(self, label="Feature to categorize"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.feature_combobox, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.bin_field = wx.TextCtrl(self, value=','.join([str(b) for b in bins]), size=(500,-1))
        bsizer.Add(wx.StaticText(self, label="Category bins "), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        bsizer.Add(self.bin_field, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        vsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.value_field = wx.TextCtrl(self, value=','.join(values), size=(500,-1))
        vsizer.Add(wx.StaticText(self, label="Category labels"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        vsizer.Add(self.value_field, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
                
        dsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.default_field = wx.TextCtrl(self, value=self.default, size=(500,-1))
        dsizer.Add(wx.StaticText(self, label="Default value"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        dsizer.Add(self.default_field, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
                
        msizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mergeinput_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Merge input")
        self.mergeinput_cb.SetValue(self.mergeinput)
        msizer.Add(self.mergeinput_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [hsizer, fsizer, bsizer, vsizer, dsizer, msizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        bins = self.bin_field.GetValue().split(',')
        values = self.value_field.GetValue().split(',')
        feature = self.allfeatures[self.feature_combobox.GetValue()]
        params['features'] = [feature]
        params['name'] = self.header_field.GetValue()
        params['categories']  = [{'value':values[i],'criteria':{'feature':feature, 'min':float(bins[i]), 'max':float(bins[i+1])}} for i in range(len(values))]
        params['default'] = self.default_field.GetValue()
        params['merge_input'] = self.mergeinput_cb.GetValue()
        print (params)
        return params


class Categorizer(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
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
        return ['any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'name': 'New Cat',
            'categories': [ 
        	    {'value':'negative',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': -100000.0,
        	         'max': -0.5,},
        	    },
        	    {'value':'neutral',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': -0.5,
        	         'max': 0.5,},
        	    },
        	    {'value':'positive',
        	     'criteria': {
        	         'feature': 'FLIRR',
        	         'min': 0.5,
        	         'max': 100000,},
        	    },
        	],
        	'default': 'unassigned',
        	'merge_input': True,
        })
        return params
            
    def run_configuration_dialog(self, parent):
        for k in self.params:
            print (k, self.params[k])
        dlg = CategorizerConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            header=self.params['name'],
            categories=self.params['categories'], 
            default=self.params['default'],
            mergeinput=self.params['merge_input'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params    
        
    def execute(self):
        colname = self.params['name']
        categories = self.params['categories']
        selfeatures = self.params['features']
        default = self.params['default']
        mins = [c['criteria']['min'] for c in categories]
        maxs = [c['criteria']['max'] for c in categories]
        values = [v['value'] for v in categories]
        print (values)
        bins = mins
        bins.append(maxs[-1])
        print (bins)
        feature = categories[0]['criteria']['feature']
        print (feature)

        catcols = self.data.select_dtypes('category').columns.values

        if self.params['merge_input']:
            cat_df = self.data.copy()
        else:
            cols = list(catcols)
            cols.extend(selfeatures)
            cat_df = self.data[cols].copy()
        cat_df[colname] = pd.cut(self.data[feature], bins=bins, labels=values)
        cat_df[colname].cat.add_categories(default, inplace=True)
        cat_df[colname].fillna(default, inplace=True)
        orderedcols = [c for c in cat_df.columns.values if c != colname]
        orderedcols.insert(len(catcols),colname)
        cat_df = cat_df[orderedcols]
        results = {
            'Categorized': cat_df,
        }
        return results
            
