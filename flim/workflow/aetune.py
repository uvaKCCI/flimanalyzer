import logging
import inspect
import itertools
import numpy as np
import os
import pandas as pd
import re
import wx
import matplotlib.pyplot as plt

from prefect import Task, Flow, Parameter, task, unmapped, flatten
from prefect.tasks.core.constants import Constant
from prefect.tasks.core.collections import List
from prefect.executors import DaskExecutor
from prefect.executors.base import Executor
from prefect.engine.results import LocalResult

import flim.resources
from flim import utils
from flim.plugin import plugin
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
from flim.workflow.basicflow import AbsWorkFlow, results_to_tasks
from flim.results import LocalResultClear

@task
def perm(a, b):
    combinations = list(itertools.product(a, b))
    return tuple(map(itemgetter(0), combinations)), tuple(map(itemgetter(1), combinations)) 
    
@task
def product(x, y):
    return list(itertools.product(x, y))
        
@task
def select(listofdict, pattern):
	return [v for entry in listofdict for k,v in entry.items() if re.search(pattern, k)]


@plugin(plugintype="Workflow")
class AEWorkflow(AbsWorkFlow):
    def __init__(self, name="FLIM Data Simulation Tuning", **kwargs):
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
                "modelfile": "AE Train Simulator",
                "model": "AE Simulator 1-6",
                "device": "cpu",
                "rescale": True,
                "checkpoint_interval": 2,  # 20
            }
        )
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AETrainingConfigDlg(
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
            modelfile=self.params["modelfile"],
            device=self.params["device"],
            rescale=self.params["rescale"],
            checkpoint_interval=self.params["checkpoint_interval"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params
        
    def construct_flow(self):
        os.environ["PREFECT__FLOWS__CHECKPOINTING"] = "true"
        checkpoint_interval = self.params["checkpoint_interval"]

        data = list(self.input.values())[0]
        sel_features = self.params["features"]
        all_features = [c for c in data.select_dtypes(include=np.number)]

        rates = [f'l{i}' for i in self.params["learning_rate"]]
        decays = [f'd{i}' for i in self.params["weight_decay"]]
        batch_sizes = [f'b{i}' for i in self.params["batch_size"]]
        combinations = list(itertools.product(batch_sizes, rates, decays))
        batch_sizes, rates, decays = utils.permutate(
            self.params["batch_size"],
            self.params["learning_rate"],
            self.params["weight_decay"],
        )

        add_noise = False
        sets = 4

        # listtask = List()
        datatask = DataBucket(name="Input")
        filtertask = Filter()
        aetraintask_10 = AETraining()
        #    learning_rate=rates,
        #    weight_decay=decays,
        #    batch_size=batch_sizes,
        #    create_plots=False,
        #    checkpoint_interval=checkpoint_interval,
        #    )

        concattask = Concatenator()
        summarytask = SummaryStats()
        unpivottask = UnPivot()
        lineplottask = LinePlot()
        barplottask = BarPlot()
        simtask = AESimulate()
        heatmaptask = Heatmap()
        kdetask = KDE()

        localresult = LocalResultClear(
            dir=f'{self.params["working_dir"]}',
            location="{flow_name}/"
            "{scheduled_start_time:%y-%m-%d_%H-%M-%S}/"
            "{task_full_name}-{task_tags}",  # -{task_run_id}-{map_index}-
        )
        with Flow(f"{self.name}", executor=self.executor, result=localresult) as flow:
            modelfile = f'{self.params["modelfile"]}-{len(self.params["features"])}'

            timeseries = Parameter("timeseries", default=self.params["timeseries"])
            grouping = Parameter("grouping", default=self.params["grouping"])
            epoches = Parameter("epoches", default=self.params["epoches"])
            rates = Parameter("learning rate", default=rates)
            decays = Parameter("weight decay", default=decays)
            batch_sizes = Parameter("batch size", default=batch_sizes)
            train_features = Parameter(
                f'features: {len(self.params["features"])}',
                default=sel_features,
            )
            model = Parameter("model", default=self.params["model"])
            add_noise = Parameter("add noise", default=add_noise)
            sets = Parameter("sets", default=sets)

            input = datatask(name="Input", input=self.input, input_select=[0])

            heatmapexp = heatmaptask(
                input=input,
                input_select=unmapped([0]),
                grouping=unmapped([]),
                features=unmapped(train_features),
                corr_type=unmapped('spearman'),
            )

            aeresults = aetraintask_10.map(
                input=unmapped(input),
                input_select=unmapped([0]),
                grouping=unmapped(grouping),
                features=unmapped(train_features),
                epoches=unmapped(epoches),
                learning_rate=rates,
                weight_decay=decays,
                batch_size=batch_sizes,
                checkpoint_interval=unmapped(checkpoint_interval),
                timeseries=unmapped(timeseries),
                rescale=unmapped(True),
                model=unmapped(model),
                modelfile=unmapped(modelfile),
                create_plots=unmapped(False),
                checkpoint=unmapped(True),
                task_tags=combinations,
            )

            concatresults = concattask(
                input=aeresults, input_select=["Table: AE Loss"], type=False
            )

            summaryresults = summarytask(
                input=concatresults, 
                input_select=[0],
                grouping=['Source', 'Batch Size', 'Learning Rate', 'Weight Decay'],
                features=['Training Loss', 'Validation Loss', 'Model File'], 
                singledf=True, 
                aggs=['min']
            )
            
            unpivotresults = unpivottask(
                input=concatresults, 
                input_select=[0],
                features=['Training Loss', 'Validation Loss'], 
                category_name='Loss Type',
                feature_name='Loss Value',
            )
            
            lineplotresults = lineplottask(
                input=unpivotresults, 
                input_select=[0],
                grouping = ['Epoch', 'Loss Type', 'Batch Size', 'Learning Rate', 'Weight Decay'],
                features = ['Loss Value']
            )

            barplotresults = barplottask(
                input=concatresults, 
                input_select=[0],
                grouping = ['Epoch', 'Batch Size', 'Learning Rate', 'Weight Decay'],
                features = ['Training Loss', 'Validation Loss'],
            )
            
            simresults = simtask.map(
                input=unmapped(input), 
                input_select=unmapped([0]),
                modelfile=select(aeresults,'Model File'),
                add_noise=unmapped(add_noise),
                sets=unmapped(sets),
                features=unmapped(train_features),
                grouping=unmapped(grouping),
                task_tags=combinations,
            )
            
            heatmapresults = heatmaptask.map(
                input=simresults,
                input_select=unmapped([0]),
                grouping=unmapped([]),
                features=unmapped(train_features),
                corr_type=unmapped('spearman'),
                task_tags=combinations,
            )
            
            kderesults = kdetask.map(
                input=simresults,
                input_select=unmapped([0]),
                grouping=unmapped(['Treatment']),
                features=unmapped(train_features),
                task_tags=combinations,
            )
        return flow
