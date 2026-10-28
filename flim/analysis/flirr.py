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
class FLIRRPlot(AbstractPlugin):
    def __init__(self, name="FLIRR Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return []

    def output_definition(self):
        return {f"FLIRR Plot: {self.params['gouping']}": matplotlib.figure.Figure}

    def execute(self):
        return self.run_tool(plot.FLIRRPlot, list(self.input.values())[0])
