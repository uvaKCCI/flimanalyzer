#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

import numpy as np
import pandas as pd
import wx
from importlib_resources import files

from flim.plugin import plugin, ALL_FEATURES
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.resources


def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)

    percentile_.__name__ = "%s percentile" % n
    return percentile_


class SummaryStatsConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        description=None,
        selectedgrouping=["None"],
        selectedfeatures=ALL_FEATURES,
        allaggs=[],
        selectedaggs="All",
        singledf=False,
        autosave=True,
        working_dir="",
    ):
        self.allaggs = allaggs
        self.selectedaggs = selectedaggs
        self.singledf = singledf
        super().__init__(
            parent,
            title,
            input=input,
            description=description,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=0,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        self.aggboxes = {}
        ssizer = wx.BoxSizer(wx.HORIZONTAL)
        self.dfoutput_opts = ["Single table", "One table per feature"]
        if self.singledf:
            sel_dfoutput = self.dfoutput_opts[0]
        else:
            sel_dfoutput = self.dfoutput_opts[1]
        self.dfoutput_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_dfoutput,
            choices=self.dfoutput_opts,
        )
        ssizer.Add(
            wx.StaticText(self.panel, label="Output "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        ssizer.Add(
            self.dfoutput_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        nestsizer = wx.BoxSizer(wx.HORIZONTAL)
        aggsizer = wx.GridSizer(5, 0, 0)
        for f in self.allaggs:
            cb = wx.CheckBox(self.panel, wx.ID_ANY, f)
            cb.SetValue((f in self.selectedaggs) or (self.selectedaggs == "All"))
            self.aggboxes[f] = cb
            aggsizer.Add(cb, 0, wx.ALL, 5)

        selectsizer = wx.BoxSizer(wx.VERTICAL)
        self.selectAllButton = wx.Button(self.panel, label="Select All")
        self.selectAllButton.Bind(wx.EVT_BUTTON, self.OnSelectAllAggs)
        selectsizer.Add(self.selectAllButton, 0, wx.ALL | wx.EXPAND, 5)
        self.deselectAllButton = wx.Button(self.panel, label="Deselect All")
        self.deselectAllButton.Bind(wx.EVT_BUTTON, self.OnDeselectAllAggs)
        selectsizer.Add(self.deselectAllButton, 0, wx.ALL | wx.EXPAND, 5)
        nestsizer.Add(aggsizer, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        nestsizer.Add(selectsizer, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)
        return [ssizer, nestsizer]

    def OnSelectAllAggs(self, event):
        if self.aggboxes:
            for key in self.aggboxes:
                self.aggboxes[key].SetValue(True)

    def OnDeselectAllAggs(self, event):
        if self.aggboxes:
            for key in self.aggboxes:
                self.aggboxes[key].SetValue(False)

    def _get_selected(self):
        selaggs = [key for key in self.aggboxes if self.aggboxes[key].GetValue()]
        params = super()._get_selected()
        params["aggs"] = selaggs
        params["singledf"] = self.dfoutput_combobox.GetValue() == self.dfoutput_opts[0]
        return params


@plugin(plugintype="Analysis")
class SummaryStats(AbstractPlugin):

    agg_functions = {
        "count": "count",
        "min": "min",
        "max": "max",
        "mean": "mean",
        "std": "std",
        "sem": "sem",
        "median": "median",
        "percentile(25)": percentile(25),
        "percentile(75)": percentile(75),
        "sum": "sum",
    }

    def __init__(self, name="Summarize", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_description(self):
        return "Calculates counts, min, max, mean, median (50th percentile), 25th percentile, and 75th percentile, StDev, S.E.M, of grouped data."

    # def __repr__(self):
    #    return f"name: {self.name}"

    def __str__(self):
        return self.name

    def get_icon(self):
        source = files(flim.resources).joinpath("summary.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "aggs": [n for n in self.agg_functions],
                "singledf": True,
                "flattenindex": True,
            }
        )
        return params

    def output_definition(self):
        if self.params["singledf"]:
            return {self._create_df_title(None): None}
        else:
            return {
                self._create_df_title(f): None for f in sorted(self.params["features"])
            }

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = SummaryStatsConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            description=self.get_description(),
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            allaggs=self.agg_functions,
            selectedaggs=self.params["aggs"],
            singledf=self.params["singledf"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        parameters = dlg.get_selected()
        self.configure(**parameters)
        return parameters

    def _create_df_title(self, feature):
        if feature:
            return "Table: " + ": ".join(["Summary", feature.replace("\n", " ")])
        else:
            return "Table: Summary"

    def get_mapped_parameters(self):
        if not self.params["singledf"]:
            parallel_params = []
            for f in self.params["features"]:
                pair_param = self.params.copy()
                pair_param["features"] = [f]
                parallel_params.append(pair_param)
            return parallel_params
        else:
            # combine all features results in single df
            return [self.params]

    def execute(self):
        summaries = {}
        data = list(self.input.values())[0]
        sel_functions = [self.agg_functions[f] for f in self.params["aggs"]]
        features = self.params["features"]
        if features == ALL_FEATURES:
            features = list(data.select_dtypes(np.number).columns.values)
        if features is None or len(features) == 0:
            return summaries
        for header in features:
            # categories = [col for col in self.flimanalyzer.get_importer().get_parser().get_regexpatterns()]
            allcats = [x for x in self.params["grouping"]]
            allcats.append(header)
            dftitle = self._create_df_title(header)
            if self.params["grouping"] is None or len(self.params["grouping"]) == 0:
                # create fake group by --> creates 'index' column that needs to removed from aggregate results
                summary = (
                    data[allcats]
                    .groupby(lambda _: True, group_keys=False)
                    .agg(sel_functions)
                )
            else:
                # data = data.copy()
                # data.reset_index(inplace=True)
                grouped_data = data[allcats].groupby(
                    self.params["grouping"], observed=True
                )
                summary = grouped_data.agg(sel_functions)
                # summary = summary.dropna()
                summary.reset_index(inplace=True)
            if self.params["flattenindex"]:
                summary.columns = [
                    "\n".join(col).strip() for col in summary.columns.values
                ]
            summaries[dftitle] = summary  # .reset_index()
        if self.params["singledf"]:
            if len(self.params["grouping"]) > 0:
                concat_df = pd.concat(
                    [
                        summaries[key].set_index(self.params["grouping"])
                        for key in summaries
                    ],
                    axis=1,
                ).reset_index()
            else:
                concat_df = pd.concat([summaries[key] for key in summaries], axis=1)
            return {self._create_df_title(None): concat_df}
        else:
            return summaries
