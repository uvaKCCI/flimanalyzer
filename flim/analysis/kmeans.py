#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 03/30/21 10:44 AM
# @Author: Jiaxin_Zhang

import logging
import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.autograd import Variable
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files, as_file

from flim.plugin import plugin, AbstractPlugin
import flim.resources
from flim.gui.dialogs import BasicAnalysisConfigDlg

ALGO_OPTIONS = ["auto", "full", "elkan"]
INIT_OPTIONS = ["k-means++", "random"]
TOLERANCE_OPTONS = ["%.1e" % (10.0 ** (-b)) for b in range(2, 6)]


class KMeansClusteringConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        n_clusters=2,
        cluster_prefix="Cluster",
        init="k-means++",
        algorithm="auto",
        n_init=4,
        max_iter=300,
        tolerance=1e-4,
        autosave=True,
        working_dir="",
    ):
        self.n_clusters = n_clusters
        self.cluster_prefix = cluster_prefix
        self.init = init
        self.max_iter = max_iter
        self.n_init = n_init
        self.tolerance = tolerance
        self.algorithm = algorithm
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

        self.n_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, initial=self.n_clusters, min=2, max=20
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Number of Clusters"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.n_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.init_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.init,
            choices=INIT_OPTIONS,
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Initialization"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.init_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.algo_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.algorithm,
            choices=ALGO_OPTIONS,
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Algorithm"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.algo_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.n_init_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, initial=self.n_init, min=1, max=50
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Runs"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.n_init_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.miter_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, initial=self.max_iter, min=100, max=1000
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Max Iterations"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.miter_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        self.tol_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value="%.1e" % self.tolerance,
            choices=TOLERANCE_OPTONS,
        )
        option_sizer.Add(
            wx.StaticText(self.panel, label="Tolerance"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        option_sizer.Add(
            self.tol_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [option_sizer]

    def OnBrowse(self, event):
        fpath = self.modelfiletxt.GetLabel()
        _, fname = os.path.split(fpath)
        with wx.FileDialog(self, "Model File", style=wx.FD_OPEN) as fileDialog:
            fileDialog.SetPath(fpath)
            fileDialog.SetFilename(fname)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.modelfiletxt.SetLabel(fname)

    def _get_selected(self):
        params = super()._get_selected()
        params["cluster_prefix"] = "Cluster"  # self.prefix_editor.GetValue()
        params["n_clusters"] = self.n_spinner.GetValue()
        params["init"] = self.init_combobox.GetValue()
        params["algorithm"] = self.algo_combobox.GetValue()
        params["n_init"] = self.n_init_spinner.GetValue()
        params["max_iter"] = self.miter_spinner.GetValue()
        params["tolerance"] = float(self.tol_combobox.GetValue())
        return params


@plugin(plugintype="Analysis")
class KMeansClustering(AbstractPlugin):
    def __init__(self, name="K-Means", **kwargs):
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
                "n_clusters": 2,
                "cluster_prefix": "Cluster",
                "init": "k-means++",
                "algorithm": "auto",
                "n_init": 4,
                "max_iter": 300,
                "tolerance": 1e-4,
            }
        )
        return params

    def output_definition(self):
        return {"Table: K-Means": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = KMeansClusteringConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            n_clusters=self.params["n_clusters"],
            cluster_prefix=self.params["cluster_prefix"],
            init=self.params["init"],
            algorithm=self.params["algorithm"],
            n_init=self.params["n_init"],
            max_iter=self.params["max_iter"],
            tolerance=self.params["tolerance"],
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
        if len(features) == 1:
            # reshape 1d array
            data_no_class = data[features].values.reshape((-1, 1))
        else:
            data_no_class = data[features].values
        scaler = StandardScaler()
        scaler.fit(data_no_class)
        standard_data = scaler.transform(data_no_class)
        kmeans = KMeans(
            n_clusters=self.params["n_clusters"],
            init=self.params["init"],
            algorithm=self.params["algorithm"],
            n_init=self.params["n_init"],
            max_iter=self.params["max_iter"],
            tol=self.params["tolerance"],
            random_state=0,
        )
        predict = kmeans.fit(standard_data)
        cat_cols = list(original.select_dtypes(["category"]).columns.values)
        cat_df = original.iloc[
            oldidx
        ].reset_index()  # match cat_df index w/ index of used prediction data
        cat_df = cat_df[cat_cols].copy()

        predict_df = pd.DataFrame(data, columns=features)
        labelcol = self.params["cluster_prefix"]
        predict_df[labelcol] = [f"{labelcol} {l + 1}" for l in predict.labels_]
        predict_df[labelcol] = predict_df[labelcol].astype("category")
        predict_df = pd.concat([cat_df, predict_df], axis=1)
        neworder = [
            c for c in list(predict_df.select_dtypes(["category"]).columns.values)
        ]
        noncategories = [c for c in predict_df.columns.values if c not in neworder]
        neworder.extend(noncategories)
        predict_df = predict_df[neworder]

        """
        estimator = make_pipeline(StandardScaler(), kmeans).fit(data)
        fit_time = time() - t0
        results = [name, fit_time, estimator[-1].inertia_]
        
        # Define the metrics which require only the true labels and estimator
        # labels
        clustering_metrics = [
            metrics.homogeneity_score,
            metrics.completeness_score,
            metrics.v_measure_score,
            metrics.adjusted_rand_score,
            metrics.adjusted_mutual_info_score,
        ]
        results += [m(labels, estimator[-1].labels_) for m in clustering_metrics]
        # The silhouette score requires the full dataset
        results += [
            metrics.silhouette_score(data, estimator[-1].labels_, metric="euclidean", sample_size=300,)
        ]
        print (results)
        """
        return {"Table: K-Means": predict_df}
