#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/17/20 10:44 AM
# @Author: Jiaxin_Zhang

import itertools

from flim.configs.analysis import DEFAULT_DEVICE
import matplotlib.figure
import pandas as pd
import flim.tools.autoencoder as ae_tools
from flim.plugin import AbstractPlugin, plugin


@plugin(plugintype="Analysis")
class AETraining(AbstractPlugin):
    def __init__(self, name="Autoencoder: Train", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.epoches = self.params["epoches"]
        self.timeseries = self.params["timeseries"]
        self.working_dir = self.params["working_dir"]
        self.modelfile = self.params["modelfile"]
        self.lr = self.params["learning_rate"]
        self.wd = self.params["weight_decay"]
        self.bs = self.params["batch_size"]
        self.device = self.params["device"]
        self.rescale = self.params["rescale"]
        self.checkpoint_interval = self.params["checkpoint_interval"]

    def get_description(self):
        descr = (
            "Train and save a new autoencoder model using selectable input features. "
            + "Training and validation datasets are randomly split based on the"
            " specified Data Grouping. "
            + "Device: auto uses a CUDA GPU or the Apple GPU (mps) if available,"
            " otherwise the CPU."
        )
        return descr

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_mapped_parameters(self):
        parallel_params = []
        sizes = self.params["batch_size"]
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        combinations = list(itertools.product(sizes, rates, decays))
        for size, rate, decay in combinations:
            param = self.params.copy()
            param["batch_size"] = [size]
            param["learning_rate"] = [rate]
            param["weight_decay"] = [decay]
            parallel_params.append(param)
        return parallel_params

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "epoches": 20,
                "learning_rate": [1e-4],
                "weight_decay": [1e-8],
                "batch_size": [128],
                "timeseries": "Treatment",
                "modelfile": "AEModel",
                "grouping": ["FOV", "Cell"],
                "features": [
                    "FAD a1",
                    "FAD a2",
                    "FAD t1",
                    "FAD t2",
                    "FAD photons",
                    "NAD(P)H a1",
                    "NAD(P)H a2",
                    "NAD(P)H t1",
                    "NAD(P)H t2",
                    "NAD(P)H photons",
                ],
                "model": "AE Dimensionality Reduction 2-10",
                "device": DEFAULT_DEVICE,
                "rescale": False,
                "create_plots": True,
                "train_size": 0.7,  # 0.0 < train_size < 1.0
                "checkpoint_interval": 20,
            }
        )
        return params

    def output_definition(self):
        output = {}
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        sizes = self.params["batch_size"]
        combinations = list(itertools.product(sizes, rates, decays))
        for size, rate, decay in combinations:
            output.update(
                {
                    f"Table: AE Loss-{size}-{rate}-{decay}": pd.DataFrame,
                    f"Table: AE Decoded-{size}-{rate}-{decay}": pd.DataFrame,
                    f"Table: AE Encoded-{size}-{rate}-{decay}": pd.DataFrame,
                    "Model File": str,
                }
            )
            if self.params["create_plots"]:
                output.update(
                    {
                        f"Plot: AE Loss-{size}-{rate}-{decay}": matplotlib.figure.Figure,
                    }
                )
        return output

    def execute(self):
        return self.run_tool(ae_tools.AETraining, list(self.input.values())[0])
