#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The wxPython GUI: its wx.App (FLIMAnalyzerApp), the main window (AppFrame) and the
settings of a GUI session."""

import matplotlib

import logging
import os
from pathlib import Path
import re
import pandas as pd
import wx
import wx.adv

from pubsub import pub
from flim._version import __version__
from wx.lib.newevent import NewEvent
from importlib.resources import files

import flim.core.parser
import flim.core.preprocessor
import flim.gui.dialogs
import flim.resources
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.core.datamgr import DataManager
from flim.core.saving import AutosaveConfig
from flim.tools.data import DropColumns, RenameColumns, import_preprocessor
from flim.core.types import TableType
from flim.core.settings import AppSettings
from flim.core.settingsmgr import SettingsManager, UserSettingsFile, user_settings_path
from flim.core.importer import dataimporter
from flim.core.paths import canonical_folder
from flim.core.graph import WorkflowGraph
from flim.core.workflow import Workflow
from flim.core.registry import GUI_GROUP, TOOLS_GROUP, discover, tools
from flim.core.runner import run_flow
from flim.gui.configdialog import open_config_dialog
from flim.gui.icons import tool_bitmap
from flim.gui.macos import set_bundle_name, set_display_name
from flim.gui.plotframe import PlotFrame
from flim.gui.progressdlg import RunProgressDialog, RunSummaryDialog
from flim.gui.datapanel import PandasFrame
from flim.gui.dialogs import ConfigureAxisDlg
from flim.gui.events import (
    EVT_DATAUPDATED,
    DataWindowEvent,
    EVT_DATA,
    EVT_DATA_TYPE,
    PlotEvent,
    EVT_PLOT,
    EVT_PLOT_TYPE,
)
from flim.gui.events import (
    FOCUSED_DATA_WINDOW,
    CLOSING_DATA_WINDOW,
    REQUEST_RENAME_DATA_WINDOW,
    RENAMED_DATA_WINDOW,
)
from flim.gui.importdlg import ImportDlg
from flim.gui.listcontrol import EVT_FILTERUPDATED, EVT_ANALYSISUPDATED
import flim.tools  # noqa: F401  (registers the built-in tools)

# field editors of the tools that need more than the generated dialog
import flim.gui.dialogs.autoencoder  # noqa: F401
import flim.gui.dialogs.categoryorder  # noqa: F401
import flim.gui.dialogs.filter  # noqa: F401
import flim.gui.dialogs.unpivot  # noqa: F401

logger = logging.getLogger(__name__)
DOCS_URL = "https://flimanalyzer.readthedocs.io"


def docs_url(version: str = __version__) -> str:
    """URL of the documentation of ``version``: a release version (X.Y.Z) has its
    own; any other version (a development build) gets the latest documentation."""
    if re.fullmatch(r"\d+\.\d+\.\d+", version):
        return f"{DOCS_URL}/en/v{version}/"
    return f"{DOCS_URL}/en/latest/"


ImportEvent, EVT_IMPORT = NewEvent()
ApplyFilterEvent, EVT_APPLYFILTER = NewEvent()
DataUpdateEvent, EVT_UPDATEDATA = NewEvent()



def app_icon():
    """The FLIMAnalyzer icon."""
    return wx.Icon(str(files(flim.resources).joinpath("flimanalyzer.png")), wx.BITMAP_TYPE_PNG)


def app_icons():
    """The FLIMAnalyzer icon in all sizes of its ICO file, so that each window can
    use a sharp one."""
    return wx.IconBundle(str(files(flim.resources).joinpath("flimanalyzer.ico")), wx.BITMAP_TYPE_ICO)


class FLIMAnalyzerApp(wx.App):
    def __init__(self, flimanalyzer=None, settings_manager=None, files=None):
        """
        Args:
            flimanalyzer: The FLIMAnalyzer object that provides the task runner and
                execution settings. None: the main window is opened later with
                `start`, e.g. after dialogs shown at startup.
            settings_manager: The SettingsManager of this session. Defaults to one with
                the built-in defaults and the user settings file.
            files: Data files to open at startup, each in its own data window.
        """
        self.flimanalyzer = flimanalyzer
        self.settings_manager = settings_manager
        self.files = list(files or [])
        # tools of other packages, and their dialogs (entry points)
        discover(TOOLS_GROUP)
        discover(GUI_GROUP)
        set_bundle_name("FLIMAnalyzer")  # before wx.App registers with macOS
        super().__init__()

    def OnInit(self):
        self.SetAppName("FLIMAnalyzer")
        self.SetAppDisplayName("FLIMAnalyzer")
        set_display_name("FLIMAnalyzer")
        # logout and shutdown: the same question as quitting, where the system lets
        # the session's end wait
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnQueryEndSession)
        if self.flimanalyzer is not None:
            self.start()
        return True

    def OnQueryEndSession(self, event):
        """Ask about unsaved windows before the session ends (AppFrame.confirm_quit);
        veto the end if the user cancels and the system allows it."""
        frame = getattr(self, "frame", None)
        if frame and event.CanVeto() and not frame.confirm_quit():
            event.Veto()
            return
        event.Skip()

    def start(self, flimanalyzer=None, settings_manager=None, files=None):
        """Open the main window, and the data files given at startup.

        Args:
            flimanalyzer: Replaces the FLIMAnalyzer object given when the app was
                created, if given.
            settings_manager: Replaces the SettingsManager given when the app was
                created, if given.
            files: Replaces the data files given when the app was created, if given.
        """
        if flimanalyzer is not None:
            self.flimanalyzer = flimanalyzer
        if settings_manager is not None:
            self.settings_manager = settings_manager
        if files is not None:
            self.files = list(files)
        if self.settings_manager is None:
            self.settings_manager = SettingsManager(
                user_file=UserSettingsFile(user_settings_path())
            )
        self.frame = AppFrame(self.flimanalyzer, self.settings_manager)
        self.dock_icon = None
        if wx.Platform == "__WXMAC__":
            # the Dock shows the Python icon unless it is replaced here
            self.dock_icon = wx.adv.TaskBarIcon(wx.adv.TBI_DOCK)
            self.dock_icon.SetIcon(app_icon(), "FLIMAnalyzer")
        self.frame.Show(True)
        if self.settings_manager.notices:  # e.g. a user settings file was renamed
            wx.CallAfter(
                wx.MessageBox,
                "\n\n".join(self.settings_manager.notices),
                "FLIMAnalyzer",
                wx.OK | wx.ICON_WARNING,
            )
        if self.files:
            wx.CallAfter(self.open_files, self.files)

    def open_files(self, files):
        """Opens each file in a data window; reports files that cannot be read."""
        failed = []
        for f in files:
            try:
                if not os.path.isfile(f) or self.frame.open_data_files([f]) is None:
                    failed.append(f)
            except Exception as e:
                logger.exception(f"Could not open {f}")
                failed.append(f"{f} ({e})")
        if failed:
            wx.MessageBox(
                "Could not open:\n" + "\n".join(failed), "Open files", wx.OK | wx.ICON_WARNING
            )

    def OnExit(self):
        if self.dock_icon:
            self.dock_icon.Destroy()
            self.dock_icon = None
        return super().OnExit()


class AppFrame(wx.Frame):
    def __init__(self, flimanalyzer, settings_manager=None):
        """
        Args:
            flimanalyzer: the FLIMAnalyzer object that provides the task runner and
                execution settings.
            settings_manager: the SettingsManager of this session (default: one with the
                built-in defaults that keeps changes in memory only).
        """
        self.flimanalyzer = flimanalyzer
        self.settings_manager = (
            settings_manager if settings_manager is not None else SettingsManager()
        )
        # the filter settings shared by the data windows; changes are reported to the
        # settings manager (report_filters)
        self.filters = self.settings.filters
        # the items the windows show (tables, plots): the windows are views of them
        self.data_manager = DataManager()
        self.windowframes = {}  # item ID -> its window
        self.window_zorder = []  # item IDs of the table windows, the current one last
        self._menu_items = {}  # item ID -> the ID of its Window menu entry
        self._save_all_dir = None  # the folder last used by Save All Windows...

        version = __version__
        super(AppFrame, self).__init__(
            None, wx.ID_ANY, title=f"FLIMAnalyzer {version}"
        )

        self.SetIcons(app_icons())

        # tool buttons, one labeled box per group, laid out in two rows
        self.toolpanel = wx.Panel(self)
        self.tool_groups = []
        self._add_tool_group(
            "File",
            [
                (
                    "Open file",
                    wx.Bitmap(str(files(flim.resources).joinpath("fileopen.png"))),
                    self.OnLoadData,
                ),
                (
                    "Import files",
                    wx.Bitmap(str(files(flim.resources).joinpath("import.png"))),
                    self.OnImportData,
                ),
            ],
        )

        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        loadmenuitem = filemenu.Append(wx.ID_ANY, "&Open...", "Open single data file")
        importmenuitem = filemenu.Append(
            wx.ID_ANY, "Import...", "Import and concatenate mutliple data files"
        )
        saveallitem = filemenu.Append(
            wx.ID_ANY, "Save All Windows...", "Save all open tables and plots"
        )
        filemenu.AppendSeparator()
        loadsettingsitem = filemenu.Append(
            wx.ID_ANY, "Import Settings...", "Use the settings in a settings file"
        )
        savesettingsitem = filemenu.Append(
            wx.ID_ANY, "Export Settings...", "Save the settings to a file"
        )
        # standard ids: wx moves Settings and Exit (Quit) to the app menu on macOS
        viewsettingsitem = filemenu.Append(
            wx.ID_PREFERENCES, "Settings...", "Show the app settings and where they come from"
        )
        filemenu.AppendSeparator()
        exitmenuitem = filemenu.Append(wx.ID_EXIT, "E&xit", "Exit the application")

        self.windowmenu = wx.Menu()
        closeallitem = self.windowmenu.Append(wx.ID_ANY, "Close all windows")
        self.windowmenu.AppendSeparator()

        helpmenu = wx.Menu()
        docsitem = helpmenu.Append(wx.ID_ANY, "Documentation", "Open the documentation of this version")
        aboutitem = helpmenu.Append(wx.ID_ABOUT, "About FLIMAnalyzer")

        menubar.Append(filemenu, "&File")
        for category in tools.categories():
            menubar.Append(self._create_tool_menu(category), f"&{category}")
        menubar.Append(self.windowmenu, "&Window")
        menubar.Append(helpmenu, "&Help")

        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.OnLoadData, loadmenuitem)
        self.Bind(wx.EVT_MENU, self.OnImportData, importmenuitem)
        self.Bind(wx.EVT_MENU, lambda e: self.save_all_windows(), saveallitem)
        self.Bind(wx.EVT_MENU, self.OnExit, exitmenuitem)
        # every way of quitting (File > Exit, the close button, Cmd-Q) closes this window
        self.Bind(wx.EVT_CLOSE, self.OnCloseApp)
        self.Bind(wx.EVT_MENU, self.OnLoadSettings, loadsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnSaveSettings, savesettingsitem)
        self.Bind(wx.EVT_MENU, self.OnViewSettings, viewsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnCloseAll, closeallitem)
        self.Bind(wx.EVT_MENU, self.OnDocumentation, docsitem)
        self.Bind(wx.EVT_MENU, self.OnAbout, aboutitem)

        self._layout_tool_groups(rows=2)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(self.toolpanel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        # size the window to the tool rows
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.Centre()
        self.Show(True)

        self.Bind(EVT_IMPORT, self.OnImport)
        self.Bind(EVT_DATA, self.OnDataWindowRequest)
        self.Bind(EVT_PLOT, self.OnPlotWindowRequest)
        self.Bind(EVT_DATAUPDATED, self.OnDataUpdated)
        self.Bind(EVT_APPLYFILTER, self.OnApplyFilter)
        self.Bind(EVT_FILTERUPDATED, self.OnRangeFilterUpdated)
        self.Bind(EVT_ANALYSISUPDATED, self.OnAnalysisUpdated)
        pub.subscribe(self.OnDataWindowFocused, FOCUSED_DATA_WINDOW)
        pub.subscribe(self.OnClosingDataWindow, CLOSING_DATA_WINDOW)
        pub.subscribe(self.OnRequestRenameDataWindow, REQUEST_RENAME_DATA_WINDOW)

    def _add_tool_group(self, label, tools):
        """Adds a labeled box with a single row of icon buttons.

        The boxes are placed by _layout_tool_groups().

        Args:
            label (str): group label shown on the box.
            tools (list): (name, bitmap, handler) tuples; name is used as tooltip
                and as the button name.
        """
        group = wx.StaticBoxSizer(wx.HORIZONTAL, self.toolpanel, label)
        box = group.GetStaticBox()
        for name, bitmap, handler in tools:
            button = wx.BitmapButton(box, wx.ID_ANY, bitmap, name=name, style=wx.BORDER_NONE)
            button.SetToolTip(name)
            button.Bind(wx.EVT_BUTTON, handler)
            group.Add(button, 0, wx.ALL, 2)
        self.tool_groups.append(group)

    def _layout_tool_groups(self, rows=2):
        """Places the tool groups in rows, keeping each group on one line.

        Groups keep their order; the row breaks are chosen so that the widest
        row is as narrow as possible.
        """
        widths = [g.GetMinSize().width for g in self.tool_groups]
        rows = max(1, min(rows, len(widths)))

        def split(start, n_rows):
            # (widest row, [end index of each row]) for groups[start:] in n_rows rows
            if n_rows == 1:
                return sum(widths[start:]), [len(widths)]
            best = None
            for end in range(start + 1, len(widths) - n_rows + 2):
                rest, ends = split(end, n_rows - 1)
                candidate = (max(sum(widths[start:end]), rest), [end] + ends)
                if best is None or candidate[0] < best[0]:
                    best = candidate
            return best

        _, ends = split(0, rows)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        start = 0
        for end in ends:
            row = wx.BoxSizer(wx.HORIZONTAL)
            for group in self.tool_groups[start:end]:
                row.Add(group, 0, wx.ALL, 4)
            panel_sizer.Add(row, 0, wx.LEFT | wx.RIGHT, 4)
            start = end
        self.toolpanel.SetSizer(panel_sizer)

    def _create_tool_menu(self, category):
        menu = wx.Menu()
        buttons = []
        for tool in tools.by_category()[category]:
            item = menu.Append(wx.ID_ANY, tool.name)
            handler = lambda event, tool=tool: self.run_tool(tool)
            self.Bind(wx.EVT_MENU, handler, item)
            buttons.append((tool.name, tool_bitmap(tool), handler))
        self._add_tool_group(category, buttons)
        return menu

    def _get_window_frame(self, obj_id):
        for title, window in self.windowframes.items():
            if isinstance(window, PandasFrame) and id(window.GetData()) == obj_id:
                logger.debug(
                    f"selected: title={title}, obj_id={obj_id},"
                    f" id={id(window.GetData())}"
                )
                return title, window
            elif isinstance(window, PlotFrame) and id(window.figure) == obj_id:
                logger.debug(
                    f"selected: title={title}, obj_id={obj_id}, id={id(window)}"
                )
                return title, window
        return

    def _own_item(self, frame):
        """Return the item ID of one of this frame's windows, or None (pubsub also
        delivers the messages of other frames' windows)."""
        item_id = getattr(frame, "item_id", None)
        return item_id if self.windowframes.get(item_id) is frame else None

    def OnDataWindowFocused(self, data, frame):
        item_id = self._own_item(frame)
        if item_id is not None:
            self.window_zorder = [i for i in self.window_zorder if i != item_id]
            self.window_zorder.append(item_id)

    @property
    def settings(self) -> AppSettings:
        """A copy of the current settings; changes are applied through
        settings_manager."""
        return self.settings_manager.settings

    def report_filters(self, filters) -> None:
        """Applies the filter settings ``filters`` (FilterSettings) and writes them to
        the user settings file."""
        self.settings_manager.update({"filters": filters.model_dump(mode="json")})

    def OnLoadData(self, event):
        dlg = ImportDlg(
            self,
            "Open File",
            self.settings,
            parsefname=False,
            preprocess=False,
            singlefile=True,
        )
        if dlg.ShowModal() == wx.ID_OK:
            imported = dlg.get_settings().import_
            # for this session only: they include data file paths
            self.settings_manager.update(
                {"import": imported.model_dump(mode="json", by_alias=True)}, keep=False
            )
            self.open_data_files(imported.include_files, imported.delimiter)

    def open_data_files(self, files, delimiter=None):
        """Opens data files in a data window, as File > Open does.

        Args:
            files: paths of the files; several files are combined in one table.
            delimiter: column delimiter characters, default: from the settings
                (tab and comma).

        Returns:
            str: title of the new data window (the file name, or "Imported Data" for
            several files, made unique), or None if no file could be read.
        """
        importer = dataimporter()
        importer.set_delimiter(delimiter or self.settings.import_.delimiter)
        importer.set_files(list(files))
        importer.set_parser(None)
        importer.set_preprocessor(None)
        data, filenames, fheaders = importer.import_data()
        if not filenames:
            return None

        windowtitle = os.path.basename(filenames[0])
        if len(filenames) != 1:
            windowtitle = "Imported Data"
        # always a new window: a window of the same title (e.g. data.txt from another
        # folder) keeps its data; the new one is named data.txt-1
        windowtitle = self.unique_window_title(windowtitle)
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(
            data,
            windowtitle,
            "createnew",
            config=None,
            showcolindex=False,
            analyzable=True,
            savemodified=True,
            enableclose=True,
            modified=False,  # just read from the file
        )
        self.GetEventHandler().ProcessEvent(event)
        return windowtitle

    def OnImportData(self, event):
        dlg = ImportDlg(self, "Import File(s)", self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            settings = dlg.get_settings()
            imported = settings.import_
            # for this session only: they include data file paths; the rename and
            # drop settings are the Rename Columns and Drop Columns tools'
            tools_changed = {
                tool.name: settings.tools.entry(tool).model_dump(mode="json")
                for tool in (RenameColumns, DropColumns)
                if settings.tools.entry(tool) is not None
            }
            self.settings_manager.update(
                {
                    "import": imported.model_dump(mode="json", by_alias=True),
                    **({"tools": tools_changed} if tools_changed else {}),
                },
                keep=False,
            )

            parsername = imported.filename_parser.parser
            parser = flim.core.parser.instantiate_parser(
                "flim.core.parser." + parsername
            )
            if parser is None:
                logger.warning(f"Could not instantiate parser {parsername}")
                return
            parser.set_regexpatterns(imported.filename_parser.patterns)

            preprocessor = import_preprocessor(self.settings)

            importer = dataimporter()
            importer.set_parser(parser)
            importer.set_delimiter(imported.delimiter)
            importer.set_files(imported.include_files)
            importer.set_column_combos(imported.category_combinations)
            importer.set_preprocessor(preprocessor)
            data, filenames, fheaders = importer.import_data()
            if data is None:
                wx.MessageBox("None of the files could be read.", "Import", wx.OK | wx.ICON_WARNING)
                return

            windowtitle = os.path.basename(filenames[0])
            if len(filenames) != 1:
                windowtitle = "Imported Data"
            event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
            event.SetEventInfo(
                data,
                windowtitle,
                "createnew",  # a new window, never into one of the same title
                config=None,
                showcolindex=False,
                analyzable=True,
                savemodified=True,
                enableclose=True,
            )
            self.GetEventHandler().ProcessEvent(event)

    def OnLoadSettings(self, event):
        with wx.FileDialog(
            self,
            "Import Settings",
            wildcard="json files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_CHANGE_DIR,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path = fileDialog.GetPath()
        try:
            self.load_settings(path)
        except Exception as err:
            logger.exception(f"Settings in {path} could not be read")
            wx.MessageBox(
                f"Could not load the settings in {path}:\n{err}",
                "Import Settings",
                wx.OK | wx.ICON_ERROR,
            )

    def load_settings(self, path) -> None:
        """Applies the sections of a settings file (any version) for this session; the
        sections it does not have (e.g. other tools') stay as they are. New data windows
        use its filter settings. If some settings cannot be used, the user chooses what
        to do (flim.gui.settingscheck.choose_settings)."""
        from flim.core.settings import check_settings_file
        from flim.gui.settingscheck import choose_settings

        check = check_settings_file(path)
        if check.problems:
            check = choose_settings(check, self)
        if check is None:
            return
        self.settings_manager.apply(check)
        self.filters = self.settings.filters

    def OnViewSettings(self, event):
        from flim.gui.settingsview import SettingsViewer

        with SettingsViewer(self, self.settings_manager) as dialog:
            dialog.ShowModal()

    def OnSaveSettings(self, event):
        with wx.FileDialog(
            self,
            "Export Settings",
            wildcard="json files (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path = fileDialog.GetPath()
        self.save_settings(path)
        self.offer_search_path(path)

    def save_settings(self, path) -> None:
        """Writes all current settings, in the current version, to a file."""
        self.settings_manager.export(path)

    def offer_search_path(self, path) -> bool:
        """Ask whether to add the folder of an exported file to the app settings search
        path, if adding it has an effect (SettingsManager.search_path_addition).

        Args:
            path: The exported file.

        Returns:
            Whether the folder was added.
        """
        folder = Path(path).parent
        if self.settings_manager.search_path_addition(folder) is None:
            return False
        with wx.MessageDialog(
            self,
            f"Add this folder to your app settings search path?\n\n{folder}\n\n"
            "The GUI then lists its files when it starts, and -s finds them by name.",
            "Export Settings",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_YES:
                return False
        return self.settings_manager.add_to_search_path(folder)

    def get_currentdata(self):
        """Return the title and the shown table of the current table window, or
        (None, None)."""
        if len(self.window_zorder) == 0:
            return None, None
        item_id = self.window_zorder[-1]
        return self.data_manager.get(item_id).title, self.windowframes[item_id].GetViewData()

    def get_alldata(self):
        """Return the shown tables of the table windows, by title."""
        return {
            self.data_manager.get(item_id).title: frame.GetViewData()
            for item_id, frame in self.windowframes.items()
            if isinstance(frame, PandasFrame)
        }

    def OnSetFilters(self, event):
        data = self.get_currentdata()
        if data is None:
            wx.MessageBox("No data available")
            return
        pass

    def tool_data_choices(self):
        """The tables of the open data windows by window title, the current one
        first. Each is a copy (TableType.snapshot): a run in its worker thread reads
        tables that later edits in the windows don't change."""
        title, currentdata = self.get_currentdata()
        data_choices = {title: currentdata} if title else {}
        data_choices.update(self.get_alldata())
        return {name: TableType.snapshot(table) for name, table in data_choices.items()}

    def run_tool(self, tool):
        """Configures a tool in its dialog and runs it on the selected tables.

        The dialog's config and run settings are stored for the tool. The run shows a
        progress dialog; afterwards a window opens for each result table and figure, or,
        for a workflow, the graph of its tasks and a run summary.
        """
        data_choices = self.tool_data_choices()
        if not data_choices:
            wx.MessageBox("Open or import data first.", tool.name, wx.OK)
            return
        config = self.settings.tools.config(tool)
        entry = self.settings.tools.entry(tool)
        saved = entry.autosave if entry else AutosaveConfig()
        folder = saved.results_dir or self.settings.resolved_results_dir()
        execution = self.flimanalyzer.execution.model_copy(
            update={
                "autosave": saved.model_copy(
                    update={"enabled": saved.enabled and bool(folder), "results_dir": folder}
                )
            }
        )
        is_workflow = issubclass(tool, Workflow)
        result = open_config_dialog(
            self,
            tool,
            config,
            data_choices=data_choices,
            execution=execution,
            autosave_locked=is_workflow,  # workflows always save their results
            strict=self.settings.strict,
            default_folder=self.settings.resolved_results_dir(),
            on_make_default=self.make_default_folder,
        )
        if result is None:
            return
        # what the tool stores: no folder if it follows the default folder
        stored = result.stored_autosave or result.execution.autosave
        self.settings_manager.set_tool(tool, result.config, stored)

        task_runner = self.flimanalyzer.get_task_runner()
        autosave = result.execution.autosave
        if is_workflow:
            folder = canonical_folder(
                autosave.results_dir or self.settings.resolved_results_dir()
            )
            autosave_dir = os.path.join(folder, tool.name)

            def start_run(cancel_token, on_progress, on_start):
                return tool().run_flow(
                    *result.inputs,
                    config=result.config,
                    task_runner=task_runner,
                    autosave_dir=autosave_dir,
                    on_progress=on_progress,
                    cancel_token=cancel_token,
                    on_start=on_start,
                    # the dialog showed the guesses; default: guess (app setting strict)
                    strict=bool(self.settings.strict),
                    settings_record=self.settings_manager.record(),
                    save_formats=autosave.formats,
                )

        else:
            configs = tool().map_configs(result.config)
            autosave_dir = (
                canonical_folder(str(autosave.results_dir)) if autosave.enabled else None
            )

            def interactive_analysis():
                for config in configs:
                    tool()(*result.inputs, config=config, task_tags=tool.name)

            def start_run(cancel_token, on_progress, on_start):
                return run_flow(
                    "Interactive Analysis",
                    interactive_analysis,
                    task_runner=task_runner,
                    autosave_dir=autosave_dir,
                    on_progress=on_progress,
                    cancel_token=cancel_token,
                    on_start=on_start,
                    settings_record=self.settings_manager.record(),
                    save_formats=autosave.formats,
                )

        flow_run = self.run_with_progress(tool.name, start_run)
        if flow_run is None:
            return  # cancelled or stopped by an error, already reported
        if is_workflow:
            self.show_workflow_graph(flow_run)
            # always: how the run ended, its results folder and Prefect flow run
            self.show_run_summary(tool.name, flow_run)
            return
        self.show_results(flow_run)
        if flow_run.warnings:
            wx.MessageBox(
                "\n\n".join(f"{label}: {message}" for label, message in flow_run.warnings),
                f"{tool.name}: warning",
                wx.OK | wx.ICON_WARNING,
            )
        if flow_run.failed:
            wx.MessageBox(
                "The following tasks failed, see the log for details:\n"
                + "\n".join(flow_run.failed),
                tool.name,
                wx.OK | wx.ICON_WARNING,
            )

    def show_workflow_graph(self, flow_run):
        """Opens a window with the graph of a workflow's tasks."""
        fig, _ = WorkflowGraph(flow_run).get_plot(pick_event=self.OnPick)
        event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
        event.SetEventInfo(fig, f"{flow_run.name} Graph", "createnew")
        self.GetEventHandler().ProcessEvent(event)

    def show_results(self, flow_run):
        """Opens a window for each table and figure the run produced. Results the run
        saved (autosave) open as saved, the others as modified."""
        saved = flow_run.autosave_dir is not None
        for results in flow_run.results():
            if not isinstance(results, dict):
                continue
            for title, result in results.items():
                if isinstance(result, pd.DataFrame):
                    event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
                    event.SetEventInfo(
                        result, title, "createnew", showcolindex=False, modified=not saved
                    )
                    self.GetEventHandler().ProcessEvent(event)
                elif isinstance(result, matplotlib.figure.Figure):
                    self.open_plot(result, title, modified=not saved)

    def run_with_progress(self, title, start_run):
        """Runs a flow behind a modal progress dialog with a Cancel button.

        Args:
            title: name of the tool or workflow.
            start_run: ``start_run(cancel_token, on_progress, on_start)`` runs the
                flow and returns its FlowRun; it is called in a worker thread.

        Returns:
            The FlowRun of a run that ended normally, or None if it was cancelled
            (the user is told where its results are) or stopped by an error.
        """
        dlg = RunProgressDialog(self, title, start_run)
        dlg.ShowModal()
        flow_run, error = dlg.run, dlg.error
        dlg.Destroy()
        if error is not None:
            wx.MessageBox(
                f"{title} stopped with an error, see the log for details:\n{error}",
                title,
                wx.OK | wx.ICON_ERROR,
            )
            return None
        if flow_run.state == "cancelled":
            self.show_run_summary(title, flow_run)
            return None
        return flow_run

    def show_run_summary(self, title, flow_run):
        """Shows how a run ended, with links to its results and Prefect flow run."""
        dlg = RunSummaryDialog(self, title, flow_run)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_hover(self, event):
        print(event)

    def register_window(self, window, value, title, modified=False, source=None):
        """Add a window's value as an item of the DataManager and list the window in
        the Window menu.

        The window's title becomes the item's (unique) title; the window reports its
        modified state through its `on_modified` callback.

        Args:
            window: The table or plot window.
            value: Its table or figure.
            title: The wanted title.
            modified: Whether the value has changes not saved to a file.
            source: Where it came from, e.g. a file path.

        Returns:
            The item.
        """
        item = self.data_manager.add(value, title, modified=modified, source=source)
        window.item_id = item.id
        window.SetTitle(item.title)
        window.on_modified = lambda m, i=item.id: self.data_manager.set_modified(i, m)
        self.windowframes[item.id] = window
        mitem = self.windowmenu.Append(wx.Window.NewControlId(), item.title)
        self._menu_items[item.id] = mitem.GetId()
        if isinstance(window, PandasFrame):
            self.window_zorder.append(item.id)
        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)
        return item

    def remove_window(self, item_id) -> bool:
        """Remove a closing window from the Window menu and close its item."""
        if item_id not in self.windowframes:
            return False
        del self.windowframes[item_id]
        menu_id = self._menu_items.pop(item_id, None)
        if menu_id is not None:
            self.windowmenu.Remove(menu_id)
        self.window_zorder = [i for i in self.window_zorder if i != item_id]
        self.data_manager.close(item_id)
        return True

    def OnDataWindowRequest(self, event):
        data = event.GetData()
        action = event.GetAction()
        title = event.GetTitle()
        logger.debug(f"{title}: {action}")
        if action == "createnew":
            title = self.unique_window_title(title)
            frame = PandasFrame(
                self,
                title,
                self.filters,  # shared by the data windows
                data,
                showcolindex=event.ShowColIndex(),
                analyzable=event.IsAnalyzable(),
                groups=event.GetGroups(),
                savemodified=event.SaveModified(),
                enableclose=event.IsEnableClose(),
                on_filters_changed=self.report_filters,
            )
            frame.set_modified(event.IsModified())
            frame.Show(True)
            self.register_window(frame, data, title, modified=event.IsModified())

    def OnRequestRenameDataWindow(self, original, new, frame):
        item_id = self._own_item(frame)
        if item_id is None:
            return
        item = self.data_manager.rename(item_id, new)
        menu_id = self._menu_items.get(item.id)
        if menu_id is not None:
            self.windowmenu.FindItemById(menu_id).SetItemLabel(item.title)
        pub.sendMessage(RENAMED_DATA_WINDOW, original=original, new=item.title, frame=frame)

    def OnClosingDataWindow(self, data, frame):
        logger.debug(f"{frame.GetLabel()}")
        item_id = self._own_item(frame)
        if item_id is not None:
            self.remove_window(item_id)

    def OnPick(self, event):
        if not event.mouseevent.dblclick:
            return  # only double clicks open the axis and label dialogs
        else:
            ax = event.artist.axes
            fig = event.artist.get_figure()
            if isinstance(event.artist, matplotlib.axis.YAxis):
                dlg = ConfigureAxisDlg(
                    self,
                    "Set Y Axis",
                    {
                        "label": event.artist.get_label_text(),
                        "min": ax.get_ylim()[0],
                        "max": ax.get_ylim()[1],
                    },
                )
                response = dlg.ShowModal()
                if response == wx.ID_OK:
                    newsettings = dlg.get_settings()
                    event.artist.set_label_text(newsettings["label"], picker=True)
                    ax.set_ylim(newsettings["min"], newsettings["max"])
                    fig.canvas.draw_idle()
                    self._plot_edited(fig)
            elif isinstance(event.artist, matplotlib.axis.XAxis):
                dlg = ConfigureAxisDlg(
                    self,
                    "Set X Axis",
                    {
                        "label": event.artist.get_label_text(),
                        "min": ax.get_xlim()[0],
                        "max": ax.get_xlim()[1],
                    },
                )
                response = dlg.ShowModal()
                if response == wx.ID_OK:
                    newsettings = dlg.get_settings()
                    event.artist.set_label_text(newsettings["label"], picker=True)
                    ax.set_xlim(newsettings["min"], newsettings["max"])
                    fig.canvas.draw_idle()
                    self._plot_edited(fig)
            elif isinstance(event.artist, matplotlib.text.Text):
                dlg = wx.TextEntryDialog(self, "Label", "Update Label")
                dlg.SetValue(event.artist.get_text())
                if dlg.ShowModal() == wx.ID_OK:
                    event.artist.set_text(dlg.GetValue())
                    fig.canvas.draw_idle()
                    self._plot_edited(fig)
                dlg.Destroy()
            elif isinstance(event.artist, matplotlib.lines.Line2D):
                data = wx.ColourData()
                data.SetColour(event.artist.get_color())
                dlg = wx.ColourDialog(self, data)
                if dlg.ShowModal() == wx.ID_OK:  # Cancel keeps the color (#188)
                    color = dlg.GetColourData().GetColour()
                    event.artist.set_color(
                        (color.Red() / 255, color.Green() / 255, color.Blue() / 255)
                    )
                    event.artist.set_alpha(color.Alpha() / 255)
                    fig.canvas.draw_idle()
                    self._plot_edited(fig)
                dlg.Destroy()

    def _plot_edited(self, figure) -> None:
        """Mark the plot window of a figure as modified after an edit in it."""
        for window in self.windowframes.values():
            if isinstance(window, PlotFrame) and window.figure is figure:
                window.modified = True

    def OnPlotWindowRequest(self, event):
        if event.GetAction() == "createnew":
            self.open_plot(event.GetFigure(), event.GetTitle(), modified=True)

    def open_plot(self, figure, title, modified=True):
        """Open a figure in a plot window, as an item of the DataManager.

        Args:
            figure: The figure.
            title: The wanted title.
            modified: Whether it has changes not saved to a file.

        Returns:
            The plot window.
        """
        frame = PlotFrame(self, figure, self.unique_window_title(title))
        frame.Bind(wx.EVT_CLOSE, self.OnClosingPlotWindow)
        figure.canvas.mpl_connect("pick_event", self.OnPick)
        self.register_window(frame, figure, title, modified=modified)
        frame.modified = modified
        frame.Show()
        return frame

    def OnClosingPlotWindow(self, event):
        logger.debug("appframe.OnClosingPlotWindow")
        self.remove_window(getattr(event.GetEventObject(), "item_id", None))
        event.Skip()

    def _raise_window(self, item_id, window):
        if isinstance(window, wx.Frame):
            window.Raise()
            if isinstance(window, PandasFrame) and self.window_zorder[-1] != item_id:
                self.window_zorder = [i for i in self.window_zorder if i != item_id]
                self.window_zorder.append(item_id)

    def OnWindowSelectedInMenu(self, event):
        menu_id = event.GetId()
        item_id = next((i for i, m in self._menu_items.items() if m == menu_id), None)
        if item_id in self.windowframes:
            self._raise_window(item_id, self.windowframes[item_id])
        logger.debug(f"select window {self.window_zorder}")

    def OnExit(self, event):
        self.Close()

    def unsaved_windows(self) -> list[str]:
        """Titles of the data windows with unsaved changes that ask to be saved when
        closed."""
        return [
            self.data_manager.get(item_id).title
            for item_id, window in self.windowframes.items()
            if isinstance(window, PandasFrame)
            and window
            and window.savemodied
            and window.modified
        ]

    def OnCloseApp(self, event):
        """Asks before quitting with unsaved windows (if the close event can be
        vetoed), because closing the main window destroys them without their own save
        question. Vetoes the close unless the user chooses how to quit."""
        if event.CanVeto() and not self.confirm_quit():
            event.Veto()
            return
        event.Skip()

    def unsaved_items(self) -> list:
        """Return the open windows with unsaved changes that ask to be saved, as
        (window, title) pairs: tables that ask when closed, and plots."""
        unsaved = []
        for item_id, window in self.windowframes.items():
            if not window or not window.modified:
                continue
            if isinstance(window, PandasFrame) and not window.savemodied:
                continue
            unsaved.append((window, self.data_manager.get(item_id).title))
        return unsaved

    def confirm_quit(self) -> bool:
        """Ask what to do with unsaved windows before quitting.

        Cancel keeps FLIMAnalyzer open; Review... asks window by window (Save, Don't
        Save, Cancel); Save All Windows... saves them all (save_all_windows); Discard
        All quits without saving.

        Returns:
            Whether to quit.
        """
        from flim.gui.saveall import CANCEL, DISCARD, REVIEW, ask_quit, ask_review

        unsaved = self.unsaved_items()
        if not unsaved:
            return True
        choice = ask_quit(self, [title for _, title in unsaved])
        if choice == CANCEL:
            return False
        if choice == DISCARD:
            return True
        if choice == REVIEW:
            for window, title in unsaved:
                window.Raise()
                answer = ask_review(self, title)
                if answer == CANCEL:
                    return False
                if answer == "save" and not self.save_window(window, title):
                    return False  # cancelled or failed: stay open
            return True
        return self.save_all_windows(quitting=True)

    def save_window(self, window, title) -> bool:
        """Save one window as its own save button does (a table with all its rows);
        mark it saved. Returns whether it was saved."""
        from flim.gui.dialogs import save_dataframe, save_figure

        if isinstance(window, PandasFrame):
            path = save_dataframe(
                window, f"Save {title}", window.data, title, saveindex=window.showcolindex
            )
        else:
            path = save_figure(window, f"Save {title}", window.figure, title)
        if path:
            window.modified = False
        return bool(path)

    def save_all_windows(self, quitting: bool = False) -> bool:
        """File > Save All Windows...: save every open table (all rows) and plot into
        a new subfolder of a folder, in the formats chosen; mark them saved.

        The folder is the one last used for this in the session, else the app's
        results folder; choosing it does not change the results folder.

        Args:
            quitting: Called when quitting: no message if there are no windows.

        Returns:
            Whether every window was saved (True if there are none).
        """
        from flim.core.saving import save_all
        from flim.core.types import DataType
        from flim.gui.saveall import ask_save_all

        windows = [
            (window, self.data_manager.get(item_id).title)
            for item_id, window in self.windowframes.items()
            if window
        ]
        if not windows:
            if not quitting:
                wx.MessageBox("There are no windows to save.", "Save All Windows", wx.OK)
            return True
        values = [w.data if isinstance(w, PandasFrame) else w.figure for w, _ in windows]
        kinds = []
        for value in values:
            data_type = DataType.of(value)
            if data_type and data_type.save_options and data_type.kind not in kinds:
                kinds.append(data_type.kind)
        folder = self._save_all_dir or self.settings.resolved_results_dir()
        answer = ask_save_all(self, folder, kinds)
        if answer is None:
            return False
        folder, formats = answer
        self._save_all_dir = folder
        target, saved, failed = save_all(
            [(title, value) for (_, title), value in zip(windows, values)], folder, formats
        )
        saved_titles = {title for title, _ in saved}
        for window, title in windows:
            if title in saved_titles:
                window.modified = False
        message = f"Saved {len(saved)} window(s) in {target}."
        if failed:
            message += "\n\nNot saved:\n" + "\n".join(f"{t}: {e}" for t, e in failed)
        wx.MessageBox(
            message, "Save All Windows", wx.OK | (wx.ICON_WARNING if failed else 0)
        )
        return not failed

    def OnDocumentation(self, event):
        wx.LaunchDefaultBrowser(docs_url())

    def OnAbout(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName("FLIMAnalyzer")
        info.SetVersion(__version__)
        info.SetDescription(
            "Analysis of Fluorescence Lifetime Imaging Microscopy (FLIM) data"
        )
        info.SetWebSite(DOCS_URL)
        wx.adv.AboutBox(info, self)

    def get_window_frames(self):
        return [
            x
            for x in self.GetChildren()
            if isinstance(x, wx.Frame)
        ]

    def make_default_folder(self, folder) -> None:
        """Make a folder the app's default results folder (results_dir), in the user
        settings file: tools without a folder of their own save there."""
        self.settings_manager.update({"results_dir": str(folder)})

    def unique_window_title(self, title):
        """Return a title no open window has (DataManager.unique_title)."""
        return self.data_manager.unique_title(title)

    def windows_by_title(self) -> dict:
        """Return the open windows by their items' titles."""
        return {self.data_manager.get(i).title: w for i, w in self.windowframes.items()}

    def window_titled(self, title):
        """Return the open window with a title, or None."""
        item = self.data_manager.find(title)
        return self.windowframes.get(item.id) if item else None

    def OnCloseAll(self, event):
        logger.debug("appframe.OnCloseAll")
        # a copy: closing a window removes it from self.windowframes
        for window in list(self.windowframes.values()):
            if window:
                window.Close()

    def OnImport(self, event):
        logger.debug(f"###############  OLD IMPORT: datatypes\n{self.rawdata.dtypes}")

    def OnDataUpdated(self, event):
        data, datatype = event.GetUpdatedData()
        logger.debug(f"###############  OLD appframe.OnDataUpdated - {datatype}")

    def OnRangeFilterUpdated(self, event):
        rfilters = event.GetUpdatedItems()
        logger.debug(
            "###############  OLD appframe.OnRangeFilterUpdated -"
            f" {len(rfilters)} Filters updated:"
        )

    def OnApplyFilter(self, event):
        logger.debug("###############  OLD AppFrame.OnApplyFilter")
        self.data = event.data
        self.analysistab.update_data(event.data)

    def OnAnalysisUpdated(self, event):
        updated = event.GetUpdatedItems()
        logger.debug(f"appframe.OnAnalysisUpdated - {len(updated)} Analysis updated:")
        for key in updated:
            logger.debug(f"\t {key} {updated[key]}")
