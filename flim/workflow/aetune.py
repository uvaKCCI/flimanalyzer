import logging
import inspect
import numpy as np
import pandas as pd
import wx
import matplotlib.pyplot as plt

from prefect import Task, Flow, Parameter, task
from prefect.tasks.core.constants import Constant
from prefect.tasks.core.collections import List
from prefect.executors import DaskExecutor
from prefect.executors.base import Executor

import flim.resources
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




                
@plugin(plugintype="Workflow")        
class AEWorkflow(AbsWorkFlow):

    def __init__(self, name="FLIM Data Simulation Tuning", **kwargs):
        super().__init__(name=name, **kwargs)
        #self.executor = None #DaskExecutor(address="tcp://172.18.75.87:8786")

    def get_required_features(self):
        return ['any']

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'grouping': ['Treatment', 'FOV', 'Cell'],
            'features': [
                'FAD a1','FAD a1[%]', 'FAD a2', 'FAD a2[%]', 'FAD t1', 'FAD t2', 'FAD photons', 
                'NAD(P)H a1', 'NAD(P)H a1[%]', 'NAD(P)H a2', 'NAD(P)H a2[%]', 'NAD(P)H t1', 'NAD(P)H t2', 'NAD(P)H photons'],
	        'timeseries': 'Treatment',
	        'epoches': 6, #20, 
	        'learning_rate': [0.00001, 0.00002], #, 0.00005, 0.0001, 0.00011, 0.00015, 0.0002], 
	        'weight_decay': [1e-7, 1e-8], 
	        'batch_size': [128, 64],
	        'modelfile': 'AE Train Simulator',
            'model': 'AE Simulator 1-6',
            'device': 'cpu',
            'rescale': True,
            'checkpoint_interval': 2, # 20
        })
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AETrainingConfigDlg(parent, f'Configuration: {self.name}', 
            input=self.input,
            description=self.get_description(), 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            epoches=self.params['epoches'], 
            batch_size=self.params['batch_size'],
            weight_decay=self.params['weight_decay'],
            learning_rate=self.params['learning_rate'],
            timeseries=self.params['timeseries'],
            model=self.params['model'],
            modelfile=self.params['modelfile'],
            device=self.params['device'],
            rescale=self.params['rescale'],
            checkpoint_interval=self.params["checkpoint_interval"])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params
                        
    def construct_flow(self):
        data = list(self.input.values())[0]
        sel_features = self.params['features']
        all_features = [c for c in data.select_dtypes(include=np.number)]

        rates = self.params['learning_rate']
        decays = self.params['weight_decay']
        batch_sizes = self.params['batch_size']
        checkpoint_interval = self.params['checkpoint_interval']
                
        #listtask = List()
        datatask = DataBucket(name='Input')
        filtertask = Filter()
        aetraintask_10 = AETraining(
            learning_rate=rates,
            weight_decay=decays,
            batch_size=batch_sizes,
            create_plots=False,
            checkpoint_interval=checkpoint_interval,
            )
        concattask = Concatenator()
        summarytask = SummaryStats()
        unpivottask = UnPivot()
        lineplottask = LinePlot()
        barplottask = BarPlot()
        
        with Flow(f'{self.name}', executor=self.executor, ) as flow:
            modelfile = f'{self.params["modelfile"]}-{len(self.params["features"])}'

            timeseries = Parameter('timeseries', default=self.params['timeseries'])
            grouping = Parameter('grouping', default=self.params['grouping'])
            epoches = Parameter('epoches', default=self.params['epoches'])
            rates = Parameter('learning rate', default=rates)
            decays = Parameter('weight decay', default=decays)
            batch_sizes = Parameter('batch size', default=batch_sizes)
            train_features = Parameter(f'features: {len(self.params["features"])}', default=self.params['features'])
            model = Parameter('model', default=self.params['model'])
            
            input = datatask(name='Input', input=self.input, input_select=[0])
            
            aeresults = results_to_tasks(aetraintask_10(
                input=input, 
                input_select=[0], 
                grouping=grouping,
                features=train_features, 
                epoches=epoches,
                learning_rate=rates,
                weight_decay=decays,
                batch_size=batch_sizes,
                checkpoint_interval=checkpoint_interval,
                timeseries=timeseries,
                rescale=True,
                model=model,
                modelfile=modelfile,
                create_plots=False,
                ))
            
            loss_tables = [k for k,output in aeresults.items() if 'Table: AE Loss' in k]
            concatresults = results_to_tasks(concattask(
                input=aeresults, 
                input_select=loss_tables, 
                type=False)
                )
            
            summaryresults = results_to_tasks(summarytask(
                input=concatresults, 
                input_select=[0],
                grouping=['Source', 'Batch Size', 'Learning Rate', 'Weight Decay'],
                features=['Training Loss', 'Validation Loss', 'Model File'], 
                singledf=True, 
                aggs=['min']
                ))
            
            unpivotresults = results_to_tasks(unpivottask(
                input=concatresults, 
                input_select=[0],
                features=['Training Loss', 'Validation Loss'], 
                category_name='Loss Type',
                feature_name='Loss Value',
                ))
            lineplotresults = results_to_tasks(lineplottask(
                input=unpivotresults, 
                input_select=[0],
                grouping = ['Epoch', 'Loss Type', 'Batch Size', 'Learning Rate', 'Weight Decay'],
                features = ['Loss Value']
                ))

            barplotresults = results_to_tasks(barplottask(
                input=concatresults, 
                input_select=[0],
                grouping = ['Epoch', 'Batch Size', 'Learning Rate', 'Weight Decay'],
                features = ['Training Loss', 'Validation Loss']
                ))
            
        return flow