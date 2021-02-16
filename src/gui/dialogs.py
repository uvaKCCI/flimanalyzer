#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 12 13:35:51 2018

@author: khs3z
"""

import logging
import wx
from wx.lib.masked import NumCtrl

def check_data_msg(data):
    ok = data is not None and len(data) > 0
    if not ok:    
        wx.MessageBox('No data loaded. Import data first.', 'Warning', wx.OK)
    return ok


def fix_filename(fname):
    if fname is None:
        return None
    else:
        fname = fname.replace(' ','')
        fname = fname.replace(',','_')
        fname = fname.replace(':','-')
        fname = fname.replace('\\','_')
        fname = fname.replace('/','_')
        fname = fname.replace('[','')
        fname = fname.replace(']','')
        fname = fname.replace('(','')
        fname = fname.replace(')','')
        fname = fname.replace('%','perc')
        fname = fname.replace('--','-')
        return fname
    
        
def save_dataframe(parent, title, data, filename, wildcard="txt files (*.txt)|*.txt", saveindex=True):
    with wx.FileDialog(parent, title, wildcard=wildcard, style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as fileDialog:    
        fileDialog.SetFilename(fix_filename(filename))
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return None
        fname = fileDialog.GetPath()                
        try:
            data.reset_index()
            # if indx was flattened in analyzer.summarize_data, multiindex col values were joined with '\n'--> revert here 
            data.columns = [c.replace('\n', ' ') for c in data.columns.values]
            data.to_csv(fname, index=saveindex, sep='\t')
        except IOError:
            wx.MessageBox('Error saving data in file %s' % fname, 'Error', wx.OK)
            return None
        return fname    
            
        

def save_figure(parent, title, fig, filename, wildcard="all files (*.*)|*.*", dpi=300, legend=None):
    with wx.FileDialog(parent, title, wildcard=wildcard, style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as fileDialog:    
        fileDialog.SetFilename(fix_filename(filename))
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return None
        fname = fileDialog.GetPath()                
        try:
            if legend is not None:
                fig.savefig(fname, dpi=dpi, bbox_extra_artists=(legend,), bbox_inches='tight')            
            else:                
                fig.savefig(fname, dpi=dpi, bbox_inches='tight')            
        except IOError:
            error = 'Error saving figure in file %s' % fname
            logging.error(error)
            wx.MessageBox(error, 'Error', wx.OK)
            return None
        return fname    
            

class SelectGroupsDlg(wx.Dialog):

    def __init__(self, parent, title, groups=[], selected='All'):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title)
        # 5 col gridsizer
        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        cbsizer = wx.GridSizer(5, 0, 0)
        if groups is None:
            groups = []
        self.cboxes = {}
        for g in groups:
            cb = wx.CheckBox(self,wx.ID_ANY,g)
            cb.SetValue((g in selected) or (selected == 'All'))
            self.cboxes[g] = cb
            cbsizer.Add(cb, 0, wx.ALL, 5)
        selectbsizer = wx.BoxSizer(wx.VERTICAL)
        self.selectAllButton = wx.Button(self, label="Select All")
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.OnSelectAll)
        selectbsizer.Add(self.selectAllButton, 0, wx.ALL|wx.EXPAND, 5)
        self.deselectAllButton = wx.Button(self, label="Deselect All")
        self.deselectAllButton.Bind(wx.EVT_BUTTON, self.OnDeselectAll)
        selectbsizer.Add(self.deselectAllButton, 0, wx.ALL|wx.EXPAND, 5)
        
        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK", pos=(110,160))
        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        buttonsizer.Add(self.okButton, 0, wx.ALL, 10)
        self.cancelButton = wx.Button(self, label="Cancel", pos=(210,160))
        self.cancelButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        buttonsizer.Add(self.cancelButton, 0, wx.ALL, 10)
        
        mainsizer.Add(cbsizer, 0, wx.ALIGN_CENTER, 5)
        mainsizer.Add(wx.StaticLine(self,style=wx.LI_VERTICAL), 0, wx.ALL|wx.EXPAND, 5)
        mainsizer.Add(selectbsizer, 0, wx.ALIGN_CENTER, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(mainsizer, 0, wx.ALIGN_CENTER, 5)
        sizer.Add(buttonsizer, 0, wx.ALIGN_CENTER, 5)
        self.SetSizer(sizer)
        
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        self.SetLayoutAdaptationMode(wx.DIALOG_ADAPTATION_MODE_ENABLED)
        self.DoLayoutAdaptation()
        self.Show()

        
    def OnSelectAll(self, event):
        for key in self.cboxes:
            self.cboxes[key].SetValue(True)


    def OnDeselectAll(self, event):
        for key in self.cboxes:
            self.cboxes[key].SetValue(False)


    def OnQuit(self, event):
        self.EndModal(wx.ID_CANCEL)


    def _get_selected(self):
        return [key for key in self.cboxes if self.cboxes[key].GetValue()]
    
    
    def get_selected(self):
        return self._get_selected()
        
        
    def OnOK(self, event):
        if len(self._get_selected()) == 0:
            wx.MessageDialog(self,'Select at least one function.')
        else:    
            self.EndModal(wx.ID_OK)



class ConfigureCategoriesDlg(wx.Dialog):

    def __init__(self, parent, title='', bins=[], labels=[]):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, "Category Configuration: %s" % title, size= (650,220))
#        self.bins = None
#        self.labels = None
        self.panel = wx.Panel(self,wx.ID_ANY)

        self.bin = wx.StaticText(self.panel, label="Category bins", pos=(20,20))
        self.bin_field = wx.TextCtrl(self.panel, value=','.join([str(b) for b in bins]), pos=(110,20), size=(500,-1))
        self.label = wx.StaticText(self.panel, label="Category labels", pos=(20,60))
        self.label_field = wx.TextCtrl(self.panel, value=','.join(labels), pos=(110,60), size=(500,-1))
        self.okButton = wx.Button(self.panel, label="OK", pos=(110,160))
        self.okButton.Bind(wx.EVT_BUTTON, self.OnSave)
        self.cancelButton = wx.Button(self.panel, label="Cancel", pos=(210,160))
        self.cancelButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        self.Show()

    def OnQuit(self, event):
        self.bins = None
        self.labels = None
        self.EndModal(wx.ID_CANCEL)

    def get_config(self):
        if  self.bins:
            return self.bins,self.labels
        else:  
            return None
    
    def OnSave(self, event):
        self.bins = [float(f) for f in self.bin_field.GetValue().split(',')]
        # self.labels = self.label_field.GetValue().encode('ascii','ignore').split(',')
        self.labels = self.label_field.GetValue().split(',')
        self.EndModal(wx.ID_OK)
        
        
class ConfigureAxisDlg(wx.Dialog):
    def __init__(self, parent, title, settings):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title, size= (650,220))
        self.panel = wx.Panel(self,wx.ID_ANY)

        self.labelname = wx.StaticText(self.panel, label="Axis label", pos=(20,20))
        self.labelinput = wx.TextCtrl(self.panel, value=settings['label'], pos=(110,20), size=(500,-1))
        self.minname = wx.StaticText(self.panel, label="Min value", pos=(20,60))
        self.mininput = NumCtrl(self.panel, value=settings['min'], fractionWidth=2, pos=(110,60))
        self.maxlabel = wx.StaticText(self.panel, label="Max value", pos=(20,100))
        self.maxinput = NumCtrl(self.panel, value=settings['max'], fractionWidth=2, pos=(110,100))
        self.okButton = wx.Button(self.panel, label="OK", pos=(110,160))
        self.closeButton =wx.Button(self.panel, label="Cancel", pos=(210,160))
        self.okButton.Bind(wx.EVT_BUTTON, self.SaveConnString)
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        
        self.settings = dict(settings)
        self.Show()

    def OnQuit(self, event):
        self.settings = None
        self.EndModal(wx.ID_CANCEL)

    def get_settings(self):
	    return self.settings
		
    def SaveConnString(self, event):
        self.settings['label'] = self.labelinput.GetValue()
        self.settings['min'] = self.mininput.GetValue()
        self.settings['max'] = self.maxinput.GetValue()
        self.EndModal(wx.ID_OK)
