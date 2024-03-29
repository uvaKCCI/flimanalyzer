#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import pandas as pd
from flim.plugin import plugin
from flim.plugin import AbstractPlugin
import matplotlib.figure
import matplotlib.pyplot as plt
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
import numpy as np
import matplotlib.ticker as mtick


def grouped_meanbarplot(
    data,
    feature,
    ax=None,
    title=None,
    bartype="single",
    categories=[],
    dropna=True,
    pivot_level=1,
    orientation="horizontal",
    error_bar="None",
    error_type="std",
    legend=True,
):
    stacked = not bartype == "single"
    # plt.rcParams.update({'figure.autolayout': True})
    a = all(e in data.columns.values for e in feature)
    if data is None or not a:
        return None
    if ax is None:
        fig, ax = plt.subplots()  # constrained_layout=True)
    else:
        fig = ax.get_figure()
    capsize = 6
    if categories is None:
        categories = []
    if len(categories) == 0:
        mean = pd.DataFrame(columns=feature)
        mean.loc[0] = data[feature].mean()
        if error_bar != "None":
            error = pd.DataFrame(columns=feature)
            if error_type == "std":
                error.loc[0] = data[feature].std()
            else:
                error.loc[0] = data[feature].sem()
        else:
            error = None
        if bartype == "100% stacked":
            # sum all columns, than devide means[all columns] by sum (row-by-row) and convert to percent
            sum = mean.abs().sum(axis=1)
            mean = mean.div(sum, axis=0) * 100.0
            if error is not None:
                error = error.div(sum, axis=0) * 100.0
        if error_bar == "+":
            error_vals = error.to_numpy().flatten()
            error = [[np.zeros_like(error_vals), error_vals]]
        ticklabels = ""  # mean.index.values
        if orientation == "horizontal":
            mean.plot.barh(
                ax=ax, xerr=error, stacked=stacked, capsize=capsize
            )  # , barsabove=True)#,figsize=fsize,width=0.8)
        else:
            mean.plot.bar(
                ax=ax, yerr=error, stacked=stacked, capsize=capsize
            )  # , barsabove=True)#,figsize=fsize,width=0.8)
    else:
        cols = [c for c in categories]
        cols.extend(feature)
        if dropna:
            groupeddata = (
                data[cols]
                .dropna(how="any", subset=feature)
                .groupby(categories, observed=True)
            )
        else:
            groupeddata = data[cols].groupby(categories, observed=True)
        # if groupeddata.ngroups == len(data):
        #    logging.debug("Single value per group.")
        #    groupeddata = data.set_index([c for c in categories], drop=True)
        mean = groupeddata.mean()
        if groupeddata.ngroups == len(data):
            dataindex = data.set_index([c for c in categories], drop=True).index
            logging.debug("Single value per group. Keeping index of original data.")
            mean = mean.reindex(index=dataindex)
        if error_bar != "None":
            if error_type == "std":
                error = groupeddata.std()
            else:
                error = groupeddata.sem()
        else:
            error = None
        if bartype == "100% stacked":
            # sum all columns, than devide means[all columns]  by sum (row-by-row)
            sum = mean.abs().sum(axis=1)
            mean = mean.div(sum, axis=0) * 100.0
            if error is not None:
                error = error.div(sum, axis=0) * 100.0
        num_bars = len(mean)
        if not stacked and pivot_level < len(categories):
            unstack_level = list(range(pivot_level))
            logging.debug(f"Unstacking: {pivot_level}, {unstack_level}")
            mean = mean.unstack(unstack_level)
            mean = mean.dropna(how="all", axis=0)
            if error is not None:
                error = error.unstack(unstack_level)
                error = error.dropna(how="all", axis=0)
        if error_bar == "+":
            error = error.transpose()
            dim = error.shape
            zeros = np.zeros_like(error)
            C = np.empty((error.shape[0] + zeros.shape[0], error.shape[1]))
            C[::2, :] = zeros
            C[1::2, :] = error
            error = C
            error = error.reshape([dim[0], 2, dim[1]])
        ticklabels = mean.index.values
        bwidth = 0.8  # * len(ticklabels)/num_bars
        fig.set_figheight(1 + num_bars // 8)
        fig.set_figwidth(6)
        if orientation == "horizontal":
            mean.plot.barh(
                ax=ax, xerr=error, width=bwidth, stacked=stacked, capsize=capsize
            )
        else:
            mean.plot.bar(
                ax=ax, yerr=error, width=bwidth, stacked=stacked, capsize=capsize
            )

    if len(categories) > 1 or stacked:
        ticklabels = [
            str(l).replace("'", "").replace("(", "").replace(")", "") for l in ticklabels
        ]
        h, labels = ax.get_legend_handles_labels()
        if stacked:
            ltitle = ""
            labels = feature
        elif len(categories) > 1:
            ltitle = ", ".join(categories[0:pivot_level])
            labels = [
                l.replace("'", "").replace("(", "").replace(")", "") for l in labels
            ]
            labels = [", ".join(label.split(",")[1:]) for label in labels]

            if orientation == "horizontal":
                ax.set_ylabel(", ".join(categories[pivot_level:]))
            else:
                ax.set_xlabel(", ".join(categories[pivot_level:]))
        no_legendcols = len(categories) // 30 + 1
        chartbox = ax.get_position()
        if bartype == "100% stacked":
            ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.set_position(
            [
                chartbox.x0,
                chartbox.y0,
                chartbox.width * (1 - 0.2 * no_legendcols),
                chartbox.height,
            ]
        )
        #        ax.legend(loc='upper center', labels=grouplabels, bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
        if legend:
            legend = ax.legend(
                labels=labels,
                title=ltitle,
                loc="upper left",
                bbox_to_anchor=(1.0, 1.0),
                fontsize="small",
                ncol=no_legendcols,
            )
            # legend = ax.legend(labels=labels,  title=', '.join(categories[0:pivot_level]), loc='upper center')
            # ax.add_artist(legend)
        else:
            legend = ax.legend()
            legend.remove()    
    else:
        legend = ax.legend()
        legend.remove()
    if orientation == "horizontal":
        ax.set_yticklabels(ticklabels)
    else:
        ax.set_xticklabels(ticklabels)
    if title is None:
        title = "|".join(feature).replace("\n", " ")  # .encode('utf-8')
        if len(categories) > 0:
            title = f"{title} grouped by {categories}"
    if len(title) > 0:
        ax.set_title(title)

    # fig.tight_layout()
    # plt.rcParams.update({'figure.autolayout': False})

    return fig


class BarPlotConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        orientation="vertical",
        ordering=[],
        ebar="+/-",
        etype="std",
        dropna=True,
        bartype="single",
        autosave=True,
        working_dir="",
        legend=True,
    ):
        self.orientation = orientation
        self.ordering = ordering
        self.ebar = ebar
        self.etype = etype
        self.sel_bartype = bartype
        self.dropna = dropna
        self.legend = legend
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
        osizer = wx.BoxSizer(wx.HORIZONTAL)
        orientation_opts = ["vertical", "horizontal"]
        sel_orientation = self.orientation
        if sel_orientation not in orientation_opts:
            sel_orientation = orientation_opts[0]
        self.orientation_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_orientation,
            choices=orientation_opts,
        )
        osizer.Add(
            wx.StaticText(self.panel, label="Orientation "),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        osizer.Add(
            self.orientation_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )

        ssizer = wx.BoxSizer(wx.HORIZONTAL)
        bartype_opts = ["single", "stacked", "100% stacked"]
        sel_bartype = self.sel_bartype
        if sel_bartype not in bartype_opts:
            sel_bartype = bartype_opts[0]
        self.bartype_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_bartype,
            choices=bartype_opts,
        )
        self.dropna_cb = wx.CheckBox(self.panel, id=wx.ID_ANY, label="Drop N/A")
        self.dropna_cb.SetValue(self.dropna)
        ssizer.Add(
            self.bartype_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        ssizer.Add(self.dropna_cb, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        ebar_opts = ["+/-", "+", "None"]
        sel_ebar = self.ebar
        if sel_ebar not in ebar_opts:
            sel_ebar = ebar_opts[0]
        self.ebar_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_ebar,
            choices=ebar_opts,
        )
        self.ebar_combobox.Bind(wx.EVT_COMBOBOX, self.OnErroBarChange)
        bsizer.Add(
            wx.StaticText(self.panel, label="Error Bar"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        bsizer.Add(
            self.ebar_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        tsizer = wx.BoxSizer(wx.HORIZONTAL)
        etype_opts = ["std", "s.e.m."]
        sel_etype = self.etype
        if sel_etype not in sel_etype:
            sel_etype = sel_etype[0]
        self.etype_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_etype,
            choices=etype_opts,
        )
        self.etype_combobox.Enable(sel_ebar != "None")
        tsizer.Add(
            wx.StaticText(self.panel, label="Error Type"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        tsizer.Add(
            self.etype_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        return [osizer, ssizer, bsizer, tsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["ordering"] = []
        params["orientation"] = self.orientation_combobox.GetValue()
        params["bar_type"] = self.bartype_combobox.GetValue()
        params["dropna"] = self.dropna_cb.GetValue()
        params["error_bar"] = self.ebar_combobox.GetValue()
        params["error_type"] = self.etype_combobox.GetValue()
        params["legend"] = self.legend
        return params

    def OnErroBarChange(self, event):
        ebar = self.ebar_combobox.GetValue()
        self.etype_combobox.Enable(ebar != "None")


@plugin(plugintype="Plot")
class BarPlot(AbstractPlugin):
    def __init__(self, name="Bar Plot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("barplot.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "display": ["auto", "auto"],
                "grouping": [],
                "features": [],
                "ordering": {},
                "orientation": "vertical",  # 'horizontal'
                "bar_type": "single",  # 'stacked', '100% stacked'
                "dropna": True,
                "error_bar": "+/-",  # '+', 'None'
                "error_type": "std",  # 's.e.m'
                "legend": True,
            }
        )
        return params

    def output_definition(self):
        if self.params["bar_type"] == "single":
            # separate plot for each feature
            return {
                f"Plot: {f}": matplotlib.figure.Figure for f in self.params["features"]
            }
        else:
            # one plot stacked with all features
            return {"Plot": matplotlib.figure.Figure}

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]
        ordering = self.params["ordering"]
        orientation = self.params["orientation"]
        etype = self.params["error_type"]
        ebar = self.params["error_bar"]
        bartype = self.params["bar_type"]
        dropna = self.params["dropna"]
        legend = self.params["legend"]
        dlg = BarPlotConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            selectedgrouping=selgrouping,
            selectedfeatures=selfeatures,
            ordering=ordering,
            orientation=orientation,
            bartype=bartype,
            dropna=dropna,
            ebar=ebar,
            etype=etype,
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
            legend=legend,
        )
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def get_mapped_parameters(self):
        if self.params["bar_type"] == "single":
            parallel_params = []
            for f in self.params["features"]:
                pair_param = self.params.copy()
                pair_param["features"] = [f]
                parallel_params.append(pair_param)
            return parallel_params
        else:
            # stacked plots process all features at once
            return [self.params]

    def execute(self):
        data = list(self.input.values())[0].copy()
        results = {}
        features = self.params["features"]
        grouping = self.params["grouping"]
        bartype = self.params["bar_type"]
        orientation = self.params["orientation"],
        error_bar = self.params["error_bar"],
        error_type = self.params["error_type"],
        dropna = self.params["dropna"]
        stacked = bartype != "single"
        legend = self.params["legend"]
        if stacked:
            logging.debug(f"\tcreating stacked mean bar plot for {features}")
            # pass and stack all features
            fig = grouped_meanbarplot(
                data,
                features,
                categories=grouping,
                dropna=dropna,
                bartype=bartype,
                orientation=self.params["orientation"],
                error_bar=self.params["error_bar"],
                error_type=self.params["error_type"],
                legend=self.params["legend"],
            )
            results[f"Plot: {'|'.join(features)}"] = fig
        else:
            # pass one feature per plot
            for feature in sorted(features):
                logging.debug(f"\tcreating mean bar plot for {feature}")
                fig = grouped_meanbarplot(
                    data,
                    [feature],
                    categories=grouping,
                    dropna=dropna,
                    bartype=bartype,
                    orientation=self.params["orientation"],
                    error_bar=self.params["error_bar"],
                    error_type=self.params["error_type"],
                    legend=self.params["legend"],
                )
                results[f"Plot: {feature}"] = fig
        self._add_picker(fig)
        return results
