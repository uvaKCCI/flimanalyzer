#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The wxPython GUI: its `wx.App`, the main window and the settings of a GUI session.

`FLIMAnalyzerApp` is the `wx.App`; `AppFrame` is the main window, with the tool panel
and the menus, and opens the table and plot windows.
"""

import matplotlib

import logging
import os
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
import re
from types import TracebackType
from typing import Any, Optional
import pandas as pd
import wx
import wx.adv

from pubsub import pub
from flim._version import __version__
from importlib.resources import files
from matplotlib.backend_bases import PickEvent
from matplotlib.figure import Figure

import flim.gui.dialogs
import flim.resources
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.configs.data import ImportTablesConfig
from flim.core.datamgr import DataManager, Item, ItemId
from flim.core.saving import AutosaveConfig
from flim.core.filtering import WindowFilters, window_filters, window_settings, with_window_ranges
from flim.tools.data import Filter
from flim.core.types import TableType
from flim.core.settings import AppSettings, tool_settings
from flim.core.settingsmgr import SettingsManager, UserSettingsFile, user_settings_path
from flim.core.reader import LEFT_OUT, ReadSettings, read_tables
from flim.core.schema import TableSchema
from flim.core.paths import canonical_folder, resolved_folder, with_extension
from flim.core.graph import WorkflowGraph
from flim.core.tool import Tool
from flim.core.tools import FLIMAnalyzer
from flim.core.workflow import Workflow
from flim.core.registry import GUI_GROUP, TOOLS_GROUP, category_path, discover, tools
from flim.core.runner import CancelToken, FlowRun, run_flow
from flim.gui.configdialog import open_config_dialog, shown_in_gui
from flim.gui.icons import icon_bitmap, tool_bitmap
from flim.gui.macos import set_bundle_name, set_display_name
from flim.gui.plotframe import PlotFrame
from flim.gui.progressdlg import RunProgressDialog, RunSummaryDialog
from flim.gui.datapanel import PandasFrame
from flim.gui.dialogs import ConfigureAxisDlg
from flim.gui.events import (
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
import flim.tools  # noqa: F401  (registers the built-in tools)

# field editors of the tools that need more than the generated dialog
import flim.gui.dialogs.autoencoder  # noqa: F401
import flim.gui.dialogs.calculate  # noqa: F401  (the calculations table and presets)
import flim.gui.dialogs.categoryorder  # noqa: F401
import flim.gui.dialogs.filter  # noqa: F401
import flim.gui.dialogs.readers  # noqa: F401  (Import Tables: the workflow choice)
import flim.gui.dialogs.separate  # noqa: F401  (Separate Categories: presets)
import flim.gui.dialogs.unpivot  # noqa: F401

logger = logging.getLogger(__name__)
# marks menu entries and buttons that open a page in the web browser
EXTERNAL = " \u2197"
DOCS_URL = "https://flimanalyzer.readthedocs.io"
CHECK_ROWS = 20  # the rows of each file Import Tables checks its run against
# macOS lists the open windows in the Window menu itself (wxWidgets makes the menu
# titled Window the system's window menu), so the GUI adds entries elsewhere only
NATIVE_WINDOW_LIST = wx.Platform == "__WXMAC__"


def docs_url(version: str = __version__) -> str:
    """Return the URL of the documentation of a version.

    Args:
        version: The FLIMAnalyzer version. Defaults to the installed version.

    Returns:
        The URL of the version's own documentation for a release version (`X.Y.Z`),
        else (a development build) the URL of the latest documentation.
    """
    if re.fullmatch(r"\d+\.\d+\.\d+", version):
        return f"{DOCS_URL}/en/v{version}/"
    return f"{DOCS_URL}/en/latest/"





def app_icon() -> wx.Icon:
    """Return the FLIMAnalyzer icon, read from `flimanalyzer.png`."""
    return wx.Icon(str(files(flim.resources).joinpath("flimanalyzer.png")), wx.BITMAP_TYPE_PNG)


def app_icons() -> wx.IconBundle:
    """Return the FLIMAnalyzer icon in all sizes of `flimanalyzer.ico`.

    Each window then uses the size that is sharpest at its resolution.
    """
    return wx.IconBundle(str(files(flim.resources).joinpath("flimanalyzer.ico")), wx.BITMAP_TYPE_ICO)


def install_error_logging() -> None:
    """Write the errors that GUI event handlers don't catch to the log.

    wxPython reports these errors through `sys.excepthook`. The installed hook logs
    each error with its traceback (except `KeyboardInterrupt`) and then calls the
    previous hook, which still prints it. Installing it again has no effect.
    """
    import sys

    previous = sys.excepthook
    if getattr(previous, "_flim_logs", False):
        return

    def hook(
        kind: type[BaseException],
        error: BaseException,
        traceback: Optional[TracebackType],
    ) -> None:
        if not issubclass(kind, KeyboardInterrupt):
            logger.error("Error in the GUI", exc_info=(kind, error, traceback))
        previous(kind, error, traceback)

    hook._flim_logs = True
    sys.excepthook = hook


class FLIMAnalyzerApp(wx.App):
    """The `wx.App` of the GUI: opens the main window and runs the startup options."""

    def __init__(
        self,
        flimanalyzer: Optional[FLIMAnalyzer] = None,
        settings_manager: Optional[SettingsManager] = None,
        files: Optional[Iterable[str | os.PathLike]] = None,
        runs: Iterable[str] = (),
        exclude: Iterable[str] = (),
    ) -> None:
        """Create the app; also discovers the tools and dialogs of other packages.

        Args:
            flimanalyzer: The FLIMAnalyzer object that provides the task runner and
                execution settings. None: the main window is opened later with
                `start`, e.g. after dialogs shown at startup.
            settings_manager: The SettingsManager of this session. Defaults to one with
                the built-in defaults and the user settings file.
            files: Data files to open at startup, each in its own data window.
            runs: The `--run` arguments, run on the files at startup in this order
                instead of opening them.
            exclude: File names not to read (`-x`).
        """
        self.flimanalyzer = flimanalyzer
        self.settings_manager = settings_manager
        self.files = list(files or [])
        self.runs = list(runs)
        self.exclude = list(exclude)
        # tools of other packages, and their dialogs (entry points)
        discover(TOOLS_GROUP)
        discover(GUI_GROUP)
        set_bundle_name("FLIMAnalyzer")  # before wx.App registers with macOS
        super().__init__()

    def OnInit(self) -> bool:
        """Set up the app and open the main window if `flimanalyzer` was given."""
        install_error_logging()
        self.SetAppName("FLIMAnalyzer")
        self.SetAppDisplayName("FLIMAnalyzer")
        set_display_name("FLIMAnalyzer")
        # logout and shutdown: the same question as quitting, where the system lets
        # the session's end wait
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnQueryEndSession)
        if self.flimanalyzer is not None:
            self.start()
        return True

    def OnQueryEndSession(self, event: wx.CloseEvent) -> None:
        """Ask about unsaved windows before the session ends; veto if cancelled."""
        frame = getattr(self, "frame", None)
        if frame and event.CanVeto() and not frame.confirm_quit():
            event.Veto()
            return
        event.Skip()

    def start(
        self,
        flimanalyzer: Optional[FLIMAnalyzer] = None,
        settings_manager: Optional[SettingsManager] = None,
        files: Optional[Iterable[str | os.PathLike]] = None,
    ) -> None:
        """Open the main window, then run or open the data files given at startup.

        Registers the workflow files of the search path first. Without a settings
        manager, one with the user settings file is created. Notices of the settings
        manager and an offer to import the workflow of the app settings file are shown
        after the window opens.

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
        # the workflow files, registered by name like tools: in the Workflow menu
        from flim.core.workflowfile import register_workflow_files

        search_path = self.settings_manager.workflow_search_path()
        for message in register_workflow_files(search_path):
            self.settings_manager.notices.append(message)
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
        check = self.settings_manager.check  # the app settings file of this session
        if getattr(check, "import_workflow", None):
            from flim.gui.settingscheck import offer_import_workflow

            wx.CallAfter(offer_import_workflow, check, self.frame, self.settings_manager)
        if self.runs:
            wx.CallAfter(self.run_at_start)
        elif self.files:
            wx.CallAfter(self.open_files, self.files)

    def run_at_start(self) -> None:
        """Run the `--run` arguments given at startup on the `-i` files, in order.

        A workflow file runs after its steps are shown and confirmed; Import Tables
        opens its dialog; a tool or code-defined workflow opens its dialog after the
        files are opened. The files are read with Open Tables' settings, without the
        `-x` files; Import Tables reads them with its own settings. A name that does
        not resolve is reported and skipped.
        """
        from flim.core.batchrun import BatchError, read_settings, resolve_run
        from flim.tools.readers import ImportTables

        search_path = self.settings_manager.workflow_search_path()
        for name in self.runs:
            try:
                tool = resolve_run(name, search_path)
            except BatchError as err:
                wx.MessageBox(str(err), "FLIMAnalyzer", wx.OK | wx.ICON_ERROR)
                continue
            if tool is ImportTables:
                self.frame.import_tables(self.files, exclude=self.exclude)
                continue
            settings = read_settings(self.frame.reader_settings(), self.exclude)
            if getattr(tool, "definition", None) is not None:
                tables = self.frame.read_files(self.files, settings, title=tool.name)
                if tables and self.frame.confirm_workflow(tool, f"{len(tables)} file(s)"):
                    self.frame.run_workflow_on_tables(tool, tables)
            else:
                self.frame.open_data_files(self.files, settings)
                self.frame.run_tool(tool)

    def open_files(self, files: Iterable[str | os.PathLike]) -> None:
        """Open each file in a table window, as File > Open Tables... does.

        The `-x` files are left out; files that cannot be read are reported.

        Args:
            files: Paths of files or folders.
        """
        from flim.core.batchrun import read_settings

        self.frame.open_data_files(files, read_settings(self.frame.reader_settings(), self.exclude))

    def OnExit(self) -> int:
        """Remove the macOS Dock icon, then exit as `wx.App.OnExit` does."""
        if self.dock_icon:
            self.dock_icon.Destroy()
            self.dock_icon = None
        return super().OnExit()


class AppFrame(wx.Frame):
    """The main window: the tool panel and the menus.

    It opens the table and plot windows and keeps their tables and figures as items
    of a `DataManager`.
    """

    def __init__(
        self,
        flimanalyzer: FLIMAnalyzer,
        settings_manager: Optional[SettingsManager] = None,
    ) -> None:
        """Create the main window with its menus and tool panel, and show it.

        Args:
            flimanalyzer: The FLIMAnalyzer object that provides the task runner and
                execution settings.
            settings_manager: The SettingsManager of this session. Defaults to one
                with the built-in defaults that keeps changes in memory only.
        """
        self.flimanalyzer = flimanalyzer
        self.settings_manager = (
            settings_manager if settings_manager is not None else SettingsManager()
        )
        # the filters new table windows start with (the Filter tool's range filters
        # and the `filters` switches); each window works on its own copy
        self.filters = WindowFilters()
        self._quit_confirmed = False  # the user chose to quit (confirm_quit)
        self.refresh_window_filters()
        flim.gui.dialogs.calculate.bind(self.settings_manager)  # the saved presets
        flim.gui.configdialog.bind_presets(self.settings_manager)  # Separate Categories, Filter
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
        self._tool_buttons = {}  # category -> its (name, bitmap, handler) tuples
        self._file_workflow_names = set()  # shown in the tool panel only as favorites
        self._panel_groups = {}  # tool or workflow name -> its tool panel group
        # menu -> submenu path (the rest of a category) -> its (name, handler) items
        self._menu_workflows = {}
        self._file_buttons = [
            (
                "Open Tables",
                icon_bitmap("fileopen.png"),
                self.OnLoadData,
            ),
            (
                "Import Tables",
                icon_bitmap("import.png"),
                self.OnImportData,
            ),
        ]

        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        loadmenuitem = filemenu.Append(
            wx.ID_ANY, "&Open Tables...", "Open data files, each in a window of its own"
        )
        importmenuitem = filemenu.Append(
            wx.ID_ANY, "Import Tables...", "Read data files and run a workflow on the tables"
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
        favoritesitem = filemenu.Append(
            wx.ID_ANY, "Favorites...", "Choose the tools and workflows the main window shows"
        )
        # standard ids: wx moves Settings and Exit (Quit) to the app menu on macOS
        viewsettingsitem = filemenu.Append(
            wx.ID_PREFERENCES, "Settings...", "Show the app settings and where they come from"
        )
        filemenu.AppendSeparator()
        exitmenuitem = filemenu.Append(wx.ID_EXIT, "E&xit", "Quit FLIMAnalyzer")

        self.windowmenu = wx.Menu()
        closeallitem = self.windowmenu.Append(wx.ID_ANY, "Close all windows")
        self.windowmenu.AppendSeparator()

        helpmenu = wx.Menu()
        docsitem = helpmenu.Append(
            wx.ID_ANY, f"Documentation{EXTERNAL}", "Open the documentation of this version in the web browser"
        )
        aboutitem = helpmenu.Append(wx.ID_ABOUT, "About FLIMAnalyzer")

        menubar.Append(filemenu, "&File")
        # the File tools (readers) are File > Open Tables... and Import Tables...
        self._collect_tools("File")  # its readers have fixed entries
        menus = {
            category: self._create_tool_menu(category)
            for category in tools.categories()
            if category != "File"
        }
        # submenus and workflow files, from their category; File's below Import...
        self._add_submenus(filemenu, "File", position=2)
        for category, menu in menus.items():
            self._add_submenus(menu, category)
            if category == "Workflow":
                menu.AppendSeparator()
                item = menu.Append(
                    wx.ID_ANY, "Run Workflow File...", "Run a workflow file on the current table"
                )
                self.Bind(wx.EVT_MENU, lambda e: self.run_workflow_file(), item)
            menubar.Append(menu, f"&{category}")
        monitormenu = wx.Menu()
        self._monitor_items = {}  # entry name -> menu item ID
        for name, _icon, handler, help_text in self.monitor_entries():
            item = monitormenu.Append(wx.ID_ANY, f"{name}{EXTERNAL}", help_text)
            self.Bind(wx.EVT_MENU, handler, item)
            self._monitor_items[name] = item.GetId()
        menubar.Append(monitormenu, "&Monitor")
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
        self.Bind(wx.EVT_MENU, self.OnFavorites, favoritesitem)
        self.Bind(wx.EVT_MENU, self.OnViewSettings, viewsettingsitem)
        self.Bind(wx.EVT_MENU, self.OnCloseAll, closeallitem)
        self.Bind(wx.EVT_MENU, self.OnDocumentation, docsitem)
        self.Bind(wx.EVT_MENU, self.OnAbout, aboutitem)

        self.build_tool_panel()
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(self.toolpanel, 1, wx.EXPAND)
        self.SetSizer(frame_sizer)

        # size the window to the tool rows
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.Centre()
        self.Show(True)

        self.Bind(EVT_DATA, self.OnDataWindowRequest)
        self.Bind(EVT_PLOT, self.OnPlotWindowRequest)
        pub.subscribe(self.OnDataWindowFocused, FOCUSED_DATA_WINDOW)
        pub.subscribe(self.OnClosingDataWindow, CLOSING_DATA_WINDOW)
        pub.subscribe(self.OnRequestRenameDataWindow, REQUEST_RENAME_DATA_WINDOW)

    def _add_tool_group(
        self,
        label: str,
        tools: Sequence[tuple[str, wx.Bitmap, Callable[[wx.CommandEvent], None]]],
    ) -> None:
        """Add a labeled box with one row of icon buttons, one per tool."""
        group = wx.StaticBoxSizer(wx.HORIZONTAL, self.toolpanel, label)
        box = group.GetStaticBox()
        for name, bitmap, handler in tools:
            button = wx.BitmapButton(box, wx.ID_ANY, bitmap, name=name, style=wx.BORDER_NONE)
            button.SetToolTip(name)
            button.Bind(wx.EVT_BUTTON, handler)
            group.Add(button, 0, wx.ALL, 2)
        self.tool_groups.append(group)

    def _layout_tool_groups(self, rows: int = 2) -> None:
        """Place the tool groups in rows, in order, so the widest row is narrowest."""
        widths = [g.GetMinSize().width for g in self.tool_groups]
        rows = max(1, min(rows, len(widths)))

        def split(start: int, n_rows: int) -> tuple[int, list[int]]:
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

    def _collect_tools(self, category: str) -> list:
        """Keep a menu's tools for the menus and the tool panel; return its own items.

        A tool shown in the GUI (`shown_in_gui`) gets a tool panel button in the
        menu's group. Tools in a submenu (the rest of their `category`) and workflow
        files are kept for `_add_submenus`; the others are returned, as (name,
        handler) items of the menu itself. File's readers have fixed entries.

        Args:
            category: The menu.

        Returns:
            The menu's own items.
        """
        items, buttons = [], []
        for tool in tools.by_category().get(category, []):
            if not shown_in_gui(tool):
                continue
            definition = getattr(tool, "definition", None)
            rest = tuple(category_path(tool)[1:])
            if category == "File" and definition is None and not rest:
                continue  # File > Open Tables... and Import Tables...
            handler = lambda event, tool=tool: self.run_tool(tool)
            buttons.append((tool.name, tool_bitmap(tool), handler))
            self._panel_groups[tool.name] = category
            if definition is not None:
                self._file_workflow_names.add(tool.name)
            if rest or definition is not None:
                self._menu_workflows.setdefault(category, {}).setdefault(rest, []).append(
                    (tool.name, handler)
                )
            else:
                items.append((tool.name, handler))
        self._tool_buttons[category] = buttons
        return items

    def _create_tool_menu(self, category: str) -> wx.Menu:
        """Return the menu of a tool category and keep its tools' buttons."""
        menu = wx.Menu()
        for name, handler in self._collect_tools(category):
            item = menu.Append(wx.ID_ANY, name)
            self.Bind(wx.EVT_MENU, handler, item)
        return menu

    def _add_submenus(self, menu: wx.Menu, label: str, position: Optional[int] = None) -> None:
        """Add a menu's submenus (from its tools' `category`) and its workflow files.

        Workflow files without a submenu are listed in the menu itself, below its
        tools; submenus are in alphabetical order.

        Args:
            menu: The menu.
            label: The menu's name, the first entry of its tools' `category`.
            position: Where to insert the submenus; None: at the end.
        """
        entries = self._menu_workflows.get(label, {})
        if not entries:
            return
        tree: dict = {}  # submenu name -> its tree; None -> the items at that level
        for rest, items in entries.items():
            node = tree
            for name in rest:
                node = node.setdefault(name, {})
            node.setdefault(None, []).extend(items)

        def fill(target: wx.Menu, node: dict) -> None:
            for name, handler in sorted(node.get(None, []), key=lambda i: i[0].lower()):
                item = target.Append(wx.ID_ANY, name)
                self.Bind(wx.EVT_MENU, handler, item)
            for name in sorted((k for k in node if k is not None), key=str.lower):
                submenu = wx.Menu()
                fill(submenu, node[name])
                target.AppendSubMenu(submenu, name)

        if position is None:
            if menu.GetMenuItemCount():
                menu.AppendSeparator()
            fill(menu, tree)
            return
        holder = wx.Menu()  # built aside, then inserted at the position
        fill(holder, tree)
        for i, item in enumerate(list(holder.GetMenuItems())):
            holder.Remove(item)
            menu.Insert(position + i, item)

    @staticmethod
    def panel_group_names() -> list[str]:
        """Return the tool panel's groups: `File`, then the other tool categories."""
        return ["File"] + [c for c in tools.categories() if c != "File"]

    def build_tool_panel(self) -> None:
        """Create the tool panel's groups: File first, one per tool category, Monitor last.

        Monitor holds the entries of `monitor_entries`, as the Monitor menu does.

        With favorites (`favorites` setting), the groups hold only them, in their
        order, each in the group of its menu (the first entry of its category); groups without
        favorites are left out (File is always shown). Without favorites, the groups
        hold all tools without the workflow files (they are in the menus).
        """
        self.tool_groups = []
        self.toolpanel.SetSizer(None)
        self.toolpanel.DestroyChildren()
        favorites = self.favorite_buttons()
        groups = {"File": list(self._file_buttons)}
        for category, buttons in self._tool_buttons.items():
            shown = [] if favorites else [b for b in buttons if b[0] not in self._file_workflow_names]
            groups[category] = groups.get(category, []) + shown  # File: after its fixed buttons
        for button in favorites:
            groups.setdefault(self._panel_groups[button[0]], []).append(button)
        for label, buttons in groups.items():
            if label == "File" or buttons or not favorites:
                self._add_tool_group(label, buttons)
        self._add_tool_group(
            "Monitor", [(name, icon_bitmap(icon), handler) for name, icon, handler, _ in self.monitor_entries()]
        )
        for name, *_ in self.monitor_entries():  # they open web pages
            wx.FindWindowByName(name, self.toolpanel).SetToolTip(f"{name}{EXTERNAL} (web browser)")
        self._layout_tool_groups(rows=2)
        self.show_last_run_state()

    @property
    def last_run_url(self) -> Optional[str]:
        """The Prefect page of the last run the GUI started (`last_run_url` setting)."""
        return self.settings_manager.settings.last_run_url

    def show_last_run_state(self) -> None:
        """Enable `Last Run` in the Monitor menu and group only if a last run is known."""
        enable = bool(self.last_run_url)
        item_id = getattr(self, "_monitor_items", {}).get("Last Run", wx.NOT_FOUND)
        if item_id != wx.NOT_FOUND and self.GetMenuBar() is not None:
            self.GetMenuBar().Enable(item_id, enable)
        button = wx.FindWindowByName("Last Run", self.toolpanel)
        if button is not None:
            button.Enable(enable)

    def monitor_entries(
        self,
    ) -> list[tuple[str, str, Callable[[wx.CommandEvent], None], str]]:
        """Return the entries of the Monitor menu and the tool panel's Monitor group.

        All of them open web pages: the menu labels and the tooltips end with
        `EXTERNAL`.

        Returns:
            One `(name, icon file, handler, help text)` per entry, in menu order.
        """
        return [
            ("Prefect Server", "prefect_server.png", self.OnPrefectServer,
             "Open the Prefect server in the web browser, with all runs and their tasks"),
            ("Last Run", "prefect_lastrun.png", self.OnLastRun,
             "Open the Prefect page of the last run started"),
        ]  # fmt: skip

    def favorite_buttons(
        self,
    ) -> list[tuple[str, wx.Bitmap, Callable[[wx.CommandEvent], None]]]:
        """Return the buttons of the `favorites` setting's tools and workflows.

        Returns:
            The (name, bitmap, handler) tuples, in the setting's order; names of
            tools that are not registered are left out.
        """
        buttons = {b[0]: b for group in self._tool_buttons.values() for b in group}
        return [buttons[name] for name in self.settings.favorites if name in buttons]

    def set_favorites(self, names: Iterable[str]) -> None:
        """Write `favorites` to the user settings file and rebuild the tool panel.

        Args:
            names: The names of the tools and workflows, in the order shown; empty
                for all tools.
        """
        self.settings_manager.update({"favorites": list(names)})
        self.build_tool_panel()
        self.SetMinSize(wx.DefaultSize)
        self.Layout()
        self.Fit()
        self.SetMinSize(self.GetSize())

    def OnFavorites(self, event: wx.CommandEvent) -> None:
        """File > Favorites...: choose the tool panel's tools and workflows."""
        names = [b[0] for group in self._tool_buttons.values() for b in group]
        chosen = [b[0] for b in self.favorite_buttons()]
        items = chosen + [n for n in names if n not in chosen]
        order = [i if i < len(chosen) else ~i for i in range(len(items))]
        with wx.RearrangeDialog(
            self,
            "Tools and workflows the main window shows, in this order."
            " None checked: all tools.",
            "Favorites", order, items,
        ) as dialog:  # fmt: skip
            if dialog.ShowModal() != wx.ID_OK:
                return
            order = dialog.GetOrder()
        self.set_favorites([items[i] for i in order if i >= 0])

    def _get_window_frame(self, obj_id: int) -> Optional[tuple[ItemId, wx.Frame]]:
        """Return the (item ID, window) whose table or figure has `id` `obj_id`."""
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

    def _own_item(self, frame: wx.Frame) -> Optional[ItemId]:
        """Return the item ID of a window of this frame, else None."""
        item_id = getattr(frame, "item_id", None)
        return item_id if self.windowframes.get(item_id) is frame else None

    def OnDataWindowFocused(self, data: pd.DataFrame, frame: wx.Frame) -> None:
        """Pubsub `FOCUSED_DATA_WINDOW`: make the table window the current one."""
        item_id = self._own_item(frame)
        if item_id is not None:
            self.window_zorder = [i for i in self.window_zorder if i != item_id]
            self.window_zorder.append(item_id)

    @property
    def settings(self) -> AppSettings:
        """A copy of the current settings; changes go through `settings_manager`."""
        return self.settings_manager.settings

    def refresh_window_filters(self) -> None:
        """Update the defaults for new tables in place from the settings.

        These are the switches (`use`, `show_dropped`) and the Filter tool's
        top-level range filters. Open table windows keep their own filters.
        """
        current = window_filters(self.settings)
        self.filters.use = current.use
        self.filters.show_dropped = current.show_dropped
        self.filters.range_filters = current.range_filters

    def filter_presets(self) -> "flim.gui.dialogs.FilterPresets":
        """Return where the table windows' `Filter Settings` load and save filters.

        The defaults for new tables are the `filters` setting (`use`) and the Filter
        tool's range filters (`window_filters`), as the Filter tool's settings; saved
        presets are the Filter tool's presets.
        """
        from flim.gui.dialogs import FilterPresets

        def save_defaults(filters: WindowFilters) -> None:
            self.report_filters(filters)
            self.refresh_window_filters()

        return FilterPresets(
            defaults=lambda: window_settings(window_filters(self.settings)),
            save_defaults=save_defaults,
            saved=lambda: self.settings.tool_presets(Filter),
            save=lambda presets: self.settings_manager.set_presets(Filter, presets),
        )

    def report_filters(self, filters: WindowFilters) -> None:
        """Write filters to the user settings file, as the defaults for new tables.

        The switches go to the `filters` setting, the range filters to the Filter
        tool's filters; its other filters are kept.

        Args:
            filters: The filters of the data windows.
        """
        settings = self.settings
        config = settings.tools.config(Filter)
        config = config.model_copy(
            update={"filters": with_window_ranges(config.filters, filters.range_filters)}
        )
        entry = settings.tools.entry(Filter)
        stored = tool_settings(config, entry.autosave if entry else None)
        self.settings_manager.update(
            {
                "filters": {"use": filters.use, "show_dropped": filters.show_dropped},
                "tools": {Filter.name: stored.model_dump(mode="json")},
            }
        )

    def OnLoadData(self, event: wx.CommandEvent) -> None:
        """File > Open Tables...: open data files, each in a window of its own."""
        paths = self.ask_data_files("Open Tables")
        if paths:
            self.open_data_files(paths, self.reader_settings())

    def reader_settings(self) -> ReadSettings:
        """Return Open Tables' read settings (the TableReader tool's)."""
        from flim.tools.readers import TableReader

        return self.settings.tools.config(TableReader).read_settings()

    def ask_data_files(self, title: str) -> list[str]:
        """Ask for data files in a file dialog.

        Args:
            title: The title of the file dialog.

        Returns:
            The paths of the chosen files; an empty list if cancelled.
        """
        with wx.FileDialog(
            self,
            title,
            wildcard="Data files (*.txt;*.csv)|*.txt;*.csv|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return []
            return list(dialog.GetPaths())

    def read_files(
        self,
        files: Iterable[str | os.PathLike],
        settings: Optional[ReadSettings] = None,
        title: str = "Open Tables",
        nrows: Optional[int] = None,
    ) -> dict[str, pd.DataFrame]:
        """Read data files into tables and report those that could not be read.

        Files left out by the settings or by `-x` are not reported. The reader's
        warnings are shown in the same message.

        Args:
            files: Paths of files or folders.
            settings: How to read them. Defaults to `ReadSettings()`.
            title: The title of the message.
            nrows: Read only this many first rows of each file; None for all rows.

        Returns:
            The tables by name.
        """
        reading = read_tables(files, settings or ReadSettings(), nrows=nrows)
        problems = [  # files left out on purpose (settings, -x) are not problems
            f"{path}: {reason}" for path, reason in reading.skipped.items() if reason != LEFT_OUT
        ]
        if problems or reading.warnings:
            wx.MessageBox(
                "\n".join((["Not read:"] + problems if problems else []) + reading.warnings),
                title,
                wx.OK | wx.ICON_WARNING,
            )
        return reading.tables

    def open_data_files(
        self,
        files: Iterable[str | os.PathLike],
        settings: Optional[ReadSettings] = None,
    ) -> list[str]:
        """Open each data file in a window of its own, as File > Open Tables... does.

        Args:
            files: Paths of files or folders.
            settings: How to read them. Defaults to `ReadSettings()`.

        Returns:
            The titles of the new windows (the file names, made unique).
        """
        titles = []
        for name, table in self.read_files(files, settings).items():
            # always a new window: a window of the same title (e.g. data.txt from
            # another folder) keeps its data; the new one is named data.txt-1
            title = self.unique_window_title(name)
            self.open_table(table, title)
            titles.append(title)
        return titles

    def open_table(self, table: pd.DataFrame, title: str) -> None:
        """Open a table just read from a file in a new window, marked not modified.

        Args:
            table: The table.
            title: The window's title.
        """
        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
        event.SetEventInfo(
            table, title, "createnew", config=None, showcolindex=False,
            analyzable=True, savemodified=True, enableclose=True,
            modified=False,  # just read from the file
        )  # fmt: skip
        self.GetEventHandler().ProcessEvent(event)

    def file_workflows(self) -> list[type[Workflow]]:
        """Return the workflows of the registered workflow files, sorted by name."""
        return sorted(
            (t for t in tools.by_category().get("Workflow", []) if getattr(t, "definition", None)),
            key=lambda t: t.name,
        )

    def ask_workflow_file(self, title: str) -> Optional[type[Workflow]]:
        """Ask for a workflow file and check it.

        Args:
            title: The title of the file dialog and of the error message.

        Returns:
            The file's workflow (a tool class), or None if no file was chosen or the
            file has errors (they are shown).
        """
        from flim.core.workflowfile import check_workflow_file, workflow_class

        with wx.FileDialog(
            self, title, wildcard="Workflow files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:  # fmt: skip
            if dialog.ShowModal() != wx.ID_OK:
                return None
            path = dialog.GetPath()
        check = check_workflow_file(path)
        if check.errors:
            wx.MessageBox("\n".join(check.errors), title, wx.OK | wx.ICON_ERROR)
            return None
        return workflow_class(check.definition, Path(path))

    def confirm_workflow(self, tool: type[Workflow], what: str) -> bool:
        """Show a workflow file's description and steps and ask whether to run it.

        Args:
            tool: The workflow file's workflow.
            what: What it runs on, for the title, e.g. a table's title.

        Returns:
            Whether the user chose Run.
        """
        from flim.core.workflowfile import describe_steps

        text = (
            f"{tool.definition.description}\n\n" if tool.definition.description else ""
        ) + describe_steps(tool.definition)
        with wx.MessageDialog(
            self, text, f"Run {tool.name} on {what}?", style=wx.OK | wx.CANCEL
        ) as dialog:
            dialog.SetOKCancelLabels("Run", "Cancel")
            return dialog.ShowModal() == wx.ID_OK

    def OnImportData(self, event: wx.CommandEvent) -> None:
        """File > Import Tables...: choose data files and run Import Tables."""
        paths = self.ask_data_files("Import Tables: choose the data files")
        if paths:
            self.import_tables(paths)

    def import_tables(
        self,
        paths: Sequence[str | os.PathLike],
        config: Optional[ImportTablesConfig] = None,
        exclude: Iterable[str] = (),
    ) -> Optional[FlowRun]:
        """Run Import Tables on data files.

        A workflow chosen in the settings runs after its steps are shown and
        confirmed.

        Args:
            paths: Files and folders.
            config: Import Tables' settings; None: chosen in its dialog, and kept as
                its settings.
            exclude: File names left out of this run besides the settings' own (`-x`);
                not kept in the settings.

        Returns:
            The FlowRun, or None if the run did not start or did not end normally.
        """
        from flim.tools.readers import ImportTables

        tool = ImportTables
        entry = self.settings.tools.entry(tool)
        saved = entry.autosave if entry else AutosaveConfig()
        folder = resolved_folder(saved.results_dir, self.settings.resolved_results_dir())
        if config is None:
            execution = self.flimanalyzer.execution.model_copy(
                update={"autosave": saved.model_copy(update={"enabled": True, "results_dir": folder})}
            )
            result = open_config_dialog(
                self, tool, self.settings.tools.config(tool), execution=execution,
                autosave_locked=True,  # the workflow's steps decide what is saved
                default_folder=self.settings.resolved_results_dir(),
                keep_relative=self.settings.results_dir is not None,
                on_make_default=self.make_default_folder,
            )  # fmt: skip
            if result is None:
                return None
            self.settings_manager.set_tool(
                tool, result.config, result.stored_autosave or result.execution.autosave
            )
            config = result.config
            folder = resolved_folder(
                result.execution.autosave.results_dir, self.settings.resolved_results_dir()
            )
        if exclude:
            config = config.model_copy(update={"exclude": list(config.exclude) + list(exclude)})
        importer = tool()
        workflow = importer.chosen_workflow(config)
        if workflow is not None and not self.confirm_workflow(workflow, f"{len(paths)} file(s)"):
            return None
        return self.run_import(importer, paths, config, folder)

    def run_import(
        self,
        importer: Tool,
        paths: Sequence[str | os.PathLike],
        config: ImportTablesConfig,
        folder: str | os.PathLike,
    ) -> Optional[FlowRun]:
        """Check an Import Tables run, run it, and open windows for its results.

        The run is checked against the files' first rows (`CHECK_ROWS`): the
        workflow's steps against the columns, and the number of windows against
        `max_windows`. Problems are shown and the run does not start. Afterwards a
        window opens for each result no later step uses, or, without a workflow, for
        each table read, and the run summary is shown.

        Args:
            importer: The Import Tables tool.
            paths: Files and folders.
            config: Import Tables' settings.
            folder: The results folder; the run saves into its subfolder named after
                the workflow, or after Import Tables without a workflow.

        Returns:
            The FlowRun, or None if the run did not start or did not end normally.
        """
        from flim.core.workflowfile import check_steps, too_many_windows, window_counts

        workflow = importer.chosen_workflow(config)
        heads = self.read_files(
            paths, config.read_settings(), title=importer.name, nrows=CHECK_ROWS
        )
        if not heads:
            return None
        schemas = {name: TableSchema.from_frame(t) for name, t in heads.items()}
        name = workflow.name if workflow is not None else importer.name
        if workflow is not None:
            errors = check_steps(workflow.definition, schemas)
            if errors:
                wx.MessageBox("\n".join(errors), name, wx.OK | wx.ICON_ERROR)
                return None
            counts = window_counts(workflow.definition, schemas)
        else:
            counts = {"table": len(schemas)}
        over = too_many_windows(counts, self.settings.max_windows)
        if over:
            wx.MessageBox(
                f"{name} would open {', '.join(over)}. Run it with flimbatch, or"
                " choose a workflow that joins the tables (e.g. with Concatenate)."
                " The limits are the app setting max_windows.",
                name,
                wx.OK | wx.ICON_WARNING,
            )
            return None
        autosave_dir = os.path.join(canonical_folder(str(folder)), name)
        task_runner = self.flimanalyzer.get_task_runner()
        formats = workflow.definition.output.formats if workflow is not None else []

        def start_run(
            cancel_token: CancelToken,
            on_progress: Callable[[int, int, str, bool], None],
            on_start: Callable[[FlowRun], None],
        ) -> FlowRun:
            return importer.run_flow(
                paths,
                config=config,
                task_runner=task_runner,
                autosave_dir=autosave_dir,  # the workflow's steps decide what is written
                on_progress=on_progress,
                cancel_token=cancel_token,
                on_start=on_start,
                settings_record=self.settings_manager.record(),
                save_formats=formats,
            )

        flow_run = self.run_with_progress(importer.name, start_run)
        if flow_run is None:
            return None
        self.show_leaves(importer, flow_run)
        self.show_run_summary(importer.name, flow_run)
        return flow_run

    def run_workflow_file(self, path: Optional[str | os.PathLike] = None) -> None:
        """Workflow > Run Workflow File...: run a workflow file on the current table.

        The file's steps are shown and confirmed first; a file with errors is
        reported.

        Args:
            path: The workflow file; None to choose it in a file dialog.
        """
        from flim.core.workflowfile import check_workflow_file, workflow_class

        title, table = self.get_currentdata()
        if table is None:
            wx.MessageBox("Open or import data first.", "Run Workflow File", wx.OK)
            return
        if path is None:
            tool = self.ask_workflow_file("Run Workflow File")
        else:
            check = check_workflow_file(path)
            if check.errors:
                wx.MessageBox("\n".join(check.errors), "Run Workflow File", wx.OK | wx.ICON_ERROR)
                return
            tool = workflow_class(check.definition, Path(path))
        if tool is not None and self.confirm_workflow(tool, title):
            self.run_workflow_on_tables(tool, {title: TableType.snapshot(table)})

    def run_workflow_on_tables(
        self,
        tool: type[Workflow],
        tables: dict[str, pd.DataFrame],
        autosave: Optional[AutosaveConfig] = None,
    ) -> Optional[FlowRun]:
        """Run a workflow file's workflow on tables and open windows for its results.

        The run is checked first: its steps against the tables' columns, and the
        number of windows against `max_windows`; problems are shown and the run does
        not start. The steps' `save` decides what is saved. Windows open for the
        results no later step uses (leaf outputs), and the run summary is shown.

        Args:
            tool: The workflow file's workflow (a tool class).
            tables: The tables by name.
            autosave: The folder and formats chosen in its dialog; None for the
                default results folder and the file's formats.

        Returns:
            The FlowRun, or None if the run did not start or did not end normally.
        """
        from flim.core.workflowfile import check_steps, too_many_windows, window_counts

        schemas = {name: TableSchema.from_frame(t) for name, t in tables.items()}
        errors = check_steps(tool.definition, schemas)
        if errors:
            wx.MessageBox("\n".join(errors), tool.name, wx.OK | wx.ICON_ERROR)
            return None
        over = too_many_windows(window_counts(tool.definition, schemas), self.settings.max_windows)
        if over:
            wx.MessageBox(
                f"{tool.name} would open {', '.join(over)}. Run it with flimbatch, or"
                " add a step that joins the tables (e.g. Concatenate) to the workflow."
                " The limits are the app setting max_windows.",
                tool.name,
                wx.OK | wx.ICON_WARNING,
            )
            return None
        folder = resolved_folder(
            autosave.results_dir if autosave is not None else None,
            self.settings.resolved_results_dir(),
        )
        autosave_dir = os.path.join(canonical_folder(str(folder)), tool.name)
        formats = autosave.formats if autosave is not None else tool.definition.output.formats
        task_runner = self.flimanalyzer.get_task_runner()
        workflow = tool()

        def start_run(
            cancel_token: CancelToken,
            on_progress: Callable[[int, int, str, bool], None],
            on_start: Callable[[FlowRun], None],
        ) -> FlowRun:
            return workflow.run_flow(
                tables,
                task_runner=task_runner,
                autosave_dir=autosave_dir,  # the steps' `save` decides what is written
                on_progress=on_progress,
                cancel_token=cancel_token,
                on_start=on_start,
                settings_record=self.settings_manager.record(),
                save_formats=formats,
            )

        flow_run = self.run_with_progress(tool.name, start_run)
        if flow_run is None:
            return None
        self.show_leaves(workflow, flow_run)
        self.show_run_summary(tool.name, flow_run)
        return flow_run

    def show_leaves(self, workflow: Tool, flow_run: FlowRun) -> None:
        """Open a window for each table and figure of a workflow's leaf steps.

        Results that their step saved (`save`) open as saved, the others as modified.
        For Import Tables without a workflow, each table read opens as read.

        Args:
            workflow: The workflow (or Import Tables) instance that ran.
            flow_run: Its run.
        """
        from flim.tools.readers import READ_STEP

        definition = getattr(workflow, "definition", None)
        steps = {s.id: s for s in definition.steps} if definition is not None else {}
        for step_id, outputs in getattr(workflow, "leaves", {}).items():
            if step_id == READ_STEP:  # Import Tables without a workflow: as read
                for entity, output in outputs.items():
                    for value in output.value().values():
                        self.open_table(value, self.unique_window_title(entity))
                continue
            save = steps[step_id].output.save
            items = outputs.items() if isinstance(outputs, dict) else [(None, outputs)]
            for entity, output in items:
                results = output.value()
                if not isinstance(results, dict):
                    continue
                for number, (name, value) in enumerate(results.items(), 1):
                    saved = save is True or (
                        isinstance(save, list) and f"{step_id}.{number}" in save
                    )
                    title = f"{name} - {entity}" if entity and len(items) > 1 else name
                    if isinstance(value, pd.DataFrame):
                        event = DataWindowEvent(EVT_DATA_TYPE, self.GetId())
                        event.SetEventInfo(
                            value, title, "createnew", showcolindex=False, modified=not saved
                        )
                        self.GetEventHandler().ProcessEvent(event)
                    elif isinstance(value, matplotlib.figure.Figure):
                        self.open_plot(value, title, modified=not saved)

    def OnLoadSettings(self, event: wx.CommandEvent) -> None:
        """File > Import Settings...: apply the settings of a chosen settings file."""
        with wx.FileDialog(
            self,
            "Import Settings",
            wildcard="json files (*.json)|*.json|All files|*",
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

    def load_settings(self, path: str | os.PathLike) -> None:
        """Apply the sections of a settings file of any version for this session.

        The sections it does not have (e.g. other tools') stay as they are; the
        windows' shared filters are updated from it. If some settings cannot be used,
        the user chooses what to do (`flim.gui.settingscheck.choose_settings`).
        Afterwards the GUI offers to import the workflow the file names, if any.

        Args:
            path: The settings file.
        """
        from flim.core.settings import check_settings_file
        from flim.gui.settingscheck import choose_settings

        check = check_settings_file(path)
        if check.problems:
            check = choose_settings(check, self)
        if check is None:
            return
        self.settings_manager.apply(check)
        self.refresh_window_filters()
        from flim.gui.settingscheck import offer_import_workflow

        offer_import_workflow(check, self, self.settings_manager)

    def OnViewSettings(self, event: wx.CommandEvent) -> None:
        """File > Settings...: show the settings and where they come from."""
        from flim.gui.settingsview import SettingsViewer

        with SettingsViewer(self, self.settings_manager) as dialog:
            dialog.ShowModal()

    def OnSaveSettings(self, event: wx.CommandEvent) -> None:
        """File > Export Settings...: write the settings to a chosen file."""
        with wx.FileDialog(
            self,
            "Export Settings",
            wildcard="json files (*.json)|*.json|All files|*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            path = with_extension(fileDialog.GetPath(), ".json")
        with wx.TextEntryDialog(
            self,
            "Description of the settings file (optional), for example a course or an"
            " experiment. It is shown when FLIMAnalyzer asks which app settings file to"
            " start with.",
            "Export Settings",
            self.settings.description or "",
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            description = dialog.GetValue().strip()
        self.save_settings(path, description)
        self.offer_search_path(path)

    def save_settings(self, path: str | os.PathLike, description: Optional[str] = None) -> None:
        """Write all current settings, in the current version, to a file.

        Args:
            path: The file.
            description: The file's description; None or empty for none.
        """
        self.settings_manager.export(path, description)

    def offer_search_path(self, path: str | os.PathLike) -> bool:
        """Ask whether to add an exported file's folder to the settings search path.

        The question is asked only if adding the folder has an effect
        (`SettingsManager.search_path_addition`).

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

    def get_currentdata(self) -> tuple[Optional[str], Optional[pd.DataFrame]]:
        """Return the title and shown table of the current table window (None, None
        if there is none)."""
        if len(self.window_zorder) == 0:
            return None, None
        item_id = self.window_zorder[-1]
        return self.data_manager.get(item_id).title, self.windowframes[item_id].GetViewData()

    def get_alldata(self) -> dict[str, pd.DataFrame]:
        """Return the shown tables of the table windows, by title."""
        return {
            self.data_manager.get(item_id).title: frame.GetViewData()
            for item_id, frame in self.windowframes.items()
            if isinstance(frame, PandasFrame)
        }

    def OnSetFilters(self, event: wx.Event) -> None:
        """Not bound to an event; shows a message if there is no data, else nothing."""
        data = self.get_currentdata()
        if data is None:
            wx.MessageBox("No data available")
            return
        pass

    def tool_data_choices(self) -> dict[str, pd.DataFrame]:
        """Return the shown tables of the table windows by title, the current first.

        Each is a copy (`TableType.snapshot`): a run in its worker thread reads
        tables that later edits in the windows don't change.
        """
        title, currentdata = self.get_currentdata()
        data_choices = {title: currentdata} if title else {}
        data_choices.update(self.get_alldata())
        return {name: TableType.snapshot(table) for name, table in data_choices.items()}

    def run_tool(self, tool: type[Tool], current: Optional[str] = None) -> None:
        """Configure a tool in its dialog and run it on the selected tables.

        The dialog's config and run settings are stored for the tool (a workflow
        file's are not). The run shows a progress dialog; afterwards a window opens
        for each result table and figure, with its warnings and failed tasks reported,
        or, for a workflow, the graph of its tasks and a run summary. A workflow
        file's workflow runs with `run_workflow_on_tables`.

        Args:
            tool: The tool.
            current: The title of the window whose table the dialog selects first;
                None for the current window's.
        """
        data_choices = self.tool_data_choices()
        if current in data_choices:  # first: the dialog selects it
            data_choices = {current: data_choices[current], **data_choices}
        if not data_choices:
            wx.MessageBox("Open or import data first.", tool.name, wx.OK)
            return
        config = tool.dialog_config(self.settings.tools.config(tool))
        entry = self.settings.tools.entry(tool)
        saved = entry.autosave if entry else AutosaveConfig()
        definition = getattr(tool, "definition", None)
        if definition is not None and definition.output.formats:
            saved = saved.model_copy(update={"formats": definition.output.formats})
        folder = resolved_folder(saved.results_dir, self.settings.resolved_results_dir())
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
            keep_relative=self.settings.results_dir is not None,
            on_make_default=self.make_default_folder,
        )
        if result is None:
            return
        if getattr(tool, "definition", None) is not None:  # a workflow file
            tables = result.inputs[0]
            tables = tables if isinstance(tables, dict) else {"Input": tables}
            self.run_workflow_on_tables(tool, tables, autosave=result.execution.autosave)
            return
        # what the tool stores: no folder if it follows the default folder
        stored = result.stored_autosave or result.execution.autosave
        self.settings_manager.set_tool(tool, result.config, stored)
        if getattr(tool, "name", None) == Filter.name:
            self.refresh_window_filters()  # the defaults for new tables

        task_runner = self.flimanalyzer.get_task_runner()
        autosave = result.execution.autosave
        if is_workflow:
            folder = canonical_folder(
                resolved_folder(autosave.results_dir, self.settings.resolved_results_dir())
            )
            autosave_dir = os.path.join(folder, tool.name)

            def start_run(
                cancel_token: CancelToken,
                on_progress: Callable[[int, int, str, bool], None],
                on_start: Callable[[FlowRun], None],
            ) -> FlowRun:
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

            def interactive_analysis() -> None:
                for config in configs:
                    tool()(*result.inputs, config=config, task_tags=tool.name)

            def start_run(
                cancel_token: CancelToken,
                on_progress: Callable[[int, int, str, bool], None],
                on_start: Callable[[FlowRun], None],
            ) -> FlowRun:
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

    def show_workflow_graph(self, flow_run: FlowRun) -> None:
        """Open a plot window with the graph of a workflow run's tasks."""
        fig, _ = WorkflowGraph(flow_run).get_plot(pick_event=self.OnPick)
        event = PlotEvent(EVT_PLOT_TYPE, self.GetId())
        event.SetEventInfo(fig, f"{flow_run.name} Graph", "createnew")
        self.GetEventHandler().ProcessEvent(event)

    def show_results(self, flow_run: FlowRun) -> None:
        """Open a window for each table and figure a run produced.

        If the run saved its results (it had an autosave folder), they open as
        saved, else as modified.
        """
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

    def run_with_progress(
        self, title: str, start_run: Callable[..., FlowRun]
    ) -> Optional[FlowRun]:
        """Run a flow behind a modal progress dialog with a Cancel button.

        Args:
            title: The name of the tool or workflow.
            start_run: `start_run(cancel_token, on_progress, on_start)` runs the
                flow and returns its FlowRun; it is called in a worker thread.

        Returns:
            The FlowRun of a run that ended normally, or None if it was cancelled
            (the run summary shows where its results are) or stopped by an error
            (shown in a message).
        """
        dlg = RunProgressDialog(self, title, start_run)
        dlg.ShowModal()
        flow_run, error = dlg.run, dlg.error
        started = dlg.started_run
        dlg.Destroy()
        if started is not None and started.ui_url:
            # also of a failed or cancelled run; kept for the next sessions
            self.settings_manager.update({"last_run_url": started.ui_url})
            self.show_last_run_state()
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

    def show_run_summary(self, title: str, flow_run: FlowRun) -> None:
        """Show how a run ended, with links to its results and Prefect flow run."""
        dlg = RunSummaryDialog(self, title, flow_run)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_hover(self, event: Any) -> None:
        """Print an event; not bound to an event."""
        print(event)

    def register_window(
        self,
        window: wx.Frame,
        value: pd.DataFrame | Figure,
        title: str,
        modified: bool = False,
        source: Optional[str] = None,
    ) -> Item:
        """Add a window's value as an item of the DataManager and list the window.

        The window is listed in the Window menu; on macOS, the system lists it (see
        `NATIVE_WINDOW_LIST`). A table window becomes the current one.

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
        if not NATIVE_WINDOW_LIST:
            mitem = self.windowmenu.Append(wx.Window.NewControlId(), item.title)
            self._menu_items[item.id] = mitem.GetId()
            self.Bind(wx.EVT_MENU, self.OnWindowSelectedInMenu, mitem)
        if isinstance(window, PandasFrame):
            self.window_zorder.append(item.id)
        return item

    def remove_window(self, item_id: Optional[ItemId]) -> bool:
        """Remove a closing window from the Window menu and close its item.

        Args:
            item_id: The window's item; None or an item without window is ignored.

        Returns:
            Whether the item had a window of this frame.
        """
        if item_id not in self.windowframes:
            return False
        del self.windowframes[item_id]
        menu_id = self._menu_items.pop(item_id, None)
        if menu_id is not None:
            self.windowmenu.Remove(menu_id)
        self.window_zorder = [i for i in self.window_zorder if i != item_id]
        self.data_manager.close(item_id)
        return True

    def OnDataWindowRequest(self, event: DataWindowEvent) -> None:
        """`EVT_DATA` with action `createnew`: open the table in a new table window."""
        data = event.GetData()
        action = event.GetAction()
        title = event.GetTitle()
        logger.debug(f"{title}: {action}")
        if action == "createnew":
            title = self.unique_window_title(title)
            frame = PandasFrame(
                self,
                title,
                self.filters,  # the defaults for new tables; each window keeps a copy
                data,
                showcolindex=event.ShowColIndex(),
                analyzable=event.IsAnalyzable(),
                groups=event.GetGroups(),
                savemodified=event.SaveModified(),
                enableclose=event.IsEnableClose(),
                on_run_tool=lambda name, window: self.run_tool(tools.get(name), current=window),
                filtered=event.IsFiltered(),
                presets=self.filter_presets(),
            )
            frame.set_modified(event.IsModified())
            frame.Show(True)
            self.register_window(frame, data, title, modified=event.IsModified())

    def OnRequestRenameDataWindow(
        self, original: str, new: str, frame: wx.Frame
    ) -> None:
        """Pubsub `REQUEST_RENAME_DATA_WINDOW`: rename the window's item.

        The new title is made unique; the Window menu entry is renamed and
        `RENAMED_DATA_WINDOW` is sent with it.
        """
        item_id = self._own_item(frame)
        if item_id is None:
            return
        item = self.data_manager.rename(item_id, new)
        menu_id = self._menu_items.get(item.id)
        if menu_id is not None:
            self.windowmenu.FindItemById(menu_id).SetItemLabel(item.title)
        pub.sendMessage(RENAMED_DATA_WINDOW, original=original, new=item.title, frame=frame)

    def OnClosingDataWindow(self, data: pd.DataFrame, frame: wx.Frame) -> None:
        """Pubsub `CLOSING_DATA_WINDOW`: remove the window and close its item."""
        logger.debug(f"{frame.GetLabel()}")
        item_id = self._own_item(frame)
        if item_id is not None:
            self.remove_window(item_id)

    def OnPick(self, event: PickEvent) -> None:
        """Matplotlib pick event: on a double click, edit what was picked in a dialog.

        A y or x axis: its label and limits; a text: the text; a line: its color and
        transparency. The plot window is then marked modified.
        """
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

    def _plot_edited(self, figure: Figure) -> None:
        """Mark the plot window of a figure as modified after an edit in it."""
        for window in self.windowframes.values():
            if isinstance(window, PlotFrame) and window.figure is figure:
                window.modified = True

    def OnPlotWindowRequest(self, event: PlotEvent) -> None:
        """`EVT_PLOT` with action `createnew`: open the figure in a plot window."""
        if event.GetAction() == "createnew":
            self.open_plot(event.GetFigure(), event.GetTitle(), modified=True)

    def open_plot(
        self, figure: Figure, title: str, modified: bool = True
    ) -> PlotFrame:
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

    def OnClosingPlotWindow(self, event: wx.CloseEvent) -> None:
        """Remove a closing plot window and close its item."""
        logger.debug("appframe.OnClosingPlotWindow")
        self.remove_window(getattr(event.GetEventObject(), "item_id", None))
        event.Skip()

    def _raise_window(self, item_id: ItemId, window: wx.Frame) -> None:
        """Raise a window; a table window becomes the current one."""
        if isinstance(window, wx.Frame):
            window.Raise()
            if isinstance(window, PandasFrame) and self.window_zorder[-1] != item_id:
                self.window_zorder = [i for i in self.window_zorder if i != item_id]
                self.window_zorder.append(item_id)

    def OnWindowSelectedInMenu(self, event: wx.CommandEvent) -> None:
        """Window menu entry: raise its window."""
        menu_id = event.GetId()
        item_id = next((i for i, m in self._menu_items.items() if m == menu_id), None)
        if item_id in self.windowframes:
            self._raise_window(item_id, self.windowframes[item_id])
        logger.debug(f"select window {self.window_zorder}")

    def OnExit(self, event: wx.CommandEvent) -> None:
        """File > Exit: close the main window, which quits the GUI."""
        self.Close()

    def unsaved_windows(self) -> list[str]:
        """Return the titles of unsaved table windows that ask to be saved on close."""
        return [
            self.data_manager.get(item_id).title
            for item_id, window in self.windowframes.items()
            if isinstance(window, PandasFrame)
            and window
            and window.savemodified
            and window.modified
        ]

    def OnCloseApp(self, event: wx.CloseEvent) -> None:
        """Ask about unsaved windows before the main window closes; veto if cancelled.

        Closing the main window destroys the other windows without their own save
        question. The question is asked only if the close event can be vetoed.
        """
        if event.CanVeto() and not self.confirm_quit():
            event.Veto()
            return
        event.Skip()

    def unsaved_items(self) -> list[tuple[wx.Frame, str]]:
        """Return the open windows with unsaved changes that ask to be saved.

        Returns:
            (window, title) pairs: the table windows that ask when closed, and the
            plot windows.
        """
        unsaved = []
        for item_id, window in self.windowframes.items():
            if not window or not window.modified:
                continue
            if isinstance(window, PandasFrame) and not window.savemodified:
                continue
            unsaved.append((window, self.data_manager.get(item_id).title))
        return unsaved

    def confirm_quit(self) -> bool:
        """Ask what to do with unsaved windows before quitting.

        Cancel keeps FLIMAnalyzer open; Review... asks window by window (Save, Don't
        Save, Cancel); Save All Windows... saves them all (save_all_windows); Discard
        All quits without saving.

        Returns:
            Whether to quit. Once the user chose to quit, it doesn't ask again: on
            macOS, Quit both closes the main window and ends the session, and each
            asks this.
        """
        if self._quit_confirmed:
            return True
        quit_ = self._confirm_quit()
        self._quit_confirmed = quit_
        return quit_

    def _confirm_quit(self) -> bool:
        """Ask what to do with the unsaved windows; return whether to quit."""
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

    def save_window(self, window: wx.Frame, title: str) -> bool:
        """Save one window as its own save button does, and mark it saved.

        A table window saves its table with all rows; a plot window its figure.

        Args:
            window: The table or plot window.
            title: Its title, for the file dialog.

        Returns:
            Whether it was saved.
        """
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
        """File > Save All Windows...: save every open table and plot, mark them saved.

        Tables are saved with all their rows, into a new subfolder of a folder, in the
        formats chosen.

        The folder is the one last used for this in the session, else the default
        results folder; choosing it does not change the results folder. A message
        lists what was saved and what was not.

        Args:
            quitting: Called when quitting: no message if there are no windows.
                Defaults to False.

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

    def OnPrefectServer(self, event: wx.CommandEvent) -> None:
        """Open the Prefect server's UI in the browser, with the runs and their tasks.

        The address is that of the server the session uses (`PREFECT_UI_URL`); without
        one, a message says that runs use temporary servers.
        """
        from prefect.settings import PREFECT_UI_URL

        url = PREFECT_UI_URL.value()
        if not url:
            wx.MessageBox(
                "No Prefect server is in use: each run uses a temporary server that"
                " stops when the run ends. Start FLIMAnalyzer without"
                " --no-prefect-server to keep a server with all runs.",
                "Prefect Server",
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        wx.LaunchDefaultBrowser(url)

    def OnLastRun(self, event: wx.CommandEvent) -> None:
        """Open the Prefect page of the last run the GUI started (`last_run_url`).

        The run may have completed, failed or been cancelled, also in an earlier
        session. Without a known run the entry is disabled; if it is used anyway, a
        message says so.
        """
        if self.last_run_url:
            wx.LaunchDefaultBrowser(self.last_run_url)
            return
        wx.MessageBox(
            "No run with a Prefect page is known yet. Runs on a temporary server"
            " (--no-prefect-server) have no page after they end.",
            "Last Run",
            wx.OK | wx.ICON_INFORMATION,
        )

    def OnDocumentation(self, event: wx.CommandEvent) -> None:
        """Help > Documentation: open this version's documentation in the browser."""
        wx.LaunchDefaultBrowser(docs_url())

    def OnAbout(self, event: wx.CommandEvent) -> None:
        """Help > About FLIMAnalyzer: show the name, version and website."""
        info = wx.adv.AboutDialogInfo()
        info.SetName("FLIMAnalyzer")
        info.SetVersion(__version__)
        info.SetDescription(
            "Analysis of Fluorescence Lifetime Imaging Microscopy (FLIM) data"
        )
        info.SetWebSite(DOCS_URL)
        wx.adv.AboutBox(info, self)

    def get_window_frames(self) -> list[wx.Frame]:
        """Return the child windows of this frame that are frames."""
        return [
            x
            for x in self.GetChildren()
            if isinstance(x, wx.Frame)
        ]

    def make_default_folder(self, folder: str | os.PathLike) -> None:
        """Make a folder the default results folder (`results_dir`).

        The setting is written to the user settings file; tools without a folder of
        their own save there.

        Args:
            folder: The folder.
        """
        self.settings_manager.update({"results_dir": str(folder)})

    def unique_window_title(self, title: str) -> str:
        """Return a title no open window has (`DataManager.unique_title`)."""
        return self.data_manager.unique_title(title)

    def windows_by_title(self) -> dict[str, wx.Frame]:
        """Return the open windows by their items' titles."""
        return {self.data_manager.get(i).title: w for i, w in self.windowframes.items()}

    def window_titled(self, title: str) -> Optional[wx.Frame]:
        """Return the open window with a title, or None."""
        item = self.data_manager.find(title)
        return self.windowframes.get(item.id) if item else None

    def OnCloseAll(self, event: wx.CommandEvent) -> None:
        """Window > Close all windows: close every table and plot window."""
        logger.debug("appframe.OnCloseAll")
        # a copy: closing a window removes it from self.windowframes
        for window in list(self.windowframes.values()):
            if window:
                window.Close()

