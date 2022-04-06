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


from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.datapanel import PandasTable
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.resources


class TablePanel(wx.Panel):

    def __init__(self, parent, header, values): 
        super().__init__(parent)
        self.catdf = pd.DataFrame({f'{header}_orig': values, header: list(values)})
        table = PandasTable(self.catdf)
        self.grid = wx.grid.Grid(self, -1, size=(400,200))
        self.grid.SetTable(table, takeOwnership=True)
        self.grid.AutoSizeColumns(setAsMin=True)
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
        for row in range(self.grid.GetNumberRows()):
            self.grid.SetReadOnly(row,1)
        gridsizer = wx.BoxSizer(wx.VERTICAL)
        gridsizer.Add(self.grid)
        
        buttonsizer = wx.BoxSizer(wx.VERTICAL)
        bmp =  wx.ArtProvider.GetBitmap(wx.ART_GO_UP, wx.ART_MENU)
        up_button = wx.BitmapButton(self, id = wx.ID_ANY, bitmap = bmp, size = (bmp.GetWidth()+10, bmp.GetHeight()+10))
        up_button.Bind(wx.EVT_BUTTON, self.move_up)
        bmp = wx.ArtProvider.GetBitmap(wx.ART_GO_DOWN, wx.ART_MENU) 
        down_button = wx.BitmapButton(self, id = wx.ID_ANY, bitmap = bmp, size = (bmp.GetWidth()+10, bmp.GetHeight()+10))
        down_button.Bind(wx.EVT_BUTTON, self.move_down)
        buttonsizer.Add(up_button)
        buttonsizer.Add(down_button)
        
        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(gridsizer)
        mainsizer.Add(buttonsizer)
        self.SetSizer(mainsizer)
    
    def get_selection(self):
        rows = []
        top_left = self.grid.GetSelectionBlockTopLeft()
        bottom_right = self.grid.GetSelectionBlockBottomRight()
        if len(top_left)>0 and len(bottom_right)>0:
            rows.extend(range(top_left[0].GetRow(), bottom_right[0].GetRow()+1))
        sel_rows = self.grid.GetSelectedRows()
        rows.extend([r for r in sel_rows])
        sel_cells = self.grid.GetSelectedCells()
        if len(sel_cells) > 0:
            rows.extend([gridcoords.GetRow() for gridcoords in sel_cells])
        if len(rows) == 0:
            cursor_row = self.grid.GetGridCursorRow()
            #print (f'cursor row:{cursor_row}')
            rows.append(cursor_row)
        rows = sorted(set(rows))
        #print (f'sel rows:{rows}')
        
        # split blocks of consecutive indices
        rows = [[e[1] for e in list(g)] for k, g in groupby(enumerate(rows), lambda ix:(ix[1]-ix[0]))]
        return rows
    
    def update_grid(self, sel_rows):
        colsizes = self.grid.GetColSizes()
        self.grid.SetTable(PandasTable(self.catdf), takeOwnership=True)
        self.grid.SetColSizes(colsizes)
        self.grid.Refresh()
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
        for row in range(self.grid.GetNumberRows()):
            self.grid.SetReadOnly(row,1)
        for i,row in enumerate(sel_rows):
            self.grid.SelectRow(row, addToSelected=i!=0)
    
    def move_up(self, evt):
        sel_rows = self.get_selection()
        flat_list = [item for sublist in sel_rows for item in sublist]
        if len(flat_list) == 0 or min(flat_list) < 1:
            return
        for rows in sel_rows:
            above_line = pd.DataFrame([self.catdf.iloc[min(rows)-1,:]], columns=self.catdf.columns.values)
            move_block = self.catdf.iloc[rows,:]
            self.catdf = pd.concat([self.catdf.iloc[:min(rows)-1], move_block, above_line, self.catdf.iloc[max(rows)+1:]]).reset_index(drop=True)
        self.update_grid([r-1 for r in flat_list])

    def move_down(self, evt):
        sel_rows = self.get_selection()
        flat_list = [item for sublist in sel_rows for item in sublist]
        if len(flat_list) == 0 or max(flat_list) == self.grid.GetNumberRows()-1:
            return
        for rows in sel_rows[::-1]:
            below_line = pd.DataFrame([self.catdf.iloc[max(rows)+1,:]], columns=self.catdf.columns.values)
            move_block = self.catdf.iloc[rows,:]
            self.catdf = pd.concat([self.catdf.iloc[:min(rows)], below_line, move_block, self.catdf.iloc[max(rows)+2:]]).reset_index(drop=True)
        self.update_grid([r+1 for r in flat_list])
      
class CategoryOrderConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, categories={}, inplace=False):
        self.categories = categories
        self.inplace = inplace
        self.data = data

        super().__init__(parent, title, data, enablegrouping=False, enablefeatures=False, optgridrows=1, optgridcols=0)
		    
    def get_option_panels(self):
        allcats = self.data.select_dtypes('category').columns.values
        catvalues = {cat:self.data[cat].unique() for cat in allcats}
        
        nb = wx.Notebook(self.panel)
        for cat in allcats:
            tabpanel = TablePanel(nb, cat, catvalues[cat])
            nb.AddPage(tabpanel, cat)        
        
        fsizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self.panel, wx.ID_ANY, "Category columns")
        fsizer.Add(label, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(nb, 1, wx.EXPAND, 5)

        return [fsizer]
        
    def _get_selected(self):
        #self.cfggrid.EnableEditing(False)
        params = super()._get_selected()
        #cfgdata = self.cfgtable.GetData()
        #params['input'] = {row['Dataset']:self.data_choices[row['Dataset']] for row in cfgdata if row['Select']}
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
class CategoryOrder(AbstractPlugin):
    
    def __init__(self, data, **kwargs):
        AbstractPlugin.__init__(self, data, **kwargs) #categories={}, default='unassigned')
        self.name = "Order Categories"
    
    #def __repr__(self):
    #    return f"{'name': {self.name}}"
    
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
            'categories': {},
            'inplace': False,
        })
        return params
            
    def run_configuration_dialog(self, parent, data_choices={}):
        categories = self.params['categories']
        inplace = self.params['inplace']
                
        dlg = CategoryOrderConfigDlg(parent, f'Order Category Values', 
            self.data, 
            categories=categories,
            inplace=inplace)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params    
        
    def execute(self):
        results = {}
        #input = self.params['input'] 
        #data = list(input.values())
        #concat_df = pd.concat(data, axis=0, copy=True)
        #results['Concatenated'] = concat_df
        return results
            
