#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  8 14:05:04 2020

@author: khs3z
"""

import wx
import wx.lib.agw.customtreectrl as CT
from wx.lib.pubsub import pub
from gui.events import FILTERS_UPDATED


class SeriesFilterCtrl(CT.CustomTreeCtrl):
    
    def __init__(self, *args, **kwargs):
        CT.CustomTreeCtrl.__init__(self, *args, **kwargs)#, agwStyle=wx.TR_DEFAULT_STYLE)
        self.Bind(CT.EVT_TREE_ITEM_CHECKED, self.SeriesFilterChanged) 
        
        #custom_tree = CT.CustomTreeCtrl(self, agwStyle=wx.TR_DEFAULT_STYLE)
      
    def fire_rowsupdated_event(self, items):
        #event = ListCtrlUpdatedEvent(EVT_FU_TYPE, self.GetId())
        #event.SetUpdatedItems(items)
        #self.GetEventHandler().ProcessEvent(event)        
        pub.sendMessage(FILTERS_UPDATED, updateditems=items)        


    def setdata(self, data):
        self.data = data
        # Add a root node to it
        root = self.AddRoot("Categories", ct_type=1)

        # Create an image list to add icons next to an item
        il = wx.ImageList(16, 16)
        fldridx     = il.Add(wx.ArtProvider.GetBitmap(wx.ART_FOLDER,      wx.ART_OTHER, (16, 16)))
        fldropenidx = il.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE,   wx.ART_OTHER, (16, 16)))

        self.SetImageList(il)
        #self.seriesfilter.SetItemImage(root, fldridx, wx.TreeItemIcon_Normal)
        #self.seriesfilter.SetItemImage(root, fldropenidx, wx.TreeItemIcon_Expanded)
        
        if self.data is not None:
            cols = self.data.select_dtypes(['category']).columns.values
            for col in cols:
                child = self.AppendItem(root, col, ct_type=1)
                #self.seriesfilter.SetItemImage(child, fldridx, wx.TreeItemIcon_Normal)
                #self.seriesfilter.SetItemImage(child, fldropenidx, wx.TreeItemIcon_Expanded)
                values = self.data[col].unique()
                for val in sorted(values):
                    last = self.AppendItem(child, val, ct_type=1)
                    #self.seriesfilter.SetItemImage(last, fldridx, wx.TreeItemIcon_Normal)
                    #self.seriesfilter.SetItemImage(last, fldropenidx, wx.TreeItemIcon_Expanded)
            #self.seriesfilter.Expand(root)


    def GetCheckedItems(self, itemParent=None, checkedItems=None):
        if self.GetRootItem is None:
            return []
        if itemParent is None:
            itemParent = self.GetRootItem()
        if checkedItems is None:
            checkedItems = []

        child, cookie = self.GetFirstChild(itemParent)
        while child:
            if self.IsItemChecked(child):
                checkedItems.append(child)
            checkedItems = self.GetCheckedItems(child, checkedItems)
            child, cookie = self.GetNextChild(itemParent, cookie)

        return checkedItems


    def GetData(self):
        checked = {}
        checkeditems = self.GetCheckedItems()
        for item in checkeditems:
            if item.GetParent() != self.GetRootItem():
                l = checked.get(item.GetParent().GetText(),[])
                l.append(item.GetText())
                checked[item.GetParent().GetText()] = l
        return checked


    def SeriesFilterChanged(self, event):
        scol = event.GetItem().GetParent().GetText()
        svalue = event.GetItem().GetText()
        print svalue, event.GetItem().IsChecked(), "parent=",scol
        
        checked = self.GetData()
        print checked
        self.fire_rowsupdated_event({})

        

        



        