#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialogs of the data and plot windows, and functions that save tables and figures.

The save functions ask for the file and its format in a file dialog.
"""

import logging
import os
import re
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
    from flim.core.settings import FilterSettings

logger = logging.getLogger(__name__)


def check_data_msg(data: Optional["pd.DataFrame"]) -> bool:
    """Return whether there is data; if not, show a warning message box.

    Args:
        data: The table; None if no data is loaded.

    Returns:
        True if `data` has rows; otherwise False, after the warning is closed.
    """
    ok = data is not None and len(data) > 0
    if not ok:
        wx.MessageBox("No data loaded. Import data first.", "Warning", wx.OK)
    return ok


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


class ConfigureFiltersDlg(wx.Dialog):
    """Dialog that edits the range filters of a table.

    The list shows each filter's column, range and the number of rows it drops from
    the view; the labels above it show the rows dropped and remaining. With OK,
    `GetData` returns an edited copy of the filter settings.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        filters: Optional["FilterSettings"] = None,
        dataframe: Optional["pd.DataFrame"] = None,
        dropped: dict[Any, Any] = {},
        showusefilter: bool = True,
    ) -> None:
        """Build the dialog and show it.

        Args:
            parent: The parent window.
            filters: The filter settings to edit; required (None is not handled).
            dataframe: The table the filters apply to; required (None is not
                handled).
            dropped: The row positions dropped from the view, by filter name or
                other key. Defaults to none.
            showusefilter: Whether the dialog shows `Use Filters` and
                `Show Dropped`, whose values `GetData` returns. Defaults to True.
        """
        wx.Dialog.__init__(
            self, parent, wx.ID_ANY, "Filter Settings", size=(650, 400)
        )
        self.dataframe = dataframe
        self.dropped = dropped
        self.showusefilter = showusefilter
        self.filters = filters
        cfgdata = filters.range_filters
        self.panel = wx.Panel(self, wx.ID_ANY)
        cbsizer = wx.BoxSizer(wx.HORIZONTAL)
        filtersizer = wx.BoxSizer(wx.VERTICAL)
        if self.showusefilter:
            self.filtercb = wx.CheckBox(self.panel, wx.ID_ANY, label="Use Filters")
            self.filtercb.SetValue(filters.use)
            self.filtercb.Bind(wx.EVT_CHECKBOX, self.OnUseFilters)
            cbsizer.Add(self.filtercb, 0, wx.ALL | wx.EXPAND, 5)
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

        buttonsizer = wx.BoxSizer(wx.VERTICAL)
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

    def OnUseFilters(self, event: wx.CommandEvent) -> None:
        """Enable the labels and the list while `Use Filters` is checked."""
        enable = event.GetEventObject().GetValue()
        self.dropped_label.Enable(enable)
        self.remaining_label.Enable(enable)
        self.filterlist.Enable(enable)

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Store the edited filter settings and close the dialog with OK."""
        cfgs = self.filterlist.GetData()
        changes = {"range_filters": [cfgs[key].get_params() for key in cfgs]}
        if self.showusefilter:
            changes["use"] = self.filtercb.GetValue()
            changes["show_dropped"] = self.showdropcb.GetValue()
        self.result = self.filters.model_copy(update=changes)
        self.EndModal(wx.ID_OK)

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel; `GetData` returns None."""
        self.result = None
        self.EndModal(wx.ID_CANCEL)


class ConfigureCategoriesDlg(wx.Dialog):
    """Dialog that edits the bins and labels of a category, as comma-separated text."""

    def __init__(
        self,
        parent: Optional[wx.Window],
        title: str = "",
        bins: list[float] = [],
        labels: list[str] = [],
    ) -> None:
        """Build the dialog and show it.

        Args:
            parent: The parent window.
            title: Appended to the dialog's title `Category Configuration: `.
                Defaults to "".
            bins: The bin edges. Defaults to none.
            labels: The category labels. Defaults to none.
        """
        wx.Dialog.__init__(
            self,
            parent,
            wx.ID_ANY,
            f"Category Configuration: {title}",
            size=(650, 220),
        )
        self.panel = wx.Panel(self, wx.ID_ANY)

        self.bin = wx.StaticText(self.panel, label="Category bins", pos=(20, 20))
        self.bin_field = wx.TextCtrl(
            self.panel,
            value=",".join([str(b) for b in bins]),
            pos=(110, 20),
            size=(500, -1),
        )
        self.label = wx.StaticText(self.panel, label="Category labels", pos=(20, 60))
        self.label_field = wx.TextCtrl(
            self.panel, value=",".join(labels), pos=(110, 60), size=(500, -1)
        )
        self.okButton = wx.Button(self.panel, label="OK", pos=(110, 160))
        self.okButton.Bind(wx.EVT_BUTTON, self.OnSave)
        self.cancelButton = wx.Button(self.panel, label="Cancel", pos=(210, 160))
        self.cancelButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        self.Show()

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel; `get_config` returns None."""
        self.bins = None
        self.labels = None
        self.EndModal(wx.ID_CANCEL)

    def get_config(self) -> Optional[tuple[list[float], list[str]]]:
        """Return the edited bins and labels; None if cancelled or there are no bins."""
        if self.bins:
            return self.bins, self.labels
        else:
            return None

    def OnSave(self, event: wx.CommandEvent) -> None:
        """Store the bins and labels and close the dialog with OK.

        Raises:
            ValueError: If a bin is not a number.
        """
        self.bins = [float(f) for f in self.bin_field.GetValue().split(",")]
        self.labels = self.label_field.GetValue().split(",")
        self.EndModal(wx.ID_OK)


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
class ConfigureFeatureDlg(wx.Dialog):
    """Dialog with an input control per option of a feature's analysis."""

    def __init__(
        self,
        parent: Optional[wx.Window],
        title: str,
        feature: str,
        settings: dict[str, list[Any]],
        defaults: Optional[dict[str, Any]],
    ) -> None:
        """Build the dialog; it is not shown.

        Args:
            parent: The parent window.
            title: The dialog's title.
            feature: Not used.
            settings: Per option name: the class of its input control and a dict of
                the control's keyword arguments.
            defaults: The value of each option to show; None: the controls'
                initial values.
        """
        wx.Dialog.__init__(
            self, parent, wx.ID_ANY, title, size=(200 * min(len(settings), 3), 120)
        )

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        optsizer = wx.WrapSizer(wx.HORIZONTAL)
        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.settings = (
            settings  # dict of option name -> [input handler class, handler args]
        )
        self.insettings = dict(self.settings)
        self.inputs = dict()

        for name, specs in self.settings.items():
            opt_handler = specs[0](self, wx.ID_ANY, **specs[1])
            self.inputs[name] = opt_handler
            if defaults is not None:
                self.inputs[name].SetValue(defaults[name])
            optsizer.Add(
                wx.StaticText(self, label=name), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5
            )
            optsizer.Add(opt_handler, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.okButton = wx.Button(self, label="OK", pos=(110, 160))
        buttonsizer.Add(self.okButton, 0, wx.ALL, 10)
        self.closeButton = wx.Button(self, label="Cancel", pos=(210, 160))
        buttonsizer.Add(self.closeButton, 0, wx.ALL, 10)
        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        self.SetSizer(mainsizer)
        mainsizer.Add(optsizer, 0, wx.ALIGN_LEFT, 10)
        mainsizer.Add(buttonsizer, 0, wx.ALIGN_CENTER, 10)

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Store the options' values and close the dialog with OK."""
        self.insettings = {
            setting: self.inputs[setting].GetValue() for setting in self.settings
        }
        self.EndModal(wx.ID_OK)

    def OnQuit(self, event: wx.Event) -> None:
        """Close the dialog with Cancel."""
        self.EndModal(wx.ID_CANCEL)

    def get_settings(self) -> dict[str, Any]:
        """Return the options' values with OK; after Cancel, the `settings` given."""
        return self.insettings  # dict of option name -> option value
