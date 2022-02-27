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
from flim.plugin import AbstractPlugin, DataBucket
from flim.data.tableops import Pivot
from flim.analysis.summarystats import SummaryStats
from flim.analysis.relativechange import RelativeChange
from flim.analysis.pca import PCAnalysis
from flim.analysis.scatterplots import ScatterPlot
from flim.analysis.barplots import BarPlot
from flim.analysis.lineplots import LinePlot
from flim.analysis.kde import KDE
from flim.gui.dialogs import BasicAnalysisConfigDlg
from flim.core.graph import WorkflowGraph
import flim.resources
import numpy as np

from prefect import Task, Flow, Parameter, task
from prefect.tasks.core.collections import List
from prefect.executors import DaskExecutor
from prefect.executors.base import Executor

import graphviz
import networkx as nx
import networkx.drawing.nx_pydot
import networkx.drawing.nx_agraph
import networkx.classes.function
import pydot
import matplotlib.pyplot as plt


class AbsWorkFlow(AbstractPlugin):

    def __init__(self, data, *args, executor=None, **kwargs):
        super().__init__(data, *args, **kwargs)
        self.name = "Abstract FLIM Workflow"
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

def results_to_tasks(task_in):
    datatask = DataBucket(None)
    print (task_in.output_definition())
    out_tasks = {k:datatask(name=k, data=task_in, input_select=[i]) for i, k in enumerate(task_in.output_definition())}
    return out_tasks
    
@task
def data_task(data):
    out = {'Out':data}
    return out
    
@task
def to_list(d):
    return [v for v in d.values()]

@plugin(plugintype="Workflow")        
class BasicFLIMWorkFlow(AbsWorkFlow):

    def __init__(self, data, *args, executor=None, **kwargs):
        super().__init__(data, *args, executor=executor, **kwargs)
        self.name = "Horst's Magic Button"
        #self.executor = None #DaskExecutor(address="tcp://172.18.75.87:8786")

    def get_required_features(self):
        return ['FLIRR', 'any']
        
    def execute(self):
        sel_features = self.params['features']
        all_features = [c for c in self.data.select_dtypes(include=np.number)]
        
        #listtask = List()
        datatask = DataBucket(None)
        stask = SummaryStats(None, features=[f'rel {f}' for f in sel_features], singledf=False)#, log_stdout=True)
        pcatask = PCAnalysis(None, explainedhisto=True)#, log_stdout=True)
        scattertask = ScatterPlot(None, features=sel_features)
        relchangetask = RelativeChange(None)
        lineplottask = LinePlot(None)
        pivottask = Pivot(None)
        barplottask = BarPlot(None)
        kdetask = KDE(None)
        #cats = list(self.data.select_dtypes('category').columns.values)
        with Flow('FLIM Flow', executor=self.executor, ) as flow:
            #input = Parameter('input', default=self.data)
            input = datatask(name='Input', data=self.data, input_select=[0])
            reltable = results_to_tasks(relchangetask(data=input, input_select=[0], grouping=['FOV', 'Cell'], features=sel_features, reference_group='Treatment', reference_value='ctrl', method='mean'))
            srelresult = results_to_tasks(stask(data=reltable['Data: Relative Change'], input_select=[0], grouping=['Cell', 'FOV', 'Treatment'],features=[f'rel {f}' for f in sel_features],aggs=['mean'], singledf=False))
            #pivotresult = results_to_tasks(pivottask(data=srelresult['Data: Summarize'], input_select=[0], grouping=['Treatment'],features=['rel FLIRR\nmean']))
            lineplotresult = results_to_tasks(lineplottask(data=reltable['Data: Relative Change'], input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR']))

            #sresult = results_to_tasks(stask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'],features=allfeatures,aggs=['max','mean','median','count']))
            #listtask = to_list(scattertask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'],features=sel_features))
            #scatter = data_task.map(listtask)
            scatter = results_to_tasks(scattertask(data=input, input_select=[0], grouping=['Treatment'],features=sel_features))
            
            pcaresult = results_to_tasks(pcatask(data=input, input_select=[0], features=all_features, explainedhisto=True))

            #reltable = datatask(name='Relative Change', data=relchresult)
            #lineplotresult = results_to_tasks(lineplottask(data=reltable['Data: Relative Change'], input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR']))

            #barplot = results_to_tasks(barplottask(data=input, input_select=[0], grouping=['Treatment', 'FOV', 'Cell'], features=['FLIRR']))
            #kdeplot = results_to_tasks(kdetask(data=reltable['Data: Relative Change'], input_select=[0], grouping=['Treatment','FOV'], features=['rel FLIRR']))
            #sresult2 = results_to_tasks(stask(data=sresult['Data: Summarize'], input_select=[0], grouping=['FOV'], features=['FLIRR\nmean'], aggs=['max']))
            #sresult3 = results_to_tasks(stask(data=pcaresult['PCA'], input_select=[0], grouping=[], features=['Principal component 1'], aggs=['max']))
            #sresult4 = results_to_tasks(stask(data=pcaresult['PCA explained'], input_select=[0], grouping=['PCA component'], features=['explained var ratio'], aggs=['max']))
        state = flow.run()
        task_refs = flow.get_tasks()
        task_results = [state.result[tr]._result.value for tr in task_refs]
        output_results = [state.result[tr]._result.value for tr in task_refs if isinstance(tr, DataBucket)]
        plugin_results = [state.result[tr]._result.value for tr in task_refs if state.result[tr]._result.value not in output_results]
        results = {f'{k}-{str(id(v))}': v for d in output_results if isinstance(d, dict) for k, v in d.items() }
        
        wg = WorkflowGraph(flow)
        fig,_ = wg.get_plot()
        results['Workflow Graph'] = fig
        """
        task_refs = flow.get_tasks()
        vgraph = flow.visualize(filename="workflow", format="svg", flow_state=state)
        #print (graphviz.Source(vgraph.source, format='svg').pipe())
        #print (vgraph.source)
        output_ids = [id(tr) for tr in task_refs if isinstance(tr, DataBucket)]
        plugin_ids = [id(tr) for tr in task_refs if not isinstance(tr, DataBucket)]
        #for n in sorted([id(tr) for tr in task_refs]):
        #    print (f'id(tr)={n}')
        #for n in sorted([id(state.result[tr]) for tr in task_refs]):
        #    print (f'id(state.result[tr])={n}')
        #for n in sorted(output_ids):
        #    print (f'output_ids={n}')
        print (f'output_ids={sorted(output_ids)}')
        print (f'plugin_ids={sorted(plugin_ids)}')
        
        pydotgraph = pydot.graph_from_dot_data(vgraph.source)[0]
        
        color_map = ['blue' if n.get_label() in output_results else 'red' for n in pydotgraph.get_nodes()]
        shape_map = ['s' if 'Data' in n.get_label() else 'o' for n in pydotgraph.get_nodes()]
        svg_string = pydotgraph.create_svg()
        #print (svg_string)
        g = networkx.drawing.nx_pydot.from_pydot(pydotgraph)
        for n in networkx.classes.function.nodes(g):
            print (f'nx.n={type(n)}')

        node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes()}
        #output_nodes = [n for n in pydotgraph.get_nodes() if int(n.get_name()) in output_ids]
        #plugin_nodes = [n for n in pydotgraph.get_nodes() if int(n.get_name()) in plugin_ids]
        output_nodes = [n for n in networkx.classes.function.nodes(g) if int(n) in output_ids]
        plugin_nodes = [n for n in networkx.classes.function.nodes(g) if int(n) in plugin_ids]
        output_node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes() if int(n.get_name()) in output_ids}
        plugin_node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes() if int(n.get_name()) in plugin_ids}
        #print (f'node_labels={node_labels}')
        #print ([n.get_name() for n in pydotgraph.get_nodes()])
        print (f'output_nodes={output_nodes}')
        print (f'plugin_nodes={plugin_nodes}')
        print (f'output_node_labels={output_node_labels}')
        print (f'plugin_node_labels={plugin_node_labels}')

        #for task in task_refs:
        #    print (type(task))
        #    g.add_edges_from(get_task_graph(task).edges)       
        fig, ax = plt.subplots()
        #pos = nx.multipartite_layout(g, subset_key="layer")
        pos = nx.drawing.nx_agraph.graphviz_layout(g, prog='dot', args='-Grankdir="LR"')
        print (pos)
        for n in output_nodes:
            print (n)
        nx.draw_networkx_nodes(g, pos, ax=ax, nodelist=output_nodes, node_color='blue', node_shape='s')
        nx.draw_networkx_nodes(g, pos, ax=ax, nodelist=plugin_nodes, node_color='red', node_shape='o')
        nx.draw_networkx_edges(g, pos, ax=ax)
        nx.draw_networkx_labels(g, pos, ax=ax, labels=node_labels)
        #nx.draw(g, pos=pos, ax=ax, node_color=color_map, labels=node_labels, with_labels = True)
        """
        return results
        
