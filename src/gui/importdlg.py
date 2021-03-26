import logging
import wx
import os
import core
import core.configuration as cfg
from core.importer import dataimporter
from core.preprocessor import defaultpreprocessor
from gui.events import DataWindowEvent, EVT_DATA_TYPE
from gui.delimpanel import DelimiterPanel
from gui.dicttablepanel import DictTable, ListTable
from gui.datapanel import PandasFrame
from pubsub import pub


class ImportDlg(wx.Dialog):
    
    def __init__(self, parent, title, config, parsefname=True, preprocess=True, excludefiles=False, singlefile=False):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title)
        self.importer = dataimporter()
        self.config = config
        self.parsefname = parsefname
        self.preprocess = preprocess
        self.excludefiles = excludefiles
        
        configsizer = wx.FlexGridSizer(2,2,5,5)
        configsizer.AddGrowableCol(1, 1)
        colsizer = wx.FlexGridSizer(2,3,5,5)
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
        
        delimiter_label = wx.StaticText(self, wx.ID_ANY, "Column Delimiter:")
        self.delimiter_panel = DelimiterPanel(self, config.get(cfg.CONFIG_DELIMITER))
        configsizer.Add(delimiter_label, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
        configsizer.Add(self.delimiter_panel, 1, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        if parsefname:
            parser_label = wx.StaticText(self, wx.ID_ANY, "Filename Parser:")
            self.avail_parsers = core.parser.get_available_parsers()
            sel_parser = self.avail_parsers.get(config.get(cfg.CONFIG_PARSER_CLASS))
            if sel_parser is None:
                sel_parser = next(iter(self.avail_parsers)) #self.avail_parsers.keys()[0]
            self.parser_chooser = wx.ComboBox(self, -1, value=sel_parser, choices=sorted(self.avail_parsers.keys()), style=wx.CB_READONLY)
            self.parser_chooser.Bind(wx.EVT_COMBOBOX, self.OnParserChanged)
            
            parsername = self.parser_chooser.GetStringSelection()
            hparser = core.parser.instantiate_parser('core.parser.' + parsername)
            
            fparse_label = wx.StaticText(self, wx.ID_ANY, "Parse from Filenames:")
            self.fparsegrid = wx.grid.Grid(self, -1)
            self.fparsegrid.SetDefaultColSize(200,True)
            self.parsetable = ListTable(hparser.get_regexpatterns(), headers=[cfg.CONFIG_PARSER_USE, cfg.CONFIG_PARSER_CATEGORY, cfg.CONFIG_PARSER_REGEX], sort=False)
            self.fparsegrid.SetTable(self.parsetable,takeOwnership=True)
            self.fparsegrid.SetRowLabelSize(0)

            configsizer.Add(parser_label, 0, wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)
            configsizer.Add(self.parser_chooser, 1, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        if preprocess:
            rename_label = wx.StaticText(self, wx.ID_ANY, "Rename Columns:")
            self.rgrid = wx.grid.Grid(self, -1)#, size=(200, 100))
            self.rgrid.SetDefaultColSize(200,True)
            self.headertable = DictTable(config.get(cfg.CONFIG_HEADERS), headers=['Original name', 'New name'])
            self.rgrid.SetTable(self.headertable,takeOwnership=True)
            self.rgrid.SetRowLabelSize(0)
            self.rgrid.Bind(wx.EVT_SIZE, self.OnRGridSize)

            drop_label = wx.StaticText(self, wx.ID_ANY, "Drop Columns:")
            self.drop_col_list = wx.TextCtrl(self, wx.ID_ANY, size=(200, 100), value="\n".join(config.get(cfg.CONFIG_DROP_COLUMNS)), style=wx.TE_MULTILINE|wx.EXPAND)

            colsizer.Add(fparse_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
            colsizer.Add(rename_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
            colsizer.Add(drop_label, 0, wx.LEFT|wx.RIGHT|wx.TOP, 5)
            colsizer.Add(self.fparsegrid, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
            colsizer.Add(self.rgrid, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
            colsizer.Add(self.drop_col_list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)

        if excludefiles:
            exclude_label = wx.StaticText(self, wx.ID_ANY, "Exclude Files:")
            self.exclude_files_list = wx.TextCtrl(self, wx.ID_ANY, value="\n".join(config.get(cfg.CONFIG_EXCLUDE_FILES)), style=wx.TE_MULTILINE|wx.EXPAND)
            filesizer.Add(exclude_label, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
            filesizer.Add(self.exclude_files_list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)


        if singlefile:
            self.open_button = wx.Button(self, wx.ID_ANY, "Open")
            self.open_button.Bind(wx.EVT_BUTTON, self.OnOpenFile)
            lbuttonsizer.Add(self.open_button, 1, wx.EXPAND|wx.ALL, 5)
        else:
            #self.sel_files_label = wx.StaticText(self, wx.ID_ANY, "Selected Files: %9d" % len(self.importer.get_files()), (20,20))    
            self.files_list = wx.ListBox(self, wx.ID_ANY, size=(400,-1), style=wx.LB_EXTENDED|wx.LB_HSCROLL|wx.LB_NEEDED_SB|wx.LB_SORT)
            #filesizer.Add(self.sel_files_label, 2, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
            filesizer.Add(self.files_list, 2, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
            
            self.add_button = wx.Button(self, wx.ID_ANY, "Add Files")
            self.add_button.Bind(wx.EVT_BUTTON, self.OnAddFiles)
            lbuttonsizer.Add(self.add_button, 1, wx.EXPAND|wx.ALL, 5)

            self.remove_button = wx.Button(self, wx.ID_ANY, "Remove Files")
            self.remove_button.Bind(wx.EVT_BUTTON, self.OnRemoveFiles)
            lbuttonsizer.Add(self.remove_button, 1, wx.EXPAND|wx.ALL, 5)

            self.reset_button = wx.Button(self, wx.ID_ANY, "Reset")
            self.reset_button.Bind(wx.EVT_BUTTON, self.OnReset)
            lbuttonsizer.Add(self.reset_button, 1, wx.EXPAND|wx.ALL, 5)

            #self.preview_button = wx.Button(self, wx.ID_ANY, "Preview")
            #self.preview_button.Bind(wx.EVT_BUTTON, self.OnPreview)
            #lbuttonsizer.Add(self.preview_button, 1, wx.EXPAND|wx.ALL, 5)

            self.import_button = wx.Button(self, wx.ID_ANY, "Import")
            self.import_button.Bind(wx.EVT_BUTTON, self.OnImportFiles)        
            lbuttonsizer.Add(self.import_button, 1, wx.EXPAND|wx.ALL, 5)

        self.cancel_button = wx.Button(self, wx.ID_ANY, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        lbuttonsizer.Add(self.cancel_button, 1, wx.EXPAND|wx.ALL, 5)

        topleftsizer.Add(configsizer, 1, wx.EXPAND|wx.ALL, 5)
        if preprocess:
            topleftsizer.Add(colsizer, 1, wx.EXPAND|wx.ALL, 5)
        
        topsizer.Add(topleftsizer, 1, wx.EXPAND|wx.ALL, 5)
        
        if not singlefile:
            bottomsizer.Add(filesizer, 1, wx.EXPAND|wx.ALL, 5)
        bottomsizer.Add(lbuttonsizer,0, wx.ALL, 5)
        
        box.Add(topsizer, 1, wx.EXPAND|wx.ALL, 5)
        box.Add(wx.StaticLine(self), 0, wx.ALL|wx.EXPAND, 5)
        box.Add(bottomsizer, 1, wx.EXPAND|wx.ALL, 5)
        
        self.SetSizerAndFit(box)        
        # self.update_files(0)
    
        
    def get_config(self):
        #config = {}
        #config.update(self.get_import_settings())
        #config.update(self.get_preprocess_settings())
        return self.config
                
    """            
    def update_config_gui_elements(self, config):
        logging.debug ("update_config_gui_elements")
        logging.debug (f"\t{cfg.CONFIG_IMPORT}, {config.get(cfg.CONFIG_IMPORT, returnkeys=True)}")
        logging.debug (f"\t{cfg.CONFIG_PREPROCESS}, {config.get(cfg.CONFIG_PREPROCESS, returnkeys=True)}")
        self.delimiter_panel.set_delimiters(config.get(cfg.CONFIG_DELIMITER))
        parsername = config.get(cfg.CONFIG_PARSER_CLASS)
        sel_parser = self.avail_parsers.get(parsername)
        if sel_parser is None:
            parsername =  self.parser_chooser.GetStringSelection()
            parsercfg = {cfg.CONFIG_PARSER_CLASS: parsername}
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
    """    
        
    def OnRGridSize(self, event):
        self.rgrid.SetDefaultColSize(event.GetSize().GetWidth()/self.rgrid.GetTable().GetNumberCols(),True)
        self.rgrid.Refresh()
        
    """
    def update_files(self, no_newfiles):
        files = self.importer.get_files()
        self.sel_files_label.SetLabel("Selected Files: %9d" % len(files))
        self.files_list.Set(files)
    """    

    def configure_importer(self, importer, files):
        importer.set_delimiter(self.delimiter_panel.get_delimiters())
        if self.parsefname:
            parsername = self.parser_chooser.GetStringSelection()
            parser = core.parser.instantiate_parser('core.parser.' + parsername)
            if parser is None:
                logging.warning (f"COULD NOT INSTANTIATE PARSER:{parsername}")
                return
            parser.set_regexpatterns(self.parsetable.GetData())
            importer.set_parser(parser)
        else:
            importer.set_parser(None)
            
        if self.preprocess:
            dropped = self.drop_col_list.GetValue().splitlines()
            if len(dropped)==1 and dropped[0]=='':
                dropped = None
            preprocessor = defaultpreprocessor()
            preprocessor.set_replacementheaders(self.headertable.GetDict())
            preprocessor.set_dropcolumns(dropped)
            parsername = self.parser_chooser.GetStringSelection()
            importer.set_preprocessor(preprocessor)
        else:
            importer.set_preprocessor(None)                
        importer.set_files(files)


    def update_listlabel(self):
        label = "Selected Files: %9d" % len(self.importer.get_files())
        if self.rawdata is not None:
            label += "; imported %d rows, %d columns" % (self.rawdata.shape[0], self.rawdata.shape[1])
        self.sel_files_label.SetLabel(label)    

       
    def OnParserChanged(self, event):
        logging.debug ("Parser changed")
        parsername = self.parser_chooser.GetStringSelection()
        hparser = core.parser.instantiate_parser('core.parser.' + parsername)
        self.parsetable = ListTable(hparser.get_regexpatterns(), headers=[cfg.CONFIG_PARSER_USE,cfg.CONFIG_PARSER_CATEGORY, cfg.CONFIG_PARSER_REGEX], sort=False)
        self.fparsegrid.SetTable(self.parsetable,takeOwnership=True)
        self.fparsegrid.SetRowLabelSize(0)
        self.fparsegrid.Refresh()


    def OnAddFiles(self, event):
        with wx.FileDialog(self, "Add Raw Data Results", wildcard="txt files (*.txt)|*.txt",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE | wx.FD_CHANGE_DIR) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            # Proceed loading the file chosen by the user
            paths = fileDialog.GetPaths()
            excluded = []
            if self.excludefiles:
                exclude_list = self.exclude_files_list.GetValue() #.encode('ascii','ignore')
                excluded = exclude_list.splitlines()              
            for path in paths:
                if os.path.isdir(path):
                    self.importer.add_files([path], exclude=[])
                else:
                    self.importer.add_files([path], exclude=excluded)
                self.files_list.Set(self.importer.get_files())

            #new_filecount = len(self.importer.get_files())
            # self.update_files(new_filecount-filecount)
#            self.statusbar.SetStatusText("Added %d file(s)" % (new_filecount - filecount))
 
    
    def OnRemoveFiles(self, event):
        selected = self.files_list.GetSelections()
        if selected is not None and len(selected) > 0: 
            selectedfiles = [self.files_list.GetString(idx) for idx in selected]
            filecount = len(self.importer.get_files())
            self.importer.remove_files(selectedfiles)
            self.files_list.Set(self.importer.get_files())

            #self.update_files(len(self.importer.get_files())-filecount)
 
    
    def OnReset(self, event):
        filecount = len(self.importer.get_files())
        self.importer.remove_allfiles()
        self.files_list.Set(self.importer.get_files())
        # self.update_files(len(self.importer.get_files())-filecount)
 
    
    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

        
        
    def OnPreview(self, event):
        previewrows = 200
        files = [self.files_list.GetString(index) for index in range(self.files_list.GetCount())]
        if len(files) > 0:
            #delimiter = self.delimiter_panel.get_delimiters()
            importer = dataimporter()
            selected = self.files_list.GetSelections()
            if selected is None or len(selected)==0:
                self.configure_importer(importer, [files[0]])
            else:
                logging.debug (f"PREVIEWING: delimiter={delimiter}, {self.files_list.GetString(selected[0])}")
            self.configure_importer(importer, [self.files_list.GetString(selected[0])])
       

    def OnOpenFile(self, event):
        with wx.FileDialog(self, "Add Raw Data Results", wildcard="txt files (*.txt)|*.txt",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_CHANGE_DIR) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            # Proceed loading the file chosen by the user
            files = fileDialog.GetPaths()
            self.configure_importer(self.importer, files)
            self.config.update(self.importer.get_config(), [cfg.CONFIG_IMPORT])
            self.EndModal(wx.ID_OK)
               
                    
    def OnImportFiles(self, event):
        files = [self.files_list.GetString(index) for index in range(self.files_list.GetCount())]
        if len(files) == 0:
            wx.MessageBox('Add files to be imported.', 'Error', wx.OK | wx.ICON_INFORMATION)    
        else:
            self.configure_importer(self.importer, files)
            self.config.update(self.importer.get_config(), [cfg.CONFIG_IMPORT])
            if self.preprocess:
                self.config.update(self.importer.get_preprocessor().get_config(), [cfg.CONFIG_PREPROCESS])
            self.EndModal(wx.ID_OK)
            

 