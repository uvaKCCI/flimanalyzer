#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import pandas as pd

import flim.tools.statistics as statistics
from flim.plugin import AbstractPlugin, plugin


@plugin(plugintype="Analysis")
class SeriesAnalyzer(AbstractPlugin):
    def __init__(self, name="Series Analysis", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "series_min": True,
                "series_max": True,
                "series_range": True,
                "series_mean": False,
                "series_median": False,
                "delta": True,
                "delta_min": True,
                "delta_max": True,
                "delta_sum": True,
                "delta_cum": True,
                "delta_norm": True,
                "merge_input": False,
            }
        )
        return params

    def output_definition(self):
        return {"Table: Series Analysis": pd.DataFrame}

    def execute(self):
        return self.run_tool(statistics.SeriesAnalysis, list(self.input.values())[0])
