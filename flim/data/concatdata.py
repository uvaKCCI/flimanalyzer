#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import pandas as pd
from flim.plugin import plugin
import flim.tools.data as tools
from flim.plugin import AbstractPlugin


@plugin(plugintype="Data")
class Concatenator(AbstractPlugin):
    def __init__(self, name="Concat Data", **kwargs):
        AbstractPlugin.__init__(self, name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "input": {},
                "type": False,
                "numbers_only": False,
                "source_suffix": True,
            }
        )
        return params

    def input_definition(self):
        return [pd.DataFrame, pd.DataFrame]

    def output_definition(self):
        return {"Table: Concatenated": pd.DataFrame}

    def execute(self):
        return self.run_tool(tools.Concat, dict(self.input))
