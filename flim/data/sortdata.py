#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import wx.grid
from wx.lib.masked import NumCtrl
import pandas as pd
from importlib_resources import files
from itertools import groupby
import numpy as np

from flim.core.filter import RangeFilter
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
from flim.gui.dicttablepanel import DictTable, ListTable
from flim.gui.datapanel import PandasTable
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.resources


@plugin(plugintype="Data")
class Sort(AbstractPlugin):
    def __init__(self, name="Sort", **kwargs):
        AbstractPlugin.__init__(
            self, name=name, **kwargs
        )  # categories={}, default='unassigned')

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("filter.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return []

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "ascending": True,
            }
        )
        return params

    def output_definition(self):
        return {"Table: Sorted": None}

    def run_configuration_dialog(self, parent, data_choices={}):
        selfeatures = self.params["features"]
        dlg = BasicAnalysisConfigDlg(
            parent,
            "Sort Data",
            input=self.input,
            enablegrouping=False,
            selectedfeatures=selfeatures,
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def execute(self):
        data = list(self.input.values())[0]
        selfeatures = self.params["features"]
        ascending = len(selfeatures) * [self.params["ascending"]]

        df = data.sort_values(by=selfeatures, ascending=ascending)

        results = {}
        results["Table: Sorted"] = df
        return results
