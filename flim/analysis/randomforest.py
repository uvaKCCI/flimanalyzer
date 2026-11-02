#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import flim.tools.ml as ml
from flim.plugin import AbstractPlugin
from flim.plugin import plugin


@plugin(plugintype="Analysis")
class RandomForest(AbstractPlugin):
    def __init__(self, name="Random Forest", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "classifier": "",
                "n_estimators": 100,
                "test_size": 0.3,
                "importancehisto": True,
            }
        )
        return params

    def execute(self):
        return self.run_tool(ml.RandomForest, list(self.input.values())[0])
