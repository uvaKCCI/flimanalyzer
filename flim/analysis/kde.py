#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import math
from flim import utils
import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.figure
import seaborn as sns
import numpy as np
import pandas as pd
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
from flim.plugin import plugin, ALL_FEATURES


default_linestyles = ["-", "--", ":", "-."]


@plugin(plugintype="Plot")
class KDE(AbstractPlugin):
    def __init__(self, name="KDE", **kwargs):
        # classifier=None, importancehisto=True, n_estimators=100, test_size=0.3, **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("kde.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return ["any"]

    def output_definition(self):
        data = list(self.input.values())[0]
        features = self.params["features"]
        if features == ALL_FEATURES and isinstance(data, pd.DataFrame):
            features = list(data.select_dtypes(np.number).columns.values)
        return_type = {"Table: KDE {header}": pd.DataFrame for feature in features}
        if self.params["single_plot"]:
            return_type["Plot: KDE"] = matplotlib.figure.Figure
        else:
            return_type.update(
                {
                    f"Plot: KDE {feature}": matplotlib.figure.Figure
                    for feature in features
                }
            )
        return return_type

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "single_plot": False,
                "col_wrap": 5,  # auto
                "return_plot": True,
            }
        )
        return params

    def get_mapped_parameters(self):
        if self.params["single_plot"]:
            return super().get_mapped_parameters()
        else:
            parallel_params = []
            for i, f in enumerate(self.params["features"]):
                pair_param = self.params.copy()
                pair_param["features"] = [f]
                parallel_params.append(pair_param)
            return parallel_params

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]

        dlg_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), self.params
        )
        dlg_params.update(
            dict(
                title=f"Configuration: {self.name}",
                input=self.input,
                selectedgrouping=selgrouping,
                selectedfeatures=selfeatures,
            )
        )

        dlg = BasicAnalysisConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def execute(self):
        return self.run_tool(plot.KDE, list(self.input.values())[0])

