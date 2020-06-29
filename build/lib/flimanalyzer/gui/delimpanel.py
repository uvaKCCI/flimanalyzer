# -*- coding: utf-8 -*-
"""
Created on Fri Jun  8 13:58:51 2018

@author: Karsten
"""

import wx

class DelimiterPanel(wx.Panel):
    
    def __init__(self, parent, delimiters=''):
        wx.Panel.__init__(self, parent)
        #delimiter_label = wx.StaticText(self, wx.ID_ANY, "Column Delimiters:")
        self.comma_box = wx.CheckBox(self, wx.ID_ANY, label="Comma")
        self.semicolon_box = wx.CheckBox(self, wx.ID_ANY, label="Semicolon")
        self.tab_box = wx.CheckBox(self, wx.ID_ANY, label="Tab")
        self.space_box = wx.CheckBox(self, wx.ID_ANY, label="Space")
        others_label = wx.StaticText(self, wx.ID_ANY, "Others:")
        self.others_field = wx.TextCtrl(self, wx.ID_ANY, value='')
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        #sizer.Add(delimiter_label, 0, wx.RIGHT, 5)
        sizer.Add(self.comma_box, 0, wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.semicolon_box, 0, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.tab_box, 0, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.space_box, 0, wx.LEFT|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(others_label, 0, wx.LEFT|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.others_field, 1, wx.EXPAND|wx.LEFT, 5)
        
        self.SetSizer(sizer)
        self.set_delimiters(delimiters)
        
    def set_delimiters(self, dels):
        if dels is None:
            dels = ""       
        self.comma_box.SetValue(',' in dels)
        self.semicolon_box.SetValue(';' in dels)
        self.tab_box.SetValue('\t' in dels)        
        self.space_box.SetValue(' ' in dels)
        dels = ''.join([d for d in dels if d not in ',;\t '])
        self.others_field.SetValue(dels)
    
    
    def get_delimiters(self):
        dels = self.others_field.GetValue() #.encode('ascii','ignore')
        if self.comma_box.IsChecked():
            dels += ','
        if self.semicolon_box.IsChecked():
            dels += ';'
        if self.tab_box.IsChecked():
            dels += '\t'       
        if self.space_box.IsChecked():
            dels += ' ' 
        return dels    