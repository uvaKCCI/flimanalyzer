#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.plugin import plugin
from flim.tools.plot import ci_to_errorbar  # noqa: F401


@plugin(plugintype="Plot")
class LinePlot(AbstractPlugin):
    def __init__(self, name="Line Plot", **kwargs):
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

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        return self.run_tool(plot.LinePlot, list(self.input.values())[0])
