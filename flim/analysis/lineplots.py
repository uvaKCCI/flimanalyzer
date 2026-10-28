#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import pandas as pd
import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter
import seaborn as sns
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
from flim import utils
from flim.plugin import plugin
from flim.tools.plot import ci_to_errorbar  # noqa: F401


@plugin(plugintype="Plot")
class LinePlot(AbstractPlugin):
    def __init__(self, name="Line Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("lineplot.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "display": ["auto", "auto"],
                "grouping": [],
                "features": [],
                "ordering": {},
                "ci": 95,  # 68, #'sd',
                "err_style": "bars",  #'band'
                "markers": True,
                "x": "",
                "hue": "",
                "style": "",
                "col": "",
            }
        )
        return params

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

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        return self.run_tool(plot.LinePlot, list(self.input.values())[0])

