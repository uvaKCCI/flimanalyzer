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
import wx.grid
from pubsub import pub
from wx.lib.masked import NumCtrl
from flim.core.filter import RangeFilter
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
        ending = options_class.extensions[fmt]
        parts.append(f"{FORMAT_NAMES.get(fmt, fmt)} (*{ending})|*{ending}")
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
    """Where `Filter Settings` loads range filters from and saves them to.

    Attributes:
        defaults: Returns the range filters new tables start with.
        save_defaults: Makes a table's filters (`WindowFilters`) the defaults.
        saved: Returns the saved presets, each a dict with `name` and `settings`.
        save: Replaces the saved presets.
    """

    defaults: Callable[[], list[dict]]
    save_defaults: Callable[["WindowFilters"], None]
    saved: Callable[[], list[dict]]
    save: Callable[[list[dict]], None]


DEFAULTS_PRESET = "Defaults for new tables"


class ConfigureFiltersDlg(wx.Dialog):
    """Dialog that edits the range filters of a table.

    The list shows each filter's column, range and the number of rows it drops from
    the view; the labels above it show the rows dropped and remaining. With
    `presets`, `Load Preset...`, `Save as Preset...` and `Remove Presets...` load
    and save the filters: the defaults for new tables, a saved preset or a file.
    With OK, `GetData` returns an edited copy of the filter settings.
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
        self.filters = filters
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

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(filtersizer)
        sizer.Add(
            wx.StaticLine(self.panel, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5
        )
        sizer.Add(buttonsizer, 0, wx.ALL | wx.EXPAND, 5)
        self.panel.SetSizer(sizer)

        pub.subscribe(self.OnFiltersUpdated, FILTERS_UPDATED)
        self.filterlist.SetData(
            currentfilters,
            dataframe=self.dataframe,
            dropped=self.dropped,
            headers=["Use", "Column", "Min", "Max", "Dropped view"],
        )

        self.Show()

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

    def current_ranges(self) -> list[dict]:
        """Return the range filters as shown, as `RangeFilter` parameters."""
        cfgs = self.filterlist.GetData()
        return [cfgs[key].get_params() for key in cfgs]

    def show_ranges(self, ranges: list[dict]) -> None:
        """Show range filters for the table's columns; report the others.

        A filter of a column the table has replaces that column's filter; the other
        columns keep theirs. The rows each selected filter drops are computed again.
        """
        cfgs = self.filterlist.GetData()
        missing = [p["name"] for p in ranges if p["name"] not in cfgs]
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

    def _on_load_preset(self, event: wx.CommandEvent) -> None:
        """Ask for the defaults, a saved preset or a file, and show its filters."""
        saved = self.presets.saved()
        choices = [DEFAULTS_PRESET] + [p["name"] for p in saved] + ["From file..."]
        with wx.SingleChoiceDialog(self, "Load filters from:", "Load Preset", choices) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            index = dialog.GetSelection()
        from flim.core.filtering import file_data_ranges, preset_ranges

        try:
            if index == 0:
                ranges = self.presets.defaults()
            elif index <= len(saved):
                ranges = preset_ranges(saved[index - 1]["settings"])
            else:
                with wx.FileDialog(
                    self, "Load Filters", wildcard="JSON files (*.json)|*.json|All files|*",
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
                ) as files:  # fmt: skip
                    if files.ShowModal() != wx.ID_OK:
                        return
                    path = files.GetPath()
                from flim.gui.editors import find_feature_settings

                with open(path) as f:
                    found = find_feature_settings(json.load(f), ["low", "high", "dropna"])
                if not found:
                    self.message.SetLabel(f"No range filters in {os.path.basename(path)}")
                    return
                ranges = file_data_ranges(found)
        except (OSError, ValueError, KeyError, TypeError) as err:
            self.message.SetLabel(f"Could not load the filters: {err}")
            return
        self.show_ranges(ranges)

    def _on_save_preset(self, event: wx.CommandEvent) -> None:
        """Ask where to save the filters: the defaults, a saved preset, a new one or a file."""
        from flim.core.filtering import ranges_file_data, ranges_preset

        saved = self.presets.saved()
        names = [p["name"] for p in saved]
        choices = [DEFAULTS_PRESET] + names + ["New preset...", "To file..."]
        with wx.SingleChoiceDialog(self, "Save the filters as:", "Save as Preset", choices) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            choice = choices[dialog.GetSelection()]
        ranges = self.current_ranges()
        if choice == DEFAULTS_PRESET:
            self.presets.save_defaults(self.filters.model_copy(update={"range_filters": ranges}))
            self.message.SetLabel("Saved as the defaults for new tables")
            return
        if choice == "To file...":
            with wx.FileDialog(
                self, "Save Filters", wildcard="JSON files (*.json)|*.json|All files|*",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            ) as files:  # fmt: skip
                if files.ShowModal() != wx.ID_OK:
                    return
                path = files.GetPath()
            try:
                with open(path, "w") as f:
                    json.dump(ranges_file_data(ranges), f, indent=2)
            except OSError as err:
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
        self.presets.save(presets + [{"name": choice, "settings": ranges_preset(ranges)}])
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
        changes = {"range_filters": self.current_ranges()}
        if self.show_dropped_option:
            changes["show_dropped"] = self.showdropcb.GetValue()
        self.result = self.filters.model_copy(update=changes)
        self.EndModal(wx.ID_OK)

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel; `GetData` returns None."""
        self.result = None
        self.EndModal(wx.ID_CANCEL)


class ConfigureAxisDlg(wx.Dialog):
    """Dialog that edits the label and the range of a plot axis."""

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
        self.mininput = NumCtrl(
            self.panel, value=settings["min"], fractionWidth=2, pos=(110, 60)
        )
        self.maxlabel = wx.StaticText(self.panel, label="Max value", pos=(20, 100))
        self.maxinput = NumCtrl(
            self.panel, value=settings["max"], fractionWidth=2, pos=(110, 100)
        )
        self.okButton = wx.Button(self.panel, label="OK", pos=(110, 160))
        self.closeButton = wx.Button(self.panel, label="Cancel", pos=(210, 160))
        self.okButton.Bind(wx.EVT_BUTTON, self.SaveConnString)
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.settings = dict(settings)
        self.Show()

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel; `get_settings` returns None."""
        self.settings = None
        self.EndModal(wx.ID_CANCEL)

    def get_settings(self) -> Optional[dict[str, Any]]:
        """Return the edited `label`, `min` and `max`; None if cancelled."""
        return self.settings

    def SaveConnString(self, event: wx.CommandEvent) -> None:
        """Store the edited label and range and close the dialog with OK."""
        self.settings["label"] = self.labelinput.GetValue()
        self.settings["min"] = self.mininput.GetValue()
        self.settings["max"] = self.maxinput.GetValue()
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
