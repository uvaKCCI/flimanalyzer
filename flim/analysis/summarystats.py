#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

import numpy as np

import flim.tools.statistics as statistics
from flim.plugin import plugin
from flim.plugin import AbstractPlugin


def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)

    percentile_.__name__ = "%s percentile" % n
    return percentile_


@plugin(plugintype="Analysis")
class SummaryStats(AbstractPlugin):
    agg_functions = {
        "count": "count",
        "min": "min",
        "max": "max",
        "mean": "mean",
        "std": "std",
        "sem": "sem",
        "median": "median",
        "percentile(25)": percentile(25),
        "percentile(75)": percentile(75),
        "sum": "sum",
    }

    def __init__(self, name="Summarize", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_description(self):
        return (
            "Calculates counts, min, max, mean, median (50th percentile), 25th"
            " percentile, and 75th percentile, StDev, S.E.M, of grouped data."
        )

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "aggs": [n for n in self.agg_functions],
                "singledf": True,
                "flattenindex": True,
            }
        )
        return params

    def output_definition(self):
        if self.params["singledf"]:
            return {self._create_df_title(None): None}
        else:
            return {
                self._create_df_title(f): None for f in sorted(self.params["features"])
            }

    def _create_df_title(self, feature):
        if feature:
            return "Table: " + ": ".join(["Summary", feature.replace("\n", " ")])
        else:
            return "Table: Summary"

    def get_mapped_parameters(self):
        if not self.params["singledf"]:
            parallel_params = []
            for f in self.params["features"]:
                pair_param = self.params.copy()
                pair_param["features"] = [f]
                parallel_params.append(pair_param)
            return parallel_params
        else:
            # combine all features results in single df
            return [self.params]

    def execute(self):
        return self.run_tool(statistics.Summarize, list(self.input.values())[0])
