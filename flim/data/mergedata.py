#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources
from flim.plugin import plugin


class MergerConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input={},
        description=None,
        data_choices={},
        how="left",
        left_on=None,
        right_on=None,
        left_index=False,
        right_index=False,
        autosave=True,
        working_dir="",
    ):
        self.data_choices = data_choices
        self.how_choices = {
            "<< merge left": "left",
            "merge right >>": "right",
            "merge inner": "inner",
            "merge outer": "outer",
        }
        howvalues = list(self.how_choices.values())
        if how in howvalues:
            keypos = howvalues.index(how)
            self.how = list(self.how_choices.keys())[keypos]
        else:
            self.how = list(self.how_choices.keys())[0]
        dc = list(data_choices.keys())
        if left_on not in dc:
            self.left_on = dc[0]
        else:
            self.left_on = left_on
        if right_on not in dc:
            self.right_on = dc[1]
        else:
            self.right_on = right_on
        self.left_index = left_index
        self.right_index = right_index
        super().__init__(
            parent,
            title,
            input=input,
            description=description,
            data_choices=data_choices,
            enablefeatures=False,
            enablegrouping=False,
            optgridrows=2,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        fsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.left_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.left_on,
            choices=list(self.data_choices.keys()),
        )
        self.how_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.how,
            choices=list(self.how_choices.keys()),
        )
        self.right_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.right_on,
            choices=list(self.data_choices.keys()),
        )
        fsizer.Add(
            wx.StaticText(self.panel, label="Table 1"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        fsizer.Add(self.left_combobox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(self.how_combobox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        fsizer.Add(
            wx.StaticText(self.panel, label="Table 2"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        fsizer.Add(self.right_combobox, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        return [fsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["how"] = self.how_choices[self.how_combobox.GetValue()]
        params["left_index"] = []
        params["right_index"] = []
        params["input"] = {
            self.left_combobox.GetValue(): self.data_choices[
                self.left_combobox.GetValue()
            ],
            self.right_combobox.GetValue(): self.data_choices[
                self.right_combobox.GetValue()
            ],
        }
        return params


@plugin(plugintype="Data")
class Merger(AbstractPlugin):
    def __init__(self, name="Merge", **kwargs):
        AbstractPlugin.__init__(
            self, name=name, **kwargs
        )  # categories={}, default='unassigned', **kwargs)

    def get_description(self):
        return (
            "Merges two data tables based on shared index. "
            + "The index is determined using category column headers found in both"
            " tables."
        )

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("merge.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return []

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "how": "",
                "left_index": [],
                "right_index": [],
                #'input': {},
            }
        )
        return params

    def input_definition(self):
        return [pd.DataFrame, pd.DataFrame]

    def output_definition(self):
        return {"Table: Merged": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        input = self.params["input"]
        # left_on and right_on are str representing dataframe window titles
        if isinstance(input, dict) and len(input) > 0:
            left_on = list(input.keys())[0]
        else:
            left_on = ""
        if isinstance(input, dict) and len(input) > 1:
            right_on = list(input.keys())[1]
        else:
            right_on = left_on

        dlg = MergerConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            description=self.get_description(),
            data_choices=data_choices,
            left_on=left_on,
            right_on=right_on,
            how=self.params["how"],
            left_index=self.params["left_index"],
            right_index=self.params["right_index"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def execute(self):
        results = {}
        data = list(self.input.values())
        left = data[0]
        right = data[1]
        how = self.params["how"]
        left_on = [c for c in list(left.select_dtypes(["category"]).columns.values)]
        right_on = [c for c in list(right.select_dtypes(["category"]).columns.values)]
        on = list(set(left_on).intersection(set(right_on)))
        merged_df = pd.merge(left, right, how=how, on=on)
        merged_df[on] = merged_df[on].astype("category")
        neworder = [
            c for c in list(merged_df.select_dtypes(["category"]).columns.values)
        ]
        noncategories = [c for c in merged_df.columns.values if c not in neworder]
        neworder.extend(noncategories)
        merged_df = merged_df[neworder]
        results["Table: Merged"] = merged_df
        return results
