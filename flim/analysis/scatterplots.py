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

import flim.tools.plot as plot
from flim.plugin import AbstractPlugin
import matplotlib
import itertools
from flim.plugin import plugin


@plugin(plugintype="Plot")
class ScatterPlot(AbstractPlugin):
    def __init__(self, name="Scatter Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

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
