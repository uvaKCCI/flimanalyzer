#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import pandas as pd
from flim.plugin import AbstractPlugin
import flim.tools.data as tools
from flim.plugin import plugin


@plugin(plugintype="Data")
class Merger(AbstractPlugin):
    def __init__(self, name="Merge", **kwargs):
        AbstractPlugin.__init__(
            self, name=name, **kwargs
        )  # categories={}, default='unassigned', **kwargs)

    def get_description(self):
        return (
            "Merges two data tables based on shared index. "
            + "The index is determined using category column headers found in both"
            " tables."
        )

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "how": "",
                "left_index": [],
                "right_index": [],
                #'input': {},
            }
        )
        return params

    def input_definition(self):
        return [pd.DataFrame, pd.DataFrame]

    def output_definition(self):
        return {"Table: Merged": pd.DataFrame}

    def execute(self):
        return self.run_tool(tools.Merge, *list(self.input.values())[:2])
