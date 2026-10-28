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
from flim.plugin import plugin


@plugin(plugintype="Plot")
class PairPlot(AbstractPlugin):
    def __init__(self, name="Pair Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "x_vars": [],  # "KDE"
                "y_vars": [],  # "KDE"
                "diag_kind": "Histogram",  # "KDE"
                "corner": False,
                "hist_bins": 20,
                # scatter panels: "all" measurements or a random "sample" of `samples`
                # (the same on every run); the diagonals always use all measurements
                "plotting": "all",
                "samples": 20000,
                "random_seed": 0,
            }
        )
        return params

    def output_definition(self):
        return {f"Pair Plot: {self.params['grouping']}": matplotlib.figure.Figure}

    def execute(self):
        return self.run_tool(plot.PairPlot, list(self.input.values())[0])
