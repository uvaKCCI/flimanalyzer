#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.ml as ml
from flim.plugin import plugin
from flim.plugin import AbstractPlugin


@plugin(plugintype="Analysis")
class Categorizer(AbstractPlugin):
    def __init__(self, name="Categorize Data", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "name": "New Cat",
                "categories": [
                    {
                        "value": "negative",
                        "criteria": {
                            "feature": "FLIRR",
                            "min": -100000.0,
                            "max": -0.5,
                        },
                    },
                    {
                        "value": "neutral",
                        "criteria": {
                            "feature": "FLIRR",
                            "min": -0.5,
                            "max": 0.5,
                        },
                    },
                    {
                        "value": "positive",
                        "criteria": {
                            "feature": "FLIRR",
                            "min": 0.5,
                            "max": 100000,
                        },
                    },
                ],
                "default": "unassigned",
                "merge_input": True,
            }
        )
        return params

    def execute(self):
        return self.run_tool(ml.Categorizer, list(self.input.values())[0])
