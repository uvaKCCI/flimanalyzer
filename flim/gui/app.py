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
from flim.core.settings import AppSettings
from flim.core.settingsmgr import SettingsManager, UserSettingsFile, user_settings_path
from flim.core.preprocessor import defaultpreprocessor
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
    NEW_DATA_WINDOW,
    CLOSING_DATA_WINDOW,
    REQUEST_RENAME_DATA_WINDOW,
    RENAMED_DATA_WINDOW,
    DATA_IMPORTED,
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
        if self.flimanalyzer is not None:
            self.start()
        return True

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
        self.windowframes = {}
        self.window_zorder = []

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

    def OnDataWindowFocused(self, data, frame):
        title = frame.GetTitle()
        self.window_zorder = [w for w in self.window_zorder if w != title]
        self.window_zorder.append(title)

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

        pub.sendMessage(DATA_IMPORTED, olddata=None, data=data)
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
            imported, preprocess = settings.import_, settings.preprocess
            # for this session only: they include data file paths
            self.settings_manager.update(
                {
                    "import": imported.model_dump(mode="json", by_alias=True),
                    "preprocess": preprocess.model_dump(mode="json"),
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

            preprocessor = defaultpreprocessor()
            preprocessor.set_replacementheaders(preprocess.rename)
            preprocessor.set_dropcolumns(preprocess.drop)

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

            # pub.sendMessage(DATA_IMPORTED, olddata=None, data=data)
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
        if len(self.window_zorder) == 0:
            return None, None
        title = self.window_zorder[-1]
        dataview = self.windowframes[title].GetViewData()
        return title, dataview

    def get_alldata(self):
        if len(self.window_zorder) == 0:
            return {}
        return {
            title: frame.GetViewData()
            for title, frame in self.windowframes.items()
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
        first."""
        title, currentdata = self.get_currentdata()
        data_choices = {title: currentdata} if title else {}
        data_choices.update(self.get_alldata())
        return data_choices

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
        folder = (entry and entry.results_dir) or self.settings.resolved_results_dir()
        execution = self.flimanalyzer.execution.model_copy(
            update={
                "autosave": bool(entry and entry.autosave) and bool(folder),
                "results_dir": folder,
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
        )
        if result is None:
            return
        self.settings_manager.set_tool(
            tool,
            result.config,
            result.execution.autosave,
            result.execution.results_dir,
        )

        task_runner = self.flimanalyzer.get_task_runner()
        execution = result.execution
        if is_workflow:
            folder = canonical_folder(
                execution.results_dir or self.settings.resolved_results_dir()
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
                )

        else:
            configs = tool().map_configs(result.config)
            autosave_dir = (
                canonical_folder(str(execution.results_dir)) if execution.autosave else None
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
        """Opens a window for each table and figure the run produced."""
        for results in flow_run.results():
            if not isinstance(results, dict):
                continue
            for title, result in results.items():
                if isinstance(result, pd.DataFrame):
                    event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
                    event.SetEventInfo(result, title, "createnew", showcolindex=False)
                    self.GetEventHandler().ProcessEvent(event)
                elif isinstance(result, matplotlib.figure.Figure):
                    event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
                    event.SetEventInfo(result, title, "createnew")
                    self.GetEventHandler().ProcessEvent(event)

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

    def append_window_to_menu(self, title, window):
        self.windowframes[title] = window
        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
        if isinstance(window, PandasFrame):
            self.window_zorder = [w for w in self.window_zorder if w != title]
            self.window_zorder.append(title)
        logger.debug(f"append window {self.window_zorder}")
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
                logger.debug(f"remove window {self.window_zorder}")
                return True
        return False

    def OnDataWindowRequest(self, event):
        data = event.GetData()
        action = event.GetAction()
        title = event.GetTitle()
        logger.debug(f"{title}: {action}")
        if action == "update":
            frame = self.windowframes.get(title)
            if frame:
                frame = self.windowframes[title]
                frame.SetData(data)
                frame.set_modified(event.IsModified())
            else:
                action = "createnew"
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
            self.append_window_to_menu(title, frame)
            pub.sendMessage(NEW_DATA_WINDOW, data=data, frame=frame)

    def OnRequestRenameDataWindow(self, original, new, frame):
        title = self.unique_window_title(new)
        self.window_zorder = [title if t == original else t for t in self.window_zorder]
        for mitem in self.windowmenu.GetMenuItems():
            if mitem.GetItemLabelText() == original:
                mitem.SetItemLabel(title)
                del self.windowframes[original]
                self.windowframes[title] = frame
                pub.sendMessage(
                    RENAMED_DATA_WINDOW, original=original, new=title, frame=frame
                )
                return

    def OnClosingDataWindow(self, data, frame):
        title = frame.GetLabel()
        logger.debug(f"{title}")
        self.remove_window_from_menu(title)

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
            elif isinstance(event.artist, matplotlib.text.Text):
                dlg = wx.TextEntryDialog(self, "Label", "Update Label")
                dlg.SetValue(event.artist.get_text())
                if dlg.ShowModal() == wx.ID_OK:
                    event.artist.set_text(dlg.GetValue())
                    fig.canvas.draw_idle()
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
                dlg.Destroy()

    def OnPlotWindowRequest(self, event):
        figure = event.GetFigure()
        title = self.unique_window_title(event.GetTitle())
        action = event.GetAction()
        logger.debug(f"{title}: {action}")
        if action == "createnew":
            frame = PlotFrame(self, figure, title)
            frame.Bind(wx.EVT_CLOSE, self.OnClosingPlotWindow)
            figure.canvas.mpl_connect("pick_event", self.OnPick)
            self.append_window_to_menu(title, frame)
            frame.Show()

    def OnClosingPlotWindow(self, event):
        logger.debug("appframe.OnClosingPlotWindow")
        self.remove_window_from_menu(event.GetEventObject().GetTitle())
        event.Skip()

    def _raise_window(self, title, window):
        if isinstance(window, wx.Frame):
            window.Raise()
            if isinstance(window, PandasFrame) and self.window_zorder[-1] != title:
                self.window_zorder = [w for w in self.window_zorder if w != title]
                self.window_zorder.append(title)

    def OnWindowSelectedInMenu(self, event):
        itemid = event.GetId()
        menu = event.GetEventObject()
        mitem = menu.FindItemById(itemid)
        if self.windowframes.get(mitem.GetItemLabelText()):
            wintitle = mitem.GetItemLabelText()
            window = self.windowframes[wintitle]
            self._raise_window(wintitle, window)
        logger.debug(f"select window {self.window_zorder}")

    def OnExit(self, event):
        self.Close()

    def unsaved_windows(self) -> list[str]:
        """Titles of the data windows with unsaved changes that ask to be saved when
        closed."""
        return [
            title
            for title, window in self.windowframes.items()
            if isinstance(window, PandasFrame)
            and window
            and window.savemodied
            and window.modified
        ]

    def OnCloseApp(self, event):
        """Asks before quitting with unsaved data windows (if the close event can be
        vetoed), because closing the main window destroys them without their own save
        question. Vetoes the close unless the user confirms."""
        unsaved = self.unsaved_windows()
        if unsaved and event.CanVeto():
            shown = "\n".join(unsaved[:10]) + ("\n..." if len(unsaved) > 10 else "")
            plural = "s have" if len(unsaved) > 1 else " has"
            dlg = wx.MessageDialog(
                self,
                f"{len(unsaved)} window{plural} unsaved results:\n\n{shown}\n\n"
                "Quit anyway? The unsaved results are lost.",
                "Quit FLIMAnalyzer",
                style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            )
            dlg.SetYesNoLabels("Quit", "Cancel")
            answer = dlg.ShowModal()
            dlg.Destroy()
            if answer != wx.ID_YES:
                event.Veto()
                return
        event.Skip()

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

    def unique_window_title(self, title):
        suffix = None
        i = 1
        while title in self.windowframes:
            if suffix:
                title = title[: -len(suffix)]
            suffix = f"-{i}"
            title = f"{title}{suffix}"
            i += 1
        return title

    def OnCloseAll(self, event):
        logger.debug("appframe.OnCloseAll")
        # a copy of the titles: closing a window removes it from self.windowframes
        windowtitles = [t for t in self.windowframes]
        for title in windowtitles:
            window = self.windowframes[title]
            if window:
                window.Close()
        self.window_zorder = []

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
