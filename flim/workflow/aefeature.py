import logging
import inspect
import itertools
import numpy as np
import os
import pandas as pd
import prefect
import re
import wx
import matplotlib.pyplot as plt

from prefect import Task, Flow, Parameter, task, unmapped, flatten, tags
from prefect.tasks.core.collections import List
from prefect.tasks.core.constants import Constant
from prefect.tasks.files.operations import Glob
from prefect.executors import DaskExecutor
from prefect.executors.base import Executor
from prefect.engine.results import LocalResult

import flim.analysis.ml.autoencoder as autoencoder
import flim.resources
from flim import utils
from flim.plugin import plugin, perm, product, select
from flim.plugin import AbstractPlugin, DataBucket, ALL_FEATURES
from flim.data.pivotdata import Pivot
from flim.data.unpivotdata import UnPivot
from flim.data.filterdata import Filter
from flim.data.concatdata import Concatenator
from flim.data.mergedata import Merger
from flim.analysis.aerun import RunAE
from flim.analysis.aetraining import AETraining, AETrainingConfigDlg
from flim.analysis.aesimulate import AESimulate
from flim.analysis.barplots import BarPlot
from flim.analysis.heatmap import Heatmap
from flim.analysis.kde import KDE
from flim.analysis.kmeans import KMeansClustering
from flim.analysis.ksstats import KSStats
from flim.analysis.lineplots import LinePlot
from flim.analysis.seriesanalyzer import SeriesAnalyzer
from flim.analysis.summarystats import SummaryStats
from flim.analysis.relativechange import RelativeChange
from flim.analysis.pca import PCAnalysis
from flim.analysis.scatterplots import ScatterPlot
from flim.analysis.barplots import BarPlot
from flim.analysis.lineplots import LinePlot
from flim.gui.dialogs import BasicAnalysisConfigDlg
from flim.workflow.aetune import AESimTuneConfigDlg
from flim.workflow.basicflow import AbsWorkFlow


@task
def create_input(a, b, c):
    return {"1": a, "2": b, "3": c}


@plugin(plugintype="Workflow")
class StdFLIMWorkflow(AbsWorkFlow):
    def __init__(self, name="FLIM Feature Analysis", **kwargs):
        super().__init__(name=name, **kwargs)
        # self.executor = None #DaskExecutor(address="tcp://172.18.75.87:8786")

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "grouping": ["Treatment", "FOV", "Cell"],
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
                "timeseries": "Treatment",
                "epoches": 6,  # 20,
                "learning_rate": [
                    0.00001,
                    0.00002,
                ],  # , 0.00005, 0.0001, 0.00011, 0.00015, 0.0002],
                "weight_decay": [1e-7, 1e-8],
                "batch_size": [128, 64],
                "working_dir": os.path.join(
                    os.path.expanduser("~"), "FLIMAnalyzerResults"
                ),
                "model": "AE Dimensionality Reduction 2-10",
                "device": "cpu",
                "rescale": True,
                "checkpoint_interval": 2,  # 20
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AESimTuneConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            description=self.get_description(),
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            epoches=self.params["epoches"],
            batch_size=self.params["batch_size"],
            weight_decay=self.params["weight_decay"],
            learning_rate=self.params["learning_rate"],
            timeseries=self.params["timeseries"],
            model=self.params["model"],
            device=self.params["device"],
            rescale=self.params["rescale"],
            checkpoint_interval=self.params["checkpoint_interval"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def construct_flow(self, executor, result):
        checkpoint_interval = self.params["checkpoint_interval"]

        data = list(self.input.values())[0]
        sel_features = self.params["features"]
        all_features = [c for c in data.select_dtypes(include=np.number)]

        batch_sizes = [f"b{i}" for i in self.params["batch_size"]]
        rates = [f"l{i}" for i in self.params["learning_rate"]]
        decays = [f"d{i}" for i in self.params["weight_decay"]]
        last_epoch = self.params["epoches"]
        combinations = [
            utils.clean(f"{str(i)} e{last_epoch:04d}")
            for i in list(itertools.product(batch_sizes, rates, decays))
        ]
        batch_sizes, rates, decays = utils.permutate(
            self.params["batch_size"],
            self.params["learning_rate"],
            self.params["weight_decay"],
        )

        # listtask = List()
        datatask = DataBucket(name="Input")
        globtask = Glob()
        filtertask = Filter()
        aetraintask = AETraining()
        aeruntask = RunAE()
        pcatask = PCAnalysis()
        stask = SummaryStats()  # , log_stdout=True)
        heatmaptask = Heatmap()
        concattask = Concatenator()
        pivottask = Pivot()
        seriestask = SeriesAnalyzer()
        bartask = BarPlot()
        kmeanstask = KMeansClustering()
        kdetask = KDE()
        mergetask = Merger()
        kstask = KSStats()

        with Flow(
            f"{self.name}",
            executor=executor,
            result=result,
        ) as flow:
            working_dir = Parameter("working_dir", self.params["working_dir"])
            modelfile = f'AEFeature-{len(self.params["features"])}'

            timeseries = Parameter("timeseries", default=self.params["timeseries"])
            timeseries_vals = [
                v for v in data[self.params["timeseries"]].unique() if not "15" in v
            ]
            t_pairs = list(zip(timeseries_vals, timeseries_vals[1:]))

            grouping = Parameter("grouping", default=self.params["grouping"])
            epoches = Parameter("epoches", default=self.params["epoches"])
            rates = Parameter("learning rate", default=rates)
            decays = Parameter("weight decay", default=decays)
            batch_sizes = Parameter("batch size", default=batch_sizes)
            features = Parameter(
                f'features: {len(self.params["features"])}',
                default=sel_features,
            )
            model = Parameter("model", default=self.params["model"])

            globresult = globtask(
                path="/Users/khs3z/FLIMAnalyzerResults/FLIM Feature Analysis/",
                pattern="AE*.model",
            )

            input = datatask(
                name="Input",
                input=self.input,
                input_select=[0],
                task_tags="Input",
            )

            input_filtered = filtertask(
                input=input,
                input_select=[0],
                task_tags="Input_Filtered",
            )

            pcaresults = pcatask(
                input=input_filtered,
                input_select=[0],
                grouping=[],  # ['FOV', 'Cell'],
                features=features,
                task_tags="Input_Filtered/PCA",
            )

            ksresults_FLIRR = kstask(
                input=input_filtered,
                input_select=[0],
                comparison="Treatment",
                grouping=["Treatment", "FOV", "Cell"],
                alpha=0.05,
                features=["FLIRR"],
                task_tags="Input_Filtered/FLIRR",
            )

            ksresults_PCA = kstask(
                input=pcaresults["Table: PCA Components"],
                input_select=[0],
                comparison="Treatment",
                grouping=["Treatment", "FOV", "Cell"],
                alpha=0.05,
                features=["PC 1"],
                task_tags="Input_Filtered/PCA",
            )

            aeresults = aetraintask.map(
                input=unmapped(input_filtered),
                input_select=unmapped([0]),
                grouping=unmapped(grouping),
                features=unmapped(features),
                epoches=unmapped(epoches),
                learning_rate=rates,
                weight_decay=decays,
                batch_size=batch_sizes,
                checkpoint_interval=unmapped(checkpoint_interval),
                timeseries=unmapped(timeseries),
                rescale=unmapped(True),
                model=unmapped(model),
                working_dir=unmapped(working_dir),
                modelfile=unmapped(modelfile),
                create_plots=unmapped(False),
                checkpoint=unmapped(True),
                task_tags=combinations,
            )

            aerunresults = aeruntask.map(
                input=unmapped(input_filtered),
                input_select=unmapped([0]),
                grouping=unmapped(grouping),
                features=unmapped(features),
                modelfile=select(
                    aeresults, key_pattern="Model File", value_pattern=f"{last_epoch:04d}"
                ),
                task_tags=combinations,
            )

            cinput = create_input.map(
                unmapped(input_filtered["Table: Filtered"]),
                select(aerunresults, "Table: Features"),
                unmapped(pcaresults["Table: PCA Components"]),
            )

            concatresults = concattask.map(
                input=cinput,
                type=unmapped(True),
                numbers_only=unmapped(True),
                task_tags=combinations,
            )

            summaryresults3 = stask.map(
                input=concatresults,
                input_select=unmapped([0]),
                grouping=unmapped(["Cell", "FOV", "Treatment"]),
                features=unmapped(["FLIRR", "Feature 1", "PC 1"]),
                aggs=unmapped(["mean"]),
                singledf=unmapped(True),
                task_tags=combinations,
            )

            pivotresult = pivottask.map(
                input=summaryresults3,
                input_select=unmapped([0]),
                grouping=unmapped([timeseries]),
                features=unmapped(["FLIRR\nmean", "Feature 1\nmean", "PC 1\nmean"]),
                task_tags=combinations,
            )

            seriesresult_F1 = seriestask.map(
                input=pivotresult,
                input_select=unmapped([0]),
                features=unmapped([f"Feature 1\nmean\n{t}" for t in timeseries_vals]),
                series_min=unmapped(False),
                series_max=unmapped(False),
                series_range=unmapped(False),
                series_mean=unmapped(False),
                series_median=unmapped(False),
                delta=unmapped(True),
                delta_min=unmapped(False),
                delta_max=unmapped(False),
                delta_sum=unmapped(False),
                delta_cum=unmapped(False),
                merge_input=unmapped(False),
                task_tags=[f"{c}/Feature 1" for c in combinations],
            )

            barresult_F1 = bartask.map(
                input=seriesresult_F1,
                input_select=unmapped([0]),
                grouping=unmapped(["FOV", "Cell"]),
                features=unmapped(
                    [f"Feature 1\nmean\ndelta {t[0]}:{t[1]}" for t in t_pairs]
                ),
                ordering=unmapped({}),
                orientation=unmapped("vertical"),  # 'horizontal'
                bar_type=unmapped("100% stacked"),  # 'single', 'stacked'
                dropna=unmapped(True),
                error_bar=unmapped("+/-"),  # '+', 'None'
                error_type=unmapped("s.e.m"),
                task_tags=[f"{c}/Feature 1" for c in combinations],
            )  # 'std'

            ksresults_F1 = kstask.map(
                input=summaryresults3,
                input_select=unmapped([0]),
                comparison=unmapped("Treatment"),
                grouping=unmapped(["Treatment", "FOV", "Cell"]),
                alpha=unmapped(0.05),
                features=unmapped(["Feature 1"]),
                task_tags=[f"{c}/Feature 1" for c in combinations],
            )

            """
            kmeansresult_F1 = kmeanstask.map(
                input=seriesresult_F1,
                input_select=unmapped([0]),
                grouping=unmapped(["Cell", "FOV", "Treatment"]),
                features=unmapped(
                    [f"Feature 1\nmean\ndelta {t[0]}:{t[1]}" for t in t_pairs]
                ),
                n_clusters=unmapped(2),
                cluster_prefix=unmapped("F1 Cluster"),
                init=unmapped("k-means++"),
                algorithm=unmapped("auto"),
                n_init=unmapped(4),
                max_iter=unmapped(300),
                tolerance=unmapped(1e-4),
                task_tags=combinations,
            )
            
            kderesults_F1 = kdetask.map(
                input=kmeansresult_F1["Table: K-Means"],
                input_select=unmapped([0]),
                grouping=unmapped(["F1 Cluster"]),
                features=unmapped(ALL_FEATURES),
                task_tags=combinations,
            )
            
            
            summaryresults_F1 = results_to_tasks(
                stask(
                    input=kmeansresult_F1["Table: K-Means"],
                    input_select=[0],
                    grouping=["F1 Cluster"],
                    features=ALL_FEATURES,
                    aggs=["count", "mean"],
                )
            )
            """

            seriesresult_FLIRR = seriestask.map(
                input=pivotresult,
                input_select=unmapped([0]),
                features=unmapped([f"FLIRR\nmean\n{t}" for t in timeseries_vals]),
                series_min=unmapped(False),
                series_max=unmapped(False),
                series_range=unmapped(False),
                series_mean=unmapped(False),
                series_median=unmapped(False),
                delta=unmapped(True),
                delta_min=unmapped(False),
                delta_max=unmapped(False),
                delta_sum=unmapped(False),
                delta_cum=unmapped(False),
                merge_input=unmapped(False),
                task_tags=[f"{c}/FLIRR" for c in combinations],
            )

            barresult_FLIRR = bartask.map(
                input=seriesresult_FLIRR,
                input_select=unmapped([0]),
                grouping=unmapped(["FOV", "Cell"]),
                features=unmapped([f"FLIRR\nmean\ndelta {t[0]}:{t[1]}" for t in t_pairs]),
                ordering=unmapped({}),
                orientation=unmapped("vertical"),  # 'horizontal'
                bar_type=unmapped("100% stacked"),  # 'single', 'stacked'
                dropna=unmapped(True),
                error_bar=unmapped("+/-"),  # '+', 'None'
                error_type=unmapped("s.e.m"),
                task_tags=[f"{c}/FLIRR" for c in combinations],
            )  # 'std'

            """
            kmeansresult_FLIRR = results_to_tasks(
                kmeanstask(
                    input=seriesresult_FLIRR["Table: Series Analysis"],
                    input_select=[0],
                    grouping=["Cell", "FOV", "Treatment"],
                    features=[
                        "FLIRR\nmean\ndelta ctrl:dox30",
                        "FLIRR\nmean\ndelta dox30:dox45",
                        "FLIRR\nmean\ndelta dox45:dox60",
                    ],
                    n_clusters=2,
                    cluster_prefix="FLIRR Cluster",
                    init="k-means++",
                    algorithm="auto",
                    n_init=4,
                    max_iter=300,
                    tolerance=1e-4,
                )
            )

            kderesults_FLIRR = results_to_tasks(
                kdetask(
                    input=kmeansresult_FLIRR["Table: K-Means"],
                    input_select=[0],
                    grouping=["FLIRR Cluster"],
                    features=ALL_FEATURES,
                )
            )

            summaryresults_FLIRR = results_to_tasks(
                stask(
                    input=kmeansresult_FLIRR["Table: K-Means"],
                    input_select=[0],
                    grouping=["FLIRR Cluster"],
                    features=ALL_FEATURES,
                    aggs=["count", "mean"],
                )
            )
            """
            # mergeresults_FLIRR = results_to_tasks(mergetask(input=None, input_select=[0],
            #    input={'left':seriesresult_FLIRR['Table: Series Analysis'], 'right': kmeansresult_FLIRR['Table: K-Means']},
            #    how='left',
            #    features=[],))

            seriesresult_PCA = seriestask.map(
                input=pivotresult,
                input_select=unmapped([0]),
                features=unmapped([f"PC 1\nmean\n{t}" for t in timeseries_vals]),
                series_min=unmapped(False),
                series_max=unmapped(False),
                series_range=unmapped(False),
                series_mean=unmapped(False),
                series_median=unmapped(False),
                delta=unmapped(True),
                delta_min=unmapped(False),
                delta_max=unmapped(False),
                delta_sum=unmapped(False),
                delta_cum=unmapped(False),
                merge_input=unmapped(False),
                task_tags=[f"{c}/PC 1" for c in combinations],
            )

            barresult_PCA = bartask.map(
                input=seriesresult_PCA,
                input_select=unmapped([0]),
                grouping=unmapped(["FOV", "Cell"]),
                features=unmapped([f"PC 1\nmean\ndelta {t[0]}:{t[1]}" for t in t_pairs]),
                ordering=unmapped({}),
                orientation=unmapped("vertical"),  # 'horizontal'
                bar_type=unmapped("100% stacked"),  # 'single', 'stacked'
                dropna=unmapped(True),
                error_bar=unmapped("+/-"),  # '+', 'None'
                error_type=unmapped("s.e.m"),
                task_tags=[f"{c}/PC 1" for c in combinations],
            )  # 'std'


            """
            kmeansresult_PCA = results_to_tasks(
                kmeanstask(
                    input=seriesresult_PCA["Table: Series Analysis"],
                    input_select=[0],
                    grouping=["Cell", "FOV", "Treatment"],
                    features=[
                        "PC 1\nmean\ndelta ctrl:dox30",
                        "PC 1\nmean\ndelta dox30:dox45",
                        "PC 1\nmean\ndelta dox45:dox60",
                    ],
                    n_clusters=2,
                    cluster_prefix="PCA Cluster",
                    init="k-means++",
                    algorithm="auto",
                    n_init=4,
                    max_iter=300,
                    tolerance=1e-4,
                )
            )

            kderesults_PCA = results_to_tasks(
                kdetask(
                    input=kmeansresult_PCA["Table: K-Means"],
                    input_select=[0],
                    grouping=["PCA Cluster"],
                    features=ALL_FEATURES,
                )
            )

            summaryresults_PCA = results_to_tasks(
                stask(
                    input=kmeansresult_PCA["Table: K-Means"],
                    input_select=[0],
                    grouping=["PCA Cluster"],
                    features=ALL_FEATURES,
                    aggs=["count", "mean"],
                )
            )
            """

            """
            mergeresults_FLIRR = results_to_tasks(
                mergetask(
                    input={
                        "left": concatresults["Table: Concatenated"],
                        "right": kmeansresult_FLIRR["Table: K-Means"],
                    },
                    how="left",
                    features=[],
                )
            )

            mergeresults_FLIRR_F1 = results_to_tasks(
                mergetask(
                    input={
                        "left": mergeresults_FLIRR["Table: Merged"],
                        "right": kmeansresult_F1["Table: K-Means"],
                    },
                    how="left",
                    features=[],
                )
            )

            mergeresults_FLIRR_F1_PCA = results_to_tasks(
                mergetask(
                    input={
                        "left": mergeresults_FLIRR_F1["Table: Merged"],
                        "right": kmeansresult_PCA["Table: K-Means"],
                    },
                    how="left",
                    features=[],
                )
            )

            ksresults_PCA = results_to_tasks(
                kstask(
                    input=mergeresults_FLIRR_F1_PCA["Table: Merged"],
                    input_select=[0],
                    comparison="Treatment",
                    grouping=["Cell", "FOV", "PCA Cluster"],
                    alpha=0.05,
                    features=["FLIRR", "Feature 1", "PC 1"],
                )
            )

            heatmap_inputresults = results_to_tasks(
                heatmaptask(
                    input=filterresults1["Table: Filtered"],
                    input_select=[0],
                    grouping=["Treatment", "FOV", "Cell"],
                    features=self.params["features"],
                )
            )

            heatmap_simrawresults = results_to_tasks(
                heatmaptask(
                    input=simresults["Table: Simulated"],
                    input_select=[0],
                    grouping=["Treatment", "FOV", "Cell"],
                    features=self.params["features"],
                )
            )

            heatmap_simfilteredresults = results_to_tasks(
                heatmaptask(
                    input=filterresults2["Table: Filtered"],
                    input_select=[0],
                    grouping=["Treatment", "FOV", "Cell"],
                    features=self.params["features"],
                )
            )

            summaryresults = results_to_tasks(
                stask(
                    input=simresults["Table: Simulated"],
                    input_select=[0],
                    features=train_features_10,
                    aggs=["min", "max", "median", "count"],
                )
            )

            summaryresults2 = results_to_tasks(
                stask(
                    input=filterresults2["Table: Filtered"],
                    input_select=[0],
                    features=train_features_10,
                    aggs=["min", "max", "median", "count"],
                )
            )
            # aetrainresults = results_to_tasks(aetraintask(input=input, input_select=[0], features=sel_features, sets=sim_sets))
            """

        return flow
