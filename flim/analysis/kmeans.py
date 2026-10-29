#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 03/30/21 10:44 AM
# @Author: Jiaxin_Zhang

import pandas as pd

import flim.tools.ml as ml
from flim.plugin import plugin, AbstractPlugin

ALGO_OPTIONS = ["lloyd", "elkan"]
# names removed in scikit-learn 1.3, both meant "lloyd"
LEGACY_ALGOS = {"auto": "lloyd", "full": "lloyd"}
INIT_OPTIONS = ["k-means++", "random"]
TOLERANCE_OPTONS = ["%.1e" % (10.0 ** (-b)) for b in range(2, 6)]


@plugin(plugintype="Analysis")
class KMeansClustering(AbstractPlugin):
    def __init__(self, name="K-Means", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "n_clusters": 2,
                "cluster_prefix": "Cluster",
                "init": "k-means++",
                "algorithm": "lloyd",
                "n_init": 4,
                "max_iter": 300,
                "tolerance": 1e-4,
            }
        )
        return params

    def output_definition(self):
        return {"Table: K-Means": pd.DataFrame}

    def execute(self):
        return self.run_tool(ml.KMeansClustering, list(self.input.values())[0])
