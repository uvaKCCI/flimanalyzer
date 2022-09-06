#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 12 13:35:51 2018

@author: khs3z
"""

import logging
import itertools
import re
from collections import OrderedDict
import wx.grid
from pubsub import pub
from wx.lib.masked import NumCtrl
from wx.lib.scrolledpanel import ScrolledPanel
from flim.core.filter import RangeFilter
import flim.core.configuration as cfg
from flim.gui.listcontrol import FilterListCtrl, FILTERS_UPDATED
from flim.gui.dicttablepanel import ListTable
from flim.plugin import ALL_FEATURES


def check_data_msg(data):
    ok = data is not None and len(data) > 0
    if not ok:
        wx.MessageBox("No data loaded. Import data first.", "Warning", wx.OK)
    return ok


def fix_filename(fname):
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


def save_dataframe(
    parent, title, data, filename, wildcard="txt files (*.txt)|*.txt", saveindex=True
):
    with wx.FileDialog(
        parent, title, wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    ) as fileDialog:
        fileDialog.SetFilename(fix_filename(filename))
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return None
        fname = fileDialog.GetPath()
        try:
            data.reset_index()
            # if indx was flattened in analyzer.summarize_data, multiindex col values were joined with '\n'--> revert here
            data.columns = [c.replace("\n", " ") for c in data.columns.values]
            data.to_csv(fname, index=saveindex, sep="\t")
        except IOError:
            wx.MessageBox("Error saving data in file %s" % fname, "Error", wx.OK)
            return None
        return fname


def save_figure(
    parent, title, fig, filename, wildcard="all files (*.*)|*.*", dpi=300, legend=None
):
    with wx.FileDialog(
        parent, title, wildcard=wildcard, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    ) as fileDialog:
        fileDialog.SetFilename(fix_filename(filename))
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return None
        fname = fileDialog.GetPath()
        try:
            if legend is not None:
                fig.savefig(
                    fname, dpi=dpi, bbox_extra_artists=(legend,), bbox_inches="tight"
                )
            else:
                fig.savefig(fname, dpi=dpi, bbox_inches="tight")
        except IOError:
            error = "Error saving figure in file %s" % fname
            logging.error(error)
            wx.MessageBox(error, "Error", wx.OK)
            return None
        return fname


class BasicAnalysisConfigDlg(wx.Dialog):
    def __init__(
        self,
        parent,
        title,
        input={},
        description=None,
        data_choices={},
        chooseinput=False,
        enablegrouping=True,
        enablefeatures=True,
        selectedgrouping=["None"],
        selectedfeatures=ALL_FEATURES,
        optgridrows=0,
        optgridcols=2,
        enablefeatsettings=False,
        featuresettings={},
        settingspecs={},
        autosave=True,
        working_dir="",
    ):
        super().__init__(parent, wx.ID_ANY, title)  # , size= (650,400))
        self.panel = wx.Panel(self, wx.ID_ANY)
        # 5 col gridsizer
        self.input = input
        self.description = description
        self.chooseinput = chooseinput
        self.enablegrouping = enablegrouping
        self.enablefeatures = enablefeatures
        self.data_choices = data_choices
        self.enablefeatsettings = enablefeatsettings
        self.featuresettings = featuresettings
        self.settingspecs = settingspecs
        self.autosave = autosave
        self.working_dir = working_dir

        data = list(self.input.values())[0]
        allfeatures = self.get_selectable_features()
        # ordered dict with label:columm items; column headers are converted to single line labels
        self.allfeatures = OrderedDict((" ".join(c.split("\n")), c) for c in allfeatures)
        if isinstance(selectedfeatures, str):
            self.selectedfeatures = {selectedfeatures: selectedfeatures}
        else:
            self.selectedfeatures = {" ".join(c.split("\n")): c for c in selectedfeatures}

        sizer = wx.BoxSizer(wx.VERTICAL)

        if description and len(description) > 0:
            sizer.Add(
                wx.StaticText(self.panel, label=description),
                0,
                wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                5,
            )
            sizer.Add(
                wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL),
                0,
                wx.ALL | wx.EXPAND,
                5,
            )
        self.optionsizer = wx.GridSizer(optgridcols, optgridrows, 0)
        for p in self.get_option_panels():
            self.optionsizer.Add(p)

        sizer.Add(self.optionsizer, 0, wx.ALIGN_LEFT, 5)
        sizer.Add(
            wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL), 0, wx.ALL | wx.EXPAND, 5
        )

        storagesizer = wx.BoxSizer(wx.HORIZONTAL)
        self.autosave_cb = wx.CheckBox(self.panel, wx.ID_ANY, "Autosave")
        self.Bind(wx.EVT_CHECKBOX, self._on_checked)
        self.autosave_cb.SetValue(self.autosave)
        self.browse_button = wx.Button(self.panel, wx.ID_ANY, "Choose...")
        self.browse_button.Bind(wx.EVT_BUTTON, self._on_browse)
        self.browse_button.Enable(self.autosave)
        self.workingdirtxt = wx.StaticText(self.panel, label=self.working_dir)
        self.workingdirtxt.Enable(self.autosave)
        storagesizer.Add(self.autosave_cb)
        storagesizer.Add(self.browse_button)
        storagesizer.Add(self.workingdirtxt)
        sizer.Add(storagesizer)
        sizer.Add(
            wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL), 0, wx.ALL | wx.EXPAND, 5
        )

        if self.enablegrouping:
            groupings = ["None"]
            if data.select_dtypes(["category"]).columns.nlevels == 1:
                categories = [
                    c for c in list(data.select_dtypes(["category"]).columns.values)
                ]
            else:
                categories = [
                    c
                    for c in list(
                        data.select_dtypes(["category"])
                        .columns.get_level_values(0)
                        .values
                    )
                ]
            logging.debug(f"groupings: {groupings}")
            for i in range(1, len(categories) + 1):
                permlist = list(itertools.permutations(categories, i))
                for p in permlist:
                    groupings.append(", ".join(p))
            if ", ".join(selectedgrouping) not in groupings:
                selectedgrouping = ["None"]
            groupingsizer = wx.BoxSizer(wx.HORIZONTAL)
            self.grouping_combobox = wx.ComboBox(
                self.panel,
                wx.ID_ANY,
                style=wx.CB_READONLY,
                value=", ".join(selectedgrouping),
                choices=groupings,
            )
            groupingsizer.Add(
                wx.StaticText(self.panel, label="Data Grouping"),
                0,
                wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                5,
            )
            groupingsizer.Add(
                self.grouping_combobox,
                0,
                wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
                5,
            )
            sizer.Add(groupingsizer, 0, wx.ALIGN_LEFT, 5)
            sizer.Add(
                wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL),
                0,
                wx.ALL | wx.EXPAND,
                5,
            )

        buttonsizer = wx.BoxSizer(wx.HORIZONTAL)
        if self.enablefeatures:
            self.scrolledpanel = ScrolledPanel(
                self.panel, wx.ID_ANY, size=(-1, self.GetSize().y / 3)
            )
            self.cbsizer = wx.GridSizer(4, 0, 0)
            self._update_feature_cbs()
            sizer.Add(self.scrolledpanel, 0, wx.EXPAND | wx.ALIGN_CENTER)

            sizer.Add(
                wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL),
                0,
                wx.ALL | wx.EXPAND,
                5,
            )

            self.selectAllButton = wx.Button(self.panel, label="Select All")
            self.selectAllButton.Bind(wx.EVT_BUTTON, self.OnSelectAll)
            buttonsizer.Add(self.selectAllButton, 0, wx.ALL | wx.EXPAND, 5)
            self.deselectAllButton = wx.Button(self.panel, label="Deselect All")
            self.deselectAllButton.Bind(wx.EVT_BUTTON, self.OnDeselectAll)
            buttonsizer.Add(self.deselectAllButton, 0, wx.ALL | wx.EXPAND, 5)

        self.okButton = wx.Button(self.panel, label="OK", pos=(110, 160))
        self.okButton.Bind(wx.EVT_BUTTON, self.OnOK)
        buttonsizer.Add(self.okButton, 0, wx.ALL, 10)
        self.cancelButton = wx.Button(self.panel, label="Cancel", pos=(210, 160))
        self.cancelButton.Bind(wx.EVT_BUTTON, self.OnQuit)
        buttonsizer.Add(self.cancelButton, 0, wx.ALL, 10)

        sizer.Add(buttonsizer, 0, wx.ALIGN_CENTER, 5)
        self.panel.SetSizer(sizer)
        self.panel.Fit()
        self.panel.Layout()
        self.Fit()

        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        self.SetLayoutAdaptationMode(wx.DIALOG_ADAPTATION_MODE_ENABLED)
        self.DoLayoutAdaptation()
        self.Show()

    def _update_feature_cbs(self):
        if self.cbsizer: 
            self.cbsizer.Clear(delete_windows=True)
        if self.allfeatures is None:
            self.allfeatures = {}
        self.cboxes = {}
        for f in self.allfeatures:
            cb = wx.CheckBox(self.scrolledpanel, wx.ID_ANY, f)
            cb.SetValue(
                (f in self.selectedfeatures) or (ALL_FEATURES in self.selectedfeatures)
            )
            self.cboxes[f] = cb
            self.cbsizer.Add(cb, 0, wx.ALL, 5)
            if self.enablefeatsettings:
                cb.Bind(wx.EVT_RIGHT_UP, self.OnClickFeature)
            cb.Bind(wx.EVT_CHECKBOX, self._on_feature_selection)
        self.scrolledpanel.SetSizer(self.cbsizer)
        self.scrolledpanel.SetupScrolling(scroll_x=False)
        self.scrolledpanel.Update()
        self.Update()

    def get_selectable_features(self):
        data = list(self.input.values())[0]
        allfeatures = data.select_dtypes(
            include=["number"], exclude=["category"]
        ).columns.values

        return allfeatures

    def _on_checked(self, event):
        is_checked = self.autosave_cb.GetValue()
        self.workingdirtxt.Enable(is_checked)
        self.browse_button.Enable(is_checked)

    def _on_browse(self, event):
        dirname = self.workingdirtxt.GetLabel()
        with wx.DirDialog(
            self,
            "Working Directory",
            dirname,
            wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dirDialog:
            # dirDialog.SetPath(dirname)
            # fileDialog.SetFilename(fname)
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            dirname = dirDialog.GetPath()
            self.workingdirtxt.SetLabel(dirname)

    def get_option_panels(self):
        return []

    def _on_feature_selection(self, event):
        pass

    def OnClickFeature(self, event):
        cbox = event.GetEventObject()
        for feature in self.cboxes.keys():
            if self.cboxes[feature] == cbox:
                default = None
                if feature in self.featuresettings:
                    default = self.featuresettings[feature]
                dlg = ConfigureFeatureDlg(
                    self,
                    title=f"{feature} config",
                    feature=feature,
                    settings=self.settingspecs,
                    defaults=default,
                )
                if dlg.ShowModal() == wx.ID_OK:
                    self.featuresettings[feature] = dlg.get_settings()
                break

    def OnSelectAll(self, event):
        if self.cboxes:
            for key in self.cboxes:
                self.cboxes[key].SetValue(True)

    def OnDeselectAll(self, event):
        if self.cboxes:
            for key in self.cboxes:
                self.cboxes[key].SetValue(False)

    def OnQuit(self, event):
        self.EndModal(wx.ID_CANCEL)

    def _get_selected(self):
        params = {}
        if self.enablegrouping:
            valuestr = self.grouping_combobox.GetValue()
            if valuestr != "None":
                params["grouping"] = valuestr.split(", ")
            else:
                params["grouping"] = []
        else:
            params["grouping"] = []
        if self.enablefeatures:
            params["features"] = [
                self.allfeatures[key]
                for key in self.cboxes
                if self.cboxes[key].GetValue()
            ]
            if self.enablefeatsettings:
                params["featuresettings"] = self.featuresettings
        else:
            params["features"] = []
        if self.chooseinput:
            params["input"] = self.input
        else:
            params["input"] = self.input
        params["autosave"] = self.autosave_cb.GetValue()
        params["working_dir"] = self.workingdirtxt.GetLabel()
        return params

    def get_selected(self):
        return self._get_selected()

    def OnOK(self, event):
        if len(self._get_selected()) == 0:
            wx.MessageDialog(self, "Select at least one function.")
        else:
            self.EndModal(wx.ID_OK)


class SelectGroupsDlg(wx.Dialog):
    def __init__(self, parent, title, groups=[], selected="All"):
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
        mainsizer.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.ALL | wx.EXPAND, 5)
        mainsizer.Add(selectbsizer, 0, wx.ALIGN_CENTER, 5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(mainsizer, 0, wx.ALIGN_CENTER, 5)
        sizer.Add(buttonsizer, 0, wx.ALIGN_CENTER, 5)
        self.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        self.SetLayoutAdaptationMode(wx.DIALOG_ADAPTATION_MODE_ENABLED)
        self.DoLayoutAdaptation()
        self.Show()

    def OnSelectAll(self, event):
        for key in self.cboxes:
            self.cboxes[key].SetValue(True)

    def OnDeselectAll(self, event):
        for key in self.cboxes:
            self.cboxes[key].SetValue(False)

    def OnQuit(self, event):
        self.EndModal(wx.ID_CANCEL)

    def _get_selected(self):
        return [key for key in self.cboxes if self.cboxes[key].GetValue()]

    def get_selected(self):
        return self._get_selected()

    def OnOK(self, event):
        if len(self._get_selected()) == 0:
            wx.MessageDialog(self, "Select at least one function.")
        else:
            self.EndModal(wx.ID_OK)


class ConfigureFiltersDlg(wx.Dialog):
    def __init__(
        self, parent, config=None, dataframe=None, dropped={}, showusefilter=True
    ):
        wx.Dialog.__init__(
            self, parent, wx.ID_ANY, "Filter Settings TEST", size=(650, 400)
        )
        self.dataframe = dataframe
        self.dropped = dropped
        self.showusefilter = showusefilter
        cfgdata = config.get(cfg.CONFIG_RANGEFILTERS)
        self.panel = wx.Panel(self, wx.ID_ANY)
        cbsizer = wx.BoxSizer(wx.HORIZONTAL)
        filtersizer = wx.BoxSizer(wx.VERTICAL)
        if self.showusefilter:
            self.filtercb = wx.CheckBox(self.panel, wx.ID_ANY, label="Use Filters")
            self.filtercb.SetValue(config.get(cfg.CONFIG_USE))
            self.filtercb.Bind(wx.EVT_CHECKBOX, self.OnUseFilters)
            cbsizer.Add(self.filtercb, 0, wx.ALL | wx.EXPAND, 5)
            self.showdropcb = wx.CheckBox(self.panel, wx.ID_ANY, label="Show Dropped")
            self.showdropcb.SetValue(config.get(cfg.CONFIG_SHOW_DROPPED))
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
        # filtersizer.Add(labelsizer)

        self.filterlist = FilterListCtrl(
            self.panel,
            showdropped=True,
            fireevents=True,
            style=wx.LC_REPORT,
            size=(500, -1),
        )  # , pos=(110,100))
        self.filterlist.InsertColumn(0, "Use")
        self.filterlist.InsertColumn(1, "Column")
        self.filterlist.InsertColumn(2, "Min", wx.LIST_FORMAT_RIGHT)
        self.filterlist.InsertColumn(3, "Max", wx.LIST_FORMAT_RIGHT)
        # self.filterlist.SetEditable([False, False, True, True])
        self.filterlist.InsertColumn(4, "Dropped view", wx.LIST_FORMAT_RIGHT)
        self.filterlist.SetEditable([False, False, True, True, False])
        self.filterlist.Arrange()
        currentfilters = {rfcfg["name"]: RangeFilter(params=rfcfg) for rfcfg in cfgdata}

        filtersizer.Add(self.filterlist, 0, wx.ALL | wx.EXPAND, 5)

        loadbutton = wx.Button(self.panel, label="Load")
        loadbutton.Bind(wx.EVT_BUTTON, self.OnLoad)
        okbutton = wx.Button(self.panel, label="OK")
        okbutton.Bind(wx.EVT_BUTTON, self.OnOK)
        cancelbutton = wx.Button(self.panel, label="Cancel")
        cancelbutton.Bind(wx.EVT_BUTTON, self.OnQuit)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        buttonsizer = wx.BoxSizer(wx.VERTICAL)
        buttonsizer.Add(loadbutton, 0, wx.ALL | wx.EXPAND, 5)
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

    def OnFiltersUpdated(self, updateditems, totaldropped, viewdropped, viewlength):
        remaining = viewlength - viewdropped
        # self.dropped_label.SetLabel(f'Dropped from view: {viewdropped:,} (of {viewlength:,})')
        # self.remaining_label.SetLabel(f'Remaining: {remaining:,} ({100.0 * remaining/viewlength:.2f}%)')
        logging.debug(f"Updated: {[name for name in updateditems]}")
        logging.debug(
            f"Dropped from view: {viewdropped:,} (of {viewlength:,}); Remaining:"
            f" {remaining:,} ({100.0 * remaining/viewlength:.2f}%)"
        )

    def GetData(self):
        return self.config

    def OnLoad(self, event):
        pass

    def OnUseFilters(self, event):
        enable = event.GetEventObject().GetValue()
        self.dropped_label.Enable(enable)
        self.remaining_label.Enable(enable)
        self.filterlist.Enable(enable)

    def OnOK(self, event):
        cfgs = self.filterlist.GetData()
        self.config = {}
        if self.showusefilter:
            self.config[cfg.CONFIG_USE] = self.filtercb.GetValue()
            self.config[cfg.CONFIG_SHOW_DROPPED] = self.showdropcb.GetValue()
        self.config[cfg.CONFIG_RANGEFILTERS] = [cfgs[key].get_params() for key in cfgs]
        self.EndModal(wx.ID_OK)

    def OnQuit(self, event):
        self.config = None
        self.EndModal(wx.ID_CANCEL)


class ConfigureCategoriesDlg(wx.Dialog):
    def __init__(self, parent, title="", bins=[], labels=[]):
        wx.Dialog.__init__(
            self,
            parent,
            wx.ID_ANY,
            "Category Configuration: %s" % title,
            size=(650, 220),
        )
        #        self.bins = None
        #        self.labels = None
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

    def OnQuit(self, event):
        self.bins = None
        self.labels = None
        self.EndModal(wx.ID_CANCEL)

    def get_config(self):
        if self.bins:
            return self.bins, self.labels
        else:
            return None

    def OnSave(self, event):
        self.bins = [float(f) for f in self.bin_field.GetValue().split(",")]
        # self.labels = self.label_field.GetValue().encode('ascii','ignore').split(',')
        self.labels = self.label_field.GetValue().split(",")
        self.EndModal(wx.ID_OK)


class ConfigureAxisDlg(wx.Dialog):
    def __init__(self, parent, title, settings):
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

    def OnQuit(self, event):
        self.settings = None
        self.EndModal(wx.ID_CANCEL)

    def get_settings(self):
        return self.settings

    def SaveConnString(self, event):
        self.settings["label"] = self.labelinput.GetValue()
        self.settings["min"] = self.mininput.GetValue()
        self.settings["max"] = self.maxinput.GetValue()
        self.EndModal(wx.ID_OK)


class RenameGroupsDlg(wx.Dialog):
    def __init__(self, parent, title):
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

    def OnOK(self, event):
        try:
            re.compile(self.patterntxt.GetLineText(0))
        except re.error:
            wx.MessageDialog(self, "Invalid regex pattern")
        else:
            self.EndModal(wx.ID_OK)

    def OnQuit(self, event):
        self.EndModal(wx.ID_CANCEL)


# Feature-level analysis customization
class ConfigureFeatureDlg(wx.Dialog):
    def __init__(self, parent, title, feature, settings, defaults):
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

    def OnOK(self, event):
        self.insettings = {
            setting: self.inputs[setting].GetValue() for setting in self.settings
        }
        # for setting in self.settings:
        #   self.insettings[setting] = self.inputs[setting].GetValue()
        self.EndModal(wx.ID_OK)

    def OnQuit(self, event):
        self.EndModal(wx.ID_CANCEL)

    def get_settings(self):
        return self.insettings  # dict of option name -> option value
