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

    def __init__(self, parent, title, data, description=None, data_choices={}, 
            how='left', left_on=None, right_on=None, left_index=False, right_index=False):
        self.data_choices = data_choices
        self.how_choices = {'<< merge left':'left', 'merge right >>':'right', 'merge inner':'inner', 'merge outer':'outer'}
        howvalues = list(self.how_choices.values())
        if how in howvalues:
            keypos = howvalues.index(how)
            self.how = list(self.how_choices.keys())[keypos]
        else:   
            self.how = list(self.how_choices.keys())[0]
        dc = list(data_choices.keys())
        if left_on not in dc:
        	self.left_on = dc[0]
        else:
            self.left_on = left_on
        if right_on not in dc:
        	self.right_on = dc[1]
        else:
            self.right_on = right_on
        self.left_index = left_index
        self.right_index = right_index
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, description=description, data_choices=data_choices, enablefeatures=False, enablegrouping=False, optgridrows=2, optgridcols=1)
		    
    def get_option_panels(self):
        fsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.left_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.left_on, choices=list(self.data_choices.keys()))
        self.how_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.how, choices=list(self.how_choices.keys()))        
        self.right_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.right_on, choices=list(self.data_choices.keys()))
        fsizer.Add(wx.StaticText(self, label="Table 1"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.left_combobox, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.how_combobox, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(wx.StaticText(self, label="Table 2"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.right_combobox, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [fsizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['how'] = self.how_choices[self.how_combobox.GetValue()]
        params['left_index'] = []
        params['right_index'] = []
        params['input'] = {self.left_combobox.GetValue(): self.data_choices[self.left_combobox.GetValue()], self.right_combobox.GetValue(): self.data_choices[self.right_combobox.GetValue()]}
        return params


class Merger(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories={}, default='unassigned')
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
        return []
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'how': '',
            'left_index': [],
            'right_index': [],
            'input': {},
        })
        return params
            
    def run_configuration_dialog(self, parent, data_choices={}):
        input = self.params['input']
        # left_on and right_on are str representing dataframe window titles
        if isinstance(input,dict) and len(input) > 0:
            left_on = list(input.keys())[0]
        else:
            left_on=''
        if isinstance(input,dict) and len(input) > 1:
            right_on = list(input.keys())[1]
        else:
            right_on=''
                
        dlg = MergerConfigDlg(
            parent, 
            f'Configuration: {self.name}', 
            self.data,
            description = self.get_description(), 
            data_choices=data_choices,
            left_on=left_on,
            right_on=right_on,
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
        input = self.params['input'] 
        data = list(input.values())
        left = data[0]
        right = data[1]
        how = self.params['how']
        left_on = [c for c in list(left.select_dtypes(['category']).columns.values)]
        right_on = [c for c in list(right.select_dtypes(['category']).columns.values)]
        on = list(set(left_on).intersection(set(right_on)))
        #left.set_index(on, inplace=True)
        #print (left.index)
        #right.set_index(on, inplace=True)
        #print (right.index)
        merged_df = pd.merge(left, right, how=how, on=on)
        merged_df[on] = merged_df[on].astype('category')
        #merged_df = pd.merge(left, right, how=how, left_index=True, right_index=True)
        neworder = [c for c in list(merged_df.select_dtypes(['category']).columns.values)]
        noncategories = [c for c in merged_df.columns.values if c not in neworder]
        neworder.extend(noncategories)
        merged_df = merged_df[neworder]
        results['Merged'] = merged_df
        return results
            
