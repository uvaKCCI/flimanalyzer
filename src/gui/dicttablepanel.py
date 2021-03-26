#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May  8 18:20:41 2018

@author: khs3z
"""

import wx

EVEN_ROW_COLOUR = '#CCE6FF'
GRID_LINE_COLOUR = '#ccc'


class ListTable(wx.grid.GridTableBase):
    def __init__(self, data=None, headers=None, sort=False, *args, **kwargs):
        super(ListTable, self).__init__(*args, **kwargs)
        self.SetData(data, headers, sort)
            

    def SetData(self, data=None, headers=None, sort=False):
        if headers == None or len(headers) < 2:
            self.headerRows = 0
        else:
            if sort:
                self.headers = sorted(headers)
            else:
                self.headers = headers
        if data is not None and len(data)>0:
            self.data = ['?'] * len(data)
            #i=0
            #for k in keys:
            #    self.data[i] = [k,data[k]]
            #    i+=1
            self.data = [[row[h] for h in self.headers] for row in data]
        else:
            self.data = []

        
    def GetNumberRows(self):
        return len(self.data)


    def GetNumberCols(self):
        return len(self.headers)


    def GetValue(self, row, col):
        return self.data[row][col]


    def SetValue(self, row, col, value):
        self.data[row][col] = value


    def GetData(self):
        data = [{h:col for h,col in zip(self.headers,row)} for row in self.data]
        #for row in self.data:
        #    datadict[row[0]] = row[1]
        return data
    
    
    def GetValueAsBool(self, row, col):
#        print "GetValueAsBool",row, col
        if col==0:
            return self.data[row][col]
        else:
            return False
       
        
    def SetValueAsBool(self, row, col, value):
#        print "SetValueAsBool",row, col, "value=",value
        if col==0:
            self.data[row][col] = value


    def CanGetValueAs(self, row, col, valuetype):
        return (col==0 and valuetype == wx.grid.GRID_VALUE_BOOL) or col!= 0
    
    """
    def CanSetValueAs(self, row, col, valuetype):
        print ("CanSetValueAs",col,valuetype)
        return (col==0 and valuetype == wx.grid.GRID_VALUE_BOOL) or col!= 0
    """
    
    def GetColLabelValue(self, col):
        if self.headers is None or len(self.headers) < col:
            return ""
        else:
            return self.headers[col]


    def GetTypeName(self, row, col):
        if col == 0:
            return wx.grid.GRID_VALUE_BOOL
        return wx.grid.GRID_VALUE_STRING



class DictTable(wx.grid.GridTableBase):
    def __init__(self, data=None, headers=None, sort=True):
        super(DictTable, self).__init__()
        self.SetData(data, headers, sort)
            

    def SetData(self, data=None, headers=None, sort=True):
        if headers == None or len(headers) < 2:
            self.headerRows = 0
        else:
            self.headers = headers[:2]
        if data is not None:
            self.data = ['?'] * len(data)
            if sort:
                keys = sorted(data.keys())
            else:
                keys = data.keys()
            #i=0
            #for k in keys:
            #    self.data[i] = [k,data[k]]
            #    i+=1
            self.data = [[k, data[k]] for k in keys]

        
    def GetNumberRows(self):
        return len(self.data)


    def GetNumberCols(self):
        return 2


    def GetValue(self, row, col):
        return self.data[row][col]


    def SetValue(self, row, col, value):
        self.data[row][col] = value


    def GetDict(self):
        datadict = {row[0]:row[1] for row in self.data}
        #for row in self.data:
        #    datadict[row[0]] = row[1]
        return datadict
    
        
    def GetColLabelValue(self, col):
        if self.headers is None or len(self.headers) < col:
            return ""
        else:
            return self.headers[col]


    def GetTypeName(self, row, col):
        return wx.grid.GRID_VALUE_STRING


#    def GetAttr(self, row, col, prop):
#        attr = wx.grid.GridCellAttr()
#        if row % 2 == 1:
#            attr.SetBackgroundColour(EVEN_ROW_COLOUR)
#        return attr
    

class DictFrame(wx.Frame):
    """
    Frame that holds all other widgets
    """

    def __init__(self, parent, title, data=None, headers=None):
        """Constructor"""
        super(DictFrame, self).__init__(parent, wx.ID_ANY, title)
        if data is None:
            data = {}
        self.data = data
        self.headers = headers
        self._init_gui()
        self.Layout()
        #self.Show()

    def _init_gui(self):
        table = DictTable(self.data, self.headers,sort=True)

        grid = wx.grid.Grid(self, -1)
        grid.SetTable(table, takeOwnership=True)
        grid.EnableEditing(False)
        grid.AutoSizeColumns()
        grid.EnableDragColSize(True)
        grid.SetRowLabelSize(0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(grid, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.exit)

    def exit(self, event):
        self.Destroy()