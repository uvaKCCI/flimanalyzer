#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 18 13:39:22 2018

@author: khs3z
"""

import wx

EVT_DU_TYPE = wx.NewEventType()
EVT_DATAUPDATED = wx.PyEventBinder(EVT_DU_TYPE, 1)

EVT_DATA_TYPE = wx.NewEventType()
EVT_DATA = wx.PyEventBinder(EVT_DATA_TYPE, 1)

EVT_PLOT_TYPE = wx.NewEventType()
EVT_PLOT = wx.PyEventBinder(EVT_PLOT_TYPE, 1)

REQUEST_CONFIG_UPDATE = 'configuration.requestuodate'
CONFIG_UPDATED = 'configuration.updated'

NEW_DATA_WINDOW = 'datawindow.new'
CLOSING_DATA_WINDOW = 'datawindow.closing'
REQUEST_RENAME_DATA_WINDOW = 'datawindow.requestrename'
RENAMED_DATA_WINDOW = 'datawindow.renamed'

NEW_PLOT_WINDOW = 'plotwindow.new'
CLOSING_PLOT_WINDOW = 'plotwindow.closing'

DATA_IMPORTED = 'data.imported'
DATA_UPDATED = 'data.updated'
FILTERED_DATA_UPDATED = 'filtereddata.updated'

ANALYSIS_BINS_UPDATED = 'analysis.bins.updated'
FILTERS_UPDATED = 'filters.updated'

class DataUpdatedEvent(wx.PyCommandEvent):
    def __init__(self, evtType, id):
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.data = None
        self.datatype = None


    def SetUpdatedData(self, data, dtype):
        self.data = data
        self.datatype = dtype

        
    def GetUpdatedData(self):
        return self.data, self.datatype
    

    
class DataWindowEvent(wx.PyCommandEvent):
    
    def __init_(self, evtType, id):
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.data = None
        self.title = None
        self.action = None
        self.showcolindex = None
        self.groups = None
        self.analyzable = None
        self.enableclose = None


    def SetEventInfo(self, data, title, action, showcolindex=True, groups=None, analyzable=True, savemodified=True, enableclose=True):
        self.data = data
        self.title = title
        self.action = action
        self.showcolindex = showcolindex
        self.groups = groups
        self.analyzable = analyzable
        self.savemodified = savemodified
        self.enableclose = enableclose
        
        
    def GetData(self):
        return self.data
    
    
    def GetTitle(self):
        return self.title
    
    
    def ShowColIndex(self):
        return self.showcolindex
    
    
    def GetGroups(self):
        return self.groups
    
    
    def IsAnalyzable(self):
        return self.analyzable
    
    
    def IsEnableClose(self):
        return self.enableclose
    
    
    def SaveModified(self):
        return self.savemodified
    
    
    def GetAction(self):
        return self.action
    
    
    
class PlotEvent(wx.PyCommandEvent):
    
    def __init_(self, evtType, id):
        wx.PyCommandEvent.__init__(self, evtType, id)
        self.figure = None
        self.title = None
        self.action = None


    def SetEventInfo(self, figure, title, action):
        self.figure = figure
        self.title = title
        self.action = action

        
    def GetFigure(self):
        return self.figure
   
    
    def GetTitle(self):
        return self.title
    
    
    def GetAction(self):
        return self.action
    
        
    
