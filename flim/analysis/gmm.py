import logging
import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.autograd import Variable
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture, BayesianGaussianMixture
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files, as_file

import flim.tools.ml as ml
from flim.plugin import plugin, AbstractPlugin
import flim.resources
from flim.gui.dialogs import BasicAnalysisConfigDlg
from flim import utils

COVAR_OPTIONS = ["spherical", "tied", "diag", "full"]
METHOD_OPTIONS = ["EM", "Variational Bayesian"]


def full_matrix(values, covar_type, n_components, n_features):
    if (
        covar_type == "full"
    ):  # each component has it's own unconstrained covariance matrix
        return values
    elif covar_type == "tied":  # all components share single common covariance matrrix
        return np.array([values for _ in range(n_components)])
    elif covar_type == "diag":  # for each component the covar is axis-aligned
        return np.array([np.diag(values[i]) for i in range(n_components)])
    elif (
        covar_type == "spherical"
    ):  # each component is a spherical Gaussian with single variance
        return np.array(
            [np.diag(np.full(n_features, values[i])) for i in range(n_components)]
        )
    else:
        return None


class GaussianMixedModelConfigDlg(BasicAnalysisConfigDlg):
    __base_params = {
        "title": "",
        "input": None,
        "selectedgrouping": ["None"],
        "selectedfeatures": "All",
        "method": "EM",
        "n_components": 2,
        "covar_type": "full",
        "saveconfig": True,
        "config_file": "",
        "autosave": True,
        "working_dir": "",
    }

    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        method="EM",
        n_components=2,
        covar_type="full",
        saveconfig=True,
        config_file="",
        autosave=True,
        working_dir="",
        **kwargs,
    ):
        basic_params = {
            "title": title,
            "input": input,
            "enablegrouping": False,
            "selectedgrouping": selectedgrouping,
            "selectedfeatures": selectedfeatures,
            "optgridrows": 0,
            "optgridcols": 1,
            "saveconfig": saveconfig,
            "config_file": config_file,
            "autosave": autosave,
            "working_dir": working_dir,
        }
        basic_params.update(**kwargs)

        self.method = method
        self.n_components = n_components
        self.covar_type = covar_type

        init_params = utils.update_left(
            BasicAnalysisConfigDlg.get_base_params(), basic_params
        )
        super().__init__(parent, **init_params)

    def get_option_panels(self):
        option_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.method_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.method,
            choices=METHOD_OPTIONS,
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Method"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.method_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.n_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, initial=self.n_components, min=2, max=20
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Number of Components"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.n_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.covar_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.covar_type,
            choices=COVAR_OPTIONS,
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Covariance Type"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.covar_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [option_sizer]

    @classmethod
    def get_base_params(cls):
        return cls.__base_params

    def _get_selected(self):
        params = super()._get_selected()
        params["method"] = self.method_combobox.GetValue()
        params["n_components"] = self.n_spinner.GetValue()
        params["covar_type"] = self.covar_combobox.GetValue()
        return params


@plugin(plugintype="Analysis")
class GaussianMixedModel(AbstractPlugin):
    def __init__(self, name="Gaussian Mixed Model", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("gmm.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "method": "EM",
                "n_components": 2,
                "covar_type": "full",
            }
        )
        return params

    def output_definition(self):
        return {"Table: Gaussian Mixed Model BIC": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        merged_base = dict(BasicAnalysisConfigDlg.get_base_params())
        merged_base.update(GaussianMixedModelConfigDlg.get_base_params())
        dlg_params = utils.update_left(merged_base, self.params)
        dlg_params.update(
            dict(
                title=f"Configuration: {self.name}",
                input=self.input,
                selectedgrouping=self.params["grouping"],
                selectedfeatures=self.params["features"],
            )
        )

        dlg = GaussianMixedModelConfigDlg(parent, **dlg_params)
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def execute(self):
        return self.run_tool(ml.GaussianMixedModel, list(self.input.values())[0])
