#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  4 09:25:32 2020

@author: khs3z
"""

import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import random
from concurrent.futures import ThreadPoolExecutor, Future
import time

nodeid = 0

def next_nodeid():
   global nodeid
   nodeid = nodeid + 1
   return nodeid
   
class BasicNode():
    
    def __init__(self, layer, config):
        self.name = 'basic'
        self.layer = layer
        self.config = config
 
    def get_name(self):
        return self.name

    def __repr__(self):
        return self.name

        
class DataNode(BasicNode):
    
    def __init__(self, layer, data, description):
        super().__init__(layer, None)
        self.name = 'data'
        self.data = data
        self.description = description
    
        
class AnalysisNode(BasicNode):
    
    def __init__(self, layer, config):
        super().__init__(layer, config)
        self.name = 'analysis'
        self.inputs = []
        self.outputs = []
        self.create_graph()
    
    def set_inputs(self, inp):
        self.inputs = inp
        
    def get_outputs(self):
        return self.outputs
    
    def apply(self):
        self.outputs = self.inputs
        return self.outputs
    
    def create_graph(self):
        graph = nx.DiGraph(descr=self.get_name())
        thisnodeid = (next_nodeid(),)
        graph.add_node(thisnodeid, subset=self.layer, item=self)
        for index,output in enumerate(self.get_outputs()):
            id = [i for i in thisnodeid]
            id.append(index)#next_nodeid()
            id = tuple(id)
            graph.add_node(id, subset=self.layer+1, item=DataNode(self.layer+1, output, ''))
            graph.add_edge(thisnodeid, id)
        self.graph  = graph
        
    def get_graph(self):
        return self.graph
        
    def __repr__(self):
        return f"{self.get_name()}"


class CreateColumn(AnalysisNode):

    def __init__(self, layer, config):
        super().__init__(layer, config)
        self.outputs = [None, None]
        self.name = 'Create column'
     
    def apply(self):
        if self.config['inplace']:
            data = self.inputs[0]
        else:
            data = self.inputs[0].copy()
        print (type(data), data.columns.values)
        col = data[self.config['col_in']] + self.config['value']
        col.name = self.config['col_out']
        self.outputs = [col, data]
        return self.outputs

        
class Merge(AnalysisNode):

    def __init__(self, layer, config):
        super().__init__(layer, config)
        self.name = 'Merge columns'
        
    def apply(self):
        self.outputs = [pd.concat(self.inputs, axis=1)]
        return self.outputs
        
        
    
if __name__ == "__main__":
    graph = nx.DiGraph(descr="All")
    df = pd.DataFrame(np.random.rand(4,3), columns=["A", "B", "C"])
    dfnode = DataNode(1, df, '')
    rootid = next_nodeid()
    graph.add_node(rootid, subset=1, item=dfnode)
    print ('subset', graph.nodes[rootid]['subset'])

    a = CreateColumn(2, {'col_in':'A', 'col_out':'D', 'operation':'add', 'value':10, 'inplace':False})
    a.set_inputs([graph.nodes[rootid]])
    #a.apply()
    a.create_graph()
    calcid = next_nodeid()
    graph.add_node(calcid, subset=2, item=a.get_graph())
    print (graph.nodes)
    print (graph.nodes[calcid]['item'].nodes)
    pos = nx.multipartite_layout(graph, align='horizontal')#, subset_key='layer')#, arrows=True)
    # invert y coordinates
    pos = {key : [pos[key][0],-pos[key][1]] for key in pos}
    nx.draw_networkx(graph, pos=pos, arrows=True)
    plt.show()
    
    plt.clf()
    
    
    
    graph = nx.DiGraph(descr="Summary")
    initialStep = AnalysisNode({})
    initialStep.set_inputs([df])
    graph.add_node(1, subset=1, input_channel=None, action=initialStep)
    graph.add_node(2, subset=2, input_channel=[0], item=CreateColumn({'col_in':'A', 'col_out':'D', 'operation':'add', 'value':10, 'inplace':False}))
    graph.add_node(3, subset=2, input_channel=[0], item=CreateColumn({'col_in':'B', 'col_out':'E', 'operation':'add', 'value':20, 'inplace':False}))
    graph.add_node(4, subset=2, input_channel=[0], item=CreateColumn({'col_in':'C', 'col_out':'F', 'operation':'add', 'value':30, 'inplace':False}))
    graph.add_node(5, subset=3, input_channel=[0], item=Merge({}))
    graph.add_node(6, subset=4, input_channel=[0], item=CreateColumn({'col_in':'D', 'col_out':'G', 'operation':'add', 'value':100, 'inplace':False}))
    graph.add_node(7, subset=5, input_channel=[0], item=Merge({}))
    graph.add_edge(1, 2, color='yellow')
    graph.add_edge(1, 3, color='yellow')
    graph.add_edge(1, 4, color='yellow')
    graph.add_edge(1, 5, color='yellow')
    graph.add_edge(2, 5, color='yellow')
    graph.add_edge(3, 5, color='yellow')
    graph.add_edge(4, 5, color='yellow')
    graph.add_edge(5, 6, color='yellow')
    graph.add_edge(2, 7, color='yellow')    
    graph.add_edge(6, 7, color='yellow')    
    print (graph.nodes.data())
    pos = nx.multipartite_layout(graph, align='horizontal')#, subset_key='layer')#, arrows=True)
    # invert y coordinates
    pos = {key : [pos[key][0],-pos[key][1]] for key in pos}
    nx.draw_networkx(graph, pos=pos, arrows=True)
    plt.show()
    plt.clf()
    
    #G = random_dag(32,128)
    futures = {}
    analyses = nx.classes.function.get_node_attributes(graph, 'item')
    print (analyses)
    #with ThreadPoolExecutor(max_workers=1) as executor:
    for node in nx.topological_sort(graph):
            predecessors = list(graph.predecessors(node))
            inputs = []
            for p in predecessors:
                inputs.extend(futures[p])
            print (node, predecessors)
            if (len(inputs)>0):
                analyses[node].set_inputs(inputs)
            futures[node] = analyses[node].apply()
#            future = executor.submit(pow, 323, 1235)
#            print(future.result())
    print (futures[7])