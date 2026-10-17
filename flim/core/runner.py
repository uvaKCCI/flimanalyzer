"""Runs flimanalyzer plugins as Prefect 3 tasks inside Prefect flows.

Workflows are written as plain Python that calls plugin instances, e.g.::

    def build():
        data = DataBucket(name="Input")(input=df, input_select=[0])
        summary = SummaryStats()(input=data, grouping=["Treatment"], features=["FLIRR"])
        KDE().map(input=unmapped(data), features=[["FLIRR"], ["trp t1"]])

    run = run_flow("My Workflow", build)

Inside :func:`run_flow` each plugin call becomes a Prefect task run and returns a
:class:`TaskOutput` handle. Handles can be indexed (``summary["Table: ..."]``) and
passed to other plugin calls; the dependencies between calls are recorded in
``run.graph`` (a networkx DiGraph) for the workflow plot.

Without a task runner, tasks run one after another in the calling thread, which is
required for plugins that create wx/matplotlib objects. With a task runner (e.g.
``prefect_dask.DaskTaskRunner``), tasks are submitted and run concurrently.
"""

import contextvars
import copy
import datetime
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional

import networkx as nx
from prefect import flow, tags, task, unmapped
from prefect.cache_policies import NO_CACHE
from prefect.futures import PrefectFuture

from flim.results import clean_path_component, save_results

__all__ = ["Parameter", "TaskOutput", "FlowRun", "run_flow", "select", "unmapped"]

_CURRENT_RUN = contextvars.ContextVar("flim_flow_run", default=None)
_MARKER = "__flim_task_output__"


def Parameter(name: str, default: Any = None) -> Any:
    """Stand-in for Prefect 1 ``Parameter``: returns the default value."""
    return default


class TaskOutput:
    """Handle to the (possibly not yet computed) result of a plugin call."""

    def __init__(self, ref: Any, node: Optional[str], keys: tuple = ()):
        self.ref = ref  # result value or PrefectFuture
        self.node = node  # graph node that produced the result
        self.keys = keys  # item lookups applied to the result

    def __getitem__(self, key):
        return TaskOutput(self.ref, self.node, self.keys + (key,))

    def value(self) -> Any:
        """Returns the result, waiting for it to be computed if necessary."""
        value = self.ref.result() if isinstance(self.ref, PrefectFuture) else self.ref
        for key in self.keys:
            value = value[key]
        return value

    def __repr__(self):
        return f"<TaskOutput node={self.node} keys={self.keys}>"


def _unwrap(obj: Any) -> Any:
    """Replaces TaskOutput markers (with futures already resolved) by their values."""
    if isinstance(obj, dict):
        if obj.get(_MARKER):
            value = obj["ref"]
            for key in obj["keys"]:
                value = value[key]
            return value
        return {k: _unwrap(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_unwrap(v) for v in obj)
    return obj


def _resolve(obj: Any) -> Any:
    """Replaces TaskOutput handles by their values (blocking)."""
    if isinstance(obj, TaskOutput):
        return obj.value()
    if isinstance(obj, dict):
        return {k: _resolve(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_resolve(v) for v in obj)
    return obj


@task(cache_policy=NO_CACHE, task_run_name="{label}")
def run_plugin(plugin, label: str, kwargs: Dict[str, Any], autosave: Optional[dict]):
    """Prefect task that runs a single plugin call."""
    results = plugin.run(**_unwrap(kwargs))
    if autosave:
        save_results(results, **autosave)
    return results


class FlowRun:
    """Records and executes the plugin calls made while a flow is running."""

    def __init__(self, name: str, submit: bool = False, autosave_dir: str = None):
        self.name = name
        self.submit = submit
        self.autosave_dir = autosave_dir
        self.start_time = datetime.datetime.now()
        self.graph = nx.DiGraph()
        self._label_counts = {}
        self._key_nodes = {}

    # graph bookkeeping -------------------------------------------------------
    def _add_node(self, label: str, kind: str, **attrs) -> str:
        node = f"n{len(self.graph)}"
        self.graph.add_node(node, label=label, kind=kind, status="pending", **attrs)
        return node

    def _key_node(self, node: str, keys: tuple) -> str:
        """Node representing an item (e.g. a table) of a plugin's result dict."""
        if not keys:
            return node
        cache_key = (node, keys)
        if cache_key not in self._key_nodes:
            label = " / ".join(str(k) for k in keys)
            key_node = self._add_node(label, "output")
            self.graph.add_edge(node, key_node)
            self._key_nodes[cache_key] = key_node
        return self._key_nodes[cache_key]

    def _to_payload(self, obj: Any, upstream: set) -> Any:
        """Converts TaskOutput handles into task arguments and collects upstream nodes."""
        if isinstance(obj, TaskOutput):
            if obj.node is not None:
                upstream.add(self._key_node(obj.node, obj.keys))
            return {_MARKER: True, "ref": obj.ref, "keys": obj.keys}
        if isinstance(obj, dict):
            return {k: self._to_payload(v, upstream) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return type(obj)(self._to_payload(v, upstream) for v in obj)
        return obj

    def _unique_label(self, label: str) -> str:
        n = self._label_counts.get(label, 0)
        self._label_counts[label] = n + 1
        return label if n == 0 else f"{label}-{n}"

    # execution -----------------------------------------------------------------
    def call(self, plugin, kwargs: Dict[str, Any], task_tags=None) -> TaskOutput:
        """Runs (or submits) one plugin call and returns a handle to its result."""
        # each call gets its own copy so calls don't share configuration
        plugin = copy.copy(plugin)
        plugin.params = dict(plugin.params)

        tag_list = [task_tags] if isinstance(task_tags, str) else list(task_tags or [])
        label = self._unique_label(plugin.name)
        node = self._add_node(label, getattr(plugin, "graph_kind", "plugin"), plugin=plugin)
        upstream = set()
        payload = self._to_payload(kwargs, upstream)
        for u in upstream:
            self.graph.add_edge(u, node)

        failed = [
            u for u in upstream if self.graph.nodes[u]["status"] in ("failed", "skipped")
        ]
        if failed:
            logging.warning(f"Skipping {label}: upstream task failed.")
            self.graph.nodes[node]["status"] = "skipped"
            return TaskOutput(None, node)

        autosave = None
        if self.autosave_dir:
            autosave = {
                "directory": os.path.join(
                    self.autosave_dir,
                    *[clean_path_component(t) for t in tag_list],
                ),
                "name": label,
            }

        with tags(*tag_list):
            if self.submit:
                ref = run_plugin.submit(plugin, label, payload, autosave)
                self.graph.nodes[node]["ref"] = ref
                return TaskOutput(ref, node)
            state = run_plugin(plugin, label, payload, autosave, return_state=True)
        if state.is_completed():
            value = state.result()
            self.graph.nodes[node].update(status="completed", ref=value)
            return TaskOutput(value, node)
        logging.error(f"{label} failed: {state.message}")
        self.graph.nodes[node].update(status="failed", message=state.message)
        return TaskOutput(None, node)

    def wait(self):
        """Waits for submitted tasks and records their final status."""
        for node, attrs in self.graph.nodes(data=True):
            ref = attrs.get("ref")
            if not isinstance(ref, PrefectFuture):
                continue
            ref.wait()
            if ref.state.is_completed():
                attrs.update(status="completed", ref=ref.result())
            else:
                attrs.update(status="failed", ref=None, message=ref.state.message)
                logging.error(f"{attrs['label']} failed: {ref.state.message}")

    def results(self) -> List[Any]:
        """Results of all completed plugin calls, in call order."""
        return [
            attrs["ref"]
            for _, attrs in self.graph.nodes(data=True)
            if "plugin" in attrs and attrs["status"] == "completed"
        ]

    @property
    def failed(self) -> List[str]:
        return [
            attrs["label"]
            for _, attrs in self.graph.nodes(data=True)
            if attrs["status"] == "failed"
        ]


def current_run() -> Optional[FlowRun]:
    """The FlowRun that is currently being executed, if any."""
    return _CURRENT_RUN.get()


def call_plugin(plugin, **kwargs):
    """Calls a plugin: runs it as a task inside a flow, or directly otherwise."""
    task_tags = kwargs.pop("task_tags", None)
    kwargs.pop("task_run_name", None)
    kwargs = {k: (v.value if isinstance(v, unmapped) else v) for k, v in kwargs.items()}
    run = current_run()
    if run is None:
        return plugin.run(**_resolve(kwargs))
    return run.call(plugin, kwargs, task_tags=task_tags)


def map_plugin(plugin, **kwargs) -> List[Any]:
    """Calls a plugin once per element of each mapped (not ``unmapped``) argument."""
    static = {k: v.value for k, v in kwargs.items() if isinstance(v, unmapped)}
    mapped = {k: v for k, v in kwargs.items() if not isinstance(v, unmapped)}
    for k, v in mapped.items():
        if isinstance(v, TaskOutput):
            # mapping over a list produced by another task
            mapped[k] = [TaskOutput(item, v.node) for item in v.value()]
    lengths = {len(v) for v in mapped.values()}
    if len(lengths) > 1:
        raise ValueError(
            f"{plugin.name}: mapped arguments differ in length:"
            f" { {k: len(v) for k, v in mapped.items()} }"
        )
    n = lengths.pop() if lengths else 0
    return [
        call_plugin(plugin, **static, **{k: v[i] for k, v in mapped.items()})
        for i in range(n)
    ]


def select(outputs, key_pattern: str = "(.*?)", value_pattern: str = None) -> list:
    """Selects result items whose key matches ``key_pattern`` from plugin outputs.

    If ``value_pattern`` is given, the matching items are expected to be lists and are
    flattened to the elements that match ``value_pattern``.
    """
    selected = []
    for out in outputs:
        is_handle = isinstance(out, TaskOutput)
        result = out.value() if is_handle else out
        if not isinstance(result, dict):
            continue
        for key, value in result.items():
            if not re.search(key_pattern, key):
                continue
            if value_pattern is None:
                selected.append(out[key] if is_handle else value)
            elif isinstance(value, list):
                for element in value:
                    if re.search(value_pattern, str(element)):
                        selected.append(
                            TaskOutput(element, out.node) if is_handle else element
                        )
    logging.debug(f"select {key_pattern}, {value_pattern}: {len(selected)} items")
    return selected


_PENDING_FLOW = contextvars.ContextVar("flim_pending_flow", default=None)


def _flow_body():
    """Body of every flimanalyzer flow.

    A module-level function (not a closure) so that the flow object, which Prefect
    sends to Dask workers, can be pickled by reference.
    """
    run, build = _PENDING_FLOW.get()
    token = _CURRENT_RUN.set(run)
    try:
        build()
        run.wait()
    finally:
        _CURRENT_RUN.reset(token)


def run_flow(
    name: str,
    build: Callable[[], Any],
    task_runner=None,
    autosave_dir: str = None,
) -> FlowRun:
    """Runs ``build`` as a Prefect flow; plugin calls inside it become task runs.

    Args:
        name: flow name shown in the Prefect UI.
        build: callable that makes the plugin calls.
        task_runner: Prefect task runner for concurrent execution; ``None`` runs the
            tasks sequentially in the calling thread.
        autosave_dir: if set, every task's results are saved below this directory
            (``<autosave_dir>/<timestamp>/<task tags>/``).

    Returns:
        FlowRun: recorded task graph and results.
    """
    run = FlowRun(name, submit=task_runner is not None)
    if autosave_dir:
        run.autosave_dir = os.path.join(
            autosave_dir, run.start_time.strftime("%Y-%m-%d_%H-%M-%S")
        )

    prefect_flow = flow(name=name, validate_parameters=False)(_flow_body)
    if task_runner is not None:
        prefect_flow = prefect_flow.with_options(task_runner=task_runner)
    token = _PENDING_FLOW.set((run, build))
    try:
        # failed tasks are recorded in run.graph; errors raised while building the
        # workflow itself propagate
        prefect_flow()
    finally:
        _PENDING_FLOW.reset(token)
    return run
