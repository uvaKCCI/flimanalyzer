#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  7 21:00:30 2018

@author: khs3z
"""

import matplotlib
#matplotlib.use('WXAgg')
import matplotlib.pyplot as plt

import logging
import os
import numpy as np
import itertools
import pandas as pd
import json

import wx
import wx.lib.agw.customtreectrl as CT
from pubsub import pub

import flim.analysis
import flim.core.configuration as cfg
from flim.core.configuration import Config
import flim.core.parser
import flim.core.plots
import flim.core.preprocessor
import flim.gui.dialogs
from flim.gui.importdlg import ImportDlg
from flim.core.preprocessor import defaultpreprocessor
from flim.core.importer import dataimporter
from flim.core.filter import RangeFilter

from flim.gui.delimpanel import DelimiterPanel
from flim.gui.datapanel import PandasFrame
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.listcontrol import AnalysisListCtrl, FilterListCtrl, EVT_FILTERUPDATED, EVT_ANALYSISUPDATED
from flim.gui.seriesfiltertree import SeriesFilterCtrl


from flim.gui.dialogs import ConfigureCategoriesDlg
from flim.gui.events import DataUpdatedEvent, EVT_DATAUPDATED, EVT_DU_TYPE, DataWindowEvent, EVT_DATA, EVT_DATA_TYPE, PlotEvent, EVT_PLOT, EVT_PLOT_TYPE 
from flim.gui.events import REQUEST_CONFIG_UPDATE, CONFIG_UPDATED
from flim.gui.events import FOCUSED_DATA_WINDOW, NEW_DATA_WINDOW, CLOSING_DATA_WINDOW, REQUEST_RENAME_DATA_WINDOW, RENAMED_DATA_WINDOW, NEW_PLOT_WINDOW, DATA_IMPORTED, FILTERS_UPDATED, FILTERED_DATA_UPDATED, DATA_UPDATED, ANALYSIS_BINS_UPDATED
from flim.gui.dialogs import SelectGroupsDlg, ConfigureAxisDlg

from wx.lib.newevent import NewEvent

ImportEvent, EVT_IMPORT = NewEvent()
ApplyFilterEvent, EVT_APPLYFILTER = NewEvent()
DataUpdateEvent, EVT_UPDATEDATA = NewEvent()

DEFAULT_COMFIFG_FILE = 'defaults.json'

class FlimAnalyzerApp(wx.App):
    
    def __init__(self, flimanalyzer, config=None):
        self.flimanalyzer = flimanalyzer
        if config is None or not isinstance(config, Config):
            self.config = Config()
            self.config.read_from_json(DEFAULT_COMFIFG_FILE, defaultonfail=True)
        else:
            self.config = config
        super(FlimAnalyzerApp,self).__init__()

        
    def OnInit(self):
        self.frame = AppFrame(self.flimanalyzer, self.config)
        self.frame.Show(True)
        return True


class TabAnalysis(wx.Panel):
    
    def __init__(self, parent, pwindow, flimanalyzer, config, use_all_raw_and_filtered=False):
        self.flimanalyzer = flimanalyzer
        self.use_all_raw_and_filtered = use_all_raw_and_filtered
        self.pwindow = pwindow
        self.config = config
        wx.Panel.__init__(self, parent)
        self.rawdata = None
        self.data = None
        self.sel_roigrouping = []
        self.roigroupings = ['None']
        self.pivot_level = 2
        self.category_colheader = 'Category'
        self.availabledata = {}
        self.windows = {}

        self.rawdatainfo = wx.StaticText(self, -1, "No raw data", (20,20))
        self.datainfo = wx.StaticText(self, -1, "No filtered data", (20,20))

        self.roigroup_combo = wx.ComboBox(self, -1, value=self.roigroupings[0], choices=self.roigroupings, style=wx.CB_READONLY, size=(400, -1)) #pos=(50, 170), size=(150, -1), 
        self.roigroup_combo.Bind(wx.EVT_COMBOBOX, self.OnRoiGroupingChanged)

        self.analysistype_combo = wx.ComboBox(self, -1, value=self.get_analysistypes()[0], choices=self.get_analysistypes(), style=wx.CB_READONLY) # pos=(50, 170), size=(150, -1),
        self.analysistype_combo.Bind(wx.EVT_COMBOBOX, self.OnAnalysisTypeChanged)

        self.datachoices_combo = wx.ComboBox(self, -1, choices=self.get_datachoices(), style=wx.CB_READONLY, size=(400, -1)) #,value=self.get_datachoices()[0], pos=(50, 170),  
        self.datachoices_combo.Bind(wx.EVT_COMBOBOX, self.OnDataChoiceChanged)

        self.ctrlgroup_label = wx.StaticText(self, -1, "Reference:")
        self.ctrlgroup_combo = wx.ComboBox(self, -1, value='', style=wx.CB_READONLY) #choices=self.get_ctrlgroupchoices(), pos=(50, 170), size=(150, -1), 
        self.ctrlgroup_combo.Bind(wx.EVT_COMBOBOX, self.OnCtrlSelChanged)

        self.selectall_button = wx.Button(self, wx.ID_ANY, "Select All")
        self.selectall_button.Bind(wx.EVT_BUTTON, self.SelectAll)
    
        self.deselectall_button = wx.Button(self, wx.ID_ANY, "Deselect All")
        self.deselectall_button.Bind(wx.EVT_BUTTON, self.DeselectAll)
    
        self.show_button = wx.Button(self, wx.ID_ANY, "Run Analysis")
        self.show_button.Bind(wx.EVT_BUTTON, self.run_analysis)
    
        #self.save_button = wx.Button(self, wx.ID_ANY, "Save Analysis")
        #self.save_button.Bind(wx.EVT_BUTTON, self.SaveAnalysis)
    
        #self.update_datachoices({'Raw data':self.rawdata, 'Filtered data':self.data}, True)
        self.set_roigroupings(None)
        self.init_analysislist()
        
        optionsizer = wx.FlexGridSizer(4,2,1,1)
        optionsizer.Add(wx.StaticText(self, -1, "Data"), 2, wx.EXPAND|wx.TOP|wx.LEFT|wx.RIGHT, 5)
        optionsizer.Add(wx.StaticText(self, -1, "Analysis Type"), 1, wx.EXPAND|wx.TOP|wx.LEFT|wx.RIGHT, 5)
        optionsizer.Add(self.datachoices_combo, 2, wx.EXPAND|wx.ALL, 5)        
        optionsizer.Add(self.analysistype_combo, 1, wx.EXPAND|wx.ALL, 5)        
        optionsizer.Add(wx.StaticText(self, -1, "ROI Grouping"), 2, wx.EXPAND|wx.TOP|wx.LEFT|wx.RIGHT, 5)
        optionsizer.Add(self.ctrlgroup_label, 1, wx.EXPAND|wx.TOP|wx.LEFT|wx.RIGHT, 5)
        optionsizer.Add(self.roigroup_combo, 2, wx.EXPAND|wx.ALL, 5)        
        optionsizer.Add(self.ctrlgroup_combo, 1, wx.EXPAND|wx.ALL, 5)        
        
        buttonsizer = wx.BoxSizer(wx.VERTICAL)
        buttonsizer.Add(self.selectall_button, 0, wx.EXPAND|wx.ALL, 5)
        buttonsizer.Add(self.deselectall_button, 0, wx.EXPAND|wx.ALL, 5)
        buttonsizer.Add(self.show_button, 0, wx.EXPAND|wx.ALL, 5)
        #buttonsizer.Add(self.save_button, 0, wx.EXPAND|wx.ALL, 5)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.analysislist, 1, wx.EXPAND|wx.ALL, 5)
        hsizer.Add(buttonsizer, 0, wx.ALL, 5)
        
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(self.rawdatainfo, 0, wx.ALL, 5)
        mainsizer.Add(self.datainfo, 0, wx.ALL, 5)
        mainsizer.Add(optionsizer,0, wx.EXPAND|wx.ALL, 5)        
        mainsizer.Add(hsizer, 1, wx.EXPAND|wx.ALL, 5) 
        
        self.SetSizer(mainsizer)
                
        #boxsizer.SetSizeHints(self)
        #self.SetSizerAndFit(boxsizer)
        
        pub.subscribe(self.OnNewDataWindow, NEW_DATA_WINDOW)
        pub.subscribe(self.OnClosingDataWindow, CLOSING_DATA_WINDOW)
        pub.subscribe(self.OnDataWindowRenamed, RENAMED_DATA_WINDOW)
        pub.subscribe(self.OnDataImported, DATA_IMPORTED)
        pub.subscribe(self.OnFiltersUpdated, FILTERS_UPDATED)
        pub.subscribe(self.OnFilteredDataUpdated, FILTERED_DATA_UPDATED)
        pub.subscribe(self.OnConfigUpdated, CONFIG_UPDATED)

        
    def get_analysis_settings(self):
        return {cfg.CONFIG_ANALYSIS:{
                cfg.CONFIG_HISTOGRAMS:{},
                cfg.CONFIG_CATEGORIES:{},
                cfg.CONFIG_SCATTER:{}}}    


    def init_analysislist(self):
        self.analysislist = AnalysisListCtrl(self, style=wx.LC_REPORT)
        self.analysislist.InsertColumn(0, "Analyze")
        self.analysislist.InsertColumn(1, "Column")
        self.analysislist.InsertColumn(2, "Min",  wx.LIST_FORMAT_RIGHT)
        self.analysislist.InsertColumn(3, "Max",  wx.LIST_FORMAT_RIGHT)
        self.analysislist.InsertColumn(4, "Bins",  wx.LIST_FORMAT_RIGHT)
        self.analysislist.SetEditable([False, False, False, False, True])
        self.analysislist.Arrange()
        self.update_analysislist()
        
                    
    def OnNewDataWindow(self, data, frame):
        label = frame.GetLabel()
        logging.debug (f"{label}")
        if frame.is_analyzable():
            self.update_datachoices({label:frame}, True)
            self.windows[label] = frame
            self.update_analysislist()
            currentdata,label = self.get_currentdata()
            self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
            logging.debug ("CURRENT DATA: {label}, {self.datachoices_combo.GetStringSelection()}")
        if label == "Raw data":
            if self.rawdata is not None:
                label += " %d rows, %d columns" % (self.rawdata.shape[0], self.rawdata.shape[1])
            self.rawdatainfo.SetLabel(label)
        elif label == "Filtered data":    
            if self.rawdata is not None:
                label += " %d rows, %d columns" % (self.data.shape[0], self.data.shape[1])
            self.datainfo.SetLabel(label)


    def OnClosingDataWindow(self, data, frame):
        logging.debug (f"{frame.GetLabel()}")
        if self.windows.get(frame.GetLabel()):
            del self.windows[frame.GetLabel()]
            self.update_datachoices({frame.GetLabel():frame}, False)
            currentdata,_ = self.get_currentdata()
            self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
            self.update_analysislist()

        
    def OnDataImported(self, olddata, data):
        logging.debug (f"{len(data)} rows, {len(data.columns.values)} columns")
        self.update_rawdata(data)


    def OnFiltersUpdated(self, updateditems):
        logging.debug (f"{len(updateditems)} updated items.")
        self.update_rangefilters(updateditems)


    def OnFilteredDataUpdated(self, originaldata, newdata):
        logging.debug ("appframe.TabAnalysis.OnFilteredDataUpdated")
        self.update_data(newdata)

        
    def OnConfigUpdated(self, source, config, updated):
        logging.debug ("appframe.TabAnalysis.OnConfigUpdated")
        if source != self and updated:
            for key in updated:
                logging.debug (f"\tupdated key:{key}")
            self.config = config    
            self.update_analysislist()

        
    def OnRoiGroupingChanged(self, event):
        groupstr = self.roigroup_combo.GetStringSelection()
        logging.debug (f"GROUPSTR={groupstr}")
        if groupstr == 'None':
            self.sel_roigrouping = []
            self.ctrlgroup_label.SetLabelText('Reference: None')
        else:    
            self.sel_roigrouping = groupstr.split(', ')
            self.ctrlgroup_label.SetLabelText('Reference: %s' % self.sel_roigrouping[0])
        logging.debug (self.sel_roigrouping)
        self.update_sel_ctrlgroup()

        
    def OnAnalysisTypeChanged(self, event):
        groupindex = event.GetSelection()
        logging.debug (f"{self.get_analysistypes()[groupindex]}")

    
    def OnDataWindowRenamed(self, original, new, data):
        logging.debug (f"{original} --> {new}")
        if original in self.windows:
            frame = self.windows[original]
            if frame.is_analyzable():
                renameselected = self.datachoices_combo.GetStringSelection() == original
                self.update_datachoices({original:frame}, add=False)
                self.update_datachoices({new:frame}, add=True)
                del self.windows[original]
                self.windows[new] = frame
                if renameselected:
                    self.datachoices_combo.SetStringSelection(new)


            
    def OnDataChoiceChanged(self, event):
        datalabel = event.GetString()
        currentdata, _ = self.get_currentdata()
        logging.debug (f"{datalabel}, {str(currentdata is not None)}")
        self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
        self.update_analysislist()
        if self.windows.get(datalabel):
            self.windows[datalabel].Raise()

                
    def OnCtrlSelChanged(self, event):
        groupindex = event.GetSelection()
        logging.debug (f"{self.get_ctrlgroupchoices()[groupindex]}")

                
    def run_analysis(self, event):
        # check that there's any data to process
        currentdata,label = self.get_currentdata()
        if not flim.gui.dialogs.check_data_msg(currentdata):
            return
        
        # check that user provided required data categories and data features
        categories = self.sel_roigrouping
        features = [c for c in self.get_checked_cols(currentdata)]
        
        atype = self.analysistype_combo.GetStringSelection()  
        logging.debug (f"{atype}")
        analysis_class = flim.analysis.absanalyzer.get_analyzer_classes()[atype]
        tool = flim.analysis.absanalyzer.create_instance(analysis_class, currentdata)

        # run optional tool config dialog and execte analysis
        parameters = tool.run_configuration_dialog(self)
        logging.debug(parameters)
        if parameters is None:
            return
        features = parameters['features']
        categories = parameters['grouping']     

        req_features = tool.get_required_features()
        not_any_features = [f for f in req_features if f != 'any']
        if features is None or len(features) < len(req_features) or not all(f in features for f in not_any_features):
            wx.MessageBox(f'Analysis tool {tool} requires selection of at least {len(req_features)} data features, including {not_any_features}.', 'Warning', wx.OK)            
            return

        req_categories = tool.get_required_categories()
        not_any_categories = [c for c in req_categories if c != 'any']
        if len(req_categories) > 0 and (categories is None or len(categories) < len(req_categories) or not all(c in categories for c in not_any_categories)):
            wx.MessageBox(f'Analysis tool {tool} requires selection of at least {len(req_categories)} groups, including {not_any_categories}.', 'Warning', wx.OK)            
            return
        
        results = tool.execute()
        
        # handle results, DataFrames or Figure objects
        if results is not None:
            for title, result in results.items():
                if isinstance(result, pd.DataFrame):
                    #cols = df.select_dtypes(['category']).columns.tolist()
                    #print (f"Categories:{cols}")
                    result = result.reset_index()
                    #print (df.columns.tolist())
                    #df = df.set_index(cols)
                    windowtitle = "%s: %s" % (title, label)
                    event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
                    event.SetEventInfo(result, 
                                       windowtitle, 
                                       'createnew', 
                                       showcolindex=False)
                    self.GetEventHandler().ProcessEvent(event)
                elif isinstance(result, tuple):
                    fig,ax = result
                    #title = "Bar plot: %s  %s" % (ax.get_title(), label)
                    fig.canvas.set_window_title(title)
                    event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
                    event.SetEventInfo(fig, title, 'createnew')
                    self.GetEventHandler().ProcessEvent(event)        

 
    def SaveAnalysis(self, event):
        atype = self.analysistype_combo.GetStringSelection()
        logging.debug (f"{atype}")
        if atype == 'Summary Tables':
            self.save_summary()
        elif atype == 'Mean Bar Plots':
            if len(self.sel_roigrouping) < 10:
                self.save_meanplots()
        elif atype == 'Box Plots':
            if len(self.sel_roigrouping) < 10:
                self.save_boxplots()
        elif atype == 'KDE Plots':
            if len(self.sel_roigrouping) < 10:
                self.save_kdeplots()
        elif atype == 'Frequency Histograms':
            if len(self.sel_roigrouping) < 10:
                self.save_freqhisto()
        elif atype == 'Scatter Plots':
            if len(self.sel_roigrouping) < 10:
                self.save_scatterplots()
        elif atype == 'Categorize':
            self.save_categorized_data()
        elif atype == 'Principal Component Analysis':
            self.save_pca_data()

     
    def SelectAll(self, event):
        self.analysislist.Freeze()
        for idx in range(self.analysislist.GetItemCount()):
            self.analysislist.CheckItem(idx, True)
        self.analysislist.Thaw()

        
    def DeselectAll(self, event):
        self.analysislist.Freeze()
        for idx in range(self.analysislist.GetItemCount()):
            self.analysislist.CheckItem(idx, False)
        self.analysislist.Thaw()


    def get_currentdata(self):
        selection = self.datachoices_combo.GetStringSelection() 
        if not self.use_all_raw_and_filtered:
            if isinstance(self.availabledata.get(selection), PandasFrame):
                logging.debug (f"Using GetViewData, selection={selection}")
                return self.availabledata[selection].GetViewData(), selection
            logging.debug (f"Could not find {selection} in existing windows")
            logging.debug (self.availabledata)
    
        if selection == 'Raw data':
            if self.rawdata is not None:
                logging.debug (f"Using selection={selection}")                
                return self.rawdata, 'Raw'
        elif selection == 'Filtered data':
            if self.data is not None:
                logging.debug (f"Using selection={selection}")
                return self.data, 'Filtered'
        return None, selection


    def update_rangefilters(self, rfilters):
        #logging.debug (f"{len(rfilters)} filters to update")
        #analysisconfig = self.config.get(cfg.CONFIG_RANGEFILTERS)
        #for key in rfilters:
        #    rfilter = rfilters[key]
        #    logging.debug (f"\trfilter.get_params: {rfilter.get_params()}")
        #    low = rfilter.get_rangelow()
        #    high = rfilter.get_rangehigh()
        #    aconfig = analysisconfig.get(rfilter.get_name())
        #    if aconfig is None:
        #        logging.debug (f"\tnot found: {rfilter.get_name()}")
        #        analysisconfig[rfilter.get_name()] = [low,high,100]
        #    else:                
        #        logging.debug (f"\told: {rfilter.get_name()}, {analysisconfig[rfilter.get_name()]}")
        #        analysisconfig[rfilter.get_name()][0] = low
        #        analysisconfig[rfilter.get_name()][1] = high
        #    logging.debug (f"\tnew: {rfilter.get_name()}, {analysisconfig[rfilter.get_name()]}")
        #    self.analysislist.SetRow(rfilter.get_name(), analysisconfig[rfilter.get_name()])
        pass


    def update_analysislist(self):
        logging.debug ("TabAnalysis.update_analysislist")
        data, label = self.get_currentdata()
        if data is None:
            return
        datacols =  data.select_dtypes(include=[np.number])
        """
        analysisconfig = self.config.get(cfg.CONFIG_HISTOGRAMS)
        if label in ['Raw', 'Filtered']:
            config = analysisconfig
        else:
            config = {}
        for header in datacols.columns.values.tolist():
            if isinstance(header, tuple):
                header = ', '.join(header)
            hconfig = config.get(header)
            if hconfig is None:
                # try to match with existing analysis config
                use_existing = False
                for existingheader in analysisconfig:
                    if existingheader in header and not 'count' in header.lower():
                        config[header] = analysisconfig[existingheader]
                        use_existing = True
                        break
                if not use_existing:    
                    config[header] = [0,1,100]
        self.analysislist.SetData(config, ['Analyze', 'Column', 'Min', 'Max', 'Bins'])        
        """

        
    def update_rawdata(self, rawdata):
        logging.debug ("appframe.TabAnalysis.update_rawdata")
        logging.debug (f"\trawdata: rows={rawdata.shape[0]}, cols={rawdata.shape[1]}")
        self.rawdata = rawdata
        #frame = PandasFrame(self, 'Raw data', data=self.rawdata)
        # *** self.update_datachoices({'Raw data':self.rawdata}, replace=False)
        label = "Raw Data:"
        if self.rawdata is not None:
            label += " %d rows, %d columns" % (self.rawdata.shape[0], self.rawdata.shape[1])
        self.rawdatainfo.SetLabel(label)
        self.update_analysislist()
        # self.update_data(None)
        currentdata,label = self.get_currentdata()
        logging.debug (f"CURRENT DATA: {label}, {self.datachoices_combo.GetStringSelection()}")
        if currentdata is not None:
            self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))



    def update_data(self, data):
        logging.debug ("appframe.TabAnalysis.update_data")
#        print "\traw data: rows=%d, cols=%d" % (self.rawdata.shape[0], self.rawdata.shape[1])
        self.data = data
        #frame = PandasFrame(self, 'Filtered data', data=self.data)
        label = "Filtered Data:"
        # *** self.update_datachoices({'Filtered data':self.data}, add=(self.data is not None))
        if self.data is not None:
            logging.debug (f"\tdata: rows={self.data.shape[0]}, cols={self.data.shape[1]}")
            label += " %d rows, %d columns" % (self.data.shape[0], self.data.shape[1])
#            label += " %d rows, %d columns" % (self.rawdata.shape[0] - self.filterlist.get_total_dropped_rows(), self.data.shape[1])
        else:
            logging.debug ("\tNo data.")
        self.datainfo.SetLabel(label)    


    def get_analysistypes(self):
        return self.flimanalyzer.get_analyzer().get_analysis_options()
    

    def update_datachoices(self, choices={}, add=True, replace=False):
        if choices is None:
            return
        if add:
            if replace:
                self.availabledata = {}
            self.availabledata.update(choices)
        else:
            for title in choices:
                if self.availabledata is not None and self.availabledata.get(title) is not None:
                    del self.availabledata[title]
        logging.debug (f"appframe.TabAnalysis.update_datachoices, {[t for t in self.availabledata]}")
        current_sel = self.datachoices_combo.GetStringSelection()
        self.datachoices_combo.Clear()
        self.datachoices_combo.AppendItems(self.get_datachoices())
        if current_sel != '' and current_sel in self.get_datachoices():
            self.datachoices_combo.SetStringSelection(current_sel)
        else:
            self.datachoices_combo.SetSelection(0)
        
        
    def get_datachoices(self):
        return sorted([title for title in self.availabledata])
#        return ['Raw data', 'Filtered Data']
    

    def get_ctrlgroupchoices(self):
        data,label = self.get_currentdata()
        if data is not None and len(self.sel_roigrouping) > 0 and self.sel_roigrouping[0] != 'None':
            uniques = []
 #           col = self.sel_roigrouping[0]
#            for col in self.sel_roigrouping:
            uniques = [sorted(data[col].unique()) for col in self.sel_roigrouping[:self.pivot_level]]
            return [', '.join(item) for item in list(itertools.product(*uniques))]
        else:
            return [' ']
            
        
    def update_sel_ctrlgroup(self):
        if not self.ctrlgroup_combo:
            return
        current_sel = self.ctrlgroup_combo.GetStringSelection()
        choices = self.get_ctrlgroupchoices()
        self.ctrlgroup_combo.Clear()
        self.ctrlgroup_combo.AppendItems(choices)
        if current_sel != '' and current_sel in choices:
            self.ctrlgroup_combo.SetStringSelection(current_sel)
        else:
            self.ctrlgroup_combo.SetSelection(0)
            
        
    def set_roigroupings(self, categories):
        options = ['None']
#        groupings = self.flimanalyzer.get_importer().get_parser().get_regexpatterns()
#        categtories = parser().get_regexpatterns()
        currentdata,label = self.get_currentdata()
        if currentdata is not None and categories is not None:
            if currentdata.select_dtypes(['category']).columns.nlevels == 1:
                categories = [c for c in categories if c in list(currentdata.select_dtypes(['category']).columns.values)]
            else:
                categories = [c for c in list(currentdata.select_dtypes(['category']).columns.get_level_values(0).values)]
            logging.debug (f"CATEGORIES: {categories}")
            for i in range(1,len(categories)+1):
                permlist = list(itertools.permutations(categories,i))
                for p in permlist:
                    options.append(', '.join(p))
        self.roigroupings = options
        current = self.roigroup_combo.GetStringSelection()
        self.roigroup_combo.Clear()
        self.roigroup_combo.AppendItems(self.roigroupings)
        if current in self.roigroupings:
            self.roigroup_combo.SetStringSelection(current)
        else:    
            self.roigroup_combo.SetSelection(0)
        self.OnRoiGroupingChanged(None)
                

    def get_checked_cols(self, data):
        if data is None:
            return None
        selcols = self.analysislist.get_checked_items()
        logging.debug (f"appFrame.TabAnalysis.get_checked_cols: SELECTED: {selcols}")
        return selcols
#        selindices = self.analysislist.get_checked_indices()
#        datacols =  data.select_dtypes(include=[np.number])
#        numcols = [datacols.columns.values.tolist()[index] for index in selindices]
#        return numcols
    
            
    def create_categorized_data_global(self, data, col, bins=[-1, 1], labels='Cat 1', normalizeto='', grouping=[], binby='xfold'):
        if not grouping or len(grouping) == 0:
            return
        controldata = data[data[grouping[0]] == normalizeto]
        grouped = controldata.groupby(grouping[1:])
        categorydef = self.config.get(cfg.CONFIG_CATEGORIES).get(col)
        if not categorydef:
            logging.debug ("Using default categories")
            bins = [1.0, 2.0]
            labels = ['cat 1']
        else:
            bins = categorydef[0]
            labels = categorydef[1]
        series = data[col]
        if normalizeto and len(normalizeto) > 0:
            median = grouped[col].median()
            logging.debug (median.describe())
            median_of_median = median.median()
            logging.debug ("MEDIAN_OF_MEDIAN: {col} {median_of_median}")
            xfold_series = series.apply(lambda x: x / median_of_median).rename('x-fold norm ' + col)
            plusminus_series = series.apply(lambda x: x - median_of_median).rename('+/- norm ' + col)
            #all_catseries.append(xfold_series)
            #all_catseries.append(plusminus_series)
            if binby == 'plusminus':
                catseries = pd.cut(plusminus_series, bins=bins, labels=labels).rename('cat %s (+/-)' % col)
            else:
                catseries = pd.cut(xfold_series, bins=bins, labels=labels).rename('cat %s (x-fold)' % col)
        else:
            catseries = pd.cut(series, bins=bins, labels=labels).rename('cat ' + col)            
        return catseries
    
        
    def create_categorized_data(self,category_colheader='Category'):
        currentdata, label = self.get_currentdata()
        cols = self.get_checked_cols(currentdata)
        ctrl_label = self.ctrlgroup_combo.GetStringSelection()
        grouping = self.sel_roigrouping

        results = {}
        if not flim.gui.dialogs.check_data_msg(currentdata):
            return results, currentdata, label
        if cols is None or len(cols) != 1:
            wx.MessageBox('A single measurement needs to be selected.', 'Warning', wx.OK)
            return results, currentdata, label 
        if  len(grouping) < 1 or ctrl_label == '':
            wx.MessageBox('A Roi grouping needs to be selected.', 'Warning', wx.OK)
            return results, currentdata, label             
        if 'Category' in grouping:
            wx.MessageBox('\'Category\' cannot be used in grouping for categorization analysis.', 'Warning', wx.OK)
            return results, currentdata, label
        if self.analysistype_combo.GetStringSelection == 'Categorize' and len(cols) != 1:
            wx.MessageBox('\'Categorization analysis requires selection of a single measurement.', 'Warning', wx.OK)
            return results, currentdata, label
        if len(self.sel_roigrouping) <= self.pivot_level:
            wx.MessageBox('\'The Roi grouping must include at least %d groups.' % (self.pivot_level + 1), 'Warning', wx.OK)
            return results, currentdata, label
        if len(self.sel_roigrouping[:self.pivot_level]) != len(ctrl_label.split(', ')):
            wx.MessageBox('\'Inconsistent pivot level and control group selection. Try to reset Roi grouping and control group selection.', 'Warning', wx.OK)
            return results, currentdata, label
        
        # example: normalizeto = {'Compartment':'Mito', 'Treatment':'Ctrl'}
        normalizeto = dict(zip(self.sel_roigrouping[:self.pivot_level], ctrl_label.split(', ')))
        
        col = sorted(cols)[0]
        categorydef = self.config.get(cfg.CONFIG_CATEGORIES).get(col)
        if not categorydef:
            bins = [0.0, 1.0, 2.0]
            labels = ['Cat 1', 'Cat 2']
        else:
            bins = categorydef[0]
            labels = categorydef[1]
        dlg = ConfigureCategoriesDlg(self, col, bins, labels) 
        if dlg.ShowModal() == wx.ID_CANCEL:
            return
        categorydef = dlg.get_config()
        dlg.Destroy()
        
        self.config.update({col:[categorydef[0],categorydef[1]]}, [cfg.CONFIG_ROOT,cfg.CONFIG_ANALYSIS,cfg.CONFIG_CATEGORIES])
        cat_med,currentdata = self.flimanalyzer.get_analyzer().categorize_data(currentdata, col, bins=categorydef[0], labels=categorydef[1], normalizeto=normalizeto, grouping=grouping, category_colheader=category_colheader)

        mediansplits = {}
        catcol = 'Category'#currentdata.iloc[:,-1].name
        split_grouping = [catcol]
        split_grouping.extend(self.sel_roigrouping[:(self.pivot_level-1)])
        logging.debug (f"SPLIT GROUPING: {split_grouping}")
        split_data = currentdata.reset_index().groupby(split_grouping)
        for split_name,group in split_data:
            mediansplit_df = group.groupby(grouping).median().dropna()#group.reset_index().groupby(grouping).median().dropna()
            mediansplits[split_name] = mediansplit_df.reset_index()

        if label.startswith('Raw'):
            self.update_rawdata(currentdata)
        elif label.startswith('Filtered'):
            self.update_data(currentdata)   
#        self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
        event = DataUpdatedEvent(EVT_DU_TYPE, self.GetId())
        event.SetUpdatedData(currentdata, label)
        self.GetEventHandler().ProcessEvent(event)        
    
        return col, cat_med, mediansplits, currentdata, label
    

    def show_categorized_data(self):
        results = self.create_categorized_data(category_colheader=self.category_colheader)
        if results is None:
            return
        col, cat_med, mediansplits, joineddata, label = results
        frame = PandasFrame(self, "Categorized by %s: Median - %s" % (col,label), cat_med, showcolindex=False)
        frame.Show(True)

        # TEST
        g = ['Category']
        g.extend(self.sel_roigrouping)
        windowtitle = "Master by %s: Median - %s" % (col,label)
        event = DataWindowEvent(EVT_DATA_TYPE,self.GetId())
        event.SetEventInfo(joineddata.groupby(g)[col].median().dropna().reset_index(), 
                          windowtitle, 
                          'createnew', 
                          showcolindex=False)
        self.GetEventHandler().ProcessEvent(event)        
        
        
        #for split_name in sorted(mediansplits):
        #    median_split = mediansplits[split_name]
        #    frame = PandasFrame(self, "Split: Medians - Cat %s: %s" % (' '.join(split_name), label), median_split, showcolindex=False)
        #    frame.Show(True)
                        
        
    def save_categorized_data(self):
        catcol = self.category_colheader
        results = self.create_categorized_data(category_colheader=catcol)
        if results is None:
            return
        col, cat_med, mediansplits, joineddata, label = results
        flim.gui.dialogs.save_dataframe(self, "Save Master file with new categories", joineddata, "Master-allcategories-%s.txt" % label, saveindex=False)
        flim.gui.dialogs.save_dataframe(self, "Save categorization summary", cat_med, "Categorized-%s-%s.txt" % (col,label), saveindex=False)
        for split_name in sorted(mediansplits):
            median_split = mediansplits[split_name]
            split_label = '-'.join(split_name)
            split_grouping = [catcol]
            split_grouping.extend(self.sel_roigrouping[:(self.pivot_level-1)])
            logging.debug (f"SPLITGROUPING: {split_grouping}, SPLITNAME={split_name}, SPLITLABEL={split_label}")
            flim.gui.dialogs.save_dataframe(self, "Save grouped medians for Cat %s: %s" % (split_label, label), median_split, "Grouped-Medians-Cat_%s-%s.txt" % (split_label,label), saveindex=False)
            
            master_split = joineddata.set_index(split_grouping).loc[split_name,:].reset_index()
            flim.gui.dialogs.save_dataframe(self, "Save master data for Cat %s: %s" % (split_label, label), master_split, "Master-Cat_%s-%s.txt" % (split_label,label), saveindex=False)

    
class AppFrame(wx.Frame):
    
    def __init__(self, flimanalyzer, config=None):
        self.flimanalyzer = flimanalyzer
        if config:
            self.config = config
        else:
            self.config = cfg.Config()
            self.config.create_default()
        self.analyzers = flim.analysis.absanalyzer.get_analyzer_classes()
        #self.rawdata = None
        #self.data = None
        #self.filtereddata = None
        self.windowframes = {}
        self.window_zorder = []
        
        super(AppFrame,self).__init__(None, wx.ID_ANY,title="FLIM Data Analyzer")#, size=(600, 500))

        tb = wx.ToolBar( self, -1 ) 
        self.ToolBar = tb
        fileopen_tool = tb.AddTool(wx.NewId(),"Open File", wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN), shortHelp="Open file")
        self.Bind(wx.EVT_TOOL, self.OnLoadData, fileopen_tool)
        fileimport_tool = tb.AddTool(wx.NewId(),"Import Files", wx.ArtProvider.GetBitmap(wx.ART_FOLDER_OPEN), shortHelp="Import files")
        self.Bind(wx.EVT_TOOL, self.OnImportData, fileimport_tool)
        
        tb.AddSeparator()
                
        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        loadmenuitem = filemenu.Append(wx.NewId(), "&Open...","Open single data file")
        importmenuitem = filemenu.Append(wx.NewId(), "Import...","Impoort and concatenate mutliple data files")
        exitmenuitem = filemenu.Append(wx.NewId(), "Exit","Exit the application")
        settingsmenu = wx.Menu()
        loadsettingsitem = settingsmenu.Append(wx.NewId(), "Load settings...")
        savesettingsitem = settingsmenu.Append(wx.NewId(), "Save settings...")
        datamenu = wx.Menu()
        setfiltersitem = datamenu.Append(wx.NewId(), "Set filters...")
        self.analysismenu = wx.Menu()
        for analyzername in sorted(self.analyzers):
            analyzer = flim.analysis.absanalyzer.create_instance(self.analyzers[analyzername], None)
            analyzeritem = self.analysismenu.Append(wx.NewId(), analyzername)
            self.Bind(wx.EVT_MENU, self.OnRunAnalysis, analyzeritem)
            analysis_tool = tb.AddTool(wx.NewId(),analyzername, analyzer.get_icon(), shortHelp=analyzername)
            self.Bind(wx.EVT_TOOL, self.OnRunAnalysis, analysis_tool)
        self.windowmenu = wx.Menu()
        closeallitem = self.windowmenu.Append(wx.NewId(), "Close all windows")
        self.windowmenu.AppendSeparator()
        menubar.Append(filemenu, "&File")
        menubar.Append(settingsmenu, "&Settings")
        menubar.Append(datamenu, "&Data")
        menubar.Append(self.analysismenu, "&Analysis")
        menubar.Append(self.windowmenu, "&Window")
        self.SetMenuBar(menubar)        
        self.Bind(wx.EVT_MENU, self.OnLoadData, loadmenuitem)
        self.Bind(wx.EVT_MENU, self.OnImportData, importmenuitem)
        self.Bind(wx.EVT_MENU, self.OnExit, exitmenuitem)
        self.Bind(wx.EVT_MENU, self.OnLoadSettings, loadsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnSaveSettings, savesettingsitem)
        self.Bind(wx.EVT_MENU, self.OnSetFilters, setfiltersitem)
        self.Bind(wx.EVT_MENU, self.OnCloseAll, closeallitem)
        
        tb.Realize()

        self.SetSize((800, 250))
        self.Centre()
        self.Show(True) 
 
        # Create a panel and notebook (tabs holder)
        #nb = wx.Notebook(self)
 
        # Create the tab windows
        # self.analysistab = TabAnalysis(nb, self, self.flimanalyzer, self.config)
 
        # Add the windows to tabs and name them.
        #nb.AddPage(self.analysistab, "Analyze")
        
#        self.update_tabs()
 
        # Set noteboook in a sizer to create the layout
        #sizer = wx.BoxSizer()
        #sizer.Add(nb, 1, wx.EXPAND)
        
        #sizer.SetSizeHints(self)
        #self.SetSizerAndFit(sizer)
        

        self.Bind(EVT_IMPORT, self.OnImport)
        self.Bind(EVT_DATA, self.OnDataWindowRequest)
        self.Bind(EVT_PLOT, self.OnPlotWindowRequest)
        self.Bind(EVT_DATAUPDATED, self.OnDataUpdated)
        self.Bind(EVT_APPLYFILTER, self.OnApplyFilter)
        self.Bind(EVT_FILTERUPDATED, self.OnRangeFilterUpdated)
        self.Bind(EVT_ANALYSISUPDATED, self.OnAnalysisUpdated)
#        pub.subscribe(self.OnNewDataWindow, NEW_DATA_WINDOW)
        #pub.subscribe(self.OnDataImported, DATA_IMPORTED)
        #pub.subscribe(self.OnFilteredDataUpdated, FILTERED_DATA_UPDATED)
        pub.subscribe(self.OnDataWindowFocused, FOCUSED_DATA_WINDOW)
        pub.subscribe(self.OnClosingDataWindow, CLOSING_DATA_WINDOW)
        pub.subscribe(self.OnRequestRenameDataWindow, REQUEST_RENAME_DATA_WINDOW)
        #pub.subscribe(self.OnNewPlotWindow, NEW_PLOT_WINDOW)
        
    
#    def OnNewDataWindow(self, data, frame):
#        title = frame.GetLabel()
#        print "appframe.OnNewDataWindow - %s" % (title)
#        self.windowframes[frame.GetLabel()] = frame
#        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
#        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)

    def OnDataWindowFocused(self, data, frame):
        title = frame.GetTitle()
        self.window_zorder = [w for w in self.window_zorder if w != title]
        self.window_zorder.append(title)

        
    def OnLoadData(self, event):
        dlg = ImportDlg(self, "Open File", self.config, parsefname=False, preprocess=False, singlefile=True)
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_config()

            importer = dataimporter()
            importer.set_delimiter(config.get([cfg.CONFIG_DELIMITER]))
            importer.set_files(config.get([cfg.CONFIG_INCLUDE_FILES]))
            importer.set_parser(None)
            importer.set_preprocessor(None) 
            data, filenames, fheaders = importer.import_data()

            pub.sendMessage(DATA_IMPORTED, olddata=None, data=data)
            windowtitle = os.path.basename(filenames[0])
            if len(filenames) != 1:
                windowtitlw = "Imported Data"
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(data, 
                              windowtitle,
                              'update',
                              config=None, 
                              showcolindex=False, 
                              analyzable=True,
                              savemodified=True,
                              enableclose=True)
            self.GetEventHandler().ProcessEvent(event)  


    def OnImportData(self, event):
        dlg = ImportDlg(self, "Import File(s)", self.config)
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_config()

            parsername = config.get([cfg.CONFIG_PARSER_CLASS])
            parser = flim.core.parser.instantiate_parser('flim.core.parser.' + parsername)
            if parser is None:
                logging.warning (f"Could not instantiate parser {parsername}")
                return
            parser.set_regexpatterns(config.get([cfg.CONFIG_PARSER_PATTERNS]))
            
            preprocessor = defaultpreprocessor()
            preprocessor.set_replacementheaders(config.get([cfg.CONFIG_HEADERS]))
            preprocessor.set_dropcolumns(config.get([cfg.CONFIG_DROP_COLUMNS]))

            importer = dataimporter()
            importer.set_parser(parser)
            importer.set_delimiter(config.get([cfg.CONFIG_DELIMITER]))
            importer.set_files(config.get([cfg.CONFIG_INCLUDE_FILES]))
            importer.set_preprocessor(preprocessor)
            data, filenames, fheaders = importer.import_data()

            #pub.sendMessage(DATA_IMPORTED, olddata=None, data=data)
            windowtitle = os.path.basename(filenames[0])
            if len(filenames) != 1:
                windowtitlw = "Imported Data"
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(data, 
                              windowtitle,
                              'update',
                              config=None, 
                              showcolindex=False, 
                              analyzable=True,
                              savemodified=True,
                              enableclose=True)
            self.GetEventHandler().ProcessEvent(event)        


    def OnLoadSettings(self, event):
        logging.debug ("appframe.OnLoadSettings")
        with wx.FileDialog(self, "Load Configuration file", wildcard="json files (*.json)|*.json",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_CHANGE_DIR) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            configfile = fileDialog.GetPath()
            config = Config()
            if config.read_from_json(configfile):
                missing,invalid = config.validate()
                if len(missing) == 0 and len(invalid) == 0:
                    self.config = config
                else:
                    message =''
                    if len(missing) > 0:
                        message += 'Missing keys:\n%s\n\n' % ('\n'.join([str(m) for m in missing]))
                    if len(invalid) > 0:
                        message += 'Missing values:\n%s\n\n' % ('\n'.join([str(i) for i in invalid]))
                    dlg = wx.MessageDialog(None, message+'\nDo you want to try to fix them?','Error: Loaded settings are not valid.',wx.YES_NO | wx.ICON_QUESTION)
                    result = dlg.ShowModal()                     
                    if result == wx.ID_YES:  
                        if config.fix():
                            self.config = config
                        else:
                            wx.MessageBox('Attempt to fix settings failed', 'Error', wx.OK | wx.ICON_INFORMATION)
                            return
                    else:
                        return
                pub.sendMessage(CONFIG_UPDATED, source=self, config=self.config, updated=self.config.get())
            else:
                wx.MessageBox('Error loading settings from %s' % configfile, 'Error', wx.OK | wx.ICON_INFORMATION)


    def OnSaveSettings(self, event):
        logging.debug ("appframe.OnSaveSettings")
        logging.debug (self.config.get())
        with wx.FileDialog(self, "Save Configuration file", wildcard="json files (*.json)|*.json",
                       style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT| wx.FD_CHANGE_DIR) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            configfile = fileDialog.GetPath()
            self.config.write_to_json(configfile)
   
        
    def get_currentdata(self):
        if len(self.window_zorder) == 0:
           return
        return self.windowframes[self.window_zorder[-1]].GetViewData()
   
   
    def OnSetFilters(self, event):
        data = self.get_currentdata()
        if data is None:
             wx.MessageBox('No data available')
             return
        pass
        
        
    def OnRunAnalysis(self, event):
        data = self.get_currentdata()
        if data is None:
             wx.MessageBox('No data available')
             return
        itemid = event.GetId()
        evtobj = event.GetEventObject()
        analyzername = ''
        if isinstance(evtobj, wx._core.ToolBar):
            analyzername = evtobj.FindById(itemid).GetLabel()
        else:
            analyzername = evtobj.FindItemById(itemid).GetItemLabelText()
        logging.debug(f"{event.GetId()}, {analyzername}")
        
        # check that there's any data to process
        if not flim.gui.dialogs.check_data_msg(data):
            return
        
        # check that user provided required data categories and data features
        #categories = self.sel_roigrouping
        #features = [c for c in self.get_checked_cols(self.currentdata)]
        
        analysis_class = flim.analysis.absanalyzer.get_analyzer_classes()[analyzername]
        tool = flim.analysis.absanalyzer.create_instance(analysis_class, data)
        parameters = self.config.get([cfg.CONFIG_ANALYSIS, analyzername])
        tool.configure(**parameters)

        # run optional tool config dialog and execte analysis
        parameters = tool.run_configuration_dialog(self)
        if parameters is None:
            return
        self.config.update(parameters, [cfg.CONFIG_ANALYSIS, analyzername])
        logging.debug(parameters)
        features = parameters['features']
        categories = parameters['grouping']     

        req_features = tool.get_required_features()
        not_any_features = [f for f in req_features if f != 'any']
        if features is None or len(features) < len(req_features) or not all(f in features for f in not_any_features):
            wx.MessageBox(f'Analysis tool {tool} requires selection of at least {len(req_features)} data features, including {not_any_features}.', 'Warning', wx.OK)            
            return

        req_categories = tool.get_required_categories()
        not_any_categories = [c for c in req_categories if c != 'any']
        if len(req_categories) > 0 and (categories is None or len(categories) < len(req_categories) or not all(c in categories for c in not_any_categories)):
            wx.MessageBox(f'Analysis tool {tool} requires selection of at least {len(req_categories)} groups, including {not_any_categories}.', 'Warning', wx.OK)            
            return
        
        results = tool.execute()
        
        # handle results, DataFrames or Figure objects
        if results is not None:
            for title, result in results.items():
                if isinstance(result, pd.DataFrame):
                    # result = result.reset_index()
                    event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
                    event.SetEventInfo(result, 
                                       title,
                                       'createnew', 
                                       showcolindex=False)
                    self.GetEventHandler().ProcessEvent(event)
                elif isinstance(result, matplotlib.figure.Figure):
                    fig = result
                    fig.canvas.set_window_title(title)
                    event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
                    event.SetEventInfo(fig, title, 'createnew')
                    self.GetEventHandler().ProcessEvent(event)                
        
        
    def append_window_to_menu(self, title, window):
        self.windowframes[title] = window
        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
        if isinstance(window, PandasFrame):
            self.window_zorder = [w for w in self.window_zorder if w != title]
            self.window_zorder.append(title)
        logging.debug(f"append window {self.window_zorder}")
        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)
        
        
    def remove_window_from_menu(self, title):
        for mitem in self.windowmenu.GetMenuItems():
            if mitem.GetItemLabelText() == title:
                self.windowmenu.Remove(mitem.GetId())
                window = self.windowframes[title] 
                del self.windowframes[title]
                if isinstance(window, PandasFrame):
                    title = window.GetTitle()
                    self.window_zorder = [w for w in self.window_zorder if w != title]
                logging.debug(f"remove window {self.window_zorder}")
                return True
        return False
    
        
    def remove_figure_from_menu(self, figure):
        for mitem in self.windowmenu.GetMenuItems():
            mlabel = mitem.GetItemLabelText()
            if mlabel in self.windowframes and self.windowframes[mlabel] == figure:
                self.windowmenu.Remove(mitem.GetId())
                del self.windowframes[mlabel]
                return True
        return False
    
    
    def OnDataWindowRequest(self, event):
        data = event.GetData()
        config = event.GetConfig()
        action = event.GetAction()
        title = event.GetTitle()
        logging.debug (f"{title}: {action}")
        if action == 'update':
            frame = self.windowframes.get(title)
            if frame:
                frame = self.windowframes[title]
                frame.SetData(data)
                # frame.SetConfog(config)
            else:
                action = 'createnew'
        if action == 'createnew':
            title = self.unique_window_title(title)
            frame = PandasFrame(self, 
                                title,
                                config, 
                                data, 
                                showcolindex=event.ShowColIndex(), 
                                analyzable=event.IsAnalyzable(), 
                                groups=event.GetGroups(),
                                savemodified=event.SaveModified(),
                                enableclose=event.IsEnableClose())
            frame.Show(True)
            self.append_window_to_menu(title, frame)
            pub.sendMessage(NEW_DATA_WINDOW, data=data, frame=frame)

    
    def OnRequestRenameDataWindow(self, original, new, data):
        title = self.unique_window_title(new)
        for mitem in self.windowmenu.GetMenuItems():
            if mitem.GetItemLabelText() == original:
                mitem.SetItemLabel(title)
                del self.windowframes[original]
                self.windowframes[title] = data
                pub.sendMessage(RENAMED_DATA_WINDOW, original=original, new=title, data=data)
                return
        
        
    def OnClosingDataWindow(self, data, frame):
        title = frame.GetLabel()
        logging.debug (f"{title}")
        self.remove_window_from_menu(title)

        	
    def OnPick(self, event):
        if event.mouseevent.dblclick:
            #print ("picked:", event.artist, type(event.artist))
    	    #print (event.mouseevent)
    	    #print (matplotlib.artist.get(event.artist))
            ax = event.artist.axes
            fig = event.artist.get_figure()
            if isinstance(event.artist,matplotlib.axis.YAxis):
    	        dlg = ConfigureAxisDlg(self, "Set Y Axis", {'label': event.artist.get_label_text(), 'min':ax.get_ylim()[0], 'max': ax.get_ylim()[1]}) 
    	        response = dlg.ShowModal()
    	        if response == wx.ID_OK:
    	            newsettings = dlg.get_settings()
    	            event.artist.set_label_text(newsettings['label'], picker=True)
    	            ax.set_ylim(newsettings['min'], newsettings['max'])
    	            fig.canvas.draw_idle()
            elif isinstance(event.artist,matplotlib.axis.XAxis):
    	        dlg = ConfigureAxisDlg(self, "Set X Axis", {'label': event.artist.get_label_text(), 'min':ax.get_xlim()[0], 'max': ax.get_xlim()[1]}) 
    	        response = dlg.ShowModal()
    	        if response == wx.ID_OK:
    	            newsettings = dlg.get_settings()
    	            event.artist.set_label_text(newsettings['label'], picker=True)
    	            ax.set_xlim(newsettings['min'], newsettings['max'])
    	            fig.canvas.draw_idle()
            elif isinstance(event.artist, matplotlib.text.Text):
                dlg = wx.TextEntryDialog(self, 'Label','Update Label')
                dlg.SetValue(event.artist.get_text())
                if dlg.ShowModal() == wx.ID_OK:
                    event.artist.set_text(dlg.GetValue())
                    fig.canvas.draw_idle()
                dlg.Destroy()
            elif isinstance(event.artist,matplotlib.lines.Line2D):
                #event.artist.set_dashes((5, 2, 1, 2))
                #event.artist.set_linewidth(2)
                data = wx.ColourData()
                data.SetColour(event.artist.get_color())
                dlg = wx.ColourDialog(self, data)
                # dlg.Bind(wx.EVT_COLOUR_CHANGED, self.OnColourChanged)
                if (dlg.ShowModal() == wx.ID_OK):
                    pass
                    
                color = dlg.GetColourData().GetColour()
                event.artist.set_color((color.Red()/255, color.Green()/255, color.Blue()/255))
                event.artist.set_alpha(color.Alpha()/255)
                fig.canvas.draw_idle()
            	
    	
    	
    def OnPlotWindowRequest(self, event):
        figure = event.GetFigure()
        title = self.unique_window_title(event.GetTitle())
        figure.canvas.set_window_title(title)
        #ON_CUSTOM_LEFT  = wx.NewId()
        #tb = figure.canvas.toolbar
        #tb.AddTool(ON_CUSTOM_LEFT, 'Axes', wx.NullBitmap,'Set range of Axes')
        #tb.Realize()
        action = event.GetAction() 
        logging.debug (f"{title}: {action}")
        if action == 'createnew':
            figure.show()
            self.append_window_to_menu(title, figure)
            figure.canvas.mpl_connect('close_event', self.OnClosingPlotWindow)
            figure.canvas.mpl_connect('pick_event', self.OnPick)

        
#    def OnNewPlotWindow(self, figure):
#        title = figure.get_axes()[0].get_title()
#        print "appframe.OnNewPlotWindow - %s, %s" % (title, figure.canvas.GetName())
#        figure.canvas.mpl_connect('close_event', self.OnClosingPlotWindow)
#        self.windowframes[title] = figure.canvas
#        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
#        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)


    def OnClosingPlotWindow(self, event):
        logging.debug ("appframe.OnClosingPlotWindow")
        self.remove_figure_from_menu(event.canvas.figure)
        
        
    def OnWindowSelectedInMenu(self, event):
        itemid = event.GetId()
        menu = event.GetEventObject()
        mitem = menu.FindItemById(itemid)
        if self.windowframes.get(mitem.GetItemLabelText()):
            wintitle = mitem.GetItemLabelText()
            window = self.windowframes[wintitle]
            if isinstance(window,wx.Frame):
                window.Raise()
                if isinstance(window, PandasFrame) and self.window_zorder[-1] != wintitle:
                    self.window_zorder = [w for w in self.window_zorder if w != wintitle]
                    self.window_zorder.append(wintitle)
            elif isinstance(window,matplotlib.figure.Figure):
                window.canvas.manager.show()
        logging.debug(f"select window {self.window_zorder}")

        
    def OnExit(self, event):
        self.Close()    
        
    
    def get_window_frames(self):
        return [x for x in self.GetChildren() if isinstance(x, wx.Frame) or isinstance(x, matplotlib.figure.Figure)]

    
    def OnCloseAll(self, event):
        logging.debug ("appframe.OnCloseAll")
        # need to create copy of keys/titles before iteration because self.windowframes will change in size when windows close
        
        #titles = [t for t in self.windowframes]
        #for title in titles:
        #    self.windowframes[title].Close()
                
        windowtitles = [t for t in self.windowframes]
        for title in windowtitles:
            window = self.windowframes[title]
            if window:
                if isinstance(window, matplotlib.figure.Figure):
                    self.remove_figure_from_menu(window)
                    window.canvas.manager.destroy()
                else:
                    window.Close()
        self.window_zorder = []
        
    
    def OnImport(self, event):
        #self.rawdata = event.rawdata
#        self.filtertab.update_rawdata(self.rawdata)        
#        self.analysistab.update_rawdata(self.rawdata)
        logging.debug (f"###############  OLD IMPORT: datatypes\n{self.rawdata.dtypes}")
        # this should not be set based on current parsers regex pattern but based on columns with 'category' as dtype
#        self.analysistab.set_roigroupings(event.importer.get_parser().get_regexpatterns().keys())


    def OnDataUpdated(self, event):
        data,datatype = event.GetUpdatedData()
        logging.debug (f"###############  OLD appframe.OnDataUpdated - {datatype}")
#        if datatype == 'Raw':
#            self.rawdata = data
#            self.filtertab.update_rawdata(data, applyfilters=True)        
#            self.analysistab.update_rawdata(data)
#        else:
#            self.filtertab.update_data(data)        
#            self.analysistab.update_data(data)
                    
        
    def OnRangeFilterUpdated(self, event):
        rfilters = event.GetUpdatedItems()
        logging.debug (f"###############  OLD appframe.OnRangeFilterUpdated - {len(rfilters)} Filters updated:")
        #for key in rfilters:
        #    rfilter = rfilters[key]
        #    print "\t %s: %s" % (key, str(rfilter.get_params()))
        #dropsbyfilter, totaldrops = self.filtertab.apply_filters(rfilters, dropsonly=True, onlyselected=False)
        #self.analysistab.update_rangefilters(rfilters)
        #self.data = self.rawdata.drop(totaldrops)
        #self.analysistab.update_data(self.data)
        #event.Skip()
        
        
    def OnApplyFilter(self, event):
        logging.debug ("###############  OLD AppFrame.OnApplyFilter")
        self.data = event.data
        self.analysistab.update_data(event.data)
        
        
    def OnAnalysisUpdated(self, event):
        updated = event.GetUpdatedItems()
        logging.debug (f"appframe.OnAnalysisUpdated - {len(updated)} Analysis updated:")
        for key in updated:
            u = updated[key]
            logging.debug ("\t {key} {str(u))}")

        
    def unique_window_title(self, title):
        suffix = None
        i = 1
        while title in self.windowframes:
            if suffix:
                title = title[:-len(suffix)]
            suffix = '-%d' % i    
            title = '%s%s' % (title, suffix)
            i += 1
        return title
    
                                    
   
