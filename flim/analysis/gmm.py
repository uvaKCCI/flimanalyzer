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

from flim.plugin import plugin, AbstractPlugin
import flim.resources
from flim.gui.dialogs import BasicAnalysisConfigDlg

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
        autosave=True,
        working_dir="",
    ):
        self.method = method
        self.n_components = n_components
        self.covar_type = covar_type
        super().__init__(
            parent,
            title,
            input=input,
            enablegrouping=False,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=0,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

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
        source = files(flim.resources).joinpath("kmeans.png")
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
        dlg = GaussianMixedModelConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            method=self.params["method"],
            n_components=self.params["n_components"],
            covar_type=self.params["covar_type"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def execute(self):
        original = list(self.input.values())[0]
        data = original[self.params["features"]]
        data = data.dropna(how="any", axis=0).reset_index()
        oldidx = data["index"]
        features = self.params["features"]
        n_features = len(features)
        method = self.params["method"]
        if n_features == 1:
            # reshape 1d array
            data_no_class = data[features].values.reshape((-1, 1))
        else:
            data_no_class = data[features].values

        cat_cols = list(original.select_dtypes(["category"]).columns.values)
        cat_df = original.iloc[
            oldidx
        ].reset_index()  # match cat_df index w/ index of used prediction data
        cat_df = cat_df[cat_cols].copy()

        n_components = self.params["n_components"]
        covar_type = self.params["covar_type"]

        models = [
            GaussianMixture(n, covariance_type=covar_type, random_state=0).fit(
                data[features]
            )
            for n in range(1, n_components + 1)
        ]
        bics = [m.bic(data[features]) for m in models]
        aics = [m.aic(data[features]) for m in models]
        components_df = pd.DataFrame(
            {"Component": list(range(1, n_components + 1)), "BIC": bics, "AIC": aics}
        )
        components_df["Component"] = components_df["Component"].astype("category")

        if method == "EM":
            gmm_model = GaussianMixture(
                n_components=n_components, covariance_type=covar_type
            )
        elif method == "Variational Bayesian":
            gmm_model = BayesianGaussianMixture(
                n_components=n_components,  # max number of components
                covariance_type=covar_type,
                weight_concentration_prior=1e-3,  # Low value encourages sparse weights
                # random_state=42,
            )
        else:
            return None

        gmm_model.fit(data[features])

        weights = gmm_model.weights_
        logging.debug(f"type(weights)={type(weights)}, weights={weights}")

        covariances = (
            gmm_model.covariances_
        )  # shape(n_components, n_features, n_features)
        covariances = full_matrix(covariances, covar_type, n_components, n_features)
        colindex = [f"{f}" for f in features]
        rowindex = [f"{f}" for f in features]
        logging.debug(
            f"full covariances.shape={covariances.shape}, covariances={covariances}"
        )
        covar_dfs = [
            pd.DataFrame(covariance, index=rowindex, columns=colindex)
            for i, covariance in enumerate(covariances)
        ]

        probs = gmm_model.predict_proba(data[features])
        probs_df = pd.DataFrame(
            probs,
            columns=[f"GMM Prob Component {i}" for i in range(1, n_components + 1)],
        )

        predictions = gmm_model.predict(data[features])
        predict_df = pd.DataFrame(data, columns=features)
        labelcol = f"GMM {covar_type}"  # self.params["cluster_prefix"]
        predict_df[labelcol] = [f"{labelcol} {str(l+1)}" for l in predictions]
        predict_df[labelcol] = predict_df[labelcol].astype("category")
        logging.debug(f"predict_df={predict_df}")
        predict_df = pd.concat([cat_df, predict_df, probs_df], axis=1)
        neworder = [
            c for c in list(predict_df.select_dtypes(["category"]).columns.values)
        ]
        noncategories = [c for c in predict_df.columns.values if c not in neworder]
        neworder.extend(noncategories)
        predict_df = predict_df[neworder]
        results = {
            f"Table: GMM {covar_type}, Covariance, component {i+1}": covar
            for i, covar in enumerate(covar_dfs)
        }
        results[f"Table: GMM {covar_type}, Feature Clustering"] = predict_df
        results[f"Table: GMM {covar_type}, Component Information Criteria"] = (
            components_df
        )
        return results
