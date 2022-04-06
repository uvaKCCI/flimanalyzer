#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  26 14:03:11 2022

@author: khs3z
"""

from flim.plugin import DataBucket

import graphviz
import networkx as nx
import networkx.drawing.nx_pydot
import networkx.drawing.nx_agraph
import networkx.classes.function
import pydot
import matplotlib.pyplot as plt

        
class WorkflowGraph():

    def __init__(self, flow):
        self.flow = flow
        self.graph = None
        
    def _clean_label(self, l):
        return l.lstrip().rstrip().replace('"', '')
        
    def create_graph(self, state=None):
        task_refs = self.flow.get_tasks()
        vgraph = self.flow.visualize(filename="workflow", format="svg", flow_state=state)

        output_ids = [id(tr) for tr in task_refs if isinstance(tr, DataBucket)]
        plugin_ids = [id(tr) for tr in task_refs if not isinstance(tr, DataBucket)]
        
        pydotgraph = pydot.graph_from_dot_data(vgraph.source)[0]
        g = networkx.drawing.nx_pydot.from_pydot(pydotgraph)

        self.node_labels = {n.get_name():self._clean_label(n.get_label()) for n in pydotgraph.get_nodes()}
        self.output_nodes = [n for n in networkx.classes.function.nodes(g) if int(n) in output_ids]
        self.plugin_nodes = [n for n in networkx.classes.function.nodes(g) if int(n) in plugin_ids]
        #output_node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes() if int(n.get_name()) in output_ids}
        #plugin_node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes() if int(n.get_name()) in plugin_ids}
        #print (f'output_ids={sorted(output_ids)}')
        #print (f'plugin_ids={sorted(plugin_ids)}')
        #print (f'output_nodes={self.output_nodes}')
        #print (f'plugin_nodes={self.plugin_nodes}')
        #print (f'output_node_labels={output_node_labels}')
        #print (f'plugin_node_labels={plugin_node_labels}')

        self.graph = g        
        return self.graph
        
    def get_plot(self, ax=None):
        if not self.graph:
            self.create_graph()
        if not ax:
            fig, ax = plt.subplots() 
        pos = nx.drawing.nx_agraph.graphviz_layout(self.graph, prog='dot', args='-Grankdir="LR"')
        nx.draw_networkx_nodes(self.graph, pos, ax=ax, nodelist=self.output_nodes, node_color='blue', node_shape='s')
        nx.draw_networkx_nodes(self.graph, pos, ax=ax, nodelist=self.plugin_nodes, node_color='red', node_shape='o')
        nx.draw_networkx_edges(self.graph, pos, ax=ax)
        nx.draw_networkx_labels(self.graph, pos, ax=ax, labels=self.node_labels)
        return fig, ax
        
        
    