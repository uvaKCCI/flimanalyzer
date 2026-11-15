#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plot of the task graph of a workflow run."""

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.axes import Axes
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from flim.core.runner import FlowRun

logger = logging.getLogger(__name__)

# (edge color, face color) per node kind
NODE_COLORS = {
    "output": ((1.0, 0.5, 0.5), (1.0, 0.8, 0.8)),
    "tool": ((0.5, 0.5, 1.0), (0.8, 0.8, 1.0)),
}
FAILED_EDGE_COLOR = (0.7, 0.0, 0.0)


class WorkflowGraph:
    """Plots the task graph recorded by `flim.core.runner.FlowRun`.

    Tool calls are drawn in blue, input and result nodes in red. Failed tasks have a
    dark red outline, skipped tasks are faded.
    """

    def __init__(self, flow_run: "FlowRun") -> None:
        """Create the plot of a run's task graph.

        Args:
            flow_run: The run; its `graph` and `name` are plotted.
        """
        self.flow_run = flow_run
        self.graph = flow_run.graph

    def layout(self) -> dict[str, tuple[float, float]]:
        """Return the node positions: one row per dependency level, top to bottom.

        Within a row the nodes are in call order, each as wide as its label plus a
        gap, and the row is centred on x = 0. Rows are 3 units apart.

        Returns:
            The position `(x, y)` of each node, in character widths.
        """
        pos = {}
        for level, nodes in enumerate(nx.topological_generations(self.graph)):
            nodes = sorted(nodes, key=lambda n: int(n[1:]))  # call order
            # the label and a gap: boxed labels of neighbours don't touch
            widths = [len(self.graph.nodes[n]["label"]) + 6 for n in nodes]
            x = -sum(widths) / 2
            for node, width in zip(nodes, widths):
                pos[node] = (x + width / 2, -level * 3)
                x += width
        return pos

    def get_plot(
        self,
        ax: Optional[Axes] = None,
        fontsize: float = 9,
        **callback: Callable[..., Any],
    ) -> tuple[Figure, Axes]:
        """Draw the graph.

        Args:
            ax: The axes to draw into; None creates a figure whose size follows the
                graph's width and number of rows.
            fontsize: The label font size, in points. Defaults to 9.
            **callback: Handlers by matplotlib event name, e.g. `pick_event=...`.
                Node labels carry the node id as `gid`; they are pickable if
                callbacks are given. A handler that can't be connected is logged.

        Returns:
            The figure and the axes.
        """
        pos = self.layout()
        if ax is None:
            if pos:
                xs = [x for x, _ in pos.values()]
                # ~0.1 inch per character of a label (font size 9 and its box)
                width = max(6, min(40, (max(xs) - min(xs) + 20) * 0.1))
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
            ec, fc = NODE_COLORS.get(attrs["kind"], NODE_COLORS["tool"])
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
                logger.debug(f"Could not connect {evt} for {routine} in {fig}")
        return fig, ax
