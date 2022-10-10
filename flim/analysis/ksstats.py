#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
from flim.plugin import AbstractPlugin
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
import pandas as pd
import numpy as np
from scipy import stats
from itertools import combinations
from flim.plugin import plugin


calpha = {0.10: 1.22, 0.05: 1.36, 0.025: 1.48, 0.01: 1.63, 0.005: 1.73, 0.001: 1.95}


class KSStatsConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        comparison="Treatment",
        alpha=0.05,
        autosave=True,
        working_dir="",
    ):
        self.comparison = comparison
        self.alpha = alpha
        super().__init__(
            parent,
            title,
            input=input,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=1,
            optgridcols=0,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        data = list(self.input.values())[0]
        osizer = wx.BoxSizer(wx.HORIZONTAL)
        comparison_opts = [
            c for c in list(data.select_dtypes(["category"]).columns.values)
        ]
        sel_comparison = self.comparison
        if sel_comparison not in comparison_opts:
            sel_comparison = comparison_opts[0]
        self.comparison_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_comparison,
            choices=comparison_opts,
        )

        alpha_opts = [str(c) for c in calpha]
        sel_alpha = str(self.alpha)
        if sel_alpha not in alpha_opts:
            sel_alpha = alpha_opts[0]
        self.alpha_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_alpha,
            choices=alpha_opts,
        )

        osizer.Add(
            wx.StaticText(self.panel, label="Comparison "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.comparison_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            wx.StaticText(self.panel, label="alpha "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.alpha_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [osizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["comparison"] = self.comparison_combobox.GetValue()
        params["alpha"] = float(self.alpha_combobox.GetValue())
        return params


@plugin(plugintype="Analysis")
class KSStats(AbstractPlugin):
    def __init__(self, name="KS-Statistics", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_icon(self):
        source = files(flim.resources).joinpath("ks.png")
        return wx.Bitmap(str(source))

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "comparison": "Treatment",
                "alpha": 0.05,
            }
        )
        return params

    def output_definition(self):
        return {"Table: KS-Stats": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = KSStatsConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            comparison=self.params["comparison"],
            alpha=self.params["alpha"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def get_mapped_parameters(self):
        parallel_params = []
        for f in self.params["features"]:
            pair_param = self.params.copy()
            pair_param["features"] = [f]
            parallel_params.append(pair_param)
        return parallel_params

    def execute(self):
        data = list(self.input.values())[0]
        results = {}
        comparison = self.params["comparison"]
        alpha = self.params["alpha"]
        for header in sorted(self.params["features"]):
            logging.debug(f"Calculating ks-statistics for {str(header)}")
            result = self.feature_kststats(
                data,
                header,
                groups=self.params["grouping"],
                comparison=comparison,
                alpha=alpha,
            )
            results[f"KS-stats: {header}"] = result
        return results

    def feature_kststats(
        self, data, column, groups=[], comparison="", alpha=0.05, dropna=True
    ):
        logging.debug(f"data.columns.values={data.columns.values}")
        if data is None or not column in data.columns.values:
            return None, None
        if len(groups) == 0:
            groupvals = [("none",)]
            cols = ["Grouping"]
        else:
            # set groups based on categories excluding the comparison category
            groups = [g for g in groups if g != comparison]
            groupvals = [name for name, _ in data.groupby(groups)]
            cols = [c for c in groups]
        dissimilar_label = f"dissimilar (<{alpha})"
        allcategories = [c for c in cols]
        allcategories.extend(
            [
                f"{comparison} 1",
                f"{comparison} 2",
                f"{comparison} 1 & 2",
                dissimilar_label,
            ]
        )
        cols.extend(
            [
                f"{comparison} 1",
                f"{comparison} 2",
                f"{comparison} 1 & 2",
                dissimilar_label,
                f"n ({comparison} 1)",
                f"n ({comparison} 2)",
                "p-values",
                "statistic",
                f"critical D ({alpha})",
            ]
        )
        rdata = []
        for groupval in groupvals:
            if len(groups) == 0:
                fdata = data
            else:
                # bracket group and grpupvals with backticks in case they contain whitespaces or special characters
                querystr = " and ".join(
                    [f'`{groups[i]}` == "{groupval[i]}"' for i in range(len(groupval))]
                )
                logging.debug(f"QUERY={querystr}, cols={data.columns.values}")
                fdata = data.query(querystr)
            if len(fdata) == 0:
                continue
            compgroups = {
                name: splitdata for name, splitdata in fdata.groupby(comparison)
            }
            comb = combinations(compgroups.keys(), 2)
            for c in comb:
                data1 = compgroups[c[0]][column]
                data2 = compgroups[c[1]][column]
                if len(data1) == 0 or len(data2) == 0:
                    continue
                ks = stats.ks_2samp(data1, data2)
                critical_d = calpha[alpha] * np.sqrt(
                    (len(data1) + len(data2)) / (len(data1) * len(data2))
                )
                row = [v for v in groupval]
                dissimilar = ks.statistic > critical_d and ks.pvalue < alpha
                row.extend(
                    [
                        c[0],
                        c[1],
                        f"{c[0]}-{c[1]}",
                        f"Yes" if dissimilar else "No",
                        len(data1),
                        len(data2),
                        ks.pvalue,
                        ks.statistic,
                        critical_d,
                    ]
                )
                rdata.append(row)
        ksdata = pd.DataFrame(rdata, columns=cols)
        for ckey in allcategories:
            ksdata[ckey] = ksdata[ckey].astype("category")
        return ksdata
