#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  26 14:03:11 2022

@author: khs3z
"""

from flim.plugin import DataBucket

import ctypes
import graphviz
import io
import logging
import networkx as nx
import networkx.drawing.nx_pydot
import networkx.drawing.nx_agraph
import networkx.classes.function
import math
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import os
import pendulum
import prefect
import pydot

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.text import Text
from matplotlib.textpath import TextPath
from matplotlib.patches import PathPatch, FancyBboxPatch
from matplotlib.font_manager import FontProperties


class WorkflowGraph:
    def __init__(self, flow, state):
        self.flow = flow
        self.state = state
        self.graph = None
        self.pydotgraph = None

    def _clean_label(self, l):
        return l.lstrip().rstrip().replace('"', "")

    def _closest_match(self, id, target_ids):
        return [t for t in target_ids if id == t[: len(id)]]

    def create_graph(self):
        task_refs = self.flow.get_tasks()
        vgraph = self.flow.visualize(
            filename="workflow", format="svg", flow_state=self.state
        )
        self.pydotgraph = pydot.graph_from_dot_data(vgraph.source)[0]
        g = networkx.drawing.nx_pydot.from_pydot(self.pydotgraph)

        self.node_labels = {
            n.get_name(): self._clean_label(n.get_label())
            for n in self.pydotgraph.get_nodes()
        }

        plugin_ids = [id(tr) for tr in task_refs]

        # create dict that uses the node label as key, and the id of the task result state object
        self.obj_ids = {}
        for tr in task_refs:
            result = self.state.result[tr]._result
            if not self.state.result[tr].is_mapped(): 
                self.obj_ids[id(tr)] = id(self.state.result[tr])
            else:
                for map_index,s in enumerate(self.state.result[tr].map_states):
                    newid  = str(id(tr)) + str(map_index)
                    self.obj_ids[int(newid)] = id(s)
            # loaded = [self.state.result[tr].load_result() for tr in task_refs]

        output_ids = [id(tr) for tr in task_refs if isinstance(tr, DataBucket)]
        plugin_ids = [id(tr) for tr in task_refs if not isinstance(tr, DataBucket)]

        logging.debug(f"output_ids={sorted(output_ids)}")
        logging.debug(f"plugin_ids={sorted(plugin_ids)}")

        self.output_nodes = [
            n for n in networkx.classes.function.nodes(g) if int(n) in output_ids
        ]
        self.plugin_nodes = [
            n for n in networkx.classes.function.nodes(g) if int(n) in plugin_ids
        ]

        self.graph = g
        return self.graph

    def get_plot(self, ax=None, fontsize=12, **callback):
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
                    label=self.obj_ids.get(int(node_id), None),
                    boxstyle="round",
                    ec=ecs[node_id],
                    fc=fcs[node_id],
                    picker=(callback is not None),
                )
            )
            tp = TextPath(
                (originx, originy),
                self.node_labels.get(node_id, "Not found"),
                size=fontsize,
                prop=fp,
            )
            ax.set_aspect(1.0)
            ax.add_patch(PathPatch(tp, color="black"))

        for evt, routine in callback.items():
            try:
                fig.canvas.mpl_connect(evt, routine)
            except:
                logging.debug(f"Could not connect {evt} for {routine} in {fig}")
        return fig, ax
