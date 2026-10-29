#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.plot as plot
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
import matplotlib.figure


from flim.tools.plot import grouped_meanbarplot  # noqa: F401  (used by flirr)


@plugin(plugintype="Plot")
class BarPlot(AbstractPlugin):
    def __init__(self, name="Bar Plot", **kwargs):
        super().__init__(name=name, **kwargs)

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
                "orientation": "vertical",  # 'horizontal'
                "bar_type": "single",  # 'stacked', '100% stacked'
                "dropna": True,
                "error_bar": "+/-",  # '+', 'None'
                "error_type": "std",  # 's.e.m'
                "legend": True,
            }
        )
        return params

    def output_definition(self):
        if self.params["bar_type"] == "single":
            # separate plot for each feature
            return {
                f"Plot: {f}": matplotlib.figure.Figure for f in self.params["features"]
            }
        else:
            # one plot stacked with all features
            return {"Plot": matplotlib.figure.Figure}

    def get_mapped_parameters(self):
        if self.params["bar_type"] == "single":
            parallel_params = []
            for f in self.params["features"]:
                pair_param = self.params.copy()
                pair_param["features"] = [f]
                parallel_params.append(pair_param)
            return parallel_params
        else:
            # stacked plots process all features at once
            return [self.params]

    def execute(self):
        return self.run_tool(plot.BarPlot, list(self.input.values())[0])
