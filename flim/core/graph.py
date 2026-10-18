#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  26 14:03:11 2022

@author: khs3z
"""

import logging

import matplotlib.pyplot as plt
import networkx as nx

# (edge color, face color) per node kind
NODE_COLORS = {
    "output": ((1.0, 0.5, 0.5), (1.0, 0.8, 0.8)),
    "plugin": ((0.5, 0.5, 1.0), (0.8, 0.8, 1.0)),
}
FAILED_EDGE_COLOR = (0.7, 0.0, 0.0)


class WorkflowGraph:
    """Plots the task graph recorded by :class:`flim.core.runner.FlowRun`.

    Plugin calls are drawn in blue, data/result nodes in red. Failed tasks have a
    dark red outline, skipped tasks are faded.
    """

    def __init__(self, flow_run):
        self.flow_run = flow_run
        self.graph = flow_run.graph

    def layout(self):
        """Returns node positions: one row per dependency level, top to bottom.

        Returns:
            dict: node -> (x, y) in character-width units.
        """
        pos = {}
        for level, nodes in enumerate(nx.topological_generations(self.graph)):
            nodes = sorted(nodes, key=lambda n: int(n[1:]))  # call order
            widths = [len(self.graph.nodes[n]["label"]) + 4 for n in nodes]
            x = -sum(widths) / 2
            for node, width in zip(nodes, widths):
                pos[node] = (x + width / 2, -level * 3)
                x += width
        return pos

    def get_plot(self, ax=None, fontsize=9, **callback):
        """Draws the graph.

        Args:
            ax: matplotlib Axes to draw into; a new figure is created if None.
            fontsize: label font size.
            callback: matplotlib event name -> handler, e.g. ``pick_event=...``.
                Node labels are pickable and carry the node id as ``gid``.

        Returns:
            (Figure, Axes)
        """
        pos = self.layout()
        if ax is None:
            if pos:
                xs = [x for x, _ in pos.values()]
                width = max(6, min(40, (max(xs) - min(xs) + 20) * 0.075))
                height = max(3, min(30, len({y for _, y in pos.values()}) * 0.6 + 1))
            else:
                width, height = 6, 3
            fig, ax = plt.subplots(figsize=(width, height))
        fig = ax.get_figure()
        ax.set_axis_off()

        for u, v in self.graph.edges():
            ax.annotate(
                "",
                xy=pos[v],
                xytext=pos[u],
                arrowprops=dict(arrowstyle="->", color="0.5", shrinkA=8, shrinkB=8),
            )
        for node, (x, y) in pos.items():
            attrs = self.graph.nodes[node]
            ec, fc = NODE_COLORS.get(attrs["kind"], NODE_COLORS["plugin"])
            if attrs["status"] == "failed":
                ec = FAILED_EDGE_COLOR
            ax.text(
                x,
                y,
                attrs["label"],
                ha="center",
                va="center",
                fontsize=fontsize,
                gid=node,
                alpha=0.4 if attrs["status"] == "skipped" else 1.0,
                bbox=dict(boxstyle="round", ec=ec, fc=fc),
                picker=bool(callback),
            )
        if pos:
            xs = [x for x, _ in pos.values()]
            ys = [y for _, y in pos.values()]
            ax.set_xlim(min(xs) - 10, max(xs) + 10)
            ax.set_ylim(min(ys) - 2, max(ys) + 2)
        ax.set_title(self.flow_run.name)

        for evt, routine in callback.items():
            try:
                fig.canvas.mpl_connect(evt, routine)
            except Exception:
                logging.debug(f"Could not connect {evt} for {routine} in {fig}")
        return fig, ax
