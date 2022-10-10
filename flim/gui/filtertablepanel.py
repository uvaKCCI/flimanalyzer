#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 18 09:17:05 2018

@author: khs3z
"""

import logging
import wx
#from wx.grid import wxGridTableMessage

EVEN_ROW_COLOUR = '#CCE6FF'
GRID_LINE_COLOUR = '#ccc'


class FilterTable(wx.grid.GridTableBase):
    
    def __init__(self, data=None, sort=True, droppedrows=True):
        super(FilterTable, self).__init__()
        if droppedrows:
            self.headers = ['Use', 'Column', 'Min', 'Max', 'Dropped Rows']
        else:
            self.headers = ['Use', 'Column', 'Min', 'Max']
        self.names = []
        self.droppedrows = {}
        self.data = {}
        if data is not None:
            self.data = data
            if sort:
                self.names = sorted(data.keys())
            else:
                self.names = data.keys()
          
    def GetData(self):
        return self.data

    
    def GetDroppedRows(self, rowkey):
        return self.droppedrows.get(rowkey)


    def SetDroppedRows(self, drows):
        if drows is None:
            drows= {}
        self.droppedrows = drows
        #msg = wxGridTableMessage(self, wx.grid.wxGRIDTABLE_REQUEST_VIEW_GET_VALUES)
        #self.GetView().ProcessTableMessage(msg)

    def GetNumberRows(self):
        return len(self.data)


    def GetNumberCols(self):
        return len(self.headers)


    def GetValue(self, row, col):
#        print "GetValue", row, col
        header = self.names[row]
        rfilter = self.data[header]
        dropped = self.droppedrows.get(header)
        if col == 0:
            return rfilter.is_selected()
        elif col == 1:
            return self.names[row]
        elif col == 2:
            return rfilter.get_rangelow()
        elif col == 3:
            return rfilter.get_rangehigh()
        elif col == 4:
            if dropped is None:
                return "---"
            else:
                return len(dropped) 
        else:
            return "?"
    
    
    def GetValueAsBool(self, row, col):
#        print "GetValueAsBool",row, col
        if col == 0:
            rfilter = self.data[self.names[row]]
#            print "    ",rfilter.is_selected()
            return rfilter.is_selected()
        else:
            return False
          
            
    def SetValueAsBool(self, row, col, value):
#        print "SetValueAsBool",row, col, "value=",value
        if col == 0:
            rfilter = self.data[self.names[row]]
            rfilter.select(value)
    
    
#    def CanSetValueAs(self, row, col, wxGRID_VALUE_BOOL):
#        print "CanSetValueAsBool",row, col
#        return col == 0
    
        
    def CanGetValueAs(self, row, col, wxGRID_VALUE_BOOL):
#        print "CanGetValueAsBool",row, col
        return col == 0
    
        
        
    def SetValue(self, row, col, value):
        logging.debug (f"SetValue: row={row}, col={col}, value={value}")
        rfilter = self.data[self.names[row]]
        if col == 0:
            rfilter.select(value)
        elif col == 1:
            self.names[row] = self.names[row]
        elif col == 2:
            rfilter.set_rangelow(value)
        elif col == 3:
            rfilter.set_rangehigh(value)
        return
    

    def GetDict(self):
        datadict = {}
        for row in self.data:
            datadict[row[0]] = row[1]
        return datadict
    
        
    def GetColLabelValue(self, col):
        if self.headers is None or len(self.headers) < col:
            return ""
        else:
            return self.headers[col]


    def GetTypeName(self, row, col):
        if col == 0:
            return wx.grid.GRID_VALUE_BOOL
        elif col == 1 or col == 4:
            return wx.grid.GRID_VALUE_STRING
        elif col == 2 or col == 3:
            return wx.grid.GRID_VALUE_FLOAT            


    def GetAttr(self, row, col, prop):
        attr = super(FilterTable, self).GetAttr(row, col, prop)
        if attr is None:
            attr = wx.grid.GridCellAttr()
        if col in [1,4]:
            attr.SetReadOnly(True)
        if col > 1:
            attr.SetAlignment(wx.ALIGN_RIGHT,wx.ALIGN_CENTRE)
#        if col == 0:
#            attr.SetEditor(wx.grid.GridCellBoolEditor())
#            attr.SetRenderer(wx.grid.GridCellBoolRenderer())
        return attr
    