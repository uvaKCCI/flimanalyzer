#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May  7 21:00:30 2018

@author: khs3z
"""

import matplotlib

# matplotlib.use('WXAgg')
import matplotlib.pyplot as plt

import logging
import os
import numpy as np
import itertools
import pandas as pd
import json
import ctypes
import wx
import wx.adv
import wx.lib.agw.customtreectrl as CT

from pubsub import pub
from flim._version import __version__
from wx.lib.newevent import NewEvent
from importlib_resources import files

import flim.analysis
import flim.core.configuration as cfg
import flim.core.parser
import flim.core.preprocessor
import flim.gui.dialogs
import flim.resources
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.core.configuration import Config
from flim.core.preprocessor import defaultpreprocessor
from flim.core.importer import dataimporter
from flim.core.filter import RangeFilter
from flim.core.graph import WorkflowGraph
from flim.core.workflow import Workflow
from flim.core.registry import GUI_GROUP, TOOLS_GROUP, discover, tools
from flim.core.runner import run_flow
from flim.gui.configdialog import open_config_dialog
from flim.gui.icons import tool_bitmap
from flim.gui.delimpanel import DelimiterPanel
from flim.gui.macos import set_bundle_name, set_display_name
from flim.gui.plotframe import PlotFrame
from flim.gui.progressdlg import RunProgressDialog, RunSummaryDialog
from flim.gui.datapanel import PandasFrame
from flim.gui.dialogs import ConfigureCategoriesDlg
from flim.gui.dialogs import SelectGroupsDlg, ConfigureAxisDlg
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.events import (
    DataUpdatedEvent,
    EVT_DATAUPDATED,
    EVT_DU_TYPE,
    DataWindowEvent,
    EVT_DATA,
    EVT_DATA_TYPE,
    PlotEvent,
    EVT_PLOT,
    EVT_PLOT_TYPE,
)
from flim.gui.events import REQUEST_CONFIG_UPDATE, CONFIG_UPDATED
from flim.gui.events import (
    FOCUSED_DATA_WINDOW,
    NEW_DATA_WINDOW,
    CLOSING_DATA_WINDOW,
    REQUEST_RENAME_DATA_WINDOW,
    RENAMED_DATA_WINDOW,
    NEW_PLOT_WINDOW,
    DATA_IMPORTED,
    FILTERS_UPDATED,
    FILTERED_DATA_UPDATED,
    DATA_UPDATED,
    ANALYSIS_BINS_UPDATED,
)
from flim.gui.importdlg import ImportDlg
from flim.gui.listcontrol import (
    AnalysisListCtrl,
    FilterListCtrl,
    EVT_FILTERUPDATED,
    EVT_ANALYSISUPDATED,
)
from flim.gui.seriesfiltertree import SeriesFilterCtrl
import flim.tools  # noqa: F401  (registers the built-in tools)

# field editors of the tools that need more than the generated dialog
import flim.gui.dialogs.autoencoder  # noqa: F401
import flim.gui.dialogs.categoryorder  # noqa: F401
import flim.gui.dialogs.filter  # noqa: F401
import flim.gui.dialogs.unpivot  # noqa: F401
# key of the full config in a tool's settings, next to its plugin parameters
CONFIG_KEY = "_config"


def config_from_settings(tool, params):
    """The tool's config from its saved settings: the full config if it was saved,
    else converted from the plugin parameters; the defaults if neither is valid."""
    params = params if isinstance(params, dict) else {}
    try:
        if CONFIG_KEY in params:
            return tool.config_class.model_validate(params[CONFIG_KEY])
        return tool.config_class.from_legacy_params(params)
    except Exception as err:
        logging.warning(f"{tool.name}: settings not valid, using the defaults ({err})")
        return tool.config_class()


def settings_from_config(config, execution):
    """Settings to save: the plugin parameters (read by older versions), the full
    config, and autosave and the results folder."""
    params = config.to_legacy_params()
    params[CONFIG_KEY] = config.model_dump(mode="json")
    params["autosave"] = execution.autosave
    if execution.results_dir is not None:
        params["working_dir"] = str(execution.results_dir)
    return params


ImportEvent, EVT_IMPORT = NewEvent()
ApplyFilterEvent, EVT_APPLYFILTER = NewEvent()
DataUpdateEvent, EVT_UPDATEDATA = NewEvent()

DEFAULT_CONFIFG_FILE = "defaults.json"


def app_icon():
    """The FLIMAnalyzer application icon."""
    return wx.Icon(str(files(flim.resources).joinpath("flimanalyzer.png")), wx.BITMAP_TYPE_PNG)


def app_icons():
    """The application icon in all sizes, so each window picks a sharp one."""
    return wx.IconBundle(str(files(flim.resources).joinpath("flimanalyzer.ico")), wx.BITMAP_TYPE_ICO)


class FLIMAnalyzerApp(wx.App):
    def __init__(self, flimanalyzer, config=None, files=None):
        """
        Args:
            files: data files to open at startup, each in its own data window.
        """
        self.flimanalyzer = flimanalyzer
        self.files = list(files or [])
        # tools of other packages, and their dialogs (entry points)
        discover(TOOLS_GROUP)
        discover(GUI_GROUP)
        if config is None or not isinstance(config, Config):
            self.config = Config()
            self.config.read_from_json(DEFAULT_CONFIFG_FILE, defaultonfail=True)
        else:
            self.config = config
        set_bundle_name("FLIMAnalyzer")  # before wx registers the app with macOS
        super().__init__()

    def OnInit(self):
        self.SetAppName("FLIMAnalyzer")
        self.SetAppDisplayName("FLIMAnalyzer")
        set_display_name("FLIMAnalyzer")
        self.frame = AppFrame(self.flimanalyzer, self.config)
        self.dock_icon = None
        if wx.Platform == "__WXMAC__":
            # the Dock shows the Python icon unless it is replaced here
            self.dock_icon = wx.adv.TaskBarIcon(wx.adv.TBI_DOCK)
            self.dock_icon.SetIcon(app_icon(), "FLIMAnalyzer")
        self.frame.Show(True)
        if self.files:
            wx.CallAfter(self.open_files, self.files)
        return True

    def open_files(self, files):
        """Opens each file in a data window; reports files that cannot be read."""
        failed = []
        for f in files:
            try:
                if not os.path.isfile(f) or self.frame.open_data_files([f]) is None:
                    failed.append(f)
            except Exception as e:
                logging.exception(f"Could not open {f}")
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
    def __init__(self, flimanalyzer, config=None):
        self.flimanalyzer = flimanalyzer
        if config:
            self.config = config
        else:
            self.config = cfg.Config()
            self.config.create_default()
        # self.analyzers = flim.analysis.absanalyzer.get_analyzer_classes()
        # self.workflows = flim.workflow.basicflow.get_workflow_classes()
        # self.rawdata = None
        # self.data = None
        # self.filtereddata = None
        self.windowframes = {}
        self.window_zorder = []

        version = __version__
        super(AppFrame, self).__init__(
            None, wx.ID_ANY, title=f"FLIMAnalyzer {version}"
        )  # , size=(600, 500))

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
        exitmenuitem = filemenu.Append(wx.ID_ANY, "Exit", "Exit the application")
        settingsmenu = wx.Menu()
        loadsettingsitem = settingsmenu.Append(wx.ID_ANY, "Load settings...")
        savesettingsitem = settingsmenu.Append(wx.ID_ANY, "Save settings...")

        self.windowmenu = wx.Menu()
        closeallitem = self.windowmenu.Append(wx.ID_ANY, "Close all windows")
        self.windowmenu.AppendSeparator()

        menubar.Append(filemenu, "&File")
        menubar.Append(settingsmenu, "&Settings")
        for category in tools.categories():
            menubar.Append(self._create_tool_menu(category), f"&{category}")
        menubar.Append(self.windowmenu, "&Window")

        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.OnLoadData, loadmenuitem)
        self.Bind(wx.EVT_MENU, self.OnImportData, importmenuitem)
        self.Bind(wx.EVT_MENU, self.OnExit, exitmenuitem)
        self.Bind(wx.EVT_MENU, self.OnLoadSettings, loadsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnSaveSettings, savesettingsitem)
        self.Bind(wx.EVT_MENU, self.OnCloseAll, closeallitem)

        self._layout_tool_groups(rows=2)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(self.toolpanel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        # size the window to the tool rows
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.Centre()
        self.Show(True)

        # Create a panel and notebook (tabs holder)
        # nb = wx.Notebook(self)

        # Create the tab windows
        # self.analysistab = TabAnalysis(nb, self, self.flimanalyzer, self.config)

        # Add the windows to tabs and name them.
        # nb.AddPage(self.analysistab, "Analyze")

        #        self.update_tabs()

        # Set noteboook in a sizer to create the layout
        # sizer = wx.BoxSizer()
        # sizer.Add(nb, 1, wx.EXPAND)

        # sizer.SetSizeHints(self)
        # self.SetSizerAndFit(sizer)

        self.Bind(EVT_IMPORT, self.OnImport)
        self.Bind(EVT_DATA, self.OnDataWindowRequest)
        self.Bind(EVT_PLOT, self.OnPlotWindowRequest)
        self.Bind(EVT_DATAUPDATED, self.OnDataUpdated)
        self.Bind(EVT_APPLYFILTER, self.OnApplyFilter)
        self.Bind(EVT_FILTERUPDATED, self.OnRangeFilterUpdated)
        self.Bind(EVT_ANALYSISUPDATED, self.OnAnalysisUpdated)
        #        pub.subscribe(self.OnNewDataWindow, NEW_DATA_WINDOW)
        # pub.subscribe(self.OnDataImported, DATA_IMPORTED)
        # pub.subscribe(self.OnFilteredDataUpdated, FILTERED_DATA_UPDATED)
        pub.subscribe(self.OnDataWindowFocused, FOCUSED_DATA_WINDOW)
        pub.subscribe(self.OnClosingDataWindow, CLOSING_DATA_WINDOW)
        pub.subscribe(self.OnRequestRenameDataWindow, REQUEST_RENAME_DATA_WINDOW)
        # pub.subscribe(self.OnNewPlotWindow, NEW_PLOT_WINDOW)

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

    #    def OnNewDataWindow(self, data, frame):
    #        title = frame.GetLabel()
    #        print "appframe.OnNewDataWindow - %s" % (title)
    #        self.windowframes[frame.GetLabel()] = frame
    #        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
    #        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)

    def _get_window_frame(self, obj_id):
        for title, window in self.windowframes.items():
            if isinstance(window, PandasFrame) and id(window.GetData()) == obj_id:
                logging.debug(
                    f"selected: title={title}, obj_id={obj_id},"
                    f" id={id(window.GetData())}"
                )
                return title, window
            elif isinstance(window, PlotFrame) and id(window.figure) == obj_id:
                logging.debug(
                    f"selected: title={title}, obj_id={obj_id}, id={id(window)}"
                )
                return title, window
        return

    def OnDataWindowFocused(self, data, frame):
        title = frame.GetTitle()
        self.window_zorder = [w for w in self.window_zorder if w != title]
        self.window_zorder.append(title)

    def OnLoadData(self, event):
        dlg = ImportDlg(
            self,
            "Open File",
            self.config,
            parsefname=False,
            preprocess=False,
            singlefile=True,
        )
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_config()
            self.open_data_files(
                config.get([cfg.CONFIG_INCLUDE_FILES]), config.get([cfg.CONFIG_DELIMITER])
            )

    def open_data_files(self, files, delimiter=None):
        """Opens data files in a data window, as File > Open does.

        Args:
            files: paths of the files; several files are combined in one table.
            delimiter: column delimiter characters, default: from the settings
                (tab and comma).

        Returns:
            str: title of the data window, or None if no file could be read.
        """
        importer = dataimporter()
        importer.set_delimiter(delimiter or self.config.get([cfg.CONFIG_DELIMITER]))
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
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(
            data,
            windowtitle,
            "update",
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
        dlg = ImportDlg(self, "Import File(s)", self.config)
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_config()

            parsername = config.get([cfg.CONFIG_PARSER_CLASS])
            parser = flim.core.parser.instantiate_parser(
                "flim.core.parser." + parsername
            )
            if parser is None:
                logging.warning(f"Could not instantiate parser {parsername}")
                return
            parser.set_regexpatterns(config.get([cfg.CONFIG_PARSER_PATTERNS]))

            preprocessor = defaultpreprocessor()
            preprocessor.set_replacementheaders(config.get([cfg.CONFIG_HEADERS]))
            preprocessor.set_dropcolumns(config.get([cfg.CONFIG_DROP_COLUMNS]))

            importer = dataimporter()
            importer.set_parser(parser)
            importer.set_delimiter(config.get([cfg.CONFIG_DELIMITER]))
            importer.set_files(config.get([cfg.CONFIG_INCLUDE_FILES]))
            importer.set_column_combos(config.get([cfg.CONFIG_CATEGORY_COMBINATIONS]))
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
                "update",
                config=None,
                showcolindex=False,
                analyzable=True,
                savemodified=True,
                enableclose=True,
            )
            self.GetEventHandler().ProcessEvent(event)

    def OnLoadSettings(self, event):
        logging.debug("Loading settings.")
        with wx.FileDialog(
            self,
            "Load Configuration file",
            wildcard="json files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_CHANGE_DIR,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            configfile = fileDialog.GetPath()
            config = Config()
            if config.read_from_json(configfile):
                missing, invalid = config.validate()
                if len(missing) == 0 and len(invalid) == 0:
                    self.config = config
                else:
                    message = ""
                    if len(missing) > 0:
                        message += "Missing keys:\n%s\n\n" % "\n".join(
                            [str(m) for m in missing]
                        )
                    if len(invalid) > 0:
                        message += "Missing values:\n%s\n\n" % "\n".join(
                            [str(i) for i in invalid]
                        )
                    dlg = wx.MessageDialog(
                        None,
                        message + "\nDo you want to try to fix them?",
                        "Error: Loaded settings are not valid.",
                        wx.YES_NO | wx.ICON_QUESTION,
                    )
                    result = dlg.ShowModal()
                    if result == wx.ID_YES:
                        if config.fix():
                            self.config = config
                        else:
                            wx.MessageBox(
                                "Attempt to fix settings failed",
                                "Error",
                                wx.OK | wx.ICON_INFORMATION,
                            )
                            return
                    else:
                        return
                pub.sendMessage(
                    CONFIG_UPDATED,
                    source=self,
                    config=self.config,
                    updated=self.config.get(),
                )
            else:
                wx.MessageBox(
                    "Error loading settings from %s" % configfile,
                    "Error",
                    wx.OK | wx.ICON_INFORMATION,
                )

    def OnSaveSettings(self, event):
        logging.debug("appframe.OnSaveSettings")
        logging.debug(self.config.get())
        with wx.FileDialog(
            self,
            "Save Configuration file",
            wildcard="json files (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            configfile = fileDialog.GetPath()
            self.config.write_to_json(configfile)

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
        """The open tables, the current one first."""
        title, currentdata = self.get_currentdata()
        data_choices = {title: currentdata} if title else {}
        data_choices.update(self.get_alldata())
        return data_choices

    def run_tool(self, tool):
        """Configures a tool in its dialog and runs it on the selected tables."""
        data_choices = self.tool_data_choices()
        if not data_choices:
            wx.MessageBox("Open or import data first.", tool.name, wx.OK)
            return
        params, keys = self.config.get([cfg.CONFIG_PLUGINS, tool.name], returnkeys=True)
        for name in tool.former_names if not params else ():
            # settings saved under an earlier name; saved under the new one below
            params = self.config.get([cfg.CONFIG_PLUGINS, name])
            if params:
                break
        params = params if isinstance(params, dict) else {}
        config = config_from_settings(tool, params)
        folder = params.get("working_dir") or self.config.get(cfg.CONFIG_WORKINGDIR)
        execution = self.flimanalyzer.execution.model_copy(
            update={
                "autosave": bool(params.get("autosave")) and bool(folder),
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
        )
        if result is None:
            return
        settings = settings_from_config(result.config, result.execution)
        if keys:
            self.config.update(settings, keys)
        else:  # a tool without saved settings, e.g. of another package
            _, plugin_keys = self.config.get([cfg.CONFIG_PLUGINS], returnkeys=True)
            self.config.update(
                {tool.name: settings}, plugin_keys or [cfg.CONFIG_PLUGINS]
            )

        task_runner = self.flimanalyzer.get_task_runner()
        execution = result.execution
        if is_workflow:
            folder = execution.results_dir or self.config.get(cfg.CONFIG_WORKINGDIR)
            autosave_dir = os.path.join(str(folder), tool.name)

            def start_run(cancel_token, on_progress, on_start):
                return tool().run_flow(
                    *result.inputs,
                    config=result.config,
                    task_runner=task_runner,
                    autosave_dir=autosave_dir,
                    on_progress=on_progress,
                    cancel_token=cancel_token,
                    on_start=on_start,
                )

        else:
            configs = tool().map_configs(result.config)
            autosave_dir = str(execution.results_dir) if execution.autosave else None

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

    def OnDataWindowRequest(self, event):
        data = event.GetData()
        config = self.config  # event.GetConfig()
        action = event.GetAction()
        title = event.GetTitle()
        logging.debug(f"{title}: {action}")
        if action == "update":
            frame = self.windowframes.get(title)
            if frame:
                frame = self.windowframes[title]
                frame.SetData(data)
                frame.set_modified(event.IsModified())
                # frame.SetConfog(config)
            else:
                action = "createnew"
        if action == "createnew":
            title = self.unique_window_title(title)
            frame = PandasFrame(
                self,
                title,
                config,
                data,
                showcolindex=event.ShowColIndex(),
                analyzable=event.IsAnalyzable(),
                groups=event.GetGroups(),
                savemodified=event.SaveModified(),
                enableclose=event.IsEnableClose(),
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
        logging.debug(f"{title}")
        self.remove_window_from_menu(title)

    def OnPick(self, event):
        if not event.mouseevent.dblclick:
            """
            try:
                print(event.artist.get_label())
                obj_id = int(event.artist.get_label())
                py_obj = ctypes.cast(obj_id, ctypes.py_object).value
                if issubclass(type(py_obj), AbstractPlugin):
                    py_obj.run_configuration_dialog(self)
                elif issubclass(type(py_obj), State):
                    print(py_obj.result)
                    print(f"is_mappeed={py_obj.is_mapped()}, {py_obj._result.location}")
                title, window = self._get_window_frame(obj_id)
                if window:
                    self._raise_window(title, window)
                else:
                    if issubclass(type(py_obj), AbstractPlugin):
                        py_obj.run_configuration_dialog(self)
            except Exception as e:
                logging.error(e)
            """
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
                # event.artist.set_dashes((5, 2, 1, 2))
                # event.artist.set_linewidth(2)
                data = wx.ColourData()
                data.SetColour(event.artist.get_color())
                dlg = wx.ColourDialog(self, data)
                # dlg.Bind(wx.EVT_COLOUR_CHANGED, self.OnColourChanged)
                if dlg.ShowModal() == wx.ID_OK:
                    pass

                color = dlg.GetColourData().GetColour()
                event.artist.set_color(
                    (color.Red() / 255, color.Green() / 255, color.Blue() / 255)
                )
                event.artist.set_alpha(color.Alpha() / 255)
                fig.canvas.draw_idle()

    def OnPlotWindowRequest(self, event):
        figure = event.GetFigure()
        title = self.unique_window_title(event.GetTitle())
        action = event.GetAction()
        logging.debug(f"{title}: {action}")
        if action == "createnew":
            frame = PlotFrame(self, figure, title)
            frame.Bind(wx.EVT_CLOSE, self.OnClosingPlotWindow)
            figure.canvas.mpl_connect("pick_event", self.OnPick)
            self.append_window_to_menu(title, frame)
            frame.Show()

    #    def OnNewPlotWindow(self, figure):
    #        title = figure.get_axes()[0].get_title()
    #        print "appframe.OnNewPlotWindow - %s, %s" % (title, figure.canvas.GetName())
    #        figure.canvas.mpl_connect('close_event', self.OnClosingPlotWindow)
    #        self.windowframes[title] = figure.canvas
    #        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
    #        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)

    def OnClosingPlotWindow(self, event):
        logging.debug("appframe.OnClosingPlotWindow")
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
        logging.debug(f"select window {self.window_zorder}")

    def OnExit(self, event):
        self.Close()

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
            suffix = "-%d" % i
            title = "%s%s" % (title, suffix)
            i += 1
        return title

    def OnCloseAll(self, event):
        logging.debug("appframe.OnCloseAll")
        # need to create copy of keys/titles before iteration because self.windowframes will change in size when windows close

        # titles = [t for t in self.windowframes]
        # for title in titles:
        #    self.windowframes[title].Close()

        windowtitles = [t for t in self.windowframes]
        for title in windowtitles:
            window = self.windowframes[title]
            if window:
                window.Close()
        self.window_zorder = []

    def OnImport(self, event):
        # self.rawdata = event.rawdata
        #        self.filtertab.update_rawdata(self.rawdata)
        #        self.analysistab.update_rawdata(self.rawdata)
        logging.debug(f"###############  OLD IMPORT: datatypes\n{self.rawdata.dtypes}")
        # this should not be set based on current parsers regex pattern but based on columns with 'category' as dtype

    #        self.analysistab.set_roigroupings(event.importer.get_parser().get_regexpatterns().keys())

    def OnDataUpdated(self, event):
        data, datatype = event.GetUpdatedData()
        logging.debug(f"###############  OLD appframe.OnDataUpdated - {datatype}")

    #        if datatype == 'Raw':
    #            self.rawdata = data
    #            self.filtertab.update_rawdata(data, applyfilters=True)
    #            self.analysistab.update_rawdata(data)
    #        else:
    #            self.filtertab.update_data(data)
    #            self.analysistab.update_data(data)

    def OnRangeFilterUpdated(self, event):
        rfilters = event.GetUpdatedItems()
        logging.debug(
            "###############  OLD appframe.OnRangeFilterUpdated -"
            f" {len(rfilters)} Filters updated:"
        )
        # for key in rfilters:
        #    rfilter = rfilters[key]
        #    print "\t %s: %s" % (key, str(rfilter.get_params()))
        # dropsbyfilter, totaldrops = self.filtertab.apply_filters(rfilters, dropsonly=True, onlyselected=False)
        # self.analysistab.update_rangefilters(rfilters)
        # self.data = self.rawdata.drop(totaldrops)
        # self.analysistab.update_data(self.data)
        # event.Skip()

    def OnApplyFilter(self, event):
        logging.debug("###############  OLD AppFrame.OnApplyFilter")
        self.data = event.data
        self.analysistab.update_data(event.data)

    def OnAnalysisUpdated(self, event):
        updated = event.GetUpdatedItems()
        logging.debug(f"appframe.OnAnalysisUpdated - {len(updated)} Analysis updated:")
        for key in updated:
            u = updated[key]
            logging.debug("\t {key} {str(u))}")
