#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

from flim.configs.analysis import DEFAULT_DEVICE
import flim.tools.autoencoder as ae_tools
from flim.plugin import AbstractPlugin
from flim.plugin import plugin


@plugin(plugintype="Analysis")
class AEAugment(AbstractPlugin):
    def __init__(self, name="Autoencoder: Augment Data", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.modelfile = self.params["modelfile"]
        self.device = self.params["device"]
        self.sets = self.params["sets"]
        self.add_noise = self.params["add_noise"]
        self.snr_db = self.params["snr_db"]

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_mapped_parameters(self):
        parallel_params = []
        files = self.params["modelfile"]
        if not isinstance(files, list):
            files = [files]
        for mf in files:
            param = self.params.copy()
            param["modelfile"] = [mf]
            parallel_params.append(param)
        return parallel_params

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "modelfile": "",
                "device": DEFAULT_DEVICE,
                "sets": 1,
                "add_noise": True,
                "snr_db": 0.0,  # 0.0 < noise < 1.0
            }
        )
        return params

    def output_definition(self):
        return {"Table: Simulated": None}

    def execute(self):
        return self.run_tool(ae_tools.AEAugment, list(self.input.values())[0])
