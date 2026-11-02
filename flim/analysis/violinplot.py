#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 16:11:37 2020

@author: khs3z
"""

import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.plugin import plugin


@plugin(plugintype="Plot")
class ViolinPlot(AbstractPlugin):
    def __init__(self, name="Violin Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        return self.run_tool(plot.ViolinPlot, list(self.input.values())[0])
