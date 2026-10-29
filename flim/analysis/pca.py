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
class PCAnalysis(AbstractPlugin):
    def __init__(self, name="PCA", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_description(self):
        return (
            "Specifiy PCA components to retain:\n\tleave empty:   retain all PCA"
            " components.\n\t0.0 < n < 1.0 (float):   retain PCA components that"
            " explain specified fraction of observed variance.\n\t1 <= n <= # features"
            " (integer):   retain first n PCA components."
        )

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "keeporig": False,
                "keepstd": True,
                "explainedhisto": False,
                "n_components": 0.999,
            }
        )
        return params

    def output_definition(self):
        if self.params["explainedhisto"]:
            return {
                "Table: PCA Components": None,
                "Table: PCA explained": None,
                "Plot: PCA Explained": None,
            }
        else:
            return {"Table: PCA Components": None, "Table: PCA explained": None}

    def execute(self):
        return self.run_tool(ml.PCAnalysis, list(self.input.values())[0])
