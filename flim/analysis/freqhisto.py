#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
from flim.plugin import plugin

default_linestyles = ["-", "--", ":", "-."]


@plugin(plugintype="Plot")
class FreqHisto(AbstractPlugin):
    def __init__(self, name="Frequency Histogram", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params["bins"] = 30
        params["density"] = False
        params["cumulative"] = False
        params["histtype"] = "step"  # 'bar', 'barstacked', 'step', 'stepfilled'
        params["stacked"] = False
        params["datatable"] = False
        params["featuresettings"] = {
            "trp t1": [0, 8000, 81, ["Treatment"]],
            "trp t2": [0, 8000, 81, ["Treatment"]],
            "trp tm": [0, 4000, 81, ["Treatment"]],
            "trp a1[%]": [0, 100, 21, ["Treatment"]],
            "trp a2[%]": [0, 100, 21, ["Treatment"]],
            "trp a1[%]/a2[%]": [0, 2, 81, ["Treatment"]],
            "trp E%1": [0, 100, 21, ["Treatment"]],
            "trp E%2": [0, 100, 21, ["Treatment"]],
            "trp E%3": [0, 100, 21, ["Treatment"]],
            "trp r1": [0, 100, 21, ["Treatment"]],
            "trp r2": [0, 100, 21, ["Treatment"]],
            "trp r3": [0, 100, 21, ["Treatment"]],
            "trp chi": [0, 4.7, 81, ["Treatment"]],
            "trp photons": [0, 160, 81, ["Treatment"]],
            "NAD(P)H t1": [0, 800, 81, ["Treatment"]],
            "NAD(P)H t2": [0, 400, 81, ["Treatment"]],
            "NAD(P)H tm": [0, 2000, 81, ["Treatment"]],
            "NAD(P)H photons": [0, 2000, 81, ["Treatment"]],
            "NAD(P)H a2[%]": [0, 100, 51, ["Treatment"]],
            #                    'NAD(P)H %': [0,99,34,['Treatment']],
            "NADPH %": [0, 99, 34, ["Treatment"]],
            "NADH %": [0, 100, 51, ["Treatment"]],
            "NAD(P)H/NADH": [0, 3, 31, ["Treatment"]],
            "NAD(P)H chi": [0.7, 4.7, 81, ["Treatment"]],
            "FAD t1": [0, 4000, 81, ["Treatment"]],
            "FAD t2": [1000, 7000, 81, ["Treatment"]],
            "FAD tm": [0, 4000, 81, ["Treatment"]],
            "FAD a1[%]": [0, 100, 51, ["Treatment"]],
            "FAD a2[%]": [0, 100, 21, ["Treatment"]],
            "FAD a1[%]/a2[%]": [0, 16, 81, ["Treatment"]],
            "FAD chi": [0.7, 4.7, 81, ["Treatment"]],
            "FAD photons": [0, 800, 81, ["Treatment"]],
            "FLIRR": [0, 2.4, 81, ["Treatment"]],
            "NADPH a2/FAD a1": [0, 10, 101, ["Treatment"]],
        }
        return params

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        return self.run_tool(plot.FrequencyHistogram, list(self.input.values())[0])
