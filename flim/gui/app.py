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
import wx.lib.agw.customtreectrl as CT

from pubsub import pub
from prefect import Flow
from prefect.backend import FlowRunView
from wx.lib.newevent import NewEvent

import flim.analysis
import flim.core.configuration as cfg
import flim.core.parser
import flim.core.plots
import flim.core.preprocessor
import flim.gui.dialogs
import flim.plugin as plugin
import flim.workflow
from flim.core.configuration import Config
from flim.core.preprocessor import defaultpreprocessor
from flim.core.importer import dataimporter
from flim.core.filter import RangeFilter
from flim.plugin import PLUGINS, AbstractPlugin
from flim.gui.delimpanel import DelimiterPanel
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
from flim.results import LocalResultClear
from flim.workflow.basicflow import AbsWorkFlow

ImportEvent, EVT_IMPORT = NewEvent()
ApplyFilterEvent, EVT_APPLYFILTER = NewEvent()
DataUpdateEvent, EVT_UPDATEDATA = NewEvent()

DEFAULT_CONFIFG_FILE = "defaults.json"


class FlimAnalyzerApp(wx.App):
    def __init__(self, flimanalyzer, config=None):
        self.flimanalyzer = flimanalyzer
        if config is None or not isinstance(config, Config):
            self.config = Config()
            self.config.read_from_json(DEFAULT_CONFIFG_FILE, defaultonfail=True)
        else:
            self.config = config
        super().__init__()

    def OnInit(self):
        self.frame = AppFrame(self.flimanalyzer, self.config)
        self.frame.Show(True)
        return True


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

        super(AppFrame, self).__init__(
            None, wx.ID_ANY, title=f"FLIM Data Analyzer {flim.__version__}"
        )  # , size=(600, 500))

        tb = wx.ToolBar(self, -1)
        self.ToolBar = tb
        fileopen_tool = tb.AddTool(
            wx.NewId(),
            "Open File",
            wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN),
            shortHelp="Open file",
        )
        self.Bind(wx.EVT_TOOL, self.OnLoadData, fileopen_tool)
        fileimport_tool = tb.AddTool(
            wx.NewId(),
            "Import Files",
            wx.ArtProvider.GetBitmap(wx.ART_FOLDER_OPEN),
            shortHelp="Import files",
        )
        self.Bind(wx.EVT_TOOL, self.OnImportData, fileimport_tool)

        tb.AddSeparator()

        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        loadmenuitem = filemenu.Append(wx.NewId(), "&Open...", "Open single data file")
        importmenuitem = filemenu.Append(
            wx.NewId(), "Import...", "Import and concatenate mutliple data files"
        )
        exitmenuitem = filemenu.Append(wx.NewId(), "Exit", "Exit the application")
        settingsmenu = wx.Menu()
        loadsettingsitem = settingsmenu.Append(wx.NewId(), "Load settings...")
        savesettingsitem = settingsmenu.Append(wx.NewId(), "Save settings...")

        self.windowmenu = wx.Menu()
        closeallitem = self.windowmenu.Append(wx.NewId(), "Close all windows")
        self.windowmenu.AppendSeparator()

        menubar.Append(filemenu, "&File")
        menubar.Append(settingsmenu, "&Settings")
        for plugintype in PLUGINS:
            menubar.Append(
                self._create_plugin_menu(plugintype, toolbar=tb), f"&{plugintype}"
            )
        menubar.Append(self.windowmenu, "&Window")

        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.OnLoadData, loadmenuitem)
        self.Bind(wx.EVT_MENU, self.OnImportData, importmenuitem)
        self.Bind(wx.EVT_MENU, self.OnExit, exitmenuitem)
        self.Bind(wx.EVT_MENU, self.OnLoadSettings, loadsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnSaveSettings, savesettingsitem)
        self.Bind(wx.EVT_MENU, self.OnCloseAll, closeallitem)

        tb.Realize()

        self.SetSize((950, 250))
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

    def _create_plugin_menu(self, menuname, toolbar=None):
        menu = wx.Menu()
        plugins = PLUGINS[menuname]
        for pname, pclass in plugins.items():
            plg = plugin.create_instance(pclass)
            menuitem = menu.Append(wx.NewId(), pname)
            self.Bind(wx.EVT_MENU, self.on_run_plugin, menuitem)
            if toolbar:
                tool = toolbar.AddTool(wx.NewId(), pname, plg.get_icon(), shortHelp=pname)
                self.Bind(wx.EVT_TOOL, self.on_run_plugin, tool)
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
                    f"selected: title={title}, obj_id={obj_id}, id={id(window.GetData())}"
                )
                return title, window
            elif isinstance(window, matplotlib.figure.Figure) and id(window) == obj_id:
                logging.debug(
                    f"selected: title={title}, obj_id={obj_id}, id={id(window)}"
                )
                return title, window
        return

    def OnDataWindowFocused(self, data, frame):
        if isinstance(frame, matplotlib.figure.Figure):
            title = frame.canvas.manager.get_window_title()
        else:
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

    def OnImportData(self, event):
        dlg = ImportDlg(self, "Import File(s)", self.config)
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_config()

            parsername = config.get([cfg.CONFIG_PARSER_CLASS])
            parser = flim.core.parser.instantiate_parser("flim.core.parser." + parsername)
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
            importer.set_preprocessor(preprocessor)
            data, filenames, fheaders = importer.import_data()

            # pub.sendMessage(DATA_IMPORTED, olddata=None, data=data)
            windowtitle = os.path.basename(filenames[0])
            if len(filenames) != 1:
                windowtitlw = "Imported Data"
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
                        message += "Missing keys:\n%s\n\n" % (
                            "\n".join([str(m) for m in missing])
                        )
                    if len(invalid) > 0:
                        message += "Missing values:\n%s\n\n" % (
                            "\n".join([str(i) for i in invalid])
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

    def on_run_plugin(self, event):
        title, data = self.get_currentdata()
        if data is None:
            wx.MessageBox("No data available")
            return
        data_choices = self.get_alldata()
        itemid = event.GetId()
        evtobj = event.GetEventObject()
        pluginname = ""
        if isinstance(evtobj, wx._core.ToolBar):
            pluginname = evtobj.FindById(itemid).GetLabel()
        else:
            pluginname = evtobj.FindItemById(itemid).GetItemLabelText()
        logging.debug(f"{event.GetId()}, {pluginname}")

        # check that there's any data to process
        if not flim.gui.dialogs.check_data_msg(data):
            return

        # check that user provided required data categories and data features

        plugin_class = next(
            plugin.get_plugin_class(pluginname)
        )  # flim.analysis.absanalyzer.get_analyzer_classes()[analyzername]
        tool = plugin.create_instance(plugin_class)  # , data_choices=data_choices)
        _, parentkeys = self.config.get_parent(
            [cfg.CONFIG_PLUGINS, pluginname], returnkeys=True
        )
        parameters, keys = self.config.get(
            [cfg.CONFIG_PLUGINS, pluginname], returnkeys=True
        )
        input = parameters.get("input")
        if len(input) != 0:
            parameters["input"] = {
                t: data_choices[title] for t in input if t in data_choices
            }
        else:
            parameters["input"] = {title: data}
        tool.configure(**parameters)

        # run optional tool config dialog and execte analysis
        parameters = tool.run_configuration_dialog(self, data_choices=data_choices)
        if parameters is None:
            return
        self.config.update(parameters, keys)
        logging.debug(f"Updating keys={keys}")
        features = parameters["features"]
        categories = parameters["grouping"]

        req_features = tool.get_required_features()
        not_any_features = [f for f in req_features if f != "any"]
        if (
            features is None
            or len(features) < len(req_features)
            or not all(f in features for f in not_any_features)
        ):
            wx.MessageBox(
                f"Analysis tool {tool} requires selection of at least {len(req_features)} data features, including {not_any_features}.",
                "Warning",
                wx.OK,
            )
            return

        req_categories = tool.get_required_categories()
        not_any_categories = [c for c in req_categories if c != "any"]
        if len(req_categories) > 0 and (
            categories is None
            or len(categories) < len(req_categories)
            or not all(c in categories for c in not_any_categories)
        ):
            wx.MessageBox(
                f"Analysis tool {tool} requires selection of at least {len(req_categories)} groups, including {not_any_categories}.",
                "Warning",
                wx.OK,
            )
            return

        # get list of configure parameters for parallel processing
        if not isinstance(tool, AbsWorkFlow) and parameters["autosave"]:
            # only need to set this up for tasks wrapped into new flow
            dirname = (
                parameters["working_dir"]
                if os.path.isdir(parameters["working_dir"])
                else self.config.get(cfg.CONFIG_WORKINGDIR)
            )
            localresult = LocalResultClear(
                dir=f"{dirname}",
                location="{scheduled_start_time:%Y-%m-%d_%H-%M-%S}/"
                "{task_tags}/pickled/"
                "{task_full_name}",  # -{task_run_id}-{map_index}-
            )
        else:
            localresult = None
        mapped_params = tool.get_mapped_parameters()
        with Flow(name="Interactive Analysis", result=localresult) as flow:
            for p in mapped_params:
                # for k,v in p.items():
                #    print (f'{k}={v}')
                tool(**p, task_tags=tool.name)

        #:print (dir(flow))
        # flow_run = FlowRunView.from_flow_run_id("4c0101af-c6bb-4b96-8661-63a5bbfb5596")
        state = flow.run()
        task_refs = flow.get_tasks()
        result_list = [state.result[tr]._result.value for tr in task_refs]

        # handle results, DataFrames or Figure objects
        for results in result_list:
            if results is not None:
                for title, result in results.items():
                    if isinstance(result, pd.DataFrame):
                        # result = result.reset_index()
                        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
                        event.SetEventInfo(result, title, "createnew", showcolindex=False)
                        self.GetEventHandler().ProcessEvent(event)
                    elif isinstance(result, matplotlib.figure.Figure):
                        fig = result
                        # fig.canvas.set_window_title(title)
                        fig.canvas.manager.set_window_title(title)
                        event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
                        event.SetEventInfo(fig, title, "createnew")
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
        config = self.config  # event.GetConfig()
        action = event.GetAction()
        title = event.GetTitle()
        logging.debug(f"{title}: {action}")
        if action == "update":
            frame = self.windowframes.get(title)
            if frame:
                frame = self.windowframes[title]
                frame.SetData(data)
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
            try:
                obj_id = int(event.artist.get_label())
                title, window = self._get_window_frame(obj_id)
                if window:
                    self._raise_window(title, window)
                else:
                    py_obj = ctypes.cast(obj_id, ctypes.py_object).value
                    if issubclass(type(py_obj), AbstractPlugin):
                        py_obj.run_configuration_dialog(self)
            except Exception as e:
                logging.error(e)
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
        # figure.canvas.set_window_title(title)
        figure.canvas.manager.set_window_title(title)
        # ON_CUSTOM_LEFT  = wx.NewId()
        # tb = figure.canvas.toolbar
        # tb.AddTool(ON_CUSTOM_LEFT, 'Axes', wx.NullBitmap,'Set range of Axes')
        # tb.Realize()
        action = event.GetAction()
        logging.debug(f"{title}: {action}")
        if action == "createnew":
            figure.show()
            self.append_window_to_menu(title, figure)
            figure.canvas.mpl_connect("close_event", self.OnClosingPlotWindow)
            figure.canvas.mpl_connect("pick_event", self.OnPick)

    #    def OnNewPlotWindow(self, figure):
    #        title = figure.get_axes()[0].get_title()
    #        print "appframe.OnNewPlotWindow - %s, %s" % (title, figure.canvas.GetName())
    #        figure.canvas.mpl_connect('close_event', self.OnClosingPlotWindow)
    #        self.windowframes[title] = figure.canvas
    #        mitem = self.windowmenu.Append(wx.Window.NewControlId(), title)
    #        self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)

    def OnClosingPlotWindow(self, event):
        logging.debug("appframe.OnClosingPlotWindow")
        self.remove_figure_from_menu(event.canvas.figure)

    def _raise_window(self, title, window):
        if isinstance(window, wx.Frame):
            window.Raise()
            if isinstance(window, PandasFrame) and self.window_zorder[-1] != title:
                self.window_zorder = [w for w in self.window_zorder if w != title]
                self.window_zorder.append(title)
        elif isinstance(window, matplotlib.figure.Figure):
            window.canvas.manager.show()

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
            if isinstance(x, wx.Frame) or isinstance(x, matplotlib.figure.Figure)
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
                if isinstance(window, matplotlib.figure.Figure):
                    self.remove_figure_from_menu(window)
                    window.canvas.manager.destroy()
                else:
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
            f"###############  OLD appframe.OnRangeFilterUpdated - {len(rfilters)} Filters updated:"
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
