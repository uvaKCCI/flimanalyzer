#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
import matplotlib
import matplotlib.figure
import numpy as np
import pandas as pd
from flim.plugin import plugin, ALL_FEATURES

default_linestyles = ["-", "--", ":", "-."]


@plugin(plugintype="Plot")
class KDE(AbstractPlugin):
    def __init__(self, name="KDE", **kwargs):
        # classifier=None, importancehisto=True, n_estimators=100, test_size=0.3, **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

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

    def execute(self):
        return self.run_tool(plot.KDE, list(self.input.values())[0])
