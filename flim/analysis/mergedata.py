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

class MergerConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, data_choices=[], 
            how='left', left_on=None, right_on=None, left_index=False, right_index=False):
        self.how = how
        if left_on not in data_choices:
        	self.left_on = data_choices[0]
        else:
            self.left_on = left_on
        if right_on not in data_choices:
        	self.right_on = data_choices[1]
        else:
            self.right_on = right_on
        self.left_index = left_index
        self.right_index = right_index
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, data_choices, enablegrouping=False, enablefeatures=False, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=2, optgridcols=1)
		    
    def get_option_panels(self):
        fsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.left_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.left_on, choices=list(self.data_choices.keys()))
        self.right_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.right_on, choices=list(self.data_choices.keys()))
        fsizer.Add(wx.StaticText(self, label="Table 1"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.left_combobox, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(wx.StaticText(self, label="Table 2"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.right_combobox, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [fsizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['how'] = 'left'
        params['left_index'] = []
        params['right_index'] = []
        print (params)
        return params


class Merger(AbstractAnalyzer):
    
    def __init__(self, data, data_choices={}, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories={}, data_choices=data_choices, default='unassigned')
        self.data_choices = data_choices
        self.name = "Merge Data"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_icon(self):
        source = files(flim.resources).joinpath('merge.png')
        return wx.Bitmap(str(source))
        
    def get_required_features(self):
        return ['any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'how': '',
            'left_index': [],
            'right_index': [],
        })
        return params
            
    def run_configuration_dialog(self, parent):
        for k in self.params:
            print (k, self.params[k])
        dlg = MergerConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            data_choices=self.data_choices,
            how=self.params['how'], 
            left_index=self.params['left_index'], 
            right_index=self.params['right_index'],)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params    
        
    def execute(self):
        results = {}
        return results
            
