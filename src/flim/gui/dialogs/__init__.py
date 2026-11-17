#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialogs of the data and plot windows, and functions that save tables and figures.

The save functions ask for the file and its format in a file dialog.
"""

import json
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Union

import numpy as np
import wx.grid
from pubsub import pub
from flim.core.filter import RangeFilter
from flim.core.paths import with_extension
from flim.gui.listcontrol import FilterListCtrl, FILTERS_UPDATED

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.artist import Artist
    from matplotlib.figure import Figure

    from flim.core.saving import SaveOptions
    from flim.core.filtering import WindowFilters
    from flim.core.settings import FilterSettings

logger = logging.getLogger(__name__)


def fix_filename(fname: Optional[str]) -> Optional[str]:
    """Return a file name without the characters that cause problems in paths.

    Spaces and `[`, `]`, `(`, `)` are removed; commas, backslashes and `/` become
    `_`, `:` becomes `-`, `%` becomes `perc`, and `--` becomes `-` (in one pass:
    `---` becomes `--`).

    Args:
        fname: The file name; None is returned unchanged.

    Returns:
        The file name, or None.
    """
    if fname is None:
        return None
    else:
        fname = fname.replace(" ", "")
        fname = fname.replace(",", "_")
        fname = fname.replace(":", "-")
        fname = fname.replace("\\", "_")
        fname = fname.replace("/", "_")
        fname = fname.replace("[", "")
        fname = fname.replace("]", "")
        fname = fname.replace("(", "")
        fname = fname.replace(")", "")
        fname = fname.replace("%", "perc")
        fname = fname.replace("--", "-")
        return fname


FORMAT_NAMES = {
    "tsv": "Tab-separated text",
    "csv": "Comma-separated text",
    "png": "PNG image",
    "svg": "SVG drawing",
    "pdf": "PDF document",
}


def _wildcard(options_class: type["SaveOptions"]) -> tuple[str, list[str]]:
    """Return a file dialog's wildcard for save options' formats, and the formats.

    The default format comes first, in the wildcard and in the list.
    """
    import typing

    formats = list(typing.get_args(options_class.model_fields["format"].annotation))
    default = options_class().format
    formats.sort(key=lambda f: f != default)
    parts = []
    for fmt in formats:
        extension = options_class.extensions[fmt]
        parts.append(f"{FORMAT_NAMES.get(fmt, fmt)} (*{extension})|*{extension}")
    return "|".join(parts), formats


def _ask_path(
    parent: Optional[wx.Window],
    title: str,
    filename: str,
    options_class: type["SaveOptions"],
) -> Optional[tuple[str, "SaveOptions"]]:
    """Ask where to save, and in which format; return path and options, or None."""
    wildcard, formats = _wildcard(options_class)
    with wx.FileDialog(
        parent, title, wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    ) as dialog:
        dialog.SetFilename(fix_filename(os.path.splitext(filename)[0]))
        if dialog.ShowModal() == wx.ID_CANCEL:
            return None
        fmt = formats[max(dialog.GetFilterIndex(), 0)]
        path = dialog.GetPath()
    options = options_class(format=fmt)
    if not path.lower().endswith(options.extension):
        path += options.extension
    return path, options


def save_dataframe(
    parent: Optional[wx.Window],
    title: str,
    data: "pd.DataFrame",
    filename: str,
    saveindex: bool = True,
) -> Optional[str]:
    """Ask where and how to save a table, and save it.

    The file dialog offers the table formats (tab- or comma-separated text). If
    column names change when saved in the chosen format, the user is asked whether
    to save anyway. A message box shows an error in writing the file.

    Args:
        parent: The parent window of the dialogs.
        title: The title of the dialogs.
        data: The table.
        filename: The proposed file name; its extension is replaced, and characters
            that cause problems in paths are removed (`fix_filename`).
        saveindex: Whether the index is written. Defaults to True.

    Returns:
        The path of the saved file, with the format's extension; None if the user
        cancelled or writing failed.
    """
    from flim.core.saving import TableSaveOptions, header_problems, write_table

    answer = _ask_path(parent, title, filename, TableSaveOptions)
    if answer is None:
        return None
    fname, options = answer
    problems = header_problems(data.columns, options)
    if problems:
        with wx.MessageDialog(
            parent,
            "Some column names change when saved in this format:\n\n"
            + "\n".join(problems)
            + "\n\nSave anyway?",
            title,
            wx.YES_NO | wx.ICON_WARNING,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_YES:
                return None
    try:
        write_table(data, fname, options, index=saveindex)
    except OSError as err:
        wx.MessageBox(f"Error saving data in file {fname}: {err}", "Error", wx.OK)
        return None
    return fname


def save_figure(
    parent: Optional[wx.Window],
    title: str,
    fig: "Figure",
    filename: str,
    legend: Optional["Artist"] = None,
) -> Optional[str]:
    """Ask where and how to save a figure, and save it, cropped to its content.

    The file dialog offers the plot formats (PNG at the default resolution, SVG,
    PDF). An error in writing the file is logged and shown in a message box.

    Args:
        parent: The parent window of the dialogs.
        title: The title of the file dialog.
        fig: The figure.
        filename: The proposed file name; its extension is replaced, and characters
            that cause problems in paths are removed (`fix_filename`).
        legend: A legend outside the axes that the cropped figure includes.
            Defaults to None.

    Returns:
        The path of the saved file, with the format's extension; None if the user
        cancelled or writing failed.
    """
    from flim.core.saving import PlotSaveOptions

    answer = _ask_path(parent, title, filename, PlotSaveOptions)
    if answer is None:
        return None
    fname, options = answer
    kwargs = {"dpi": options.dpi} if options.format == "png" else {}
    if legend is not None:
        kwargs["bbox_extra_artists"] = (legend,)
    try:
        fig.savefig(fname, format=options.format, bbox_inches="tight", **kwargs)
    except OSError as err:
        error = f"Error saving figure in file {fname}: {err}"
        logger.error(error)
        wx.MessageBox(error, "Error", wx.OK)
        return None
    return fname


class SelectGroupsDlg(wx.Dialog):
    """Dialog with a check box per value of a category column.

    `Select All` and `Deselect All` check or uncheck all boxes. OK requires at least
    one checked value; `get_selected` returns the checked values.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        title: str,
        groups: Optional[list[Any]] = [],
        selected: Union[str, list[Any]] = "All",
    ) -> None:
        """Build the dialog and show it.

        Args:
            parent: The parent window.
            title: The dialog's title.
            groups: The values, one check box each. Defaults to none.
            selected: The values that are checked, or `All` to check all. Defaults
                to `All`.
        """
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title)
        # 5 col gridsizer
        mainsizer = wx.BoxSizer(wx.HORIZONTAL)

        cbsizer = wx.GridSizer(5, 0, 0)
        if groups is None:
            groups = []
        self.cboxes = {}
        for g in groups:
            cb = wx.CheckBox(self, wx.ID_ANY, str(g))
            cb.SetValue((g in selected) or (selected == "All"))
            self.cboxes[g] = cb
            cbsizer.Add(cb, 0, wx.ALL, 5)
        selectbsizer = wx.BoxSizer(wx.VERTICAL)
        self.selectAllButton = wx.Button(self, label="Select All")
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.OnSelectAll)
        selectbsizer.Add(self.selectAllButton, 0, wx.ALL | wx.EXPAND, 5)
        self.deselectAllButton = wx.Button(self, label="Deselect All")
        self.deselectAllButton.Bind(wx.EVT_BUTTON, self.OnDeselectAll)
        selectbsizer.Add(self.deselectAllButton, 0, wx.ALL | wx.EXPAND, 5)

        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK", pos=(110, 160))
        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        buttonsizer.Add(self.okButton, 0, wx.ALL, 10)
        self.cancelButton = wx.Button(self, label="Cancel", pos=(210, 160))
        self.cancelButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        buttonsizer.Add(self.cancelButton, 0, wx.ALL, 10)

        mainsizer.Add(cbsizer, 0, wx.ALIGN_CENTER, 5)
        mainsizer.Add(
            wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5
        )
        mainsizer.Add(selectbsizer, 0, wx.ALIGN_CENTER, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(mainsizer, 0, wx.ALIGN_CENTER, 5)
        sizer.Add(buttonsizer, 0, wx.ALIGN_CENTER, 5)
        self.SetSizerAndFit(sizer)  # as large as the check boxes and buttons

        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        if self.GetSize().height > wx.GetDisplaySize().height * 0.9:
            # too tall for the screen: let wx make the dialog scrollable
            self.SetLayoutAdaptationMode(wx.DIALOG_ADAPTATION_MODE_ENABLED)
            self.DoLayoutAdaptation()
        self.Show()

    def OnSelectAll(self, event: wx.CommandEvent) -> None:
        """Check all values."""
        for key in self.cboxes:
            self.cboxes[key].SetValue(True)

    def OnDeselectAll(self, event: wx.CommandEvent) -> None:
        """Uncheck all values."""
        for key in self.cboxes:
            self.cboxes[key].SetValue(False)

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel."""
        self.EndModal(wx.ID_CANCEL)

    def _get_selected(self) -> list[Any]:
        """Return the checked values."""
        return [key for key in self.cboxes if self.cboxes[key].GetValue()]

    def get_selected(self) -> list[Any]:
        """Return the checked values, in the order of the check boxes."""
        return self._get_selected()

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Close the dialog with OK if a value is checked, else show a warning."""
        if len(self._get_selected()) == 0:
            wx.MessageBox("Select at least one.", self.GetTitle(), wx.OK | wx.ICON_WARNING, self)
        else:
            self.EndModal(wx.ID_OK)


@dataclass
class FilterPresets:
    """Where `Filter Settings` loads filters from and saves them to.

    Attributes:
        defaults: Returns the filters new tables start with, as the Filter tool's
            settings (`enabled` and `filters`).
        save_defaults: Makes a table's filters (`WindowFilters`) the defaults.
        saved: Returns the saved presets, each a dict with `name` and `settings`.
        save: Replaces the saved presets.
    """

    defaults: Callable[[], dict]
    save_defaults: Callable[["WindowFilters"], None]
    saved: Callable[[], list[dict]]
    save: Callable[[list[dict]], None]


DEFAULTS_PRESET = "Defaults for new tables"


class ConfigureFiltersDlg(wx.Dialog):
    """Dialog that edits the range filters of a table.

    The list shows each filter's column, range and the number of rows it drops from
    the view; the labels above it show the rows dropped and remaining. With
    `presets`, `Load Preset...`, `Save as Preset...` and `Remove Presets...` load
    and save the table's filters as the Filter tool's settings: the switch of all
    filters (`Filter Data`), the range filters and the category values kept. They
    go to the defaults for new tables, a saved preset or a settings file. With OK,
    `GetData` returns an edited copy of the filter settings.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        filters: Optional["FilterSettings"] = None,
        dataframe: Optional["pd.DataFrame"] = None,
        dropped: dict[Any, Any] = {},
        show_dropped_option: bool = True,
        presets: Optional[FilterPresets] = None,
    ) -> None:
        """Build the dialog and show it.

        Args:
            parent: The parent window.
            filters: The filter settings to edit; required (None is not handled).
            dataframe: The table the filters apply to; required (None is not
                handled).
            dropped: The row positions dropped from the view, by filter name or
                other key. Defaults to none.
            show_dropped_option: Whether the dialog shows `Show Dropped`, whose value
                `GetData` returns. Defaults to True.
            presets: Where the preset buttons load and save filters; None for no
                preset buttons. Defaults to None.
        """
        wx.Dialog.__init__(
            self, parent, wx.ID_ANY, "Filter Settings", size=(650, 400)
        )
        self.dataframe = dataframe
        self.dropped = dropped
        self.show_dropped_option = show_dropped_option
        self.presets = presets
        self.result = None  # set by OK; None after Cancel or closing the window
        self.filters = filters
        self.use = filters.use  # Filter Data; a loaded preset can change it
        self.categories = dict(filters.category_filters)  # likewise
        cfgdata = filters.range_filters
        self.panel = wx.Panel(self, wx.ID_ANY)
        cbsizer = wx.BoxSizer(wx.HORIZONTAL)
        filtersizer = wx.BoxSizer(wx.VERTICAL)
        if self.show_dropped_option:
            self.showdropcb = wx.CheckBox(self.panel, wx.ID_ANY, label="Show Dropped")
            self.showdropcb.SetValue(filters.show_dropped)
            cbsizer.Add(self.showdropcb, 0, wx.ALL | wx.EXPAND, 5)
            filtersizer.Add(cbsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.dropped_label = wx.StaticText(
            self.panel, label=f"Dropped from view: ??? (of {len(self.dataframe):,})"
        )
        self.remaining_label = wx.StaticText(
            self.panel, label=f"Remaining: ??? (of {len(self.dataframe):,})"
        )
        filtersizer.Add(self.dropped_label, 0, wx.ALL | wx.EXPAND, 5)
        filtersizer.Add(self.remaining_label, 0, wx.ALL | wx.EXPAND, 5)

        self.filterlist = FilterListCtrl(
            self.panel,
            showdropped=True,
            fireevents=True,
            style=wx.LC_REPORT,
            size=(500, -1),
        )
        self.filterlist.InsertColumn(0, "Use")
        self.filterlist.InsertColumn(1, "Column")
        self.filterlist.InsertColumn(2, "Min", wx.LIST_FORMAT_RIGHT)
        self.filterlist.InsertColumn(3, "Max", wx.LIST_FORMAT_RIGHT)
        self.filterlist.InsertColumn(4, "Dropped view", wx.LIST_FORMAT_RIGHT)
        self.filterlist.SetEditable([False, False, True, True, False])
        self.filterlist.Arrange()
        currentfilters = {rfcfg["name"]: RangeFilter(params=rfcfg) for rfcfg in cfgdata}

        filtersizer.Add(self.filterlist, 0, wx.ALL | wx.EXPAND, 5)
        checks = wx.BoxSizer(wx.HORIZONTAL)
        for label, check in (("Select All", True), ("Deselect All", False)):
            button = wx.Button(self.panel, label=label)
            button.Bind(wx.EVT_BUTTON, lambda event, check=check: self.use_all(check))
            checks.Add(button, 0, wx.RIGHT, 5)
        filtersizer.Add(checks, 0, wx.LEFT | wx.RIGHT, 5)

        okbutton = wx.Button(self.panel, label="OK")
        okbutton.Bind(wx.EVT_BUTTON, self.OnOK)
        cancelbutton = wx.Button(self.panel, label="Cancel")
        cancelbutton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.message = wx.StaticText(self.panel, label="")
        filtersizer.Add(self.message, 0, wx.ALL | wx.EXPAND, 5)

        buttonsizer = wx.BoxSizer(wx.VERTICAL)
        if self.presets is not None:
            for label, tip, handler in (
                ("Load Preset...", "Filters of the defaults, a saved preset or a file", self._on_load_preset),
                ("Save as Preset...", "Save these filters as the defaults, a preset or a file", self._on_save_preset),
                ("Remove Presets...", "Remove saved presets", self._on_remove_presets),
            ):
                button = wx.Button(self.panel, label=label)
                button.SetToolTip(tip)
                button.Bind(wx.EVT_BUTTON, handler)
                buttonsizer.Add(button, 0, wx.ALL | wx.EXPAND, 5)
        buttonsizer.Add(
            wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL), 0, wx.ALL | wx.EXPAND, 5
        )
        buttonsizer.Add(okbutton, 0, wx.ALL | wx.EXPAND, 5)
        buttonsizer.Add(cancelbutton, 0, wx.ALL | wx.EXPAND, 5)
        # room around the longest label: macOS shortens labels that just fit
        buttons = [i.GetWindow() for i in buttonsizer.GetChildren() if isinstance(i.GetWindow(), wx.Button)]
        width = max(b.GetBestSize().width for b in buttons) + 24
        for button in buttons:
            button.SetMinSize((width, -1))

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(filtersizer)
        sizer.Add(
            wx.StaticLine(self.panel, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5
        )
        sizer.Add(buttonsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.panel.SetSizer(sizer)
        # at least as large as the content, so that the button column keeps its width
        needed = self.ClientToWindowSize(sizer.GetMinSize())
        size = self.GetSize()
        self.SetMinSize(needed)
        self.SetSize((max(size.width, needed.width), max(size.height, needed.height)))

        pub.subscribe(self.OnFiltersUpdated, FILTERS_UPDATED)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)
        self.filterlist.SetData(
            currentfilters,
            dataframe=self.dataframe,
            dropped=self.dropped,
            headers=["Use", "Column", "Min", "Max", "Dropped view"],
        )

        self.Show()

    def _on_destroy(self, event: wx.WindowDestroyEvent) -> None:
        """Stop receiving `FILTERS_UPDATED` when the dialog is destroyed."""
        if event.GetEventObject() is self:
            pub.unsubscribe(self.OnFiltersUpdated, FILTERS_UPDATED)
        event.Skip()

    def OnFiltersUpdated(
        self,
        updateditems: dict[str, Any],
        totaldropped: int,
        viewdropped: int,
        viewlength: int,
    ) -> None:
        """Show the numbers of dropped and remaining rows (`FILTERS_UPDATED`).

        Args:
            updateditems: The changed filters by name.
            totaldropped: The number of rows dropped by all filters.
            viewdropped: The number of rows dropped from the view.
            viewlength: The number of rows of the view before the filters.
        """
        remaining = viewlength - viewdropped
        self.dropped_label.SetLabel(
            f"Dropped from view: {viewdropped:,} (of {viewlength:,})"
        )
        share = 100.0 * remaining / viewlength if viewlength else 0.0
        self.remaining_label.SetLabel(f"Remaining: {remaining:,} ({share:.2f}%)")
        logger.debug(f"Updated: {[name for name in updateditems]}")
        logger.debug(
            f"Dropped from view: {viewdropped:,} (of {viewlength:,}); Remaining:"
            f" {remaining:,} ({100.0 * remaining/viewlength:.2f}%)"
        )

    def GetData(self) -> Optional["FilterSettings"]:
        """Return the edited filter settings; None if the dialog was cancelled."""
        return self.result

    def use_all(self, check: bool) -> None:
        """Check (`Select All`) or uncheck (`Deselect All`) the Use of every range filter."""
        self.filterlist.check_items(list(self.filterlist.GetData()), check)

    def current_ranges(self) -> list[dict]:
        """Return the range filters as shown, as `RangeFilter` parameters."""
        cfgs = self.filterlist.GetData()
        return [cfgs[key].get_params() for key in cfgs]

    def show_ranges(self, ranges: list[dict], others_off: bool = False) -> None:
        """Show range filters for the table's columns; report the others.

        A filter of a column the table has replaces that column's filter. The rows
        each selected filter drops are computed again.

        Args:
            ranges: `RangeFilter` parameters.
            others_off: Whether the filters of the columns not in `ranges` are
                switched off; else they stay as they are.
        """
        cfgs = self.filterlist.GetData()
        missing = [p["name"] for p in ranges if p["name"] not in cfgs]
        if others_off:
            named = {p["name"] for p in ranges}
            for name, rfilter in cfgs.items():
                if name not in named:
                    rfilter.select(False)
        for params in ranges:
            if params["name"] in cfgs:
                cfgs[params["name"]] = RangeFilter(params=params)
        dropped = dict(self.dropped)
        for name, rfilter in cfgs.items():
            if rfilter.is_selected():
                dropped[name] = rfilter.get_dropped(self.dataframe)
            else:
                dropped.pop(name, None)
        self.dropped = dropped
        self.filterlist.SetData(
            cfgs,
            dataframe=self.dataframe,
            dropped=dropped,
            headers=["Use", "Column", "Min", "Max", "Dropped view"],
        )
        loaded = len(ranges) - len(missing)
        text = f"{loaded} filters loaded"
        if missing:
            text += f"; not in this table: {', '.join(missing)}"
        self.message.SetLabel(text)

    def current_filters(self) -> "WindowFilters":
        """Return the filters as shown: the switch, the ranges and the category values."""
        return self.filters.model_copy(
            update={
                "use": self.use,
                "range_filters": self.current_ranges(),
                "category_filters": dict(self.categories),
            }
        )

    def show_settings(self, settings: dict) -> None:
        """Show the Filter tool's settings: the switch, the ranges and the category values.

        The settings replace all filters of the table: range filters of columns they
        don't have are switched off, and category columns they don't have keep all
        values. Settings without `enabled` leave `Filter Data` as it is. The
        message lists what is not used.

        Args:
            settings: The Filter tool's settings, or a part of them (`enabled`,
                `filters`).

        Raises:
            ValueError: If the settings are not valid Filter settings.
        """
        from flim.core.filtering import window_part

        part = window_part(settings)
        if part.use is not None:
            self.use = part.use
        columns = set(self.dataframe.columns)
        self.categories = {c: keep for c, keep in part.categories.items() if c in columns}
        # the rows the category values hide, for the counts
        self.dropped = {k: v for k, v in self.dropped.items() if not isinstance(k, tuple)}
        for column, keep in self.categories.items():
            for value in self.dataframe[column].dropna().unique():
                if value not in keep:
                    self.dropped[(column, value)] = np.flatnonzero(self.dataframe[column] == value)
        self.show_ranges(part.ranges, others_off=True)
        notes = [self.message.GetLabel(), f"Filter Data {'on' if self.use else 'off'}"]
        if self.categories:
            notes.append(f"category values kept in {', '.join(self.categories)}")
        missing = [c for c in part.categories if c not in columns]
        if missing:
            notes.append(f"category columns not in this table: {', '.join(missing)}")
        if part.unused:
            notes.append(f"{part.unused} filters not used by table windows")
        self.message.SetLabel("; ".join(notes))

    def _on_load_preset(self, event: wx.CommandEvent) -> None:
        """Ask for the defaults, a saved preset or a settings file, and show its filters."""
        saved = self.presets.saved()
        choices = [DEFAULTS_PRESET] + [p["name"] for p in saved] + ["From file..."]
        with wx.SingleChoiceDialog(self, "Load filters from:", "Load Preset", choices) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            index = dialog.GetSelection()
        try:
            if index == 0:
                settings = self.presets.defaults()
            elif index <= len(saved):
                settings = saved[index - 1]["settings"]
            else:
                with wx.FileDialog(
                    self, "Load Filters", wildcard="JSON files (*.json)|*.json|All files|*",
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
                ) as files:  # fmt: skip
                    if files.ShowModal() != wx.ID_OK:
                        return
                    path = files.GetPath()
                settings = _file_filter_settings(path)
                if settings is None:
                    self.message.SetLabel(f"No Filter settings in {os.path.basename(path)}")
                    return
            self.show_settings(settings)
        except (OSError, ValueError, KeyError, TypeError) as err:
            self.message.SetLabel(f"Could not load the filters: {err}")

    def _on_save_preset(self, event: wx.CommandEvent) -> None:
        """Ask where to save the filters: the defaults, a saved preset, a new one or a file."""
        from flim.core.filtering import window_settings

        saved = self.presets.saved()
        names = [p["name"] for p in saved]
        choices = [DEFAULTS_PRESET] + names + ["New preset...", "To file..."]
        with wx.SingleChoiceDialog(self, "Save the filters as:", "Save as Preset", choices) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            choice = choices[dialog.GetSelection()]
        current = self.current_filters()
        if choice == DEFAULTS_PRESET:
            self.presets.save_defaults(current)
            note = "; the category values are not part of them" if self.categories else ""
            self.message.SetLabel(f"Saved as the defaults for new tables{note}")
            return
        if choice == "To file...":
            with wx.FileDialog(
                self, "Save Filters", wildcard="JSON files (*.json)|*.json|All files|*",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            ) as files:  # fmt: skip
                if files.ShowModal() != wx.ID_OK:
                    return
                path = with_extension(files.GetPath(), ".json")
            try:
                _write_filter_settings(path, window_settings(current))
            except (OSError, ValueError) as err:
                self.message.SetLabel(f"Could not save {os.path.basename(path)}: {err}")
                return
            self.message.SetLabel(f"Saved to {os.path.basename(path)}")
            return
        if choice == "New preset...":
            with wx.TextEntryDialog(self, "Name of the preset:", "Save as Preset") as entry:
                if entry.ShowModal() != wx.ID_OK:
                    return
                choice = entry.GetValue().strip()
            if not choice or choice == DEFAULTS_PRESET:
                return
        presets = [p for p in saved if p["name"] != choice]  # same name: replaced
        self.presets.save(presets + [{"name": choice, "settings": window_settings(current)}])
        self.message.SetLabel(f"Saved as preset {choice}")

    def _on_remove_presets(self, event: wx.CommandEvent) -> None:
        """Ask for saved presets and remove them."""
        saved = self.presets.saved()
        if not saved:
            self.message.SetLabel("No saved presets")
            return
        names = [p["name"] for p in saved]
        with wx.MultiChoiceDialog(self, "Saved presets to remove:", "Remove Presets", names) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            remove = {names[i] for i in dialog.GetSelections()}
        self.presets.save([p for p in saved if p["name"] not in remove])
        self.message.SetLabel(f"{len(remove)} presets removed")

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Store the edited filter settings and close the dialog with OK."""
        result = self.current_filters()
        if self.show_dropped_option:
            result.show_dropped = self.showdropcb.GetValue()
        self.result = result
        self.EndModal(wx.ID_OK)

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel; `GetData` returns None."""
        self.result = None
        self.EndModal(wx.ID_CANCEL)


def _file_filter_settings(path: str) -> Optional[dict]:
    """Return the Filter tool's settings in a file, as `Filter Settings` loads them.

    The file is a settings file with a Filter section (as `Save Settings...` of the
    Filter dialog and `To file...` write it), a Filter config alone, or a file of
    `Save Feature Settings...` (ranges only, all of them switched on).

    Args:
        path: The file.

    Returns:
        The settings (`enabled`, `filters`; ranges only: `filters`), or None if the
        file has none.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not JSON or its Filter settings are not valid.
    """
    from flim.core.filtering import file_data_ranges, with_window_ranges
    from flim.core.settings import read_tool_settings
    from flim.gui.editors import find_feature_settings
    from flim.tools.data import Filter

    entry = read_tool_settings(path, Filter)
    if entry is not None and entry.config is not None:
        config = Filter.config_class.model_validate(entry.config)
        return config.model_dump(mode="json", include={"enabled", "filters"})
    with open(path) as f:
        found = find_feature_settings(json.load(f), ["low", "high", "dropna"])
    if not found:
        return None
    nodes = with_window_ranges([], file_data_ranges(found))
    return {"filters": [node.model_dump(mode="json") for node in nodes]}


def _write_filter_settings(path: str, settings: dict) -> None:
    """Write the Filter tool's settings into a settings file, as `Save Settings...` does.

    The file's other sections are kept, and so are the Filter section's other
    settings and how it saves its results.

    Args:
        path: The settings file; created if it does not exist.
        settings: `enabled` and `filters`.

    Raises:
        OSError: If the file cannot be read or written.
        ValueError: If an existing file is not a settings file.
    """
    from flim.core.settings import read_tool_settings, tool_settings, write_tool_settings
    from flim.tools.data import Filter

    entry = read_tool_settings(path, Filter) if os.path.exists(path) else None
    base = (entry.config if entry is not None and entry.config else None) or Filter.config_class().model_dump(mode="json")
    config = Filter.config_class.model_validate({**base, **settings})
    autosave = entry.autosave if entry is not None else None
    write_tool_settings(path, Filter, tool_settings(config, autosave))


class ConfigureAxisDlg(wx.Dialog):
    """Dialog that edits the label and the range of a plot axis.

    The limits show with all their digits. A limit that is not edited is returned
    unchanged; an edited limit must be a finite number.
    """

    def __init__(
        self, parent: Optional[wx.Window], title: str, settings: dict[str, Any]
    ) -> None:
        """Build the dialog and show it.

        Args:
            parent: The parent window.
            title: The dialog's title.
            settings: The axis label (`label`) and the range (`min`, `max`).
        """
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title, size=(650, 220))
        self.panel = wx.Panel(self, wx.ID_ANY)

        self.labelname = wx.StaticText(self.panel, label="Axis label", pos=(20, 20))
        self.labelinput = wx.TextCtrl(
            self.panel, value=settings["label"], pos=(110, 20), size=(500, -1)
        )
        self.minname = wx.StaticText(self.panel, label="Min value", pos=(20, 60))
        self.mininput = wx.TextCtrl(
            self.panel, value=self._limit_text(settings["min"]), pos=(110, 60),
            size=(200, -1),
        )  # fmt: skip
        self.maxlabel = wx.StaticText(self.panel, label="Max value", pos=(20, 100))
        self.maxinput = wx.TextCtrl(
            self.panel, value=self._limit_text(settings["max"]), pos=(110, 100),
            size=(200, -1),
        )  # fmt: skip
        self.okButton = wx.Button(self.panel, label="OK", pos=(110, 160))
        self.closeButton = wx.Button(self.panel, label="Cancel", pos=(210, 160))
        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.settings = dict(settings)
        # the texts shown first: a limit whose text is not changed stays unchanged
        self._shown = {
            "min": self.mininput.GetValue(),
            "max": self.maxinput.GetValue(),
        }
        self.Show()

    @staticmethod
    def _limit_text(value: float) -> str:
        """Return the shortest text that reads back as the same float."""
        return repr(float(value))

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel; `get_settings` returns None."""
        self.settings = None
        self.EndModal(wx.ID_CANCEL)

    def get_settings(self) -> Optional[dict[str, Any]]:
        """Return the edited `label`, `min` and `max`; None if cancelled."""
        return self.settings

    def OnOK(self, event: Optional[wx.CommandEvent]) -> None:
        """Store the edited label and range and close the dialog with OK.

        If an edited limit is not a finite number, a message box shows it and the
        dialog stays open.
        """
        limits = {}
        for key, field, name in (
            ("min", self.mininput, "Min value"),
            ("max", self.maxinput, "Max value"),
        ):
            text = field.GetValue().strip()
            if text == self._shown[key].strip():
                limits[key] = self.settings[key]
                continue
            try:
                value = float(text)
            except ValueError:
                value = None
            if value is None or not np.isfinite(value):
                wx.MessageBox(
                    f"{name}: not a valid number: {text!r}", self.GetTitle(),
                    wx.OK | wx.ICON_WARNING, self,
                )  # fmt: skip
                return
            limits[key] = value
        self.settings["label"] = self.labelinput.GetValue()
        self.settings.update(limits)
        self.EndModal(wx.ID_OK)


class RenameGroupsDlg(wx.Dialog):
    """Dialog that asks for a pattern (regular expression) and its replacement.

    The caller reads the texts from `patterntxt` and `replacetxt`.
    """

    def __init__(self, parent: Optional[wx.Window], title: str) -> None:
        """Build the dialog and show it; the pattern is `^0+` (leading zeros)."""
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title, size=(450, 120))
        mainsizer = wx.BoxSizer(wx.VERTICAL)

        patternsizer = wx.BoxSizer(wx.HORIZONTAL)
        patternlabel = wx.StaticText(self, label="Pattern match")
        patternsizer.Add(patternlabel, 0, wx.ALL | wx.EXPAND, 5)
        self.patterntxt = wx.TextCtrl(self, value="^0+")
        patternsizer.Add(self.patterntxt, 0, wx.ALL | wx.EXPAND, 5)
        replacelabel = wx.StaticText(self, label="Replacement")
        patternsizer.Add(replacelabel, 0, wx.ALL | wx.EXPAND, 5)
        self.replacetxt = wx.TextCtrl(self, value="")
        patternsizer.Add(self.replacetxt, 0, wx.ALL | wx.EXPAND, 5)
        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okButton = wx.Button(self, label="OK", pos=(110, 160))
        buttonsizer.Add(self.okButton, 0, wx.ALL, 10)
        self.closeButton = wx.Button(self, label="Cancel", pos=(210, 160))
        buttonsizer.Add(self.closeButton, 0, wx.ALL, 10)
        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.SetSizer(mainsizer)
        mainsizer.Add(patternsizer, 0, wx.ALIGN_CENTER, 10)
        mainsizer.Add(buttonsizer, 0, wx.ALIGN_CENTER, 10)

        self.Show()

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Close the dialog with OK if the pattern is valid, else show a warning."""
        try:
            re.compile(self.patterntxt.GetLineText(0))
        except re.error:
            wx.MessageBox(
                "Not a valid pattern (regular expression).", self.GetTitle(),
                wx.OK | wx.ICON_WARNING, self,
            )  # fmt: skip
        else:
            self.EndModal(wx.ID_OK)

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel."""
        self.EndModal(wx.ID_CANCEL)


# Feature-level analysis customization

def register_generic_dialogs() -> None:
    """Register the generic `ConfigDialog` for FLIMAnalyzer's tools that use it.

    Explicitly, one config class each: registering says the tool can be fully
    configured in the GUI (see `flim.gui.configdialog.shown_in_gui`). Filter and
    Separate Categories register dialogs of their own; Collect Files none (its inputs
    are files, which the GUI has no windows for).
    """
    from flim import configs
    from flim.gui.configdialog import ConfigDialog, register_dialog

    names = (
        "AEAugmentConfig",
        "AEFeatureConfig",
        "AERunConfig",
        "AETrainConfig",
        "AETuneConfig",
        "BarPlotConfig",
        "BasicFLIRRConfig",
        "BoxPlotConfig",
        "CalculateConfig",
        "CategorizerConfig",
        "CategoryOrderConfig",
        "ConcatConfig",
        "DropColumnsConfig",
        "FLIRRPlotConfig",
        "FuseCategoriesConfig",
        "GMMConfig",
        "HeatmapConfig",
        "HistogramConfig",
        "ImportTablesConfig",
        "KDEConfig",
        "KMeansConfig",
        "KSStatsConfig",
        "LinePlotConfig",
        "MergeConfig",
        "PCAConfig",
        "PairPlotConfig",
        "PivotConfig",
        "RandomForestConfig",
        "RelativeChangeConfig",
        "RenameColumnsConfig",
        "ScaleConfig",
        "ScatterPlotConfig",
        "SeriesAnalysisConfig",
        "SortConfig",
        "SourceFromPathConfig",
        "SplitConfig",
        "SummaryConfig",
        "SwarmPlotConfig",
        "TableReaderConfig",
        "UnpivotConfig",
        "ViolinPlotConfig",
    )
    register_dialog(*(getattr(configs, name) for name in names))(ConfigDialog)


register_generic_dialogs()
