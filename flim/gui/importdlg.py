import logging
import itertools
import wx
import os
import flim.core
from flim.core.importer import dataimporter
from flim.core.parser import PATTERN_CATEGORY, PATTERN_REGEX, PATTERN_USE
from flim.core.preprocessor import defaultpreprocessor
from flim.gui.events import DataWindowEvent, EVT_DATA_TYPE
from flim.gui.delimpanel import DelimiterPanel
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.datapanel import PandasFrame
from pubsub import pub


class ImportDlg(wx.Dialog):
    def __init__(
        self,
        parent,
        title,
        settings,
        parsefname=True,
        preprocess=True,
        excludefiles=False,
        singlefile=False,
    ):
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title)
        self.importer = dataimporter()
        self.settings = settings  # AppSettings: updated by Open and Import
        self.parsefname = parsefname
        self.preprocess = preprocess
        self.excludefiles = excludefiles

        configsizer = wx.FlexGridSizer(3, 2, 5, 5)
        configsizer.AddGrowableCol(1, 1)
        colsizer = wx.FlexGridSizer(2, 3, 5, 5)
        colsizer.AddGrowableCol(0, 2)
        colsizer.AddGrowableCol(1, 1)
        colsizer.AddGrowableRow(1, 1)
        lbuttonsizer = wx.BoxSizer(wx.VERTICAL)
        filesizer = wx.FlexGridSizer(2, 2, 5, 5)
        filesizer.AddGrowableCol(0, 1)
        filesizer.AddGrowableCol(1, 3)
        filesizer.AddGrowableRow(1, 1)
        topleftsizer = wx.FlexGridSizer(2, 1, 5, 5)
        topleftsizer.AddGrowableCol(0, 1)
        topleftsizer.AddGrowableRow(1, 1)
        topsizer = wx.BoxSizer(wx.HORIZONTAL)
        bottomsizer = wx.BoxSizer(wx.HORIZONTAL)
        box = wx.BoxSizer(wx.VERTICAL)

        delimiter_label = wx.StaticText(self, wx.ID_ANY, "Column Delimiter:")
        self.delimiter_panel = DelimiterPanel(self, settings.import_.delimiter)
        configsizer.Add(
            delimiter_label, 0, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 5
        )
        configsizer.Add(
            self.delimiter_panel, 1, wx.EXPAND | wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5
        )

        if parsefname:
            parser_label = wx.StaticText(self, wx.ID_ANY, "Filename Parser:")
            self.avail_parsers = flim.core.parser.get_available_parsers()
            sel_parser = self.avail_parsers.get(
                settings.import_.filename_parser.parser
            )
            if sel_parser is None:
                sel_parser = next(
                    iter(self.avail_parsers)
                )  # self.avail_parsers.keys()[0]
            self.parser_chooser = wx.ComboBox(
                self,
                -1,
                style=wx.CB_READONLY,
                value=sel_parser,
                choices=sorted(self.avail_parsers.keys()),
            )
            self.parser_chooser.Bind(wx.EVT_COMBOBOX, self.OnParserChanged)

            parsername = self.parser_chooser.GetStringSelection()
            hparser = flim.core.parser.instantiate_parser(
                "flim.core.parser." + parsername
            )

            fparse_label = wx.StaticText(self, wx.ID_ANY, "Parse from Filenames:")
            self.fparsegrid = wx.grid.Grid(self, -1)
            self.fparsegrid.SetDefaultColSize(200, True)
            self.parsetable = ListTable(
                hparser.get_regexpatterns(),
                headers=[
                    PATTERN_USE,
                    PATTERN_CATEGORY,
                    PATTERN_REGEX,
                ],
                sort=False,
            )
            self.fparsegrid.SetTable(self.parsetable, takeOwnership=True)
            self.fparsegrid.SetRowLabelSize(0)

            configsizer.Add(
                parser_label, 0, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 5
            )
            configsizer.Add(
                self.parser_chooser, 1, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
            )

            # Combined col labels
            combo_label = wx.StaticText(self, wx.ID_ANY, "Column Combos:")
            self.combo_panel = wx.Panel(self, wx.ID_ANY)
            wx.CheckBox(self.combo_panel, wx.ID_ANY)
            configsizer.Add(
                combo_label, 0, wx.ALL | wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL, 5
            )
            configsizer.Add(
                self.combo_panel,
                1,
                wx.ALL | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL,
                5,
            )

        if preprocess:
            rename_label = wx.StaticText(self, wx.ID_ANY, "Rename Columns:")
            self.rgrid = wx.grid.Grid(self, -1)  # , size=(200, 100))
            self.rgrid.SetDefaultColSize(200, True)
            self.headertable = DictTable(
                settings.preprocess.rename, headers=["Original name", "New name"]
            )
            self.rgrid.SetTable(self.headertable, takeOwnership=True)
            self.rgrid.SetRowLabelSize(0)
            self.rgrid.Bind(wx.EVT_SIZE, self.OnRGridSize)

            drop_label = wx.StaticText(self, wx.ID_ANY, "Drop Columns:")
            self.drop_col_list = wx.TextCtrl(
                self,
                wx.ID_ANY,
                size=(200, 100),
                value="\n".join(settings.preprocess.drop),
                style=wx.TE_MULTILINE | wx.EXPAND,
            )

            colsizer.Add(fparse_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
            colsizer.Add(rename_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
            colsizer.Add(drop_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
            colsizer.Add(
                self.fparsegrid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
            )
            colsizer.Add(self.rgrid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
            colsizer.Add(
                self.drop_col_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
            )

        if excludefiles:
            exclude_label = wx.StaticText(self, wx.ID_ANY, "Exclude Files:")
            self.exclude_files_list = wx.TextCtrl(
                self,
                wx.ID_ANY,
                value="\n".join(settings.import_.exclude_files),
                style=wx.TE_MULTILINE | wx.EXPAND,
            )
            filesizer.Add(exclude_label, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
            filesizer.Add(
                self.exclude_files_list,
                1,
                wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                5,
            )

        if singlefile:
            self.open_button = wx.Button(self, wx.ID_ANY, "Open")
            self.open_button.Bind(wx.EVT_BUTTON, self.OnOpenFile)
            lbuttonsizer.Add(self.open_button, 1, wx.EXPAND | wx.ALL, 5)
        else:
            # self.sel_files_label = wx.StaticText(self, wx.ID_ANY, "Selected Files: %9d" % len(self.importer.get_files()), (20,20))
            self.files_list = wx.ListBox(
                self,
                wx.ID_ANY,
                size=(400, -1),
                style=wx.LB_EXTENDED | wx.LB_HSCROLL | wx.LB_NEEDED_SB | wx.LB_SORT,
            )
            # filesizer.Add(self.sel_files_label, 2, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
            filesizer.Add(
                self.files_list, 2, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
            )

            self.add_button = wx.Button(self, wx.ID_ANY, "Add Files")
            self.add_button.Bind(wx.EVT_BUTTON, self.OnAddFiles)
            lbuttonsizer.Add(self.add_button, 1, wx.EXPAND | wx.ALL, 5)

            self.remove_button = wx.Button(self, wx.ID_ANY, "Remove Files")
            self.remove_button.Bind(wx.EVT_BUTTON, self.OnRemoveFiles)
            lbuttonsizer.Add(self.remove_button, 1, wx.EXPAND | wx.ALL, 5)

            self.reset_button = wx.Button(self, wx.ID_ANY, "Reset")
            self.reset_button.Bind(wx.EVT_BUTTON, self.OnReset)
            lbuttonsizer.Add(self.reset_button, 1, wx.EXPAND | wx.ALL, 5)

            # self.preview_button = wx.Button(self, wx.ID_ANY, "Preview")
            # self.preview_button.Bind(wx.EVT_BUTTON, self.OnPreview)
            # lbuttonsizer.Add(self.preview_button, 1, wx.EXPAND|wx.ALL, 5)

            self.import_button = wx.Button(self, wx.ID_ANY, "Import")
            self.import_button.Bind(wx.EVT_BUTTON, self.OnImportFiles)
            lbuttonsizer.Add(self.import_button, 1, wx.EXPAND | wx.ALL, 5)

        self.cancel_button = wx.Button(self, wx.ID_ANY, "Cancel")
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        lbuttonsizer.Add(self.cancel_button, 1, wx.EXPAND | wx.ALL, 5)

        topleftsizer.Add(configsizer, 1, wx.EXPAND | wx.ALL, 5)
        if preprocess:
            topleftsizer.Add(colsizer, 1, wx.EXPAND | wx.ALL, 5)

        topsizer.Add(topleftsizer, 1, wx.EXPAND | wx.ALL, 5)

        if not singlefile:
            bottomsizer.Add(filesizer, 1, wx.EXPAND | wx.ALL, 5)
        bottomsizer.Add(lbuttonsizer, 0, wx.ALL, 5)

        box.Add(topsizer, 1, wx.EXPAND | wx.ALL, 5)
        box.Add(wx.StaticLine(self), 0, wx.ALL | wx.EXPAND, 5)
        box.Add(bottomsizer, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizerAndFit(box)
        # self.update_files(0)

    def get_settings(self):
        """The settings, with those of the files opened or imported."""
        return self.settings

    def OnRGridSize(self, event):
        self.rgrid.SetDefaultColSize(
            event.GetSize().GetWidth() // self.rgrid.GetTable().GetNumberCols(), True
        )
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
            parser = flim.core.parser.instantiate_parser(
                "flim.core.parser." + parsername
            )
            if parser is None:
                logging.warning(f"COULD NOT INSTANTIATE PARSER:{parsername}")
                return
            parser.set_regexpatterns(self.parsetable.GetData())

            comboscb = self.combo_panel.GetChildren()[0]
            if comboscb.GetValue():
                catlist = [
                    pattern[PATTERN_CATEGORY]
                    for pattern in self.parsetable.GetData()
                ]
                combolist = [combo for combo in itertools.combinations(catlist, 2)]
                importer.set_column_combos(combolist)
            else:
                importer.set_column_combos(None)

            importer.set_parser(parser)
        else:
            importer.set_parser(None)

        if self.preprocess:
            dropped = self.drop_col_list.GetValue().splitlines()
            if len(dropped) == 1 and dropped[0] == "":
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
            label += "; imported %d rows, %d columns" % (
                self.rawdata.shape[0],
                self.rawdata.shape[1],
            )
        self.sel_files_label.SetLabel(label)

    def OnParserChanged(self, event):
        logging.debug("Parser changed")
        parsername = self.parser_chooser.GetStringSelection()
        hparser = flim.core.parser.instantiate_parser("flim.core.parser." + parsername)
        self.parsetable = ListTable(
            hparser.get_regexpatterns(),
            headers=[
                PATTERN_USE,
                PATTERN_CATEGORY,
                PATTERN_REGEX,
            ],
            sort=False,
        )
        self.fparsegrid.SetTable(self.parsetable, takeOwnership=True)
        self.fparsegrid.SetRowLabelSize(0)
        self.fparsegrid.Refresh()

    def OnAddFiles(self, event):
        with wx.FileDialog(
            self,
            "Add Raw Data Results",
            wildcard="txt files (*.txt)|*.txt|csv files (*.csv)|*.csv",
            style=wx.FD_OPEN
            | wx.FD_FILE_MUST_EXIST
            | wx.FD_MULTIPLE
            | wx.FD_CHANGE_DIR,
        ) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            # Proceed loading the file chosen by the user
            paths = fileDialog.GetPaths()
            excluded = []
            if self.excludefiles:
                exclude_list = (
                    self.exclude_files_list.GetValue()
                )  # .encode('ascii','ignore')
                excluded = exclude_list.splitlines()
            for path in paths:
                if os.path.isdir(path):
                    self.importer.add_files([path], exclude=[])
                else:
                    self.importer.add_files([path], exclude=excluded)
                self.files_list.Set(self.importer.get_files())

            # new_filecount = len(self.importer.get_files())
            # self.update_files(new_filecount-filecount)

    #            self.statusbar.SetStatusText("Added %d file(s)" % (new_filecount - filecount))

    def OnRemoveFiles(self, event):
        selected = self.files_list.GetSelections()
        if selected is not None and len(selected) > 0:
            selectedfiles = [self.files_list.GetString(idx) for idx in selected]
            filecount = len(self.importer.get_files())
            self.importer.remove_files(selectedfiles)
            self.files_list.Set(self.importer.get_files())

            # self.update_files(len(self.importer.get_files())-filecount)

    def OnReset(self, event):
        filecount = len(self.importer.get_files())
        self.importer.remove_allfiles()
        self.files_list.Set(self.importer.get_files())
        # self.update_files(len(self.importer.get_files())-filecount)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnPreview(self, event):
        previewrows = 200
        files = [
            self.files_list.GetString(index)
            for index in range(self.files_list.GetCount())
        ]
        if len(files) > 0:
            importer = dataimporter()
            selected = self.files_list.GetSelections()
            # the first selected file, else the first file
            file = self.files_list.GetString(selected[0]) if selected else files[0]
            logging.debug(f"Previewing {file}")
            self.configure_importer(importer, [file])

    def OnOpenFile(self, event):
        with wx.FileDialog(
            self,
            "Add Raw Data Results",
            wildcard="txt files (*.txt)|*.txt|csv files (*.csv)|*.csv",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_CHANGE_DIR,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            # Proceed loading the file chosen by the user
            files = fileDialog.GetPaths()
            self.importer.set_delimiter("\t,")
            self.configure_importer(self.importer, files)
            self.settings.import_ = self.importer.settings()
            self.EndModal(wx.ID_OK)

    def OnImportFiles(self, event):
        files = [
            self.files_list.GetString(index)
            for index in range(self.files_list.GetCount())
        ]
        if len(files) == 0:
            wx.MessageBox(
                "Add files to be imported.", "Error", wx.OK | wx.ICON_INFORMATION
            )
        else:
            self.configure_importer(self.importer, files)
            self.settings.import_ = self.importer.settings()
            if self.preprocess:
                self.settings.preprocess = self.importer.get_preprocessor().settings()
            self.EndModal(wx.ID_OK)
