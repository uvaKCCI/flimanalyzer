#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.statistics as statistics
from flim.plugin import AbstractPlugin
import pandas as pd
from flim.plugin import plugin

calpha = {0.10: 1.22, 0.05: 1.36, 0.025: 1.48, 0.01: 1.63, 0.005: 1.73, 0.001: 1.95}


@plugin(plugintype="Analysis")
class KSStats(AbstractPlugin):
    def __init__(self, name="KS-Statistics", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "comparison": "Treatment",
                "alpha": 0.05,
            }
        )
        return params

    def output_definition(self):
        return {"Table: KS-Stats": pd.DataFrame}

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        return self.run_tool(statistics.KSStats, list(self.input.values())[0])
