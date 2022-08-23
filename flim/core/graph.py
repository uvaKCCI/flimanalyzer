#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  26 14:03:11 2022

@author: khs3z
"""

from flim.plugin import DataBucket

import io
import math
import matplotlib.image as mpimg
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.text import Text
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch, FancyBboxPatch
from matplotlib.font_manager import FontProperties

import graphviz
import networkx as nx
import networkx.drawing.nx_pydot
import networkx.drawing.nx_agraph
import networkx.classes.function
import pydot
import matplotlib.pyplot as plt

import logging


class WorkflowGraph:
    def __init__(self, flow):
        self.flow = flow
        self.graph = None
        self.pydotgraph = None

    def _clean_label(self, l):
        return l.lstrip().rstrip().replace('"', "")

    def create_graph(self, state=None):
        task_refs = self.flow.get_tasks()
        vgraph = self.flow.visualize(filename="workflow", format="svg", flow_state=state)

        output_ids = [id(tr) for tr in task_refs if isinstance(tr, DataBucket)]
        plugin_ids = [id(tr) for tr in task_refs if not isinstance(tr, DataBucket)]
        self.obj_ids = {
            id(tr): (
                id(list(tr.input.values())[0]) if isinstance(tr, DataBucket) else id(tr)
            )
            for tr in task_refs
        }
        logging.debug(f"output_ids={sorted(output_ids)}")
        logging.debug(f"plugin_ids={sorted(plugin_ids)}")

        self.pydotgraph = pydot.graph_from_dot_data(vgraph.source)[0]
        g = networkx.drawing.nx_pydot.from_pydot(self.pydotgraph)

        self.node_labels = {
            n.get_name(): self._clean_label(n.get_label())
            for n in self.pydotgraph.get_nodes()
        }
        self.output_nodes = [
            n for n in networkx.classes.function.nodes(g) if int(n) in output_ids
        ]
        self.plugin_nodes = [
            n for n in networkx.classes.function.nodes(g) if int(n) in plugin_ids
        ]
        # output_node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes() if int(n.get_name()) in output_ids}
        # plugin_node_labels = {n.get_name():n.get_label() for n in pydotgraph.get_nodes() if int(n.get_name()) in plugin_ids}
        # print (f'output_ids={sorted(output_ids)}')
        # print (f'plugin_ids={sorted(plugin_ids)}')
        # print (f'output_nodes={self.output_nodes}')
        # print (f'plugin_nodes={self.plugin_nodes}')
        # print (f'output_node_labels={output_node_labels}')
        # print (f'plugin_node_labels={plugin_node_labels}')

        self.graph = g
        return self.graph

    def get_plot(self, ax=None, fontsize=16, callback=None):
        if not self.graph:
            self.create_graph()
        if not ax:
            fig, ax = plt.subplots()

        # render the `pydot` by calling `dot`, no file saved to disk
        png_str = self.pydotgraph.create_png(prog="dot")
        # treat the DOT output as an image file
        sio = io.BytesIO()
        sio.write(png_str)
        sio.seek(0)
        img = mpimg.imread(sio)
        # plot the image
        # ax.imshow(img, aspect='equal')

        pos = nx.drawing.nx_agraph.graphviz_layout(
            self.graph, prog="dot"
        )  # , args='-Grankdir="LR"')
        # print (f'pos.keys()={sorted(pos.keys())}')
        # nx.draw_networkx_nodes(self.graph, pos, ax=ax, nodelist=self.output_nodes, node_color='blue', node_shape='o', alpha=0.5)
        # nx.draw_networkx_nodes(self.graph, pos, ax=ax, nodelist=self.plugin_nodes, node_color='red', node_shape='s', alpha=0.5)
        nx.draw_networkx_edges(self.graph, pos, ax=ax)
        # nx.draw_networkx_labels(self.graph, pos, ax=ax, labels=self.node_labels)
        ecs = {
            node_id: (1.0, 0.5, 0.5) if node_id in self.output_nodes else (0.5, 0.5, 1.0)
            for node_id in pos.keys()
        }
        fcs = {
            node_id: (1.0, 0.8, 0.8) if node_id in self.output_nodes else (0.8, 0.8, 1.0)
            for node_id in pos.keys()
        }

        # dummy to get standard text box height for given fontsize
        fp = FontProperties(style="normal", weight="light")
        tp = TextPath((0, 0), "Test q [](){}%", size=fontsize, prop=fp)
        box = tp.get_extents()
        _, _, _, height = box.bounds
        for node_id, (x, y) in pos.items():
            tp = TextPath((x, y), self.node_labels[node_id], size=fontsize, prop=fp)
            box = tp.get_extents()
            _, _, width, _ = box.bounds
            originx = x - int(0.5 * width)
            originy = y - int(0.5 * height)
            width_box = width + 10
            height_box = math.ceil(1.25 * height)
            originx_box = x - int(0.5 * width_box)
            originy_box = y - int(0.5 * height_box)
            ax.add_patch(
                FancyBboxPatch(
                    (originx_box, originy_box),
                    width=width_box,
                    height=height_box,
                    label=self.obj_ids[int(node_id)],
                    boxstyle="round",
                    ec=ecs[node_id],
                    fc=fcs[node_id],
                    picker=(callback is not None),
                )
            )
            tp = TextPath(
                (originx, originy), self.node_labels[node_id], size=fontsize, prop=fp
            )
            ax.set_aspect(1.0)
            ax.add_patch(PathPatch(tp, color="black"))

        if callback is not None:
            fig.canvas.mpl_connect("pick_event", callback)
        return fig, ax
