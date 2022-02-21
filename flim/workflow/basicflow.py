#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:35:56 2020

@author: khs3z
"""

from abc import ABC, abstractmethod
from flim.plugin import plugin
import logging
import inspect
import os
import pkgutil
import importlib
from importlib_resources import files
import wx
from flim.plugin import AbstractPlugin
from flim.data.tableops import Pivot
from flim.analysis.summarystats import SummaryStats
from flim.analysis.relativechange import RelativeChange
from flim.analysis.pca import PCAnalysis
from flim.analysis.barplots import BarPlot
from flim.analysis.lineplots import LinePlot
from flim.analysis.kde import KDE
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.resources
import numpy as np

from prefect import Task, Flow, Parameter
from prefect.executors import DaskExecutor
from prefect.executors.base import Executor


class AbsWorkFlow(AbstractPlugin):

    def __init__(self, data, *args, executor=None, **kwargs):
        super().__init__(data, *args, **kwargs)
        self.name = "Abstract FLIM Workflow"
        self.set_executor(executor)

    def __repr__(self):
        return f"{'name: {self.name}'}"

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
                }
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
        dlg = BasicAnalysisConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        return {}


class InputTask(Task):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Input"
        
    def run(self, data):
        print (f'{self.name}: type(data)={type(data)}')
        if isinstance(data, dict):
            return data
        else: 
            return {'Input': data}

        
@plugin(plugintype="Workflow")        
class BasicFLIMWorkFlow(AbsWorkFlow):

    def __init__(self, data, *args, executor=None, **kwargs):
        super().__init__(data, *args, executor=executor, **kwargs)
        self.name = "Horst's Magic Button"
        #self.executor = None #DaskExecutor(address="tcp://172.18.75.87:8786")

    def execute(self):
        
        inputtask = InputTask()
        stask = SummaryStats(None)#, log_stdout=True)
        pcatask = PCAnalysis(None)#, log_stdout=True)
        relchangetask = RelativeChange(None)
        lineplottask = LinePlot(None)
        pivottask = Pivot(None)
        barplottask = BarPlot(None)
        kdetask = KDE(None)
        #cats = list(self.data.select_dtypes('category').columns.values)
        allfeatures = [c for c in self.data.select_dtypes(include=np.number)]
        with Flow('FLIM Flow', executor=self.executor) as flow:
            input = inputtask(data=self.data)
            #input = Parameter('input', default = self.data)
            sresult = stask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'],features=allfeatures,aggs=['max','mean','median','count'])
            relchresult = relchangetask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'], features=allfeatures, reference_group='Treatment', reference_value='ctrl')
            reltable = inputtask(data=relchresult)
            lineplotresult = lineplottask(data=reltable, input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR'])
            srelresult = stask(data=reltable, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'],features=['rel FLIRR'],aggs=['max','mean','median','count'])
            pivotresult = pivottask(data=srelresult, input_select=[0], grouping=['Treatment'],features=['rel FLIRR\nmean'])

            #pcaresult = pcatask(data=input, input_select=[0], features=['FLIRR', 'trp t1'], keeporig=True)
            #barplot = barplottask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'], features=['FLIRR'])
            #kdeplot = kdetask(data=relchresults, input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR'])
            #sresult2 = stask(data=sresult, input_select=[0], grouping=['FOV'], features=['FLIRR\nmean'], aggs=['max'])
            #sresult3 = stask(data=pcaresult, input_select=['PCA'], grouping=[], features=['Principal component 1'], aggs=['max'])
            #sresult4 = stask(data=pcaresult, input_select=['PCA explained'], grouping=['PCA component'], features=['explained var ratio'], aggs=['max'])
        task_refs = flow.get_tasks()
        state = flow.run()
        vgraph = flow.visualize(filename="workflow", format="svg", flow_state=state)
        import graphviz
        #print (graphviz.Source(vgraph.source, format='svg').pipe())
        #print (vgraph.source)
        task_results = [state.result[tr]._result.value for tr in task_refs]
        results = {f'{k}-{str(id(v))}': v for d in task_results for k, v in d.items()}
        
        import networkx as nx
        import networkx.drawing.nx_pydot
        import networkx.drawing.nx_agraph
        import pydot
        import matplotlib.pyplot as plt
        pydotgraph = pydot.graph_from_dot_data(vgraph.source)[0]
        node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes()}
        svg_string = pydotgraph.create_svg()
        #print (svg_string)
        g = networkx.drawing.nx_pydot.from_pydot(pydotgraph)        
        fig, ax = plt.subplots()
        #pos = nx.multipartite_layout(g, subset_key="layer")
        pos = nx.drawing.nx_agraph.graphviz_layout(g, prog='dot')
        nx.draw(g, pos=pos, ax=ax, labels=node_labels, with_labels = True)
        results['Workflow Graph'] = fig
        
        return results
        
