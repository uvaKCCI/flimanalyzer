#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

import pandas as pd
import flim.tools.statistics as statistics
from flim.plugin import AbstractPlugin
from flim.plugin import plugin


@plugin(plugintype="Analysis")
class RelativeChange(AbstractPlugin):
    def __init__(self, name="Relative Change", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "method": "mean",  # 'median'
                "reference_group": "Treatment",
                "reference_value": "Ctrl",
            }
        )
        return params

    def output_definition(self):
        return {"Table: Relative Change": pd.DataFrame}

    def execute(self):
        return self.run_tool(statistics.RelativeChange, list(self.input.values())[0])
