#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 03/30/21 10:44 AM
# @Author: Jiaxin_Zhang


import flim.tools.autoencoder as ae_tools
from flim.plugin import plugin, AbstractPlugin
from flim.configs.analysis import DEFAULT_DEVICE


@plugin(plugintype="Analysis")
class RunAE(AbstractPlugin):
    def __init__(self, name="Autoencoder: Run", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.modelfile = self.params["modelfile"]
        self.device = self.params["device"]

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "modelfile": "",
                "device": DEFAULT_DEVICE,
            }
        )
        return params

    def output_definition(self):
        return {"Table: Reconstructed": None, "Table: Features": None}

    def execute(self):
        return self.run_tool(ae_tools.RunAE, list(self.input.values())[0])
