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

Every plugin call is submitted to the flow's task runner: Prefect starts a task once
its inputs (results of other tasks) are ready and runs independent tasks concurrently,
up to the task runner's number of workers and the tag concurrency limits configured on
the Prefect server (each task is tagged with its ``task_tags``). Without an explicit
task runner, a ``ThreadPoolTaskRunner`` with :func:`default_max_workers` threads is
used. Plugins that draw figures hold :data:`pyplot_lock`, as pyplot is not thread-safe.
"""

import contextlib
import contextvars
import copy
import datetime
import logging
import os
import re
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

import matplotlib.figure
import networkx as nx
from prefect import flow, tags, task, unmapped
from prefect.cache_policies import NO_CACHE
from prefect.context import FlowRunContext
from prefect.futures import PrefectFuture
from prefect.settings import get_current_settings
from prefect.states import Cancelled
from prefect.task_runners import ThreadPoolTaskRunner

from flim.results import clean_path_component, save_results

__all__ = [
    "Parameter",
    "TaskOutput",
    "FlowRun",
    "run_flow",
    "select",
    "unmapped",
    "pyplot_lock",
    "default_max_workers",
    "default_task_runner",
    "TaskCancelled",
    "CancelToken",
]

_CURRENT_RUN = contextvars.ContextVar("flim_flow_run", default=None)
_MARKER = "__flim_task_output__"

# pyplot's figure registry and current-figure state are shared by all threads: tasks
# that draw figures take turns, all other tasks run concurrently
pyplot_lock = threading.RLock()


class TaskCancelled(Exception):
    """Raised by :meth:`flim.plugin.AbstractPlugin.cancel` to stop the running task.

    Prefect handles it like any other exception (the task run ends Failed and tasks
    that depend on it are not run); the runner records the task as cancelled.
    """


class _RunCancelled(Exception):
    """Stops the workflow script once the run has been cancelled."""


class CancelToken:
    """Run-wide cancel signal, see :meth:`flim.plugin.AbstractPlugin.check_cancelled`.

    A threading.Event in this process; with a Dask task runner it is mirrored in a
    ``distributed.Event`` so that tasks running in other processes see it too.
    """

    def __init__(self):
        self.name = f"flim-cancel-{uuid.uuid4()}"
        self._local = threading.Event()
        self._client = None  # Dask client, set when the flow uses Dask
        self._dask = False

    def use_dask(self, client):
        self._client = client
        self._dask = True

    def set(self):
        """Requests cancellation of the run."""
        if self._local is not None:
            self._local.set()
        if self._dask:
            try:
                import distributed

                distributed.Event(self.name, client=self._client).set()
            except Exception:
                logging.exception("Could not signal cancellation to the Dask workers")

    def is_set(self) -> bool:
        if self._local is not None:
            return self._local.is_set()
        if self._dask:  # unpickled in a Dask worker process
            try:
                import distributed

                return distributed.Event(self.name).is_set()
            except Exception:
                return False
        return False

    def __getstate__(self):
        # events and clients cannot be pickled; workers use the distributed.Event
        return {"name": self.name, "_dask": self._dask}

    def __setstate__(self, state):
        self.__dict__.update(state, _local=None, _client=None)


def default_max_workers() -> int:
    """Number of threads for concurrent tasks: Prefect's ``thread_pool_max_workers``
    setting if set, otherwise the number of CPUs."""
    return get_current_settings().tasks.runner.thread_pool_max_workers or os.cpu_count() or 1


def default_task_runner(max_workers: Optional[int] = None) -> ThreadPoolTaskRunner:
    """Thread pool task runner; ``max_workers=1`` runs one task at a time."""
    return ThreadPoolTaskRunner(max_workers=max_workers or default_max_workers())


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
        """Returns the result, waiting for it to be computed if necessary.

        Returns None if the task did not complete (failed or skipped).
        """
        value = self.ref
        if isinstance(value, PrefectFuture):
            value.wait()
            if not value.state.is_completed():
                return None
            value = value.result()
        for key in self.keys:
            if value is None:
                return None
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


def _run_plugin(plugin, kwargs: Dict[str, Any]):
    """Runs a plugin; plugins that draw figures hold pyplot_lock.

    Kept out of the task function: Dask pickles that by value together with the
    globals it uses, and a lock cannot be pickled.
    """
    plugin.check_cancelled()  # tasks that start after a cancel stop right away
    draws = getattr(plugin, "draws_figures", False)
    with pyplot_lock if draws else contextlib.nullcontext():
        results = plugin.run(**_unwrap(kwargs))
    _release_figures(results)
    return results


def _release_figures(results):
    """Removes result figures from pyplot's registry, which keeps every figure it
    created until it is closed. The figures stay usable (saving, showing)."""
    if not isinstance(results, dict):
        return
    figures = [v for v in results.values() if isinstance(v, matplotlib.figure.Figure)]
    if figures:
        import matplotlib.pyplot as plt

        with pyplot_lock:
            for figure in figures:
                plt.close(figure)


def _retry_unless_cancelled(task, task_run, state) -> bool:
    """A cancelled task is never retried, even if retries are configured."""
    try:
        state.result()  # re-raises the task's exception
    except TaskCancelled:
        return False
    except Exception:
        return True
    return True


@task(
    cache_policy=NO_CACHE,
    task_run_name="{label}",
    retry_condition_fn=_retry_unless_cancelled,
)
def run_plugin(plugin, label: str, kwargs: Dict[str, Any], autosave: Optional[dict]):
    """Prefect task that runs a single plugin call."""
    results = _run_plugin(plugin, kwargs)
    if autosave:
        save_results(results, **autosave)
    return results


class FlowRun:
    """Records and executes the plugin calls made while a flow is running."""

    def __init__(
        self,
        name: str,
        autosave_dir: str = None,
        on_progress: Optional[Callable[[int, int, str, bool], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ):
        """
        Args:
            name: flow name.
            autosave_dir: directory to save task results in, ``None`` disables saving.
            on_progress: called as ``on_progress(done, total, label, complete)`` when
                a task is submitted or finishes, from the thread that submitted or ran
                it; ``total`` counts the tasks submitted so far, ``complete`` is True
                once the workflow script has made all its calls (no more tasks).
            cancel_token: signal that cancels the run when set.
        """
        self.name = name
        self.autosave_dir = autosave_dir
        self.on_progress = on_progress
        self.cancel_token = cancel_token or CancelToken()
        self.flow_run_id = None
        self.state = "running"  # completed, cancelled or failed when the run ends
        self.complete = False  # True once the workflow script has made all its calls
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.graph = nx.DiGraph()
        self._label_counts = {}
        self._key_nodes = {}
        self._lock = threading.RLock()

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
        plugin._cancel_token = self.cancel_token

        tag_list = [task_tags] if isinstance(task_tags, str) else list(task_tags or [])
        label = self._unique_label(plugin.name)
        node = self._add_node(label, getattr(plugin, "graph_kind", "plugin"), plugin=plugin)
        upstream = set()
        payload = self._to_payload(kwargs, upstream)
        for u in upstream:
            self.graph.add_edge(u, node)

        if self.cancel_token.is_set():
            with self._lock:
                self.graph.nodes[node].update(status="cancelled", message="Run cancelled")
            self._report_progress(label)
            raise _RunCancelled()

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

        # Prefect starts the task once the futures among its inputs are completed and
        # skips it (state NotReady) if one of them did not complete
        with tags(*tag_list):
            ref = run_plugin.submit(plugin, label, payload, autosave)
        with self._lock:
            self.graph.nodes[node]["ref"] = ref
        self._report_progress(label)
        ref.add_done_callback(lambda future, node=node: self._record(node))
        return TaskOutput(ref, node)

    def _record(self, node: str):
        """Records the final status of a finished task (once)."""
        with self._lock:
            attrs = self.graph.nodes[node]
            ref = attrs.get("ref")
            if not isinstance(ref, PrefectFuture):
                return  # already recorded
            ref.wait()  # done: stores the final state, which `state` would else read from the API
            state = ref.state
            if state.is_completed():
                attrs.update(status="completed", ref=ref.result())
            elif state.is_pending() and state.name == "NotReady":
                attrs.update(status="skipped", ref=None, message=state.message)
                logging.warning(f"Skipped {attrs['label']}: upstream task did not complete.")
            elif isinstance(exc := ref.result(raise_on_failure=False), TaskCancelled):
                attrs.update(status="cancelled", ref=None, message=str(exc) or "Cancelled")
                logging.info(f"{attrs['label']} cancelled: {attrs['message']}")
            else:
                attrs.update(status="failed", ref=None, message=state.message)
                logging.error(f"{attrs['label']} failed: {state.message}")
        self._report_progress(attrs["label"])

    def _report_progress(self, label: str):
        if self.on_progress is None:
            return
        with self._lock:
            tasks = [a for _, a in self.graph.nodes(data=True) if "plugin" in a]
            done = sum(a["status"] != "pending" for a in tasks)
        try:
            self.on_progress(done, len(tasks), label, self.complete)
        except Exception:
            logging.exception("Progress callback failed")

    def wait(self):
        """Waits for all submitted tasks and records their final status."""
        for node, attrs in list(self.graph.nodes(data=True)):
            ref = attrs.get("ref")
            if isinstance(ref, PrefectFuture):
                ref.wait()
                self._record(node)

    def results(self) -> List[Any]:
        """Results of all completed plugin calls, in call order."""
        return [
            attrs["ref"]
            for _, attrs in self.graph.nodes(data=True)
            if "plugin" in attrs and attrs["status"] == "completed"
        ]

    def _labels(self, status: str) -> List[str]:
        return [a["label"] for _, a in self.graph.nodes(data=True) if a["status"] == status]

    @property
    def failed(self) -> List[str]:
        return self._labels("failed")

    @property
    def cancelled(self) -> List[str]:
        return self._labels("cancelled")

    def cancel(self):
        """Cancels the run: no new tasks start, and running tasks stop at their next
        :meth:`~flim.plugin.AbstractPlugin.check_cancelled`."""
        self.cancel_token.set()

    def task_counts(self) -> Dict[str, int]:
        """Number of tasks per status (completed, failed, cancelled, skipped, ...)."""
        counts = {}
        for _, attrs in self.graph.nodes(data=True):
            if "plugin" in attrs:
                counts[attrs["status"]] = counts.get(attrs["status"], 0) + 1
        return counts

    @property
    def ui_url(self) -> Optional[str]:
        """Link to the flow run in the Prefect UI, None without a Prefect server."""
        if self.flow_run_id is None:
            return None
        from prefect.utilities.urls import url_for

        return url_for("flow-run", obj_id=self.flow_run_id)

    def write_summary(self) -> Optional[str]:
        """Writes ``run_summary.txt`` into the results directory, if there is one."""
        if not self.autosave_dir:
            return None
        os.makedirs(self.autosave_dir, exist_ok=True)
        counts = self.task_counts()
        tasks = [a for _, a in self.graph.nodes(data=True) if "plugin" in a]
        width = max([len(a["label"]) for a in tasks] + [4])
        lines = [
            "FLIMAnalyzer run summary",
            "",
            f"Flow:       {self.name}",
            f"State:      {self.state}",
            f"Started:    {self.start_time:%Y-%m-%d %H:%M:%S}",
            f"Finished:   {self.end_time:%Y-%m-%d %H:%M:%S}" if self.end_time else "Finished:",
            f"Prefect:    {self.ui_url or self.flow_run_id or '-'}",
            f"Results:    {self.autosave_dir}",
            "Tasks:      " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())),
            "",
            f"{'Task'.ljust(width)}  {'Status'.ljust(9)}  Message",
        ]
        for a in tasks:
            message = (a.get("message") or "").replace("\n", " ")
            lines.append(f"{a['label'].ljust(width)}  {a['status'].ljust(9)}  {message}".rstrip())
        path = os.path.join(self.autosave_dir, "run_summary.txt")
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        return path


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
            mapped[k] = [TaskOutput(item, v.node) for item in v.value() or []]
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
    context = FlowRunContext.get()
    if context is not None and context.flow_run is not None:
        run.flow_run_id = context.flow_run.id
    task_runner = getattr(context, "task_runner", None)
    if type(task_runner).__name__ == "DaskTaskRunner":
        # let tasks in other processes see a cancel; the client (and a local
        # cluster) is created on first access, which submitting would do anyway
        run.cancel_token.use_dask(task_runner.client)
    token = _CURRENT_RUN.set(run)
    try:
        try:
            build()
        except _RunCancelled:
            pass
        run.complete = True
        run._report_progress("")
        run.wait()
    finally:
        _CURRENT_RUN.reset(token)
    if run.cancel_token.is_set():
        return Cancelled(message="Cancelled by the user")


def run_flow(
    name: str,
    build: Callable[[], Any],
    task_runner=None,
    autosave_dir: str = None,
    on_progress: Optional[Callable[[int, int, str, bool], None]] = None,
    cancel_token: Optional[CancelToken] = None,
) -> FlowRun:
    """Runs ``build`` as a Prefect flow; plugin calls inside it become task runs.

    Args:
        name: flow name shown in the Prefect UI.
        build: callable that makes the plugin calls.
        task_runner: Prefect task runner; ``None`` uses :func:`default_task_runner`.
        autosave_dir: if set, every task's results are saved below this directory
            (``<autosave_dir>/<timestamp>/<task tags>/``).
        on_progress: see :class:`FlowRun`.
        cancel_token: :class:`CancelToken` that cancels the run when set, e.g. from
            another thread.

    Returns:
        FlowRun: recorded task graph and results; ``state`` is completed,
        cancelled or failed (some tasks failed).
    """
    run = FlowRun(name, on_progress=on_progress, cancel_token=cancel_token)
    if autosave_dir:
        run.autosave_dir = os.path.join(
            autosave_dir, run.start_time.strftime("%Y-%m-%d_%H-%M-%S")
        )

    if task_runner is None:
        task_runner = default_task_runner()
    prefect_flow = flow(name=name, validate_parameters=False, task_runner=task_runner)(
        _flow_body
    )
    token = _PENDING_FLOW.set((run, build))
    try:
        state = prefect_flow(return_state=True)
    finally:
        _PENDING_FLOW.reset(token)
        run.end_time = datetime.datetime.now()
    if state.is_cancelled():
        run.state = "cancelled"
    elif state.is_completed():
        run.state = "failed" if run.failed else "completed"
    else:
        run.state = "failed"
    run.write_summary()
    if not (state.is_completed() or state.is_cancelled()):
        # failed tasks are recorded in run.graph; errors raised while building the
        # workflow itself propagate
        state.result()
    return run
