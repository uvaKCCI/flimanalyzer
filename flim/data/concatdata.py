#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import pandas as pd
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.plugin import plugin 
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources



class ConcatenatorConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, data_choices={}, data_selected={}):
        self.data_choices = data_choices
        self.data_selected = data_selected

        BasicAnalysisConfigDlg.__init__(self, parent, title, data, data_choices=data_choices, enablefeatures=False, enablegrouping=False, optgridrows=2, optgridcols=1)
		    
    def get_option_panels(self):
        cfgdata = [{'Select':name in self.data_selected, 'Dataset': name} for name in self.data_choices]
        
        fsizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self.panel, wx.ID_ANY, "Select datasets to concatenate:")
        self.catsel = wx.CheckBox(self.panel, wx.ID_ANY, "Horizontal Concatenate ")
        self.cfggrid = wx.grid.Grid(self.panel)
        self.cfggrid.SetDefaultColSize(500,True)
        self.cfgtable = ListTable(cfgdata, headers=['Select', 'Dataset'], sort=False)
        self.cfggrid.SetTable(self.cfgtable,takeOwnership=True)
        self.cfggrid.SetRowLabelSize(0)
        self.cfggrid.SetColSize(0, -1)
        
        fsizer.Add(self.catsel, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(label, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.cfggrid, 1, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        return [fsizer]
        
    def _get_selected(self):
        self.cfggrid.EnableEditing(False)
        params = super()._get_selected()
        cfgdata = self.cfgtable.GetData()
        params['input'] = {row['Dataset']:self.data_choices[row['Dataset']] for row in cfgdata if row['Select']}
        params['type'] = self.catsel.GetValue()
        return params

    def OnSelectAll(self, event):
        col = 0
        for row in range(self.cfgtable.GetNumberRows()):
            self.cfgtable.SetValue(row, col, True)
        self.cfggrid.ForceRefresh()

    def OnDeselectAll(self, event):
        col = 0
        for row in range(self.cfgtable.GetNumberRows()):
            self.cfgtable.SetValue(row, col, False)
        self.cfggrid.ForceRefresh()

@plugin(plugintype='Data')
class Concatenator(AbstractPlugin):
    
    def __init__(self, data, **kwargs):
        AbstractPlugin.__init__(self, data, **kwargs)
        self.name = "Concatenate"
            
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_icon(self):
        source = files(flim.resources).joinpath('concatenate.png')
        return wx.Bitmap(str(source))
        
    def get_required_features(self):
        return []
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'input': {},
            'type': False
        })
        return params
            
    def output_definition(self):
        return {'Table: Concatenated': pd.DataFrame}
        
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
                
        dlg = ConcatenatorConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            data_choices=data_choices,
            data_selected=input)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params    
        
    def execute(self):
        results = {}
        input = self.params['input']
        cattype = self.params['type']
        if cattype: #horizontal
            caxis = 1
        else:
            caxis = 0
        data = list(input.values())
        concat_df = pd.concat(data, axis=caxis, copy=True)
        results['Table: Concatenated'] = concat_df
        return results
            
            
