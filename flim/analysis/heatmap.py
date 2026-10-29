#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 1/10/21 5:16 PM
# @Author: Jiaxin_Zhang

import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.plugin import plugin


@plugin(plugintype="Plot")
class Heatmap(AbstractPlugin):
    def __init__(self, name="Heatmap", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def output_definition(self):
        return {"Plot: Heatmap": None}

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({"corr_type": "pearson", "numbers": False})
        return params

    def execute(self):
        return self.run_tool(plot.Heatmap, list(self.input.values())[0])
