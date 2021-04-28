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


class RelativeChangeConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', method='mean', refgroup='', refvalue=''):
        self.data = data
        self.method_options = ['mean', 'median']
        self.sel_method = method
        if self.sel_method not in self.method_options:
            self.sel_method = self.method_options[0]

        self.categories = list(data.select_dtypes(['category']).columns.values)
        self.sel_refgroup = refgroup
        if self.sel_refgroup not in self.categories:
            self.sel_refgroup = self.categories[0]

        self.refval_options = data[self.sel_refgroup].unique()
        self.sel_refvalue = refvalue
        if self.sel_refvalue not in self.refval_options:
            self.sel_refvalue = self.refval_options[0]
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=1, optgridcols=1)
		    
    def get_option_panels(self):
        self.aggboxes = {}
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refgrp_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.sel_refgroup, choices=self.categories)
        self.refgrp_combobox.Bind(wx.EVT_COMBOBOX, self.OnRefGroupChanged)
        sizer.Add(wx.StaticText(self, label="Reference Group"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.refgrp_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        dummy = [a for c in self.categories for a in self.data[c].unique()]
        self.refval_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.sel_refvalue, choices=dummy)
        self.refval_combobox.SetItems(self.refval_options)
        self.refval_combobox.SetValue(self.sel_refvalue)
        sizer.Add(wx.StaticText(self, label="Reference Value"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.refval_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.method_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.sel_method, choices=self.method_options)
        sizer.Add(wx.StaticText(self, label="Method"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.method_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        return [sizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['method'] = self.method_combobox.GetValue()
        params['reference_group'] = self.refgrp_combobox.GetValue()
        params['reference_value'] = self.refval_combobox.GetValue()
        return params

    def OnRefGroupChanged(self, event):
        sel_refgroup = self.refgrp_combobox.GetValue()
        self.refval_options = self.data[sel_refgroup].unique()
        self.sel_refvalue = self.refval_options[0]
        self.refval_combobox.SetItems(self.refval_options)
        self.refval_combobox.SetValue(self.sel_refvalue)
        

class RelativeChange(AbstractAnalyzer):
     
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Relative Change"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        return wx.Bitmap("resources/relchange.png")
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'method': 'mean', # 'median'
            'reference_group': 'Treatment',
            'reference_value': 'Ctrl',
            })
        return params
        
    def run_configuration_dialog(self, parent):
        dlg = RelativeChangeConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            method=self.params['method'],
            refgroup=self.params['reference_group'],
            refvalue=self.params['reference_value'],
            )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        parameters = dlg.get_selected()  
        self.configure(**parameters)
        return parameters
    
    def execute(self):
        method = self.params['method']
        allcategories = list(self.data.select_dtypes(['category']).columns.values)
        features = self.params['features']
        grouping = self.params['grouping']
        refgroup = self.params['reference_group']
        refvalue = self.params['reference_value']
        cols = allcategories + features
        data = self.data[cols]

        nonrefcategories = [c for c in allcategories if c != refgroup]

        refdf = data.loc[data[refgroup]==refvalue]
        if method == 'median':
            transdf = refdf.groupby(grouping)[features].transform('median')
        else:
            transdf = refdf.groupby(grouping)[features].transform('mean')
        data = data.set_index(allcategories)
        transdf = pd.concat([refdf[nonrefcategories], transdf], axis=1)
        transdf = transdf.drop_duplicates()
        transdf = transdf.set_index(nonrefcategories)        
        transdef = transdf.reindex(data.index)
        reldf = data[features].div(transdf).reset_index()
        for ckey in allcategories:
            reldf[ckey] = reldf[ckey].astype('category')
        columnlabels = [col if col in allcategories else f'rel {col}' for col in reldf.columns.values]
        reldf.columns = columnlabels
                 
        title = f'Relative-{method}'
        return {title:reldf}
