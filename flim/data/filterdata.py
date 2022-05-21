#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import wx.grid
from wx.lib.masked import NumCtrl
import pandas as pd
from importlib_resources import files
from itertools import groupby
import numpy as np

from flim.core.filter import RangeFilter
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.datapanel import PandasTable
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.resources


class FilterConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, input=None, filter_params={}, use=True, show_dropped=False, inplace=False):
        self.filter_params = filter_params
        self.use = use
        self.show_dropped = show_dropped
        self.inplace = inplace
        super().__init__(parent, title, input=input, enablegrouping=False, enablefeatures=False, optgridrows=1, optgridcols=0)
		    
    def get_option_panels(self):
        fsizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self.panel, wx.ID_ANY, "Filter data")
        fsizer.Add(label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)

        return [fsizer]
        
    def _get_selected(self):
        #self.cfggrid.EnableEditing(False)
        params = super()._get_selected()
        params['category_filters'] = {}
        params['range_filters'] = self.filter_params
        params['use'] = self.use
        params['show_dropped'] = self.show_dropped
        params['inplace'] = self.inplace # leave unchanged
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
class Filter(AbstractPlugin):
    
    def __init__(self, name='Filter', **kwargs):
        AbstractPlugin.__init__(self, name=name, **kwargs) #categories={}, default='unassigned')
        default_filters = [
                        RangeFilter('trp t1',0,2500).get_params(),
                        RangeFilter('trp t2',0,8000).get_params(),
                        RangeFilter('trp tm',0,4000,selected=False).get_params(),
                        RangeFilter('trp a1[%]',0,100).get_params(),
                        RangeFilter('trp a2[%]',0,100).get_params(),
                        RangeFilter('trp a1[%]/a2[%]',0,2).get_params(),
                        RangeFilter('trp E%1',0,100).get_params(),
                        RangeFilter('trp E%2',0,100).get_params(),
                        RangeFilter('trp E%3',0,100).get_params(),
                        RangeFilter('trp r1',0,15).get_params(),
                        RangeFilter('trp r2',0,3).get_params(),
                        RangeFilter('trp r3',0,3).get_params(),
                        RangeFilter('trp chi',0,4.7).get_params(),
                        RangeFilter('trp photons',0,160).get_params(),
                        RangeFilter('NAD(P)H a1',0,1000, selected=True).get_params(),
                        RangeFilter('NAD(P)H a1[%]',0,100).get_params(),
                        RangeFilter('NAD(P)H a2',5,300, selected=True).get_params(),
                        RangeFilter('NAD(P)H a2[%]',0,100).get_params(),
                        RangeFilter('NAD(P)H t1',10,1000, selected=True).get_params(),
                        RangeFilter('NAD(P)H t2',2000,7000, selected=True).get_params(),
                        RangeFilter('NAD(P)H tm',0,2000).get_params(),
                        RangeFilter('NAD(P)H photons',10,2000, selected=True).get_params(),
                        RangeFilter('NAD(P)H a2[%]',0,100).get_params(),
                        RangeFilter('NADPH %',0,99).get_params(),
                        RangeFilter('NADH %',0,100).get_params(),
                        RangeFilter('NADPH/NADH',0,3).get_params(),
                        RangeFilter('NAD(P)H chi',0.7,4.7).get_params(),
                        RangeFilter('FAD t1',10,1500, selected=True).get_params(),
                        RangeFilter('FAD t2',1000,6000, selected=True).get_params(),
                        RangeFilter('FAD tm',0,2500).get_params(),
                        RangeFilter('FAD a1',10,500, selected=True).get_params(),
                        RangeFilter('FAD a1[%]',0,100).get_params(),
                        RangeFilter('FAD a2',10,300, selected=True).get_params(),
                        RangeFilter('FAD a2[%]',0,100).get_params(),
                        RangeFilter('FAD a1[%]/a2[%]',0,16).get_params(),
                        RangeFilter('FLIRR',0,2.4).get_params(),
                        RangeFilter('FAD chi',0.7,4.7).get_params(),
                        RangeFilter('FAD photons',10,1000, selected=True).get_params(),
                        RangeFilter('FAD photons/NAD(P)H photons',0,2).get_params(),
        ]
        self.default_filters = {filter['name']:filter for filter in default_filters}
    
    #def __repr__(self):
    #    return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_icon(self):
        source = files(flim.resources).joinpath('filter.png')
        return wx.Bitmap(str(source))
        
    def get_required_features(self):
        return []
    
    def _sort_category(values, sort_algo):
        return values
        
    def _update_filter_params(self, data, filter_params=[]):
        updated_params = []
        if data is not None:
            number_cols = list(data.select_dtypes(np.number).columns.values)
            updated_params = [fparam for fparam in filter_params if fparam['name'] in number_cols]
            existing_names = [fparam['name'] for fparam in filter_params]
            missing_names = [n for n in number_cols if n not in existing_names]
            # create defaults for missing filters 
            for col in missing_names:
                fparams = self.default_filters.get(col, RangeFilter(col).get_params())
                updated_params.append(fparams)
        return updated_params
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'category_filters': {},
            'range_filters': self._update_filter_params(None),
            'use': True,
            'show_dropped': False,
            'inplace': False,
        })
        return params
            
    def output_definition(self):
        return {'Table: Filtered': None}
        
    def run_configuration_dialog(self, parent, data_choices={}):
        data = list(self.input.values())[0]
        filter_params = self._update_filter_params(data, self.params['range_filters'])
        logging.debug (filter_params)
        inplace = self.params['inplace']
                
        dlg = FilterConfigDlg(parent, f'Configuration: {self.name}',
            input=self.input, 
            filter_params=filter_params,
            inplace=inplace)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        print (self.params)
        return self.params    
        
    def execute(self):
        data = list(self.input.values())[0]
        if not self.params['inplace']:
            data = data.copy()
        
        droppedrows = {}
        for cat,values in self.params['category_filters'].items():
            drop_values = [v for v in data[cat].unique() if v not in values]
            droppedrows[cat] = np.flatnonzero(data[cat].isin(drop_values))
            
        filter_params = {f['name']:f for f in self._update_filter_params(data, self.params['range_filters'])}
        for fname in filter_params:
            filter = RangeFilter(params=filter_params[fname])
            if filter.is_selected():
                droppedrows[fname] = filter.get_dropped(data)
            #elif droppedrows.get(fname) is not None:
            # 	del droppedrows[fname]
            	
        # all dropped rows are the unique elements of the union of rfilterdropped andcatdropped
        arraylist = [drows for drows in droppedrows.values() if len(drows) > 0]
        if len(arraylist) > 0:
            arraylist = np.concatenate(arraylist)
        droppedrows = np.unique(arraylist)

        logging.debug (f'droppedrows={droppedrows}')
        if len(droppedrows) != 0:
            data = data.drop(data.index[droppedrows]).reset_index(drop=True)
        results = {}
        results['Table: Filtered'] = data
        return results
            
