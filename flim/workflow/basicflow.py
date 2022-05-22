#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:35:56 2020

@author: khs3z
"""

import json
import logging
import inspect
import os
import pkgutil
import importlib
import numpy as np
import pandas as pd
import wx
import graphviz
import networkx as nx
import networkx.drawing.nx_pydot
import networkx.drawing.nx_agraph
import networkx.classes.function
import pydot
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
from importlib_resources import files
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
from flim.analysis.aetraining import AETraining
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
from flim.core.graph import WorkflowGraph




class AbsWorkFlow(AbstractPlugin):

    def __init__(self, name="Base Workflow", executor=None, **kwargs):
        super().__init__(name=name, **kwargs)
        #self.name = "Abstract FLIM Workflow"
        self.set_executor(executor)

    #def __repr__(self):
    #    return f"{'name: {self.name}'}"

    def __str__(self):
        return self.name

    def get_icon(self):
        source = files(flim.resources).joinpath('heatmap.png')
        return wx.Bitmap(str(source))        

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'grouping': self.get_required_categories(),
            'features': self.get_required_features(),
            'executor': {
                'class': 'prefect.executors.local.LocalExecutor',
                'args': {},
                },
            'register': False,
            'project': 'FLIM', #self.name,
            
        })
        return params
        
    def set_executor(self, executor=None, **kwargs):
        modulename = '<unresolved'
        classname = '<unresolved'
        if executor is None:
            # use default, ignore kwargs
            executor = self.params['executor']['class']
            kwargs = self.params['executor']['args']
        elif isinstance(executor, dict):
            kwargs = executor.get('args', {})
            executor = executor.get('class', 'prefect.executors.local.LocalExecutor')
        if isinstance(executor, str):
            modulename, _, classname = executor.rpartition('.')
            try:
                module = importlib.import_module(modulename)
                class_ = getattr(module, classname)
                self.executor = class_(**kwargs)
            except Exception as err:
                logging.error(f"Error: {err}")
                logging.error(f"Error instantiating {modulename}.{classname} plugin tool.")
                self.executor = LocalExecutor()
        elif issubclass(self.executor, Executor):
            modulename = clazz.__module__
            classname = clazz.__name__
            self.executor = executor
        logging.debug(f"Executor modulename={modulename}, classname={classname}")
        assert issubclass(self.executor.__class__, Executor)
                
    def get_required_categories(self):
        return ['Treatment', 'FOV', 'Cell']

    def get_required_features(self):
        return ['FLIRR', 'trp t1']

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = BasicAnalysisConfigDlg(parent, f'Configuration: {self.name}', 
            input=self.input, 
            selectedgrouping=selgrouping, 
            selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    @abstractmethod
    def construct_flow(self):
        return Flow()
        
    def execute(self):
        flow = self.construct_flow()
        if self.params['register']:
            flow.register(project_name=self.params['project'], idempotency_key=flow.serialized_hash()) # prevent version bump when reregistering an unchanged flow
        
        flow.visualize()
        with open(f'{self.name}.json', 'w') as fp: 
            json.dump(flow.serialize(), fp, indent=4)

        
        state = flow.run()
        task_refs = flow.get_tasks()
        task_results = [state.result[tr]._result.value for tr in task_refs]
        output_results = [tr for tr in list(task_results) if not isinstance(tr, dict)]
        plugin_results = [tr for tr in list(task_results) if isinstance(tr, dict)] #state.result[tr]._result.value not in output_results]
        results = {f'{k}-{str(id(v))}': v for d in plugin_results if isinstance(d, dict) for k, v in d.items() }
        
        wg = WorkflowGraph(flow)
        fig,_ = wg.get_plot()
        results[f'{self.name} Graph'] = fig

        return results


def get_task_graph(task):
    g = nx.DiGraph()
    g.add_node(task.name)
    #g.add_node(tnode)
    for rname,robject in task.output_definition().items():
        print (f'edge: {task.name} -> {rname}')
        g.add_edge(task.name, rname)
    print (f'len(g):{len(g)}')
    return g

"""
@task
def results_to_tasks(task_in):
    datatask = DataBucket(None)
    results = task_in
    if len(task_in) > 1:
        print ("MAPPING", "|".join([t for t in task_in]))
        #task_list = [v for v in task_in.values()]
        #mapped = data_task.map(task_list)
        #out_tasks = {f'Out {i}':d for i,d in enumerate(mapped)}
        out_tasks = {k:datatask(name=k, data=task_in[k], input_select=[0]) for i, k in enumerate(task_in)}
    else:
        out_tasks = task_in
        #out_tasks = {k:datatask(name=k, data=results, input_select=[i]) for i, k in enumerate(task_in.output_definition())}
    return out_tasks
"""

def _get_input_label(self, data):
        if data == pd.DataFrame or isinstance(data, pd.DataFrame):
            return 'Table'
        elif isinstance(data, matplotlib.figure.Figure):
            return 'Plot'
        elif isinstance(data, str) and os.path.isabs(data):
            return 'File'
        else:
            return 'Data'

def results_to_tasks(task_in):
    #datatask = DataBucket(None)
    #print (f'task_in.output_definition()={task_in.output_definition()}')
    out_tasks = {}
    for i, output_name in enumerate(task_in.output_definition()):
        datatask = DataBucket()#task_in, name=output_name, task_run_name="Hello")
        #out_tasks[output_name] = datatask(name=output_name, task_run_name="Hello", input=task_in, input_select=[i])
        dt_result = datatask(name=output_name, task_run_name="Hello", input=task_in, input_select=[i])
        out_tasks[output_name] = dt_result
    # out_tasks = {k:datatask(name=k, data=task_in, input_select=[i]) for i, k in enumerate(task_in.output_definition())}
    # print (f'out_tasks={out_tasks}')
    return out_tasks
    
@task
def data_task(data):
    out = {'Out':data}
    return out
    
@task
def to_list(d):
    return [v for v in d.values()]

@plugin(plugintype="Workflow")        
class StdFLIMWorkflow(AbsWorkFlow):

    def __init__(self, name="Standard FLIM Analysis", **kwargs):
        super().__init__(name=name, **kwargs)
        #self.executor = None #DaskExecutor(address="tcp://172.18.75.87:8786")

    def get_required_features(self):
        return ['any']

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'features': [
                'FAD a1','FAD a1[%]', 'FAD a2', 'FAD a2[%]', 'FAD t1', 'FAD t2', 'FAD photons', 
                'NAD(P)H a1', 'NAD(P)H a1[%]', 'NAD(P)H a2', 'NAD(P)H a2[%]', 'NAD(P)H t1', 'NAD(P)H t2', 'NAD(P)H photons'],
        })
        return params
                
    def construct_flow(self):
        data = list(self.input.values())[0]
        sel_features = self.params['features']
        all_features = [c for c in data.select_dtypes(include=np.number)]
        
        #listtask = List()
        datatask = DataBucket(name='Input')
        aetraintask_10 = AETraining()
        aetraintask_14 = AETraining()
        simtask = AESimulate()
        aeruntask = RunAE()
        filtertask = Filter()
        pcatask = PCAnalysis()
        stask = SummaryStats()#, log_stdout=True)
        heatmaptask = Heatmap()
        concattask = Concatenator()
        pivottask = Pivot()
        seriestask = SeriesAnalyzer()
        bartask = BarPlot(bar_type='100% stacked', features=['Feature 1\nmean\ndelta Ctrl:dox30', 'Feature 1\nmean\ndelta dox30:dox45', 'Feature 1\nmean\ndelta dox45:dox60'])
        kmeanstask = KMeansClustering()
        kdetask = KDE(features=['Feature 1\nmean\ndelta ctrl:dox30', 'Feature 1\nmean\ndelta dox30:dox45', 'Feature 1\nmean\ndelta dox45:dox60'])
        mergetask = Merger()
        kstask = KSStats()
        
        with Flow(f'{self.name}', executor=self.executor, ) as flow:
            #input = Parameter('input', default=data)
            modelfile_10 = Parameter('modelfile: 10', default='AETrain-10.model')
            modelfile_14 = Parameter('modelfile: 14', default='AETrain-14.model')

            train_features_10 = Parameter('features: 10', default=[
                'FAD a1', 'FAD a2', 'FAD t1', 'FAD t2', 'FAD photons', 
                'NAD(P)H a1','NAD(P)H a2', 'NAD(P)H t1', 'NAD(P)H t2', 'NAD(P)H photons'])
            pca_features_14 = Parameter('pca features: 14', default=[
                'FAD a1', 'FAD a1[%]', 'FAD a2', 'FAD a2[%]', 'FAD t1', 'FAD t2', 'FAD photons', 
                'NAD(P)H a1','NAD(P)H a1[%]', 'NAD(P)H a2','NAD(P)H a2[%]', 'NAD(P)H t1', 'NAD(P)H t2', 'NAD(P)H photons'])
            #train_features_14 = Parameter('features: 14', default=[
            #    'FAD a1', 'FAD a1%', 'FAD a2', 'FAD a2%', 'FAD t1', 'FAD t2', 'FAD photons', 
            #    'NAD(P)H a1','NAD(P)H a1%', 'NAD(P)H a2','NAD(P)H a2%', 'NAD(P)H t1', 'NAD(P)H t2', 'NAD(P)H photons'])

            sim_sets = Parameter('sim_sets', default=4) 
            
            input = datatask(name='Input', input=self.input, input_select=[0])
            
            filterresults1 = results_to_tasks(filtertask(
                input=input, 
                input_select=[0]
                ))

            pcaresults = results_to_tasks(pcatask(
                input=filterresults1['Table: Filtered'], 
                input_select=[0], 
                grouping=[], #['FOV', 'Cell'],
                features=pca_features_14
                ))
                
            aeresults = results_to_tasks(aetraintask_10(
                input=filterresults1['Table: Filtered'], 
                input_select=[0], 
                grouping=['FOV', 'Cell'],
                features=train_features_10, 
                epochs=20,
                learning_rate=[0.0001],
                weight_decay=[0.00000001],
                batch_size=[128],
                timeseries='Treatment',
                rescale=True,
                model='Autoencoder 1',
                modelfile=modelfile_10
                ))

            simresults = results_to_tasks(simtask(
                input=filterresults1['Table: Filtered'], 
                input_select=[0], 
                grouping=['FOV', 'Cell'], 
                features=train_features_10, 
                modelfile=aeresults['Model File'], 
                sets=sim_sets
                ))
                
            filterresults2 = results_to_tasks(filtertask(
                input=simresults['Table: Simulated'], 
                input_select=[0]
                ))
            
            aeresults2 = results_to_tasks(aetraintask_14(
                input=filterresults2['Table: Filtered'], 
                input_select=[0], 
                grouping=['FOV', 'Cell'],
                features=self.params['features'], #train_features_14, 
                epochs=20,
                learning_rate=[0.00015],
                weight_decay=[0.00000001],
                batch_size=[500],
                timeseries='Treatment',
                rescale=True,
                model='Autoencoder 2',
                modelfile=modelfile_14
                ))

            aerunresults = results_to_tasks(aeruntask(
                input=filterresults1['Table: Filtered'], 
                input_select=[0],
                grouping=['FOV', 'Cell'],
                features=self.params['features'],
                modelfile=aeresults2['Model File']
                ))
            
            concatresults = results_to_tasks(concattask(
                input={
                    '1': filterresults1['Table: Filtered'], 
                    '2': aerunresults['Table: Features'], 
                    '3': pcaresults['Table: PCA Components']},
                type=True,
                numbers_only=True
                ))
                
            summaryresults3 = results_to_tasks(stask(
                input=concatresults['Table: Concatenated'], 
                input_select=[0], 
                grouping=['Cell', 'FOV', 'Treatment'],
                features=['FLIRR', 'Feature 1', 'PC 1'], 
                aggs=['mean']
                ))

            pivotresult = results_to_tasks(pivottask(
                input=summaryresults3['Table: Summary'], 
                input_select=[0], 
                grouping=['Treatment'],
                features=['FLIRR\nmean', 'Feature 1\nmean', 'PC 1\nmean']
                ))

            seriesresult_F1 = results_to_tasks(seriestask(
                input=pivotresult['Table: Pivoted'], 
                input_select=[0], 
                features=['Feature 1\nmean\nctrl', 'Feature 1\nmean\ndox30', 'Feature 1\nmean\ndox45', 'Feature 1\nmean\ndox60'],
                series_min=False,
                series_max=False,
                series_range=False,
                series_mean=False,
                series_median=False,
                delta=True, 
                delta_min=False,
                delta_max=False,
                delta_sum=False,
                delta_cum=False,
                merge_input=False
                ))

            barresult_F1 = results_to_tasks(bartask(
                input=seriesresult_F1['Table: Series Analysis'], 
                input_select=[0], 
                grouping=['FOV', 'Cell'],
                features=['Feature 1\nmean\ndelta ctrl:dox30', 'Feature 1\nmean\ndelta dox30:dox45', 'Feature 1\nmean\ndelta dox45:dox60'],
                ordering={},
                orientation='vertical', # 'horizontal'
                bar_type='100% stacked', # 'single', 'stacked'
                dropna=True,
                error_bar='+/-', # '+', 'None'
                error_type='s.e.m'
                )) # 'std'

            kmeansresult_F1 = results_to_tasks(kmeanstask(
                input=seriesresult_F1['Table: Series Analysis'], 
                input_select=[0], 
                grouping=['Cell', 'FOV', 'Treatment'],
                features=['Feature 1\nmean\ndelta ctrl:dox30', 'Feature 1\nmean\ndelta dox30:dox45', 'Feature 1\nmean\ndelta dox45:dox60'],
                n_clusters=2,
                cluster_prefix='F1 Cluster',
                init='k-means++',
                algorithm='auto',
                n_init=4,
                max_iter=300,
                tolerance=1e-4
                ))

            kderesults_F1 = results_to_tasks(kdetask(
                input=kmeansresult_F1['Table: K-Means'], 
                input_select=[0], 
                grouping=['F1 Cluster'],
                features=ALL_FEATURES
                ))
            
            summaryresults_F1 = results_to_tasks(stask(
                input=kmeansresult_F1['Table: K-Means'], 
                input_select=[0], 
                grouping=['F1 Cluster'],
                features=ALL_FEATURES, 
                aggs=['count', 'mean']
                ))
                
            seriesresult_FLIRR = results_to_tasks(seriestask(
                input=pivotresult['Table: Pivoted'], 
                input_select=[0], 
                features=['FLIRR\nmean\nctrl', 'FLIRR\nmean\ndox30', 'FLIRR\nmean\ndox45', 'FLIRR\nmean\ndox60'],
                series_min=False,
                series_max=False,
                series_range=False,
                series_mean=False,
                series_median=False,
                delta=True, 
                delta_min=False,
                delta_max=False,
                delta_sum=False,
                delta_cum=False,
                merge_input=False
                ))

            barresult_FLIRR = results_to_tasks(bartask(
                input=seriesresult_FLIRR['Table: Series Analysis'], 
                input_select=[0], 
                grouping=['FOV', 'Cell'],
                features=['FLIRR\nmean\ndelta ctrl:dox30', 'FLIRR\nmean\ndelta dox30:dox45', 'FLIRR\nmean\ndelta dox45:dox60'],
                ordering={},
                orientation='vertical', # 'horizontal'
                bar_type='100% stacked', # 'single', 'stacked'
                dropna=True,
                error_bar='+/-', # '+', 'None'
                error_type='s.e.m'
                )) # 'std'

            kmeansresult_FLIRR = results_to_tasks(kmeanstask(
                input=seriesresult_FLIRR['Table: Series Analysis'], 
                input_select=[0], 
                grouping=['Cell', 'FOV', 'Treatment'],
                features=['FLIRR\nmean\ndelta ctrl:dox30', 'FLIRR\nmean\ndelta dox30:dox45', 'FLIRR\nmean\ndelta dox45:dox60'],
                n_clusters=2,
                cluster_prefix='FLIRR Cluster',
                init='k-means++',
                algorithm='auto',
                n_init=4,
                max_iter=300,
                tolerance=1e-4
                ))

            kderesults_FLIRR = results_to_tasks(kdetask(
                input=kmeansresult_FLIRR['Table: K-Means'], 
                input_select=[0], 
                grouping=['FLIRR Cluster'],
                features=ALL_FEATURES
                ))
            
            summaryresults_FLIRR = results_to_tasks(stask(
                input=kmeansresult_FLIRR['Table: K-Means'], 
                input_select=[0], 
                grouping=['FLIRR Cluster'],
                features=ALL_FEATURES,
                aggs=['count', 'mean']
                ))
                
            #mergeresults_FLIRR = results_to_tasks(mergetask(input=None, input_select=[0],
            #    input={'left':seriesresult_FLIRR['Table: Series Analysis'], 'right': kmeansresult_FLIRR['Table: K-Means']},
            #    how='left', 
            #    features=[],))

           
                
            seriesresult_PCA = results_to_tasks(seriestask(
                input=pivotresult['Table: Pivoted'], 
                input_select=[0], 
                features=['PC 1\nmean\nctrl', 'PC 1\nmean\ndox30', 'PC 1\nmean\ndox45', 'PC 1\nmean\ndox60'],
                series_min=False,
                series_max=False,
                series_range=False,
                series_mean=False,
                series_median=False,
                delta=True, 
                delta_min=False,
                delta_max=False,
                delta_sum=False,
                delta_cum=False,
                merge_input=False
                ))

            barresult_PCA = results_to_tasks(bartask(
                input=seriesresult_PCA['Table: Series Analysis'], 
                input_select=[0], 
                grouping=['FOV', 'Cell'],
                features=['PC 1\nmean\ndelta ctrl:dox30', 'PC 1\nmean\ndelta dox30:dox45', 'PC 1\nmean\ndelta dox45:dox60'],
                ordering={},
                orientation='vertical', # 'horizontal'
                bar_type='100% stacked', # 'single', 'stacked'
                dropna=True,
                error_bar='+/-', # '+', 'None'
                error_type='s.e.m'
                )) # 'std'

            kmeansresult_PCA = results_to_tasks(kmeanstask(
                input=seriesresult_PCA['Table: Series Analysis'], 
                input_select=[0], 
                grouping=['Cell', 'FOV', 'Treatment'],
                features=['PC 1\nmean\ndelta ctrl:dox30', 'PC 1\nmean\ndelta dox30:dox45', 'PC 1\nmean\ndelta dox45:dox60'],
                n_clusters=2,
                cluster_prefix='PCA Cluster',
                init='k-means++',
                algorithm='auto',
                n_init=4,
                max_iter=300,
                tolerance=1e-4
                ))

            kderesults_PCA = results_to_tasks(kdetask(
                input=kmeansresult_PCA['Table: K-Means'], 
                input_select=[0], 
                grouping=['PCA Cluster'],
                features=ALL_FEATURES
                ))
            
            summaryresults_PCA = results_to_tasks(stask(
                input=kmeansresult_PCA['Table: K-Means'], 
                input_select=[0], 
                grouping=['PCA Cluster'],
                features=ALL_FEATURES,
                aggs=['count', 'mean']
                ))

            mergeresults_FLIRR = results_to_tasks(mergetask(
                input={'left':concatresults['Table: Concatenated'], 'right': kmeansresult_FLIRR['Table: K-Means']},
                how='left', 
                features=[]
                ))

            mergeresults_FLIRR_F1 = results_to_tasks(mergetask(
                input={'left':mergeresults_FLIRR['Table: Merged'], 'right': kmeansresult_F1['Table: K-Means']},
                how='left', 
                features=[]
                ))

            mergeresults_FLIRR_F1_PCA = results_to_tasks(mergetask(
                input={'left':mergeresults_FLIRR_F1['Table: Merged'], 'right': kmeansresult_PCA['Table: K-Means']},
                how='left', 
                features=[]
                ))

            ksresults_PCA = results_to_tasks(kstask(
                input=mergeresults_FLIRR_F1_PCA['Table: Merged'], 
                input_select=[0], 
                comparison='Treatment',
                grouping=['Cell', 'FOV', 'PCA Cluster'], 
                alpha=0.05,
                features=['FLIRR','Feature 1','PC 1']
                ))
            

            heatmap_inputresults = results_to_tasks(heatmaptask(
                input=filterresults1['Table: Filtered'], 
                input_select=[0],
                grouping=['Treatment','FOV', 'Cell'],
                features=self.params['features']
                ))
                
            heatmap_simrawresults = results_to_tasks(heatmaptask(
                input=simresults['Table: Simulated'], 
                input_select=[0],
                grouping=['Treatment','FOV', 'Cell'],
                features=self.params['features']
                ))

            heatmap_simfilteredresults = results_to_tasks(heatmaptask(
                input=filterresults2['Table: Filtered'], 
                input_select=[0],
                grouping=['Treatment','FOV', 'Cell'],
                features=self.params['features']
                ))

            summaryresults = results_to_tasks(stask(
                input=simresults['Table: Simulated'], 
                input_select=[0], 
                features=train_features_10, 
                aggs=['min', 'max', 'median', 'count']
                ))
                
            summaryresults2 = results_to_tasks(stask(
                input=filterresults2['Table: Filtered'], 
                input_select=[0], 
                features=train_features_10, 
                aggs=['min', 'max', 'median', 'count']
                ))
            #aetrainresults = results_to_tasks(aetraintask(input=input, input_select=[0], features=sel_features, sets=sim_sets))
        
        return flow

        
@plugin(plugintype="Workflow")        
class TestWorkFlow(AbsWorkFlow):

    def __init__(self, name="Test Workflow", **kwargs):
        super().__init__(name=name, **kwargs)
        #self.executor = None #DaskExecutor(address="tcp://172.18.75.87:8786")

    def get_required_features(self):
        return ['FLIRR', 'any']
        
    def construct_flow(self):
        data = list(self.input.values())[0].copy()
        sel_features = self.params['features']
        all_features = [c for c in data.select_dtypes(include=np.number)]
        
        #listtask = List()
        datatask = DataBucket()#None, name='Input')
        stask = SummaryStats(None, features=[f'rel {f}' for f in sel_features], singledf=False)#, log_stdout=True)
        pcatask = PCAnalysis(None, explainedhisto=True)#, log_stdout=True)
        scattertask = ScatterPlot(None, features=sel_features)
        relchangetask = RelativeChange(None)
        lineplottask = LinePlot(None)
        pivottask = Pivot(None)
        barplottask = BarPlot(None)
        kdetask = KDE(None)
        #cats = list(data.select_dtypes('category').columns.values)
        with Flow(f'{self.name}', executor=self.executor, ) as flow:
            #input = Parameter('input', default=data)
            inputresult = datatask(name='Input', input=self.input, input_select=[0])

            reltable = results_to_tasks(relchangetask(
                input=inputresult, 
                task_run_name="1.0 {relchangetask.name}", 
                input_select=[0], grouping=['FOV', 'Cell'], 
                features=sel_features, reference_group='Treatment', 
                reference_value='ctrl', 
                method='mean'))
            srelresult = results_to_tasks(stask(input=reltable['Table: Relative Change'], input_select=[0], grouping=['Cell', 'FOV', 'Treatment'],features=[f'rel {f}' for f in sel_features], aggs=['mean'], singledf=False))
            #pivotresult = results_to_tasks(pivottask(data=srelresult['Data: Summarize'], input_select=[0], grouping=['Treatment'],features=['rel FLIRR\nmean']))
            lineplotresult = results_to_tasks(lineplottask(input=reltable['Table: Relative Change'], input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR']))

            #sresult = results_to_tasks(stask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'],features=allfeatures,aggs=['max','mean','median','count']))
            #listtask = to_list(scattertask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'],features=sel_features))
            #scatter = data_task.map(listtask)
            scatter = results_to_tasks(scattertask(input=inputresult, input_select=[0], grouping=['Treatment'],features=sel_features))
            
            pcaresult = results_to_tasks(pcatask(input=inputresult, input_select=[0], features=all_features, explainedhisto=True))

            #reltable = datatask(name='Relative Change', data=relchresult)
            #lineplotresult = results_to_tasks(lineplottask(data=reltable['Data: Relative Change'], input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR']))

            #barplot = results_to_tasks(barplottask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'], features=['FLIRR']))
            #kdeplot = results_to_tasks(kdetask(data=reltable['Data: Relative Change'], input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR']))
            #sresult2 = results_to_tasks(stask(data=sresult['Data: Summarize'], input_select=[0], grouping=['FOV'], features=['FLIRR\nmean'], aggs=['max']))
            #sresult3 = results_to_tasks(stask(data=pcaresult, input_select=[0], grouping=[], features=['Principal component 1'], aggs=['max']))
            #sresult4 = results_to_tasks(stask(data=pcaresult['PCA explained'], input_select=[0], grouping=['PCA component'], features=['explained var ratio'], aggs=['max']))
        return flow

