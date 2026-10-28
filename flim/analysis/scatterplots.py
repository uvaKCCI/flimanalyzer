#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 16:11:28 2020

@author: khs3z
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import pandas as pd
import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import matplotlib
import matplotlib.pyplot as plt
import itertools
from importlib_resources import files
import flim.resources
from flim import utils
from flim.plugin import plugin


@plugin(plugintype="Plot")
class ScatterPlot(AbstractPlugin):
    def __init__(self, name="Scatter Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("scatter.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

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
        combs = itertools.combinations(self.params["features"], 2)
        for pair in combs:
            pair_param = self.params.copy()
            pair_param["features"] = [f for f in pair]
            parallel_params.append(pair_param)
        return parallel_params

    def output_definition(self):
        combs = itertools.combinations(self.params["features"], 2)
        return {f"Scatter: {c}": matplotlib.figure.Figure for c in sorted(combs)}

    def execute(self):
        return self.run_tool(plot.ScatterPlot, list(self.input.values())[0])

