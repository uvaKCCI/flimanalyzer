#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon May  7 21:00:30 2018

@author: khs3z
"""

import os
import numpy as np
import matplotlib
matplotlib.use('WXAgg')
import matplotlib.pyplot as plt
import itertools
import pandas as pd
import json

import wx
import wx.lib.agw.customtreectrl as CT
from wx.lib.pubsub import pub

import core.configuration as cfg
from core.configuration import Config
import core.parser
import core.plots
import core.preprocessor
import gui.dialogs
from core.preprocessor import defaultpreprocessor
from core.importer import dataimporter
from core.filter import RangeFilter
from gui.delimpanel import DelimiterPanel
from gui.datapanel import PandasFrame
from gui.dicttablepanel import DictTable
from gui.listcontrol import AnalysisListCtrl, FilterListCtrl, EVT_FILTERUPDATED, EVT_ANALYSISUPDATED
from gui.seriesfiltertree import SeriesFilterCtrl
#from gui.mpanel import MatplotlibFrame
#from core.plots import MatplotlibFigure
from gui.dialogs import ConfigureCategoriesDlg
from gui.events import DataUpdatedEvent, EVT_DATAUPDATED, EVT_DU_TYPE, DataWindowEvent, EVT_DATA, EVT_DATA_TYPE, PlotEvent, EVT_PLOT, EVT_PLOT_TYPE 
from gui.events import REQUEST_CONFIG_UPDATE, CONFIG_UPDATED, NEW_DATA_WINDOW, CLOSING_DATA_WINDOW, REQUEST_RENAME_DATA_WINDOW, RENAMED_DATA_WINDOW, NEW_PLOT_WINDOW, DATA_IMPORTED, FILTERS_UPDATED, FILTERED_DATA_UPDATED, DATA_UPDATED, ANALYSIS_BINS_UPDATED
from gui.dialogs import SelectGroupsDlg

from wx.lib.newevent import NewEvent

ImportEvent, EVT_IMPORT = NewEvent()
ApplyFilterEvent, EVT_APPLYFILTER = NewEvent()
DataUpdateEvent, EVT_UPDATEDATA = NewEvent()


class FlimAnalyzerApp(wx.App):
    
    def __init__(self, flimanalyzer, config=None):
        self.flimanalyzer = flimanalyzer
        if config is None or not isinstance(config, Config):
            self.config = Config()
            self.config.create_default()
        else:
            self.config = config
        super(FlimAnalyzerApp,self).__init__()
        self.Bind(EVT_FILTERUPDATED, self.OnFilterUpdated)
        pub.subscribe(self.OnConfigUpdated, CONFIG_UPDATED)

        
    def OnInit(self):
        self.frame = AppFrame(self.flimanalyzer, self.config)
        self.frame.Show(True)
        return True


    def OnConfigUpdated(self, source, config, updated):
        print "FLIMANALYZERAPP.OnConfigUpdated"
        if source != self and updated:
            for key in updated:
                print "    updated key", key
        
        
    def OnFilterUpdated(self, event):
        print "FLIMANALYZERAPP: filter updated:"

    
class TabImport(wx.Panel):
    
    def __init__(self, parent, pwindow, flimanalyzer, config):
        self.pwindow = pwindow
        self.flimanalyzer = flimanalyzer
        self.config_calc_columns = config.get(cfg.CONFIG_CALC_COLUMNS)
        
        #self.delimiter = config[CONFIG_DELIMITER]
        #self.parser = config[CONFIG_PARSERCLASS]
        #self.drop_columns = config[CONFIG_DROP_COLUMNS]
        #self.excluded_files = config[CONFIG_EXCLUDE_FILES]
        #self.calc_columns = config[CONFIG_CALC_COLUMNS]
        #self.filters = config[CONFIG_FILTERS]
        #self.headers = config[CONFIG_HEADERS]

        self.rawdata = None
        super(TabImport,self).__init__(parent)
                
        delimiter_label = wx.StaticText(self, wx.ID_ANY, "Column Delimiter:")
        self.delimiter_panel = DelimiterPanel(self, config.get(cfg.CONFIG_DELIMITER))
        
        parser_label = wx.StaticText(self, wx.ID_ANY, "Filename Parser:")
        #self.parser_field = wx.TextCtrl(self, wx.ID_ANY, value=self.parser)
        self.avail_parsers = core.parser.get_available_parsers()
        sel_parser = self.avail_parsers.get(config.get(cfg.CONFIG_PARSERCLASS))
        if sel_parser is None:
            sel_parser = self.avail_parsers.keys()[0]
        self.parser_chooser = wx.ComboBox(self, -1, value=sel_parser, choices=sorted(self.avail_parsers.keys()), style=wx.CB_READONLY)
        self.parser_chooser.Bind(wx.EVT_CHOICE, self.OnParserChanged)

        self.sel_files_label = wx.StaticText(self, wx.ID_ANY, "Selected Files: %9d" % len(flimanalyzer.get_importer().get_files()), (20,20))    
        self.files_list = wx.ListBox(self, wx.ID_ANY, style=wx.LB_EXTENDED|wx.LB_HSCROLL|wx.LB_NEEDED_SB|wx.LB_SORT)

        exclude_label = wx.StaticText(self, wx.ID_ANY, "Exclude Files:")
        self.exclude_files_list = wx.TextCtrl(self, wx.ID_ANY, value="\n".join(config.get(cfg.CONFIG_EXCLUDE_FILES)), style=wx.TE_MULTILINE|wx.EXPAND)
        
        rename_label = wx.StaticText(self, wx.ID_ANY, "Rename Columns:")
        self.rgrid = wx.grid.Grid(self, -1)#, size=(200, 100))
        self.rgrid.SetDefaultColSize(200,True)
        self.headertable = DictTable(config.get(cfg.CONFIG_HEADERS), headers=['Original name', 'New name'])
        self.rgrid.SetTable(self.headertable,takeOwnership=True)
        self.rgrid.SetRowLabelSize(0)

        drop_label = wx.StaticText(self, wx.ID_ANY, "Drop Columns:")
        self.drop_col_list = wx.TextCtrl(self, wx.ID_ANY, size=(200, 100), value="\n".join(config.get(cfg.CONFIG_DROP_COLUMNS)), style=wx.TE_MULTILINE|wx.EXPAND)

        self.add_button = wx.Button(self, wx.ID_ANY, "Add Files")
        self.add_button.Bind(wx.EVT_BUTTON, self.OnAddFiles)

        self.remove_button = wx.Button(self, wx.ID_ANY, "Remove Files")
        self.remove_button.Bind(wx.EVT_BUTTON, self.OnRemoveFiles)

        self.reset_button = wx.Button(self, wx.ID_ANY, "Reset")
        self.reset_button.Bind(wx.EVT_BUTTON, self.OnReset)

        self.preview_button = wx.Button(self, wx.ID_ANY, "Preview")
        self.preview_button.Bind(wx.EVT_BUTTON, self.OnPreview)

        self.import_button = wx.Button(self, wx.ID_ANY, "Import")
        self.import_button.Bind(wx.EVT_BUTTON, self.OnImportFiles)


        configsizer = wx.FlexGridSizer(2,2,5,5)
        configsizer.AddGrowableCol(1, 1)
        colsizer = wx.FlexGridSizer(2,2,5,5)
        colsizer.AddGrowableCol(0, 2)
        colsizer.AddGrowableCol(1, 1)
        colsizer.AddGrowableRow(1, 1)
        lbuttonsizer = wx.BoxSizer(wx.VERTICAL)
        filesizer = wx.FlexGridSizer(2,2,5,5)
        filesizer.AddGrowableCol(0,1)
        filesizer.AddGrowableCol(1,3)
        filesizer.AddGrowableRow(1,1)
        topleftsizer = wx.FlexGridSizer(2,1,5,5)
        topleftsizer.AddGrowableCol(0, 1)
        topleftsizer.AddGrowableRow(1, 1)
        topsizer = wx.BoxSizer(wx.HORIZONTAL)
        bottomsizer = wx.BoxSizer(wx.HORIZONTAL)
        box = wx.BoxSizer(wx.VERTICAL)
        
        configsizer.Add(delimiter_label, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        configsizer.Add(self.delimiter_panel, 1, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        configsizer.Add(parser_label, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        configsizer.Add(self.parser_chooser, 1, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        colsizer.Add(rename_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
        colsizer.Add(drop_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
        colsizer.Add(self.rgrid, 2, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        colsizer.Add(self.drop_col_list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        
        lbuttonsizer.Add(self.add_button, 1, wx.EXPAND|wx.ALL, 5)
        lbuttonsizer.Add(self.remove_button, 1, wx.EXPAND|wx.ALL, 5)
        lbuttonsizer.Add(self.reset_button, 1, wx.EXPAND|wx.ALL, 5)
        lbuttonsizer.Add(self.preview_button, 1, wx.EXPAND|wx.ALL, 5)
        lbuttonsizer.Add(self.import_button, 1, wx.EXPAND|wx.ALL, 5)

        filesizer.Add(exclude_label, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
        filesizer.Add(self.sel_files_label, 2, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
        filesizer.Add(self.exclude_files_list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        filesizer.Add(self.files_list, 2, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        
        topleftsizer.Add(configsizer, 1, wx.EXPAND|wx.ALL, 5)
        topleftsizer.Add(colsizer, 1, wx.EXPAND|wx.ALL, 5)
        
        topsizer.Add(topleftsizer, 1, wx.EXPAND|wx.ALL, 5)
        
        bottomsizer.Add(filesizer, 1, wx.EXPAND|wx.ALL, 5)
        bottomsizer.Add(lbuttonsizer,0, wx.ALL, 5)
        
        box.Add(topsizer, 1, wx.EXPAND|wx.ALL, 5)
        box.Add(wx.StaticLine(self), 0, wx.ALL|wx.EXPAND, 5)
        box.Add(bottomsizer, 1, wx.EXPAND|wx.ALL, 5)
        
        self.SetSizerAndFit(box)
        
        self.update_files(0)

        self.rgrid.Bind(wx.EVT_SIZE, self.OnRGridSize)
        pub.subscribe(self.OnConfigUpdated, CONFIG_UPDATED)
    
    
    def get_import_settings(self):
        importconfig = {}
        importconfig.update({cfg.CONFIG_PARSERCLASS : self.parser_chooser.GetStringSelection()})
        importconfig.update({cfg.CONFIG_EXCLUDE_FILES : self.exclude_files_list.GetValue().encode('ascii','ignore').split('\n')})
        importconfig.update({cfg.CONFIG_DELIMITER : self.delimiter_panel.get_delimiters()})
        #self.config[CONFIG_CALC_COLUMNS] = 'calculate columns'
        return {cfg.CONFIG_IMPORT:importconfig}    
        
    
    def get_preprocess_settings(self):
        preprocessconfig = {}
        preprocessconfig.update({cfg.CONFIG_HEADERS : self.rgrid.GetTable().GetDict()})
        preprocessconfig.update({cfg.CONFIG_DROP_COLUMNS : self.drop_col_list.GetValue().encode('ascii','ignore').split('\n')})
        preprocessconfig.update({cfg.CONFIG_CALC_COLUMNS : self.config_calc_columns})
        return {cfg.CONFIG_PREPROCESS:preprocessconfig}    
        
    
    def OnConfigUpdated(self, source, config, updated):
        print "appframe.TabImport.OnConfigUpdated"
        if source != self:
            for key in updated:
                if key in [cfg.CONFIG_ROOT, cfg.CONFIG_IMPORT, cfg.CONFIG_PREPROCESS]:
                    print "    updating: %s" % key
                    self.update_config_gui_elements(config)
                else:
                    print "    ignoring: %s" % key
        
        
    def update_config_gui_elements(self, config):
        #self.config = config
        #self.delimiter = rootconfig[CONFIG_DELIMITER]
        #self.parser = rootconfig[CONFIG_PARSERCLASS]
        #self.drop_columns = rootconfig[CONFIG_DROP_COLUMNS]
        #self.excluded_files = rootconfig[CONFIG_EXCLUDE_FILES]
        
        #self.calc_columns = rootconfig[CONFIG_CALC_COLUMNS]
        #self.filters = rootconfig[CONFIG_FILTERS]
        #self.headers = rootconfig[CONFIG_HEADERS]
        print "update_config_gui_elements"
        print "    ", cfg.CONFIG_IMPORT, config.get(cfg.CONFIG_IMPORT, returnkeys=True)
        print "    ", cfg.CONFIG_PREPROCESS, config.get(cfg.CONFIG_PREPROCESS, returnkeys=True)
        self.delimiter_panel.set_delimiters(config.get(cfg.CONFIG_DELIMITER))
        parsername = config.get(cfg.CONFIG_PARSERCLASS)
        sel_parser = self.avail_parsers.get(parsername)
        if sel_parser is None:
            parsername =  self.parser_chooser.GetStringSelection()
            parsercfg = {cfg.CONFIG_PARSERCLASS: parsername}
            config.update(parsercfg)
            pub.sendMessage(CONFIG_UPDATED, source=self, config=config, updated=parsercfg)
            # config[CONFIG_PARSERCLASS] = self.parser
        else:
            self.parser_chooser.SetStringSelection(parsername)
        if config.get(cfg.CONFIG_EXCLUDE_FILES) is not None:    
            self.exclude_files_list.SetValue('\n'.join(config.get(cfg.CONFIG_EXCLUDE_FILES)))
        else:
            self.exclude_files_list.SetValue('')            
        if config.get(cfg.CONFIG_DROP_COLUMNS) is not None:    
            self.drop_col_list.SetValue('\n'.join(config.get(cfg.CONFIG_DROP_COLUMNS)))
        else:
            self.exclude_files_list.SetValue('')            
        self.headertable = DictTable(config.get(cfg.CONFIG_HEADERS), headers=['Original name', 'New name'])
        self.rgrid.SetTable(self.headertable,takeOwnership=True) 
        self.rgrid.Refresh()
        
        
    def OnRGridSize(self, event):
        self.rgrid.SetDefaultColSize(event.GetSize().GetWidth()/self.rgrid.GetTable().GetNumberCols(),True)
        self.rgrid.Refresh()
        
    
    def update_files(self, no_newfiles):
        importer = self.flimanalyzer.get_importer()
        files = importer.get_files()
        self.sel_files_label.SetLabel("Selected Files: %9d" % len(files))
        self.files_list.Set(files)
        
        
    def OnParserChanged(self, event):
        print "Parser changed"
        #parser_chooser = event.GetEventObject()
        #parserparams = {cfg.CONFIG_PARSERCLASS:parser_chooser.GetStringSelection()}
        ##self.config.update(parsercfg)
        #pub.sendMessage(CONFIG_UPDATED, source=self, config=self.config, updated=parserparams)


    def OnAddFiles(self, event):
        with wx.FileDialog(self, "Add Raw Data Results", wildcard="txt files (*.txt)|*.txt",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE | wx.FD_CHANGE_DIR) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            # Proceed loading the file chosen by the user
            paths = fileDialog.GetPaths()
            importer = self.flimanalyzer.get_importer()
            filecount = len(importer.get_files())
            for path in paths:
                if os.path.isdir(path):
                    importer.add_files([path], exclude=[])
                else:
                    excluded = self.exclude_files_list.GetValue().encode('ascii','ignore').split('\n')              
                    importer.add_files([path], exclude=excluded)
            new_filecount = len(importer.get_files())
            self.update_files(new_filecount-filecount)
#            self.statusbar.SetStatusText("Added %d file(s)" % (new_filecount - filecount))
 
    
    def OnRemoveFiles(self, event):
        selected = self.files_list.GetSelections()
        if selected is not None and len(selected) > 0: 
            selectedfiles = [self.files_list.GetString(idx) for idx in selected]
            importer = self.flimanalyzer.get_importer()
            filecount = len(importer.get_files())
            importer.remove_files(selectedfiles)
            self.update_files(len(importer.get_files())-filecount)
 
    
    def OnReset(self, event):
        importer = self.flimanalyzer.get_importer()
        filecount = len(importer.get_files())
        self.flimanalyzer.get_importer().remove_allfiles()
        self.update_files(len(importer.get_files())-filecount)
 
    
    def configure_importer(self, importer):
#        hparser = core.parser.instantiate_parser(self.parser_field.GetValue())
        parsername = self.parser_chooser.GetStringSelection()
        hparser = core.parser.instantiate_parser('core.parser.' + parsername)
        if hparser is None:
            print "COULD NOT INSTANTIATE PARSER:", parsername 
            return
        dropped = self.drop_col_list.GetValue().encode('ascii','ignore').split('\n')
        if len(dropped)==1 and dropped[0]=='':
            dropped = None

        preprocessor = defaultpreprocessor()
        preprocessor.set_replacementheaders(self.headertable.GetDict())
        preprocessor.set_dropcolumns(dropped)
        importer.set_parser(hparser)
        importer.set_preprocessor(preprocessor)

        
    def OnPreview(self, event):
        previewrows = 200
        files = self.flimanalyzer.get_importer().get_files()
        if len(files) > 0:
            delimiter = self.delimiter_panel.get_delimiters()
            importer = dataimporter()
            self.configure_importer(importer)
            selected = self.files_list.GetSelections()
            if selected is None or len(selected)==0:
                importer.set_files([files[0]])
            else:
                print "PREVIEWING: delimiter=%s, %s" % (delimiter,self.files_list.GetString(selected[0]))
                importer.set_files([self.files_list.GetString(selected[0])])
            rawdata, readfiles, headers = importer.import_data(delimiter=delimiter, nrows=previewrows)
            rawdata = self.calc_additional_columns(rawdata) 
#            rawdata = core.preprocessor.reorder_columns(rawdata,headers)
            rawdata = core.preprocessor.reorder_columns(rawdata)

            windowtitle = "Import Preview (single file): showing first %d rows" % len(rawdata)
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(rawdata, 
                              windowtitle, 
                              'createnew', 
                              showcolindex=False, 
                              analyzable=False,
                              savemodified=False)
            self.GetEventHandler().ProcessEvent(event)        
        
    
    def update_listlabel(self):
        label = "Selected Files: %9d" % len(self.flimanalyzer.get_importer().get_files())
        if self.rawdata is not None:
            label += "; imported %d rows, %d columns" % (self.rawdata.shape[0], self.rawdata.shape[1])
        self.sel_files_label.SetLabel(label)    


    def calc_additional_columns(self, data):
        analyzer = self.flimanalyzer.get_analyzer()
        analyzer.add_columns(self.config_calc_columns)
        data,calculated,skipped = analyzer.calculate(data)
        print "CALC:", calculated
        print "SKIPPED", skipped
        return data
    
                    
    def OnImportFiles(self, event):
        importer = self.flimanalyzer.get_importer()
        files = self.flimanalyzer.get_importer().get_files()
        if len(files) == 0:
            wx.MessageBox('Add files to be imported.', 'Error', wx.OK | wx.ICON_INFORMATION)    
        else:
            delimiter = self.delimiter_panel.get_delimiters()
    #        self.statusbar.SetStatusText("Importing raw data from %d file(s)..." % len(importer.get_files()))
            self.configure_importer(importer)
            importer.set_files(files)
            oldrawdata= self.rawdata
            self.rawdata, readfiles, parsed_headers = importer.import_data(delimiter=delimiter)
            self.rawdata = self.calc_additional_columns(self.rawdata)    
            self.rawdata = core.preprocessor.reorder_columns(self.rawdata)            

            pub.sendMessage(DATA_IMPORTED, olddata=oldrawdata, data=self.rawdata)
            windowtitle = "Raw data"
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(self.rawdata, 
                              windowtitle, 
                              'update', 
                              showcolindex=False, 
                              analyzable=True,
                              savemodified=True,
                              enableclose=False)
            self.GetEventHandler().ProcessEvent(event)        
            
            self.update_listlabel()
            #if len(files) > 1:
            #    with wx.FileDialog(self, "Save imported raw data", wildcard="txt files (*.txt)|*.txt", style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as fileDialog:    
            #        fileDialog.SetFilename('Master.txt')
            #        if fileDialog.ShowModal() == wx.ID_CANCEL:
            #            return
            #        fname = fileDialog.GetPath()   
            #        try:
            #            self.rawdata.to_csv(fname, index=False, sep='\t')
            #        except IOError:
            #            wx.MessageBox('Error saving imported raw data file %s' % fname, 'Error', wx.OK | wx.ICON_INFORMATION)
 
    
       
    
class TabFilter(wx.Panel):
    
    def __init__(self, parent, pwindow, flimanalyzer, config):
        self.flimanalyzer = flimanalyzer
        self.pwindow = pwindow
        self.config = config
        wx.Panel.__init__(self, parent)
        self.rawdata = None
        self.data = None
        self.summary_group = []
        
        self.rgrid_sel_cell = None

        self.rawdatainfo = wx.StaticText(self, -1, "No raw data", (20,20))
        self.datainfo = wx.StaticText(self, -1, "No filtered data", (20,20))
    
        self.selectall_button = wx.Button(self, wx.ID_ANY, "Select All")
        self.selectall_button.Bind(wx.EVT_BUTTON, self.SelectAll)
    
        self.deselectall_button = wx.Button(self, wx.ID_ANY, "Deselect All")
        self.deselectall_button.Bind(wx.EVT_BUTTON, self.DeselectAll)
    
        #self.filter_button = wx.Button(self, wx.ID_ANY, "Apply Filter")
        #self.filter_button.Bind(wx.EVT_BUTTON, self.OnApplyFilter)
    
        self.dropinfo_button = wx.Button(self, wx.ID_ANY, "Info on Drop")
        self.dropinfo_button.Bind(wx.EVT_BUTTON, self.InfoOnDrop)
    
        self.rlabel = wx.StaticText(self, wx.ID_ANY, "Row Filters:")
        #self.init_filtergrid()
        self.init_filterlist()
#        self.filterlist.Bind(wx.EVT_LIST_END_LABEL_EDIT,pwindow.OnFilterUpdate)
                
        self.init_seriesfilter()
        
        buttonsizer = wx.BoxSizer(wx.VERTICAL)
        buttonsizer.Add(self.selectall_button, 0, wx.EXPAND, 0)
        buttonsizer.Add(self.deselectall_button, 0, wx.EXPAND, 0)
        #buttonsizer.Add(self.filter_button, 0, wx.EXPAND, 0)
        buttonsizer.Add(self.dropinfo_button, 0, wx.EXPAND, 0)

        ssizer = wx.BoxSizer(wx.VERTICAL)
        ssizer.Add(wx.StaticText(self, -1, "Required Series"))
        ssizer.Add(self.seriesfilter, 3, wx.ALL|wx.EXPAND, 5)

        fsizer = wx.BoxSizer(wx.HORIZONTAL)       
        fsizer.Add(self.filterlist, 3, wx.ALL|wx.EXPAND, 5)
        fsizer.Add(buttonsizer)
        fsizer.Add(ssizer, 1, wx.ALL|wx.EXPAND, 5)

        boxsizer = wx.BoxSizer(wx.VERTICAL) 
        boxsizer.Add(self.rawdatainfo)
        boxsizer.Add(self.datainfo)
        boxsizer.Add(self.rlabel)
        boxsizer.Add(fsizer, 1, wx.EXPAND, 0)
        
        boxsizer.SetSizeHints(self)
        self.SetSizerAndFit(boxsizer)

        pub.subscribe(self.OnDataImported, DATA_IMPORTED)
        pub.subscribe(self.OnFiltersUpdated, FILTERS_UPDATED)
        pub.subscribe(self.OnConfigUpdated, CONFIG_UPDATED)

#    def get_summarygroups(self):
#        cats = self.flimanalyzer.get_importer().get_parser().get_regexpatterns()
#        return ['None', 'Treatment', 'FOV,Treatment', 'Treatment,FOV', 'FOV,Cell,Treatment','Treatment,FOV,Cell']
        
        
    def init_filterlist(self):
        self.filterlist = FilterListCtrl(self, style=wx.LC_REPORT)
        self.filterlist.InsertColumn(0, "Use")
        self.filterlist.InsertColumn(1, "Column")
        self.filterlist.InsertColumn(2, "Min", wx.LIST_FORMAT_RIGHT)
        self.filterlist.InsertColumn(3, "Max", wx.LIST_FORMAT_RIGHT)
        self.filterlist.InsertColumn(4, "Dropped", wx.LIST_FORMAT_RIGHT)
        self.filterlist.SetEditable([False, False, True, True, False])
        self.filterlist.Arrange()


    def init_seriesfilter(self):
        #self.seriesfilter = SeriesFilterCtrl(parent=self)
        #self.seriesfilter.setdata(self.rawdata)
        
        self.seriesfilter = SeriesFilterCtrl(self, agwStyle=(wx.TR_DEFAULT_STYLE|0x800|0x4000|0x10000)) # hide root, autocheck child and parent


    def update_seriesfilter(self):
        self.seriesfilter.DeleteAllItems()
        if self.rawdata is not None:
            self.seriesfilter.setdata(self.rawdata)        

                
    def get_filter_settings(self):
        cfgs = self.filterlist.GetData()
        # convert dict to list
        rangefilterparams = [cfgs[key].get_params() for key in cfgs]  
        # add rangefilterparams to filterparams
        filterparams = {cfg.CONFIG_RANGEFILTERS:rangefilterparams}
        return {cfg.CONFIG_FILTERS:filterparams}    


    def OnDataImported(self, olddata, data):
        print "appframe.TabFilters.OnDataImported - %d rows, %d columns" % (len(data), len(data.columns.values))
        self.update_rawdata(data)


    def OnFiltersUpdated(self, updateditems):
        rfilters = updateditems
        if rfilters is None:
            rfilters = self.filterlist.GetData()
        print "appframe.TabFilters.OnFiltersUpdated - %d Filters updated:" % len(rfilters)
        for key in rfilters:
            rfilter = rfilters[key]
            print "\t %s: %s" % (key, str(rfilter.get_parameters()))
        olddata = self.data
        filtereddata, dropsbyfilter, totaldrops, droppedindex = self.apply_filters(self.filterlist.GetData(), self.seriesfilter.GetData(), dropsonly=False, onlyselected=True)
        self.update_data(filtereddata)

        """
        self.data = self.rawdata.drop(totaldrops)
        print self.data.head()
        if droppedindex is not None:
            self.data.set_index(droppedindex.names, inplace=True, drop=False)
            print self.data.index
            print droppedindex
            currentcols = self.data.columns.tolist()
            droppedindex = droppedindex.intersection(self.data.index)
            print droppedindex
            if not droppedindex.empty:
                self.data = self.data.set_index(droppedindex.names, drop=False).drop(droppedindex)
            self.data.reset_index(inplace=True, drop=True)
            self.data = self.data[currentcols]
        print self.data.head()    
        self.update_data(self.data)
        """
        #pub.sendMessage(FILTERED_DATA_UPDATED, originaldata=olddata, newdata=self.data)
        #pub.sendMessage(DATA_UPDATED, originaldata=olddata, newdata=self.data)
        
        #cfgs = self.filterlist.GetData()
        ## convert dict to list
        #rangefilterconfigs = [cfgs[key].get_params() for key in cfgs]
        #self.config.update({cfg.CONFIG_RANGEFILTERS:rangefilterconfigs}, [cfg.CONFIG_ROOT, cfg.CONFIG_FILTERS])
        #pub.sendMessage(REQUEST_CONFIG_UPDATE, source=self, updated={cfg.CONFIG_RANGEFILTERS:rangefilterconfigs})
        

    def OnConfigUpdated(self, source, config, updated):
        print "appframe.TabFilters.OnConfigUpdated"
        if source != self and updated:
            self.config = config
            self.set_filterlist()
            for key in updated:
                print "    updated key", key
        
                
    def SelectAll(self, event):
        self.filterlist.check_items(self.filterlist.GetData(),True)

        
    def DeselectAll(self, event):
        self.filterlist.check_items(self.filterlist.GetData(),False)


#    def init_filtergrid(self):
#        self.rgrid = wx.grid.Grid(self, -1)
#        self.filtertable = FilterTable(self.config[CONFIG_FILTERS])
#        self.rgrid.SetTable(self.filtertable,takeOwnership=True)
#        self.rgrid.SetCellAlignment(1,4,wx.ALIGN_RIGHT,wx.ALIGN_CENTRE,)
#        self.rgrid.SetRowLabelSize(0)
#        self.rgrid.SetColFormatBool(0)
#        self.rgrid.SetColFormatFloat(2,precision=3)
#        self.rgrid.SetColFormatFloat(3,precision=3)
#        self.rgrid.SetSelectionMode(wx.grid.Grid.wxGridSelectCells)
#        self.rgrid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.onSingleSelect)
#        self.rgrid.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.onDragSelection)
               
        

#    def OnGroupChanged(self, event):
#        groupindex = event.GetSelection()
#        groupstr = self.get_summarygroups()[groupindex]
#        if groupstr == 'None':
#            self.summary_group = []
#        else:    
#            self.summary_group = groupstr.split(',')
#        print self.summary_group
        
        
#    def onSingleSelect(self, event):
#        """
#        Get the selection of a single cell by clicking or 
#        moving the selection with the arrow keys
#        """
#        self.rgrid_sel_cell = (event.GetRow(),event.GetCol())
#        event.Skip()
        
    
#    def onDragSelection(self, event):
#        """
#        Gets the cells that are selected by holding the left
#        mouse button down and dragging
#        """
#        if self.rgrid.GetSelectionBlockTopLeft():
#            self.rgrid_sel_cell = self.rgrid.GetSelectionBlockTopLeft()[0]
#            bottom_right = self.rgrid.GetSelectionBlockBottomRight()[0]
    
    def update_rawdata(self, rawdata, applyfilters=True):
        self.rawdata = rawdata
        label = "Raw Data:"
        if self.rawdata is not None:
            label += " %d rows, %d columns" % (self.rawdata.shape[0], self.rawdata.shape[1])
        self.rawdatainfo.SetLabel(label)
        #self.update_data(None)

        categories = list(self.rawdata.select_dtypes(['category']).columns.values)
        print 'COLUMNS WITH CATEGORY AS DTYPE', categories
        if 'Category' in categories:
            print 'CATEGORY VALUES:', sorted(self.rawdata['Category'].unique())
        self.update_seriesfilter()
        self.set_filterlist()
        if applyfilters:
            self.apply_filters(self.filterlist.GetData(), self.seriesfilter.GetData(), dropsonly=False)
        
         
    def update_data(self, data):
        olddata = self.data
        self.data = data
        label = "Filtered Data:"
        if self.data is not None:
            label += " %d rows, %d columns" % (self.data.shape[0], self.data.shape[1])
        print "appframe.TabFilter.update_data:", self.data.shape[0], "rows" 
        self.datainfo.SetLabel(label)    
        pub.sendMessage(FILTERED_DATA_UPDATED, originaldata=olddata, newdata=self.data)
        pub.sendMessage(DATA_UPDATED, originaldata=olddata, newdata=self.data)        

        windowtitle = "Filtered data"
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(self.data, 
                          windowtitle, 
                          'update', 
                          showcolindex=False, 
                          analyzable=True,
                          savemodified=True,
                          enableclose=False)
        self.GetEventHandler().ProcessEvent(event)        

    
    def set_filterlist(self, dropped={}):
        data = self.rawdata
        if data is None:
            return
        datacols =  data.select_dtypes(include=[np.number])
        datacols.columns.values.tolist()
        rangefiltercfgs = self.config.get(cfg.CONFIG_RANGEFILTERS)
        filternames = [fc['name'] for fc in rangefiltercfgs]
        for key in datacols.columns.values.tolist():
            if key not in filternames:
                print "key", key, "not found. creating default"        
                rangefiltercfgs.append(RangeFilter(key,0,100, selected=False).get_params())
            else:
                print "key", key, "FOUND."
        currentfilters = {rfcfg['name']:RangeFilter(params=rfcfg) for rfcfg in rangefiltercfgs if rfcfg['name'] in datacols.columns.values.tolist()}        
        print "\n******\n",currentfilters        
        self.filterlist.SetData(currentfilters, dropped, ['Use', 'Column', 'Min', 'Max', 'Dropped'])        


    def apply_filters(self, rangefilters, seriesfilter, onlyselected=True, setall=False, dropsonly=False):
        if rangefilters is None:
            return
        analyzer = self.flimanalyzer.get_analyzer()
        analyzer.set_rangefilters(rangefilters)
        analyzer.set_seriesfilter(seriesfilter)
        #self.data = self.rawdata.copy()
        filtereddata, usedfilters, skippedfilters, no_droppedrows, droppedindex = analyzer.apply_filter(self.rawdata,dropna=True,onlyselected=onlyselected,inplace=False, dropsonly=dropsonly)
        print "TabFilter.applyfilters, dropsonly=%s" % str(dropsonly)
        print "\trawdata: rawdata.shape[0]=%d, dropped overall %d rows" % (self.rawdata.shape[0],no_droppedrows)
        print "\tdata: data.shape[0]=%d" % (filtereddata.shape[0])
        
        droppedrows = {f[0]:f[2] for f in usedfilters}
        if setall:
            self.filterlist.SetDroppedRows(droppedrows)
        else:    
            self.filterlist.UpdateDroppedRows(droppedrows)
        """
        if not dropsonly:
            # wx.PostEvent(self.pwindow, ApplyFilterEvent(data=self.data))
            self.update_data(data)
        """    
        return filtereddata, droppedrows, self.filterlist.get_total_dropped_rows(), droppedindex
        
        
    def InfoOnDrop(self, event):
        if self.rawdata is None:
            wx.MessageBox('No data imported.', 'Error', wx.OK | wx.ICON_INFORMATION)
            return
        selidx = self.filterlist.GetFirstSelected()
        if selidx == -1:
            wx.MessageBox('Select a single row in the Filters table.', 'Error', wx.OK | wx.ICON_INFORMATION)  
            return
        # get selected row in Filters table
        rowkey = self.filterlist.GetItem(selidx,self.filterlist.get_key_col()).GetText()    
        rows = self.filterlist.GetDroppedRows(rowkey)
        rowdata = self.rawdata.iloc[rows]
        rpatterns = self.flimanalyzer.get_importer().get_reserved_categorycols()
        cols = [c for c in rpatterns if c in rowdata.columns.values]
        cols.extend(['Directory','File',rowkey])
        rowdata = core.preprocessor.reorder_columns(rowdata[cols])
        windowtitle = "%s, dropped rows: %d" % (rowkey, len(rows))
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(rowdata, 
                          windowtitle, 
                          'createnew', 
                          showcolindex=False, 
                          analyzable=False,
                          savemodified=False)
        self.GetEventHandler().ProcessEvent(event)        
                                    



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
    
        self.show_button = wx.Button(self, wx.ID_ANY, "Show Analysis")
        self.show_button.Bind(wx.EVT_BUTTON, self.ShowAnalysis)
    
        self.save_button = wx.Button(self, wx.ID_ANY, "Save Analysis")
        self.save_button.Bind(wx.EVT_BUTTON, self.SaveAnalysis)
    
#        self.update_datachoices({'Raw data':self.rawdata, 'Filtered data':self.data}, True)
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
        buttonsizer.Add(self.save_button, 0, wx.EXPAND|wx.ALL, 5)

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
        print "appframe.TabAnalysis.OnNewDataWindow - %s" % (label)
        if frame.is_analyzable():
            self.update_datachoices({label:frame}, True)
            self.windows[label] = frame
            self.update_analysislist()
            currentdata,label = self.get_currentdata()
            self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
            print "CURRENT DATA", label, self.datachoices_combo.GetStringSelection()
        if label == "Raw data":
            if self.rawdata is not None:
                label += " %d rows, %d columns" % (self.rawdata.shape[0], self.rawdata.shape[1])
            self.rawdatainfo.SetLabel(label)
        elif label == "Filtered data":    
            if self.rawdata is not None:
                label += " %d rows, %d columns" % (self.data.shape[0], self.data.shape[1])
            self.datainfo.SetLabel(label)


    def OnClosingDataWindow(self, data, frame):
        print "appframe.TabAnalysis.OnClosingDataWindow - %s" % (frame.GetLabel())
        if self.windows.get(frame.GetLabel()):
            del self.windows[frame.GetLabel()]
            self.update_datachoices({frame.GetLabel():frame}, False)
            currentdata,_ = self.get_currentdata()
            self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
            self.update_analysislist()

        
    def OnDataImported(self, olddata, data):
        print "appframe.TabAnalysis.OnDataImported - %d rows, %d columns" % (len(data), len(data.columns.values))
        self.update_rawdata(data)


    def OnFiltersUpdated(self, updateditems):
        print "appframe.TabAnalysis.OnFiltersUpdated - %d " % (len(updateditems))
        self.update_rangefilters(updateditems)


    def OnFilteredDataUpdated(self, originaldata, newdata):
        print "appframe.TabAnalysis.OnFilteredDataUpdated"
        self.update_data(newdata)

        
    def OnConfigUpdated(self, source, config, updated):
        print "appframe.TabAnalysis.OnConfigUpdated"
        if source != self and updated:
            for key in updated:
                print "    updated key", key
            self.config = config    
            self.update_analysislist()

        
    def OnRoiGroupingChanged(self, event):
        groupstr = self.roigroup_combo.GetStringSelection()
        print "appframe.TabAnalysis.OnRoiGroupingChanged.GROUPSTR=", groupstr
        if groupstr == 'None':
            self.sel_roigrouping = []
            self.ctrlgroup_label.SetLabelText('Reference: None')
        else:    
            self.sel_roigrouping = groupstr.split(', ')
            self.ctrlgroup_label.SetLabelText('Reference: %s' % self.sel_roigrouping[0])
        print self.sel_roigrouping
        self.update_sel_ctrlgroup()

        
    def OnAnalysisTypeChanged(self, event):
        groupindex = event.GetSelection()
        print "appframe.TabAnalysis.OnAnalysisTypeChanged: %s " % self.get_analysistypes()[groupindex]

    
    def OnDataWindowRenamed(self, original, new, data):
        print "appframe.TabAnalysis.OnDataWindowRenamed - %s --> %s" % (original, new)
        if self.windows.has_key(original):
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
        print "appframe.TabAnalysis.OnDataChoiceChanged: %s, %s" % (datalabel, str(currentdata is not None))
        self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))
        self.update_analysislist()
        if self.windows.get(datalabel):
            self.windows[datalabel].Raise()

                
    def OnCtrlSelChanged(self, event):
        groupindex = event.GetSelection()
        print "appframe.TabAnalysis.OnCtrlSelChanged: %s " % self.get_ctrlgroupchoices()[groupindex]

                
    def ShowAnalysis(self, event):
        atype = self.analysistype_combo.GetStringSelection()
        print 'appframe.TabAnalysis.ShowAnalysis: %s' % atype
        if atype == 'Summary Tables':
            self.show_summary()
        elif atype == 'Mean Bar Plots':
            if len(self.sel_roigrouping) < 10:
                self.show_meanplots()
        elif atype == 'Box Plots':
            if len(self.sel_roigrouping) < 10:
                self.show_boxplots()
        elif atype == 'Frequency Histograms':
            if len(self.sel_roigrouping) < 10:
                self.show_freqhisto()
        elif atype == 'KDE Plots':
            if len(self.sel_roigrouping) < 10:
                self.show_kdeplots()
        elif atype == 'Scatter Plots':
            if len(self.sel_roigrouping) < 10:
                self.show_scatterplots()
        elif atype == 'Categorize':
            self.show_categorized_data()
        elif atype == 'Principal Component Analysis':
            self.show_pca_data()

        
    def SaveAnalysis(self, event):
        atype = self.analysistype_combo.GetStringSelection()
        print 'TabAnalysis.SaveAnalysis: %s' % atype
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
                print "Using GetViewData"
                return self.availabledata[selection].GetViewData(), selection
            print "COULD NOT FIND %s in existing windows" % selection
            print self.availabledata
        if selection == 'Raw data':
            if self.rawdata is not None:
                return self.rawdata, 'Raw'
        elif selection == 'Filtered data':
            if self.data is not None:
                return self.data, 'Filtered'
        return None, selection


    def update_rangefilters(self, rfilters):
        print "AnalysisTab.update_rangefilters: %d filters to update" % len(rfilters)
        analysisconfig = self.config.get(cfg.CONFIG_HISTOGRAMS)
        for key in rfilters:
            rfilter = rfilters[key]
            print "\trfilter.get_parameters:", rfilter.get_parameters()
            low = rfilter.get_rangelow()
            high = rfilter.get_rangehigh()
            aconfig = analysisconfig.get(rfilter.get_name())
            if aconfig is None:
                print "\tnot found:", rfilter.get_name()
                analysisconfig[rfilter.get_name()] = [low,high,100]
            else:                
                print "\told:", rfilter.get_name(), analysisconfig[rfilter.get_name()]
                analysisconfig[rfilter.get_name()][0] = low
                analysisconfig[rfilter.get_name()][1] = high
            print "\tnew:", rfilter.get_name(), analysisconfig[rfilter.get_name()]
            self.analysislist.SetRow(rfilter.get_name(), analysisconfig[rfilter.get_name()])


    def update_analysislist(self):
        print "TabAnalysis.update_analysislist"
        data, label = self.get_currentdata()
        if data is None:
            return
        datacols =  data.select_dtypes(include=[np.number])
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
        
        
    def update_rawdata(self, rawdata):
        print "appframe.TabAnalysis.update_rawdata"
        print "\trawdata: rows=%d, cols=%d" % (rawdata.shape[0], rawdata.shape[1])
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
        print "CURRENT DATA", label, self.datachoices_combo.GetStringSelection()
        if currentdata is not None:
            self.set_roigroupings(list(currentdata.select_dtypes(['category']).columns.values))



    def update_data(self, data):
        print "appframe.TabAnalysis.update_data"
#        print "\traw data: rows=%d, cols=%d" % (self.rawdata.shape[0], self.rawdata.shape[1])
        self.data = data
        #frame = PandasFrame(self, 'Filtered data', data=self.data)
        label = "Filtered Data:"
        # *** self.update_datachoices({'Filtered data':self.data}, add=(self.data is not None))
        if self.data is not None:
            print "\tdata: rows=%d, cols=%d" % (self.data.shape[0], self.data.shape[1])
            label += " %d rows, %d columns" % (self.data.shape[0], self.data.shape[1])
#            label += " %d rows, %d columns" % (self.rawdata.shape[0] - self.filterlist.get_total_dropped_rows(), self.data.shape[1])
        else:
            print "\tDATA IS NONE"
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
        print "appframe.TabAnalysis.update_datachoices", [t for t in self.availabledata]
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
            print "CATEGORIES:", categories
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
        print "appFrame.TabAnalysis.get_checked_cols: SELECTED", selcols
        return selcols
#        selindices = self.analysislist.get_checked_indices()
#        datacols =  data.select_dtypes(include=[np.number])
#        numcols = [datacols.columns.values.tolist()[index] for index in selindices]
#        return numcols
    
        
    def create_freq_histograms(self, data, label, groups):
        histos = {}
        if not gui.dialogs.check_data_msg(data):
            return {}
        cols = self.get_checked_cols(data)
        if cols is None or len(cols) == 0:
            wx.MessageBox('No Measurements selected.', 'Warning', wx.OK)
            return {}
        for header in sorted(cols):
            hconfig = cols[header]
#            hconfig = self.config[CONFIG_HISTOGRAMS].get(header)
            mrange = (data[header].min(), data[header].max())
            if hconfig is None:
                bins = 100
            else:
                if self.datachoices_combo.GetStringSelection() == self.get_datachoices()[1]:
                    mrange = (hconfig[0],hconfig[1])
                bins = hconfig[2]
            print "\tcreating frequency histogram plot for %s with %d bins" % (header, bins)     
            #categories = [col for col in self.flimanalyzer.get_importer().get_parser().get_regexpatterns()]
#            fig, ax = MatplotlibFigure()
            #fig = plt.figure(FigureClass=MatplotlibFigure)
            #ax = fig.add_subplot(111)
            fig, ax = plt.subplots()
            binvalues, binedges, groupnames, fig, ax = core.plots.histogram(ax, data, header, titlesuffix=label, groups=groups, normalize=100, range=mrange, stacked=False, bins=bins, histtype='step')                
            histos[header] = (binvalues, binedges, groupnames, fig,ax)
        return histos

        
    def create_meanbarplots(self, data, groups):
        bars = {}
        if not gui.dialogs.check_data_msg(data):
            return {}
        cols = [c.decode('utf-8') for c in self.get_checked_cols(data)]
        if cols is None or len(cols) == 0:
            wx.MessageBox('No measurements selected.', 'Warning', wx.OK)
            return {}
        for col in sorted(cols):
            print "\tcreating mean bar plot for %s" % (col)
            fig, ax = plt.subplots()
            fig, ax = core.plots.grouped_meanbarplot(ax, data, col, groups=groups)
            bars[col] = (fig,ax)
        return bars


    def create_boxplots(self, data, groups):
        bars = {}
        if not gui.dialogs.check_data_msg(data):
            return {}
        cols = [c for c in self.get_checked_cols(data)]
        if cols is None or len(cols) == 0:
            wx.MessageBox('No measurements selected.', 'Warning', wx.OK)
            return {}
        for col in sorted(cols):
            print "\tcreating box plot for %s" % (col)
            fig, ax = plt.subplots()
            fig, ax = core.plots.grouped_boxplot(ax, data, col, groups=groups, grid=False, rot=90, showmeans=True, showfliers=True, whis=[5,95])#whis=float("inf")
            bars[col] = (fig,ax)
        return bars


    def create_kdeplots(self, data, groups):
        kdes = {}
        if not gui.dialogs.check_data_msg(data):
            return {}
        cols = self.get_checked_cols(data)
        if cols is None or len(cols) < 1:
            wx.MessageBox('Select at least 1 measurements.', 'Warning', wx.OK)
            return {}
        for header in sorted(cols):
            hconfig = cols[header]
#            hconfig = self.config[CONFIG_HISTOGRAMS].get(header)
            if hconfig is None:
                bins = 100
                minx = None
                maxx = None
            else:
                bins = hconfig[2]
                minx = hconfig[0]
                maxx = hconfig[1]
            print "\tcreating kde plot for %s, bins=%s" % (str(header), str(bins))
            fig, ax = plt.subplots()
            fig, ax = core.plots.grouped_kdeplot(ax, data, header, groups=groups, hist=False, bins=bins, kde_kws={'clip':(hconfig[0], hconfig[1])})
            ax.set_xlim(minx, maxx)
            kdes[header] = (fig,ax)
        return kdes


    def create_scatterplots(self, data, groups):
        scatters = {}
        if not gui.dialogs.check_data_msg(data):
            return {}
        cols = [c for c in self.get_checked_cols(data)]
        if cols is None or len(cols) < 2:
            wx.MessageBox('Select at least 2 measurements.', 'Warning', wx.OK)
            return {}
        combs = itertools.combinations(cols, 2)
        for comb in sorted(combs):
            print "\tcreating scatter plot for %s" % (str(comb))
            fig, ax = plt.subplots()
            fig, ax = core.plots.grouped_scatterplot(ax, data, comb, groups=groups, marker='o', s=10)#, facecolors='none', edgecolors='r')
            scatters[comb] = (fig,ax)
        return scatters

    
    def create_pca(self, data):
        if not gui.dialogs.check_data_msg(data):
            return
        cols = [c for c in self.get_checked_cols(data)]
        if cols is None or len(cols) < 2:
            wx.MessageBox('Select at least 2 measurements.', 'Warning', wx.OK)
            return
        n = ''
        dlg = wx.TextEntryDialog(self, 'Specifiy PCA components to retain:'\
                                 '\n\tleave empty:   retain all PCA components.'\
                                 '\n\t0.0 < n < 1.0 (float):   retain PCA components that explain specified fraction of observed variance.'\
                                 '\n\t1 <= n <= %d (integer):   retain first n PCA components.' % len(cols),'PCA Configuration')
        dlg.SetValue(n)
        while True:
            if dlg.ShowModal() != wx.ID_OK:
                break
            entry = dlg.GetValue()
            if entry == '':
                n = None
            else:    
                try:
                    n = float(entry)
                    n = int(entry)
                except:
                    pass
            if n is None or (n > 0 and ((isinstance(n, float) and n <1.0) or (isinstance(n, int) and n >= 1 and n <= len(cols)))):
                seed = np.random.randint(10000000)
                return self.flimanalyzer.get_analyzer().pca(data, cols, explainedhisto=True, random_state=seed, n_components=n)
        return
    

    def create_summaries(self, data, titleprefix='Summary'):
        if not gui.dialogs.check_data_msg(data):
            return {}
        # create list of col dictionary headers
        cols = [c for c in self.get_checked_cols(data)]
        if cols is None or len(cols) == 0:
            wx.MessageBox('No Measurements selected.', 'Warning', wx.OK)
            return {}
        
        agg_functions = sorted([funcname for funcname in self.flimanalyzer.get_analyzer().get_analysis_function('Summary Tables')['functions']])
        dlg = SelectGroupsDlg(self, title='Summary: aggregation functions', groups=agg_functions) 
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return
        agg_functions = dlg.get_selected()        
        print agg_functions
        if data.columns.nlevels != 1:
            cols = [tuple(col.split(',')) for col in cols]
        summaries = self.flimanalyzer.get_analyzer().summarize_data(titleprefix, data, cols, self.sel_roigrouping, aggs=agg_functions)
        return summaries
        
    
    def create_categorized_data_global(self, data, col, bins=[-1, 1], labels='Cat 1', normalizeto='', grouping=[], binby='xfold'):
        if not grouping or len(grouping) == 0:
            return
        controldata = data[data[grouping[0]] == normalizeto]
        grouped = controldata.groupby(grouping[1:])
        categorydef = self.config.get(cfg.CONFIG_CATEGORIES).get(col)
        if not categorydef:
            print "Using default categories"
            bins = [1.0, 2.0]
            labels = ['cat 1']
        else:
            bins = categorydef[0]
            labels = categorydef[1]
        series = data[col]
        if normalizeto and len(normalizeto) > 0:
            median = grouped[col].median()
            print median.describe()
            median_of_median = median.median()
            print "MEDIAN_OF_MEDIAN: %s %f" % (col, median_of_median)
            xfold_series = series.apply(lambda x: x / median_of_median).rename('x-fold norm ' + col)
            plusminus_series = series.apply(lambda x: x - median_of_median).rename('+/- norm ' + col)
            all_catseries.append(xfold_series)
            all_catseries.append(plusminus_series)
            if binby == 'plusminus':
                catseries = pd.cut(plusminus_series, bins=bins, labels=labels).rename('cat %s (+/-)' % col)
            else:
                catseries = pd.cut(xfold_series, bins=bins, labels=labels).rename('cat %s (x-fold)' % col)
        else:
            catseries = pd.cut(series, bins=bins, labels=labels).rename('cat ' + col)            
        return catseries
    
    
    def save_summary(self):
        currentdata,label = self.get_currentdata()        
        summaries = self.create_summaries(currentdata)
        if summaries is not None and len(summaries) > 0:
            for title in summaries:
                summary_df = summaries[title].reset_index()
                gui.dialogs.save_dataframe(self, "Save summary data", summary_df, '%s-%s.txt' % (title,label), saveindex=False)
       
        
    def show_summary(self):
        currentdata,label = self.get_currentdata()
        summaries = self.create_summaries(currentdata)
        for title in summaries:
            df = summaries[title]
            df = df.reset_index()
            windowtitle = "%s: %s" % (title, label)
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(df, 
                               windowtitle, 
                               'createnew', 
                               showcolindex=False)
            self.GetEventHandler().ProcessEvent(event)        
            

    def show_meanplots(self):
        currentdata, label = self.get_currentdata()
        bars = self.create_meanbarplots(currentdata,self.sel_roigrouping)
        for b in sorted(bars):
            fig,ax = bars[b]
            title = "Bar plot: %s  %s" % (ax.get_title(), label)
            fig.canvas.set_window_title(title)
            event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
            event.SetEventInfo(fig, title, 'createnew')
            self.GetEventHandler().ProcessEvent(event)        
        
        
    def save_meanplots(self):
        currentdata, label = self.get_currentdata()
        bars = self.create_meanbarplots(currentdata,self.sel_roigrouping)
        if len(bars) == 0:
            return
        for b in sorted(bars):
            fig,ax = bars[b]
            gui.dialogs.save_figure(self, 'Save Mean Bar Plot', fig, 'Bar-%s-%s.png' % (ax.get_title(), label), legend=ax.get_legend())
                
     
    def show_boxplots(self):
        currentdata, label = self.get_currentdata()
        bars = self.create_boxplots(currentdata, self.sel_roigrouping)
        for b in sorted(bars):
            fig,ax = bars[b]
            title = "Box plot: %s - %s" % (ax.get_title(), label)
            fig.canvas.set_window_title(title)
            event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
            event.SetEventInfo(fig, title, 'createnew')
            self.GetEventHandler().ProcessEvent(event)        
        
        
    def save_boxplots(self):
        currentdata, label = self.get_currentdata()
        bars = self.create_boxplots(currentdata,self.sel_roigrouping)
        if len(bars) == 0:
            return
        for b in sorted(bars):
            fig,ax = bars[b]
            gui.dialogs.save_figure(self, 'Save Box Plot', fig, 'Box-%s-%s.png' % (ax.get_title(), label), legend=ax.get_legend())
                
     
    def show_scatterplots(self):
        currentdata, label = self.get_currentdata()
        splots = self.create_scatterplots(currentdata, self.sel_roigrouping)
        for sp in sorted(splots):
            fig,ax = splots[sp]
            title = "Scatter plot: %s - %s" % (ax.get_title(), label)
            fig.canvas.set_window_title(title)
            event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
            event.SetEventInfo(fig, title, 'createnew')
            self.GetEventHandler().ProcessEvent(event)        
        
        
    def save_scatterplots(self):
        currentdata, label = self.get_currentdata()
        splots = self.create_scatterplots(currentdata,self.sel_roigrouping)
        if len(splots) == 0:
            return
        for sp in sorted(splots):
            fig,ax = splots[sp]
            gui.dialogs.save_figure(self, 'Save Scatter Plot', fig, 'Scatter-%s-%s.png' % (ax.get_title(), label), legend=ax.get_legend())
                
     
    def show_kdeplots(self):
        currentdata, label = self.get_currentdata()
        kdes = self.create_kdeplots(currentdata, self.sel_roigrouping)
        if kdes is None:
            return
        for kde in kdes:
            fig, ax = kdes[kde]
            title = "KDE: %s - %s" % (ax.get_title(), label)
            fig.canvas.set_window_title(title)
            event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
            event.SetEventInfo(fig, title, 'createnew')
            self.GetEventHandler().ProcessEvent(event)        


    def save_kdeplots(self):
        currentdata, label = self.get_currentdata()
        kdeplots = self.create_kdeplots(currentdata, self.sel_roigrouping)
        if len(kdeplots) == 0:
            return
        for kde in sorted(kdeplots):
            fig,ax = kdeplots[kde]
            gui.dialogs.save_figure(self, 'Save Scatter Plot', fig, 'Scatter-%s-%s.png' % (ax.get_title(), label), legend=ax.get_legend())
                
     
    def show_freqhisto(self):
        currentdata, label = self.get_currentdata()
        histos = self.create_freq_histograms(currentdata, label,self.sel_roigrouping)
        if histos is None:
            return
        for h in histos:
            binvalues, binedges, groupnames, fig, ax = histos[h]
            title = "Histogram: %s - %s" % (ax.get_title(), label)
            fig.canvas.set_window_title(title)
            event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
            event.SetEventInfo(fig, title, 'createnew')
            self.GetEventHandler().ProcessEvent(event)        
#            fig.show()
            
#            frame = MatplotlibFrame(self, title, fig, ax)
#            frame.Show()
        
        
    def save_freqhisto(self):
        currentdata, label = self.get_currentdata()
        histos = self.create_freq_histograms(currentdata, label, self.sel_roigrouping)
        if histos is None:
            return
        for h in histos:
            binvalues, binedges, groupnames, fig, ax = histos[h]
            gui.dialogs.save_figure(self, 'Save Frequency Histogram Figure', fig, 'Histo-%s.png' % ax.get_title())
            bindata = core.plots.bindata(binvalues,binedges, groupnames)
            bindata = bindata.reset_index()
            gui.dialogs.save_dataframe(self, 'Save Frequency Histogram Data Table', bindata, 'Histo-%s.txt' % ax.get_title(), saveindex=False)
                
    
    def create_categorized_data(self,category_colheader='Category'):
        currentdata, label = self.get_currentdata()
        cols = self.get_checked_cols(currentdata)
        ctrl_label = self.ctrlgroup_combo.GetStringSelection()
        grouping = self.sel_roigrouping

        results = {}
        if not gui.dialogs.check_data_msg(currentdata):
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
        print "SPLIT GROUPING",split_grouping
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
        gui.dialogs.save_dataframe(self, "Save Master file with new categories", joineddata, "Master-allcategories-%s.txt" % label, saveindex=False)
        gui.dialogs.save_dataframe(self, "Save categorization summary", cat_med, "Categorized-%s-%s.txt" % (col,label), saveindex=False)
        for split_name in sorted(mediansplits):
            median_split = mediansplits[split_name]
            split_label = '-'.join(split_name)
            split_grouping = [catcol]
            split_grouping.extend(self.sel_roigrouping[:(self.pivot_level-1)])
            print "SPLITGROUPING", split_grouping, "SPLITNAME", split_name, "SPLITLABEL", split_label
            gui.dialogs.save_dataframe(self, "Save grouped medians for Cat %s: %s" % (split_label, label), median_split, "Grouped-Medians-Cat_%s-%s.txt" % (split_label,label), saveindex=False)
            
            master_split = joineddata.set_index(split_grouping).loc[split_name,:].reset_index()
            gui.dialogs.save_dataframe(self, "Save master data for Cat %s: %s" % (split_label, label), master_split, "Master-Cat_%s-%s.txt" % (split_label,label), saveindex=False)
                
             
    def show_pca_data(self):
        currentdata, label = self.get_currentdata()
        pca_results = self.create_pca(currentdata)
        if pca_results is None:
            return
        pca_data, pca_explained_var_ratio, pca_explained_histo_ax = pca_results

        windowtitle = "PCA var ratio: %s" % label
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(pca_explained_var_ratio, 
                           windowtitle, 
                           'createnew', 
                           showcolindex=False,
                           analyzable=False)
        self.GetEventHandler().ProcessEvent(event)        

        pca_data = pca_data.reset_index()
        windowtitle = "PCA: %s" % label
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(pca_data, 
                           windowtitle, 
                           'createnew', 
                           showcolindex=False)
        self.GetEventHandler().ProcessEvent(event)   
        
        windowtitle = "PCA var ratio - Bar plot: %s" % label
        fig = pca_explained_histo_ax.get_figure()
        fig.canvas.set_window_title(windowtitle)
        event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
        event.SetEventInfo(fig, windowtitle, 'createnew')
        self.GetEventHandler().ProcessEvent(event)        

                        
        
    def save_pca_data(self):
        currentdata, label = self.get_currentdata()
        pca_results = self.create_pca(currentdata)
        if pca_results is None:
            return
        pca_data, pca_explained_var_ratio, pca_explained_histo_ax = pca_results
        gui.dialogs.save_dataframe(self, 'Save PCA ', pca_data, 'PCA-%s.txt' % label, saveindex=False)
        gui.dialogs.save_dataframe(self, 'Save PCA explained variance', pca_explained_var_ratio, 'PCA-var-ratio-%s.txt' % label, saveindex=False)
        gui.dialogs.save_figure(self, 'Save PCA explained variance - Bar plot', pca_explained_histo_ax.get_figure(), 'PCA-var-ratio-bar-%s.png' % pca_explained_histo_ax.get_title())
    
    
class AppFrame(wx.Frame):
    
    def __init__(self, flimanalyzer, config=None):
        self.flimanalyzer = flimanalyzer
        if config:
            self.config = config
        else:
            self.config = cfg.Config()
            self.config.create_default()
        #self.rawdata = None
        #self.data = None
        #self.filtereddata = None
        self.windowframes = {}
        
        super(AppFrame,self).__init__(None, wx.ID_ANY,title="FLIM Data Analyzer")#, size=(600, 500))
                
        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        exitmenuitem = filemenu.Append(wx.NewId(), "Exit","Exit the application")
        self.windowmenu = wx.Menu()
        closeallitem = self.windowmenu.Append(wx.NewId(), "Close all windows")
        self.windowmenu.AppendSeparator()
        settingsmenu = wx.Menu()
        loadsettingsitem = settingsmenu.Append(wx.NewId(), "Load settings...")
        savesettingsitem = settingsmenu.Append(wx.NewId(), "Save settings...")
        menubar.Append(filemenu, "&File")
        menubar.Append(settingsmenu, "&Settings")
        menubar.Append(self.windowmenu, "&Window")
        self.SetMenuBar(menubar)        
        self.Bind(wx.EVT_MENU, self.OnExit, exitmenuitem)
        self.Bind(wx.EVT_MENU, self.OnLoadSettings, loadsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnSaveSettings, savesettingsitem)
        self.Bind(wx.EVT_MENU, self.OnCloseAll, closeallitem)
 
        # Create a panel and notebook (tabs holder)
#        panel = wx.Panel(self)
#        nb = wx.Notebook(panel)
        nb = wx.Notebook(self)
 
        # Create the tab windows
        self.importtab = TabImport(nb, self, self.flimanalyzer, self.config)
        self.filtertab = TabFilter(nb, self, self.flimanalyzer, self.config)
        self.analysistab = TabAnalysis(nb, self, self.flimanalyzer, self.config)
 
        # Add the windows to tabs and name them.
        nb.AddPage(self.importtab, "Import")
        nb.AddPage(self.filtertab, "Filter")
        nb.AddPage(self.analysistab, "Analyze")
        
#        self.update_tabs()
 
        # Set noteboook in a sizer to create the layout
        sizer = wx.BoxSizer()
        sizer.Add(nb, 1, wx.EXPAND)
        
        sizer.SetSizeHints(self)
        self.SetSizerAndFit(sizer)
        

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
        pub.subscribe(self.OnClosingDataWindow, CLOSING_DATA_WINDOW)
        pub.subscribe(self.OnRequestRenameDataWindow, REQUEST_RENAME_DATA_WINDOW)
        #pub.subscribe(self.OnNewPlotWindow, NEW_PLOT_WINDOW)
        
    
#    def OnNewDataWindow(self, data, frame):
#        title = frame.GetLabel()
#        print "appframe.OnNewDataWindow - %s" % (title)
#        self.windowframes[frame.GetLabel()] = frame
#        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
#        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)

    def OnLoadSettings(self, event):
        print "appframe.OnLoadSettings"
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
        print "appframe.OnSaveSettings"
        rootconfig = {}
        rootconfig.update(self.importtab.get_import_settings())
        rootconfig.update(self.importtab.get_preprocess_settings())
        rootconfig.update(self.filtertab.get_filter_settings())
        rootconfig.update(self.analysistab.get_analysis_settings())
        self.config.update({cfg.CONFIG_ROOT:rootconfig})

        print self.config.get()
        with wx.FileDialog(self, "Save Configuration file", wildcard="json files (*.json)|*.json",
                       style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT| wx.FD_CHANGE_DIR) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            configfile = fileDialog.GetPath()
            self.config.write_to_json(configfile)
        
    
    def append_window_to_menu(self, title, window):
        self.windowframes[title] = window
        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)
        
        
    def remove_window_from_menu(self, title):
        for mitem in self.windowmenu.GetMenuItems():
            if mitem.GetLabel() == title:
                self.windowmenu.Remove(mitem.GetId())
                del self.windowframes[title]
                return True
        return False
    
        
    def remove_figure_from_menu(self, figure):
        for mitem in self.windowmenu.GetMenuItems():
            mlabel = mitem.GetLabel()
            if self.windowframes.has_key(mlabel) and self.windowframes[mlabel] == figure:
                self.windowmenu.Remove(mitem.GetId())
                del self.windowframes[mitem.GetLabel()]
                return True
        return False
    
    
    def OnDataWindowRequest(self, event):
        data = event.GetData()
        action = event.GetAction()
        title = event.GetTitle()
        print "appframe.OnDataWindowRequest - %s: %s" % (title, action)
        if action == 'update':
            frame = self.windowframes.get(title)
            if frame:
                frame = self.windowframes[title]
                frame.SetData(data)
            else:
                action = 'createnew'
        if action == 'createnew':
            title = self.unique_window_title(title)
            frame = PandasFrame(self, 
                                title, 
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
            if mitem.GetLabel() == original:
                mitem.SetItemLabel(title)
                del self.windowframes[original]
                self.windowframes[title] = data
                pub.sendMessage(RENAMED_DATA_WINDOW, original=original, new=title, data=data)
                return
        
        
    def OnClosingDataWindow(self, data, frame):
        title = frame.GetLabel()
        print "appframe.OnClosingDataWindow - %s" % (title)
        self.remove_window_from_menu(title)

    
    def OnPlotWindowRequest(self, event):
        figure = event.GetFigure()
        title = self.unique_window_title(event.GetTitle())
        figure.canvas.set_window_title(title)
        action = event.GetAction() 
        print "appframe.OnPlotWindow - %s: %s" % (title, action)
        if action == 'createnew':
            figure.show()
            self.append_window_to_menu(title, figure)
            figure.canvas.mpl_connect('close_event', self.OnClosingPlotWindow)

        
#    def OnNewPlotWindow(self, figure):
#        title = figure.get_axes()[0].get_title()
#        print "appframe.OnNewPlotWindow - %s, %s" % (title, figure.canvas.GetName())
#        figure.canvas.mpl_connect('close_event', self.OnClosingPlotWindow)
#        self.windowframes[title] = figure.canvas
#        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
#        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)


    def OnClosingPlotWindow(self, event):
        print "appframe.OnClosingPlotWindow"
        self.remove_figure_from_menu(event.canvas.figure)
        
        
    def OnWindowSelectedInMenu(self, event):
        itemid = event.GetId()
        menu = event.GetEventObject()
        mitem = menu.FindItemById(itemid)
        if self.windowframes.get(mitem.GetLabel()):
            window = self.windowframes[mitem.GetLabel()]
            if isinstance(window,wx.Frame):
                window.Raise()
            elif isinstance(window,matplotlib.figure.Figure):
                window.canvas.manager.show()

        
    def OnExit(self, event):
        self.Close()    
        
    
    def get_window_frames(self):
        return [x for x in self.GetChildren() if isinstance(x, wx.Frame) or isinstance(x, matplotlib.figure.Figure)]

    
    def OnCloseAll(self, event):
        print "appframe.OnCloseAll"
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
        
    
    def OnImport(self, event):
        self.rawdata = event.rawdata
#        self.filtertab.update_rawdata(self.rawdata)        
#        self.analysistab.update_rawdata(self.rawdata)
        print "###############  OLD IMPORT: datatypes\n",self.rawdata.dtypes
        # this should not be set based on current parsers regex pattern but based on columns with 'category' as dtype
#        self.analysistab.set_roigroupings(event.importer.get_parser().get_regexpatterns().keys())


    def OnDataUpdated(self, event):
        data,datatype = event.GetUpdatedData()
        print "###############  OLD appframe.OnDataUpdated - %s:" % (datatype)
#        if datatype == 'Raw':
#            self.rawdata = data
#            self.filtertab.update_rawdata(data, applyfilters=True)        
#            self.analysistab.update_rawdata(data)
#        else:
#            self.filtertab.update_data(data)        
#            self.analysistab.update_data(data)
                    
        
    def OnRangeFilterUpdated(self, event):
        rfilters = event.GetUpdatedItems()
        print "###############  OLD appframe.OnRangeFilterUpdated - %d Filters updated:" % len(rfilters)
        #for key in rfilters:
        #    rfilter = rfilters[key]
        #    print "\t %s: %s" % (key, str(rfilter.get_parameters()))
        #dropsbyfilter, totaldrops = self.filtertab.apply_filters(rfilters, dropsonly=True, onlyselected=False)
        #self.analysistab.update_rangefilters(rfilters)
        #self.data = self.rawdata.drop(totaldrops)
        #self.analysistab.update_data(self.data)
        #event.Skip()
        
        
    def OnApplyFilter(self, event):
        print "###############  OLD AppFrame.OnApplyFilter"
        self.data = event.data
        self.analysistab.update_data(event.data)
        
        
    def OnAnalysisUpdated(self, event):
        updated = event.GetUpdatedItems()
        print "appframe.OnAnalysisUpdated - %d Analysis updated:" % len(updated)
        for key in updated:
            u = updated[key]
            print "\t %s: %s" % (key, str(u))

        
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
    
                                    
   