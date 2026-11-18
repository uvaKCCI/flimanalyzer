"""Runs flimanalyzer tools as Prefect 3 tasks inside Prefect flows.

Workflows are written as plain Python that calls tools (`flim.core.tool.Tool`),
e.g.::

    def build():
        data = workflow_input(df)
        summary = Summarize()(
            data, config=SummaryConfig(grouping=["Treatment"], features=["FLIRR"])
        )
        for feature in ("FLIRR", "trp t1"):
            KDE()(data, config=KDEConfig(features=[feature]))

    run = run_flow("My Workflow", build)

Inside `run_flow` each tool call becomes a Prefect task run and returns a
`TaskOutput` handle. Handles can be indexed (`summary["Table: ..."]`) and passed to
other tool calls; the dependencies between calls are recorded in `run.graph` (a
networkx DiGraph) for the workflow plot.

Every tool call is submitted to the flow's task runner: Prefect starts a task once
its inputs (results of other tasks) are ready and runs independent tasks concurrently,
up to the task runner's number of workers and the tag concurrency limits configured on
the Prefect server (each task is tagged with its `task_tags` and its tool's name).
Without an explicit task runner, a `ThreadPoolTaskRunner` with `default_workers`
threads is used. Tools that draw figures hold `pyplot_lock`, as pyplot is not
thread-safe.
"""

import contextlib
import contextvars
import copy
from dataclasses import dataclass
import datetime
import logging
import os
from pathlib import Path
import re
import threading
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence, Union

import networkx as nx
from prefect import flow, tags, task, unmapped
from prefect.cache_policies import NO_CACHE
from prefect.context import FlowRunContext
from prefect.futures import PrefectFuture
from prefect.settings import get_current_settings
from prefect.states import Cancelled, Completed, State
from prefect.task_runners import TaskRunner, ThreadPoolTaskRunner

from flim.core.deprecation import deprecated_names
from flim.core.tool import TaskCancelled, Tool, pyplot_lock, release_figures
from flim.core.types import DataType, FileType
from flim.core.paths import unique_run_folder  # noqa: F401  (also used from here)
from flim.core.paths import DEFAULT_CHAR_REPLACEMENTS, path_name
from flim.results import save_results

if TYPE_CHECKING:
    from prefect import Task
    from prefect.client.schemas.objects import TaskRun

    from flim.core.config import TaskConfig

logger = logging.getLogger(__name__)

# names of 0.6 that were renamed (PEP 562: resolved with a DeprecationWarning)
__getattr__ = deprecated_names(
    __name__, {"default_max_workers": ("flim.core.runner", "default_workers", "0.8.0")}
)

__all__ = [
    "Parameter",
    "TaskOutput",
    "FlowRun",
    "run_flow",
    "select",
    "unmapped",
    "pyplot_lock",
    "default_workers",
    "default_task_runner",
    "TaskCancelled",
    "CancelToken",
]

_CURRENT_RUN = contextvars.ContextVar("flim_flow_run", default=None)
# tags put in front of the task tags of every call made inside (`tag_prefix`), e.g.
# the input a workflow defined in code runs on: they name the first results folders
_TAG_PREFIX: contextvars.ContextVar = contextvars.ContextVar("flim_tag_prefix", default=())


@contextlib.contextmanager
def tag_prefix(*tags: str) -> Iterator[None]:
    """Put tags in front of the task tags of the calls made inside the block.

    Args:
        *tags: The tags, e.g. the name of the input a workflow runs on.

    Yields:
        Nothing; the prefix is removed when the block ends.
    """
    token = _TAG_PREFIX.set(_TAG_PREFIX.get() + tuple(tags))
    try:
        yield
    finally:
        _TAG_PREFIX.reset(token)
_MARKER = "__flim_task_output__"
_AFTER = "__flim_after__"  # tasks a tool call waits for, see call_tool



class _RunCancelled(Exception):
    """Stops the workflow script once the run has been cancelled."""


class CancelToken:
    """Run-wide cancel signal, see `flim.core.tool.Tool.check_cancelled`.

    A `threading.Event` in this process; with a Dask task runner it is mirrored in a
    `distributed.Event` so that tasks running in other processes see it too.
    """

    def __init__(self) -> None:
        """Create a signal that is not set, with a unique name for Dask."""
        self.name = f"flim-cancel-{uuid.uuid4()}"
        self._local = threading.Event()
        self._client = None  # Dask client, set when the flow uses Dask
        self._dask = False

    def use_dask(self, client: Any) -> None:
        """Mirror the signal in a `distributed.Event` of a Dask client.

        Args:
            client: The `distributed.Client` of the flow's Dask task runner.
        """
        self._client = client
        self._dask = True

    def set(self) -> None:
        """Request cancellation of the run.

        A failure to set the Dask event is logged, not raised.
        """
        if self._local is not None:
            self._local.set()
        if self._dask:
            try:
                import distributed

                distributed.Event(self.name, client=self._client).set()
            except Exception:
                logger.exception("Could not signal cancellation to the Dask workers")

    def is_set(self) -> bool:
        """Return whether cancellation has been requested.

        In a Dask worker process the `distributed.Event` is read; False if it can't
        be read.
        """
        if self._local is not None:
            return self._local.is_set()
        if self._dask:  # unpickled in a Dask worker process
            try:
                import distributed

                return distributed.Event(self.name).is_set()
            except Exception:
                return False
        return False

    def __getstate__(self) -> Dict[str, Any]:
        """Return the name and the Dask flag only, for pickling."""
        # events and clients cannot be pickled; workers use the distributed.Event
        return {"name": self.name, "_dask": self._dask}

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Restore a pickled signal, without a local event or client."""
        self.__dict__.update(state, _local=None, _client=None)


def elapsed(start: datetime.datetime, end: datetime.datetime) -> str:
    """Return the time from `start` to `end` as hours, minutes and seconds.

    Args:
        start: When the run started.
        end: When it finished.

    Returns:
        For example `0:02:05`, or `27:00:00` for more than a day.
    """
    seconds = max(0, round((end - start).total_seconds()))
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def default_workers() -> int:
    """Return the number of threads for concurrent tasks.

    Returns:
        Prefect's `thread_pool_max_workers` setting if set, otherwise the number of
        CPUs (1 if unknown).
    """
    return get_current_settings().tasks.runner.thread_pool_max_workers or os.cpu_count() or 1


def default_task_runner(workers: Optional[int] = None) -> ThreadPoolTaskRunner:
    """Create a thread pool task runner.

    Args:
        workers: Number of tasks run at the same time; 1 runs one task at a time.
            Defaults to `default_workers()`.

    Returns:
        A Prefect `ThreadPoolTaskRunner`.
    """
    return ThreadPoolTaskRunner(max_workers=workers or default_workers())


def Parameter(name: str, default: Any = None) -> Any:
    """Stand in for the `Parameter` of Prefect 1: return the default value.

    Args:
        name: The parameter's name; not used.
        default: The value.

    Returns:
        `default`.
    """
    return default


@dataclass(frozen=True)
class Nth:
    """A key that selects a tool's result by position.

    `Nth(2)` is its second output, in the order the tool returns them (a workflow
    file's `"4.2"`).
    """

    number: int  # from 1

    def __str__(self) -> str:
        """Return `output <number>`."""
        return f"output {self.number}"


def _lookup(value: Any, key: Any) -> Any:
    """Return `value[key]`; an `Nth` key selects by position."""
    if isinstance(key, Nth):
        values = list(value.values())
        if key.number > len(values):
            raise KeyError(f"no {key}: the step has {len(values)} output(s)")
        return values[key.number - 1]
    return value[key]


class TaskOutput:
    """Handle to the (possibly not yet computed) result of a tool call."""

    def __init__(self, ref: Any, node: Optional[str], keys: tuple = ()) -> None:
        """Create a handle.

        Args:
            ref: The result value, or the `PrefectFuture` of the task.
            node: The graph node of the task that produced the result; None if there
                is none.
            keys: The item lookups applied to the result, in order.
        """
        self.ref = ref  # result value or PrefectFuture
        self.node = node  # graph node that produced the result
        self.keys = keys  # item lookups applied to the result

    def __getitem__(self, key: Any) -> "TaskOutput":
        """Return a handle to an item of the result, e.g. a table, or an `Nth` key."""
        return TaskOutput(self.ref, self.node, self.keys + (key,))

    def value(self) -> Any:
        """Return the result, waiting for it to be computed if necessary.

        Returns:
            The result with the item lookups applied; None if the task did not
            complete (failed, cancelled or skipped).

        Raises:
            KeyError: If the result has no item for a key.
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
            value = _lookup(value, key)
        return value

    def __repr__(self) -> str:
        """Return the node and the keys."""
        return f"<TaskOutput node={self.node} keys={self.keys}>"


def _unwrap(obj: Any) -> Any:
    """Replace TaskOutput markers (with futures already resolved) by their values."""
    if isinstance(obj, dict):
        if obj.get(_MARKER):
            value = obj["ref"]
            for key in obj["keys"]:
                value = _lookup(value, key)
            return value
        return {k: _unwrap(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_unwrap(v) for v in obj)
    return obj


def _resolve(obj: Any) -> Any:
    """Replace TaskOutput handles by their values (blocking)."""
    if isinstance(obj, TaskOutput):
        return obj.value()
    if isinstance(obj, dict):
        return {k: _resolve(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_resolve(v) for v in obj)
    return obj


def _run_tool(tool: Tool, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Run a tool; tools that draw figures hold pyplot_lock.

    Kept out of the task function: Dask pickles that by value together with the
    globals it uses, and a lock cannot be pickled.
    """
    tool.check_cancelled()  # tasks that start after a cancel stop right away
    draws = getattr(tool, "draws_figures", False)
    with pyplot_lock if draws else contextlib.nullcontext():
        if draws:
            tool.check_cancelled()  # the run may have been cancelled while waiting
        started = getattr(tool, "_notify_started", None)
        if started is not None:
            started()
        # tools (flim.core.tool.Tool) run with run_task(inputs, config)
        run = tool.run_task
        kwargs = _unwrap(kwargs)
        kwargs.pop(_AFTER, None)  # only waited for
        results = run(**kwargs)
    release_figures(results)
    return results


def _retry_unless_cancelled(task: "Task", task_run: "TaskRun", state: State) -> bool:
    """Return False for a cancelled task: it is never retried, even with retries."""
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
def run_tool(
    tool: Tool, label: str, kwargs: Dict[str, Any], autosave: Optional[dict]
) -> Union[Dict[str, Any], State]:
    """Run a single tool call, as a Prefect task.

    Records the config as a Prefect artifact, runs the tool and saves its results.

    Args:
        tool: The tool.
        label: The task run's name.
        kwargs: The tool's `inputs` and `config`, with `TaskOutput` markers whose
            futures Prefect has resolved.
        autosave: The arguments of `flim.results.save_results`, and `only`, the
            numbers (from 1) of the outputs to save; None saves nothing.

    Returns:
        The results by display name; if the tool warned, a `Completed` state with
        the warnings as its message and the results as its data.
    """
    _record_settings(tool, kwargs.get("config"), _unwrap(kwargs).get("inputs"))
    results = _run_tool(tool, kwargs)
    if autosave:
        only = autosave.get("only")
        saved = results
        if only is not None:  # a workflow file's step saves some of its outputs
            items = list(results.items())
            saved = dict(items[n - 1] for n in only if n <= len(items))
        save_results(saved, **{k: v for k, v in autosave.items() if k != "only"})
    warnings = getattr(getattr(tool, "context", None), "warnings", None)
    if warnings:
        # the warnings become the completed task's message (run summary, Prefect UI);
        # the results still go to the next tasks (checked with Prefect 3.8.8)
        return Completed(message="; ".join(warnings), data=results)
    return results


def _record_settings(
    tool: Tool, config: Optional["TaskConfig"], inputs: Optional[Sequence[Any]] = None
) -> None:
    """Attach the config a task runs with to its task run, as a Prefect artifact.

    The artifact (the run's Artifacts tab in the Prefect UI) holds the config as
    JSON, no data values, with the values the tool uses on the inputs filled in
    (`Tool.used_config`). A failure is logged, not raised: the run doesn't depend on
    it.
    """
    if config is None or not hasattr(config, "model_dump_json"):
        return
    try:
        config = type(tool).used_config(config, list(inputs or []))
    except Exception as err:  # the record falls back to the config as given
        logger.debug(f"Used config not found: {err}")
    try:
        from prefect.artifacts import create_markdown_artifact

        create_markdown_artifact(
            markdown=f"```json\n{config.model_dump_json(indent=2)}\n```",
            description=f"{getattr(tool, 'name', 'Tool')}: settings",
        )
    except Exception as err:  # e.g. no Prefect API reachable
        logger.debug(f"Settings artifact not created: {err}")


@dataclass(frozen=True)
class InputOrigin:
    """Where a value that enters a run comes from, for the run summary's `Inputs`.

    Attributes:
        file: The file it was read from: the input is listed as that file (until
            readers are tasks of the run, the file is read before the run starts).
        details: Text added to the input's details, e.g. the GUI item and window
            filters it came from.
    """

    file: Optional[Path] = None
    details: str = ""


def _entry_values(value: Any) -> Iterator[Any]:
    """Yield the data values among a tool call's inputs, not handles to other tasks."""
    if isinstance(value, TaskOutput) or value is None:
        return
    if isinstance(value, dict):
        if value.get(_MARKER):
            return
        for item in value.values():
            yield from _entry_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _entry_values(item)
    else:
        yield value


def _sources(value: Any) -> set[str]:
    """Return the values of the `Source` columns of the tables in `value`.

    `value` is a tool call's arguments: tables, lists and dicts of them, and
    `TaskOutput` handles of other tasks, which are left out (their tables come
    from the run itself).
    """
    import pandas as pd

    if isinstance(value, pd.DataFrame):
        if "Source" in value.columns:
            return {str(v) for v in value["Source"].dropna().unique()}
        return set()
    if isinstance(value, dict):
        value = value.values()
    if isinstance(value, (list, tuple, set, type({}.values()))):
        found: set[str] = set()
        for item in value:
            found |= _sources(item)
        return found
    return set()


# extras of FLIMAnalyzer whose packages a run doesn't record (not used by a run)
UNRECORDED_EXTRAS = ("test",)
# the packages that run the tasks of a Dask executor (indirect dependencies, through
# prefect-dask), recorded for runs on one
DASK_PACKAGES = ("dask", "distributed")
_NAME = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXTRA = re.compile(r"""extra\s*==\s*["']([^"']+)["']""")


def recorded_packages() -> list[str]:
    """Return the packages whose versions a run records, besides FLIMAnalyzer.

    FLIMAnalyzer's declared dependencies as installed (`dependencies` and the
    optional extras of `pyproject.toml`, from the installed package's metadata),
    without the extras in `UNRECORDED_EXTRAS`; then the installed packages that
    provide tools of other packages (entry points of `flim.core.registry.TOOLS_GROUP`).

    Returns:
        The package names, each once, in that order.
    """
    from importlib.metadata import PackageNotFoundError, entry_points, requires

    from flim.core.registry import TOOLS_GROUP

    names: list[str] = []
    try:
        requirements = requires("flimanalyzer") or []
    except PackageNotFoundError:  # running from files that are not installed
        requirements = []
    for requirement in requirements:
        name, extra = _NAME.match(requirement), _EXTRA.search(requirement)
        if name and not (extra and extra.group(1) in UNRECORDED_EXTRAS):
            names.append(name.group(1))
    for entry in entry_points(group=TOOLS_GROUP):
        if entry.dist is not None and entry.dist.name != "flimanalyzer":
            names.append(entry.dist.name)
    return list(dict.fromkeys(names))


def _versions(task_runner: Any = None) -> dict[str, str]:
    """Return the versions of FLIMAnalyzer, Python and the recorded packages installed.

    See `recorded_packages`; with a Dask task runner also `DASK_PACKAGES`. A package
    that is not installed (e.g. an extra) is left out.

    Args:
        task_runner: The run's task runner; None for none.
    """
    import platform
    from importlib.metadata import PackageNotFoundError, version

    from flim import __version__

    found = {"FLIMAnalyzer": __version__, "Python": platform.python_version()}
    names = recorded_packages()
    if type(task_runner).__name__ == "DaskTaskRunner":
        names += [n for n in DASK_PACKAGES if n not in names]
    for name in names:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            pass  # not installed, e.g. the dask extra
    return found


def _execution(task_runner: Any) -> dict[str, Any]:
    """Return how a flow's tasks run: the task runner and its settings."""
    found: dict[str, Any] = {"task runner": type(task_runner).__name__}
    if type(task_runner).__name__ == "ThreadPoolTaskRunner":
        found["threads"] = getattr(task_runner, "_max_workers", None)
    elif type(task_runner).__name__ == "DaskTaskRunner":
        for key in ("address", "cluster_class", "cluster_kwargs", "adapt_kwargs"):
            value = getattr(task_runner, key, None)
            if value:
                found[key] = value if isinstance(value, (str, dict)) else getattr(value, "__name__", str(value))
    return found


def _record_run(run: "FlowRun", task_runner: Any) -> None:
    """Record the app versions, the execution and the input files of a flow run.

    They are kept in `run.versions` and `run.execution` for the run summary, and
    attached to the flow run as a Prefect artifact (the flow run's Artifacts tab),
    next to the settings that each task records (`_record_settings`). A failure to
    create the artifact is logged, not raised.
    """
    import json

    run.versions, run.execution = _versions(task_runner), _execution(task_runner)
    record = {
        "app": run.versions,
        "execution": run.execution,
        "input files": sorted(run.sources),
    }
    try:
        from prefect.artifacts import create_markdown_artifact

        create_markdown_artifact(
            markdown=f"```json\n{json.dumps(record, indent=2, default=str)}\n```",
            description=f"{run.name}: app version, execution and input files",
        )
    except Exception as err:  # e.g. no Prefect API reachable
        logger.debug(f"Run artifact not created: {err}")


class _InRun(logging.Filter):
    """Passes only records logged inside a Prefect flow or task run."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether a flow or task run is active in this thread."""
        from prefect.context import TaskRunContext

        return FlowRunContext.get() is not None or TaskRunContext.get() is not None


def forward_logs_to_prefect() -> None:
    """Send FLIMAnalyzer's log records from inside runs to the Prefect server.

    A Prefect API log handler on the `flim` logger, with a filter that passes only
    records logged in a flow or task run, so that they appear with the run's logs
    in the Prefect UI; records logged elsewhere (the GUI) go to the log file only.
    The handler is added once.
    """
    from prefect.logging.handlers import APILogHandler

    flim_logger = logging.getLogger("flim")
    if any(isinstance(h, APILogHandler) for h in flim_logger.handlers):
        return
    handler = APILogHandler()
    handler.addFilter(_InRun())
    flim_logger.addHandler(handler)


class _StartNotifier:
    """Marks a task as running when it starts.

    Only works in this process: pickled into a Dask worker process it does
    nothing, and the task goes from pending to its final status.
    """

    def __init__(self, run: Optional["FlowRun"], node: str) -> None:
        """Create a notifier for a node of a run."""
        self.run, self.node = run, node

    def __call__(self) -> None:
        """Mark the node as running."""
        if self.run is not None:
            self.run._mark_running(self.node)

    def __getstate__(self) -> Dict[str, Any]:
        """Return the node only, for pickling."""
        return {"run": None, "node": self.node}


# task statuses: pending (submitted, waiting for its inputs or a worker), running,
# and the final ones
FINAL_STATUSES = ("completed", "failed", "cancelled", "skipped")


class FlowRun:
    """Records and executes the tool calls made while a flow is running."""

    def __init__(
        self,
        name: str,
        autosave_dir: Optional[str | os.PathLike] = None,
        on_progress: Optional[Callable[[int, int, str, bool], None]] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> None:
        """Create the record of a run.

        Args:
            name: The flow's name.
            autosave_dir: The folder to save the task results in; None disables
                saving.
            on_progress: Called as `on_progress(done, total, label, complete)` when
                a task is submitted, starts running (in this process only) or
                finishes, and once (with label `""`) when the workflow script has
                made all its calls; from the thread where that happens. `done`
                counts the tasks in a final status, `total` the tasks so far;
                `complete` is True once the workflow script has made all its calls.
                An exception it raises is logged.
            cancel_token: The signal that cancels the run when set; None for a new
                one.
        """
        self.name = name
        self.autosave_dir = Path(autosave_dir) if autosave_dir else None
        self.on_progress = on_progress
        self.cancel_token = cancel_token or CancelToken()
        self.flow_run_id = None
        self.state = "running"  # completed, cancelled or failed when the run ends
        self.complete = False  # True once the workflow script has made all its calls
        self.start_time = datetime.datetime.now()
        self.end_time = None
        self.notes: List[str] = []  # for the run summary, e.g. guessed columns
        self.sources: set[str] = set()  # the files of the tables that enter the run
        self.settings_record: List[str] = []  # the settings files, for the run summary
        self.save_formats: list = []  # AutosaveConfig.formats of the run
        # the run's `output.char_replacements` (None: the defaults); a workflow file's
        # step may have its own
        self.char_replacements: Optional[dict[str, str]] = None
        # the values that enter the run from outside, by id: the value (kept, so the
        # id stays its), its row of the run summary's `Inputs`, the steps it enters
        # and the `Input` nodes it enters through
        self.inputs: dict[int, dict[str, Any]] = {}
        self.input_origins: dict[int, InputOrigin] = {}  # by id of the value
        # the runtime, for the run summary: FLIMAnalyzer, Python and package versions,
        # and the task runner (see _record_run)
        self.versions: dict[str, str] = {}
        self.execution: dict[str, Any] = {}
        self.graph = nx.DiGraph()
        self._label_counts = {}
        self._key_nodes = {}
        self._lock = threading.RLock()

    # graph bookkeeping -------------------------------------------------------
    def _add_node(self, label: str, kind: str, **attrs: Any) -> str:
        """Add a pending node to the graph and return its id."""
        node = f"n{len(self.graph)}"
        self.graph.add_node(node, label=label, kind=kind, status="pending", **attrs)
        return node

    def _key_node(self, node: str, keys: tuple) -> str:
        """Return the node of an item (e.g. a table) of a tool's result dict."""
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
        """Convert TaskOutput handles into task arguments; collect upstream nodes."""
        if isinstance(obj, TaskOutput):
            if obj.node is not None:
                upstream.add(self._key_node(obj.node, obj.keys))
            return {_MARKER: True, "ref": obj.ref, "keys": obj.keys}
        if isinstance(obj, dict):
            return {k: self._to_payload(v, upstream) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return type(obj)(self._to_payload(v, upstream) for v in obj)
        return obj

    def _record_inputs(self, inputs: Any, node: str, step: Optional[str], through: bool) -> None:
        """Record the values among a call's inputs that enter the run from outside.

        Each value is recorded once, by its id, with its content hash and description
        (`DataType.content_hash`, `DataType.describe`), or those of the file it was
        read from (`InputOrigin.file`). Values of types without a hash are left out.

        Args:
            inputs: The call's inputs.
            node: The call's node.
            step: The call's step id; None for none.
            through: Whether the call is an `Input` node, which passes the value on:
                its steps are those of the tasks that use the node's output.
        """
        for value in _entry_values(inputs):
            data_type = DataType.of(value)
            if data_type is None:
                continue
            entry = self.inputs.get(id(value))
            if entry is None:
                origin = self.input_origins.get(id(value), InputOrigin())
                if origin.file is not None:
                    kind, shown = FileType, Path(origin.file)
                else:
                    kind, shown = data_type, value
                described = kind.describe(shown)
                if origin.details:
                    described["details"] = "; ".join(
                        d for d in (described["details"], origin.details) if d
                    )
                entry = {
                    "value": value,
                    "kind": kind.kind,
                    "hash": kind.content_hash(shown) or "-",
                    **described,
                    "steps": set(),
                    "nodes": set(),
                }
                self.inputs[id(value)] = entry
            if through:
                entry["nodes"].add(node)
            else:
                entry["steps"].add(step or "")

    def _input_steps(self, entry: dict[str, Any]) -> list[str]:
        """Return the steps an input enters: its own, and those of the tasks that use
        the outputs of the `Input` nodes it passes through."""
        steps = set(entry["steps"])
        for node in entry["nodes"]:
            todo, seen = list(self.graph.successors(node)), set()
            while todo:
                n = todo.pop()
                if n in seen:
                    continue
                seen.add(n)
                attrs = self.graph.nodes[n]
                if "tool" in attrs:  # a task that uses it
                    steps.add(attrs.get("step") or "")
                else:  # an item of the node's results
                    todo.extend(self.graph.successors(n))
        return sorted(s or "-" for s in steps) or ["-"]

    def _inputs_lines(self) -> list[str]:
        """Return the run summary's `Inputs` table: one line per input."""
        if not self.inputs:
            return []
        header = ["Input", "Step", "Kind", "Identity", "Size/Shape", "Type", "SHA-256", "Details"]
        rows = [
            [str(n), ", ".join(self._input_steps(e)), e["kind"], e["identity"], e["size"],
             e["type"], e["hash"], e["details"]]
            for n, e in enumerate(self.inputs.values(), 1)
        ]  # fmt: skip
        widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header))]
        lines = ["Inputs:"]
        for row in [header, *rows]:
            cells = [c.ljust(w) for c, w in zip(row, widths)]
            lines.append("  " + "  ".join(cells).rstrip())
        return lines + [""]

    def _unique_label(self, label: str) -> str:
        """Return the label, with `-<n>` appended from its second use."""
        n = self._label_counts.get(label, 0)
        self._label_counts[label] = n + 1
        return label if n == 0 else f"{label}-{n}"

    # execution -----------------------------------------------------------------
    def call(
        self,
        tool: Tool,
        kwargs: Dict[str, Any],
        task_tags: Optional[str | Sequence[str]] = None,
        step: Optional[str] = None,
    ) -> TaskOutput:
        """Submit one tool call as a Prefect task and return a handle to its result.

        If the run has been cancelled, the call is recorded as cancelled and
        `_RunCancelled` is raised, which ends the workflow script. If an upstream
        task failed, was skipped or was cancelled, the call is not submitted: it is
        recorded as skipped and its handle holds None. With a results folder, the
        task saves its results below it, in the folders its tags name, unless the
        tool's `_save` is False.

        Args:
            tool: The tool; the call runs a shallow copy of it.
            kwargs: The tool's `inputs` and `config`, which may hold `TaskOutput`
                handles, and the handles the task waits for.
            task_tags: The task's tags, one or several; None for none. The task is
                also tagged with the tool's name.
            step: The id of the workflow step the call belongs to, e.g. `03`; None
                for none. Its results go into the folder `<step>-<tool>`, before the
                folders of `tag_prefix` and `task_tags`.

        Returns:
            The handle to the task's result.

        Raises:
            _RunCancelled: If the run has been cancelled.
        """
        # each call gets its own (shallow) copy, so the attributes set below are not
        # shared between calls
        tool = copy.copy(tool)
        tool._cancel_token = self.cancel_token

        tag_list = [task_tags] if isinstance(task_tags, str) else list(task_tags or [])
        # the results folders: the step's (`<id>-<tool>`), the input's, then the task's
        # own (e.g. its part), as in a workflow file
        step_tags = [f"{step}-{type(tool).name}"] if step else []
        tag_list = step_tags + list(_TAG_PREFIX.get()) + tag_list
        label = self._unique_label(tool.name)
        # the task's names of files and folders: a workflow file's step: its own
        # `output.char_replacements`, else the run's (the workflow's), else the defaults
        replacements = (
            getattr(tool, "_char_replacements", None)
            or self.char_replacements
            or DEFAULT_CHAR_REPLACEMENTS
        )
        folder = "/".join(path_name(str(t), replacements) for t in tag_list)  # as on disk
        node = self._add_node(
            label, getattr(tool, "graph_kind", "tool"), tool=tool, step=step, folder=folder
        )
        tool._notify_started = _StartNotifier(self, node)
        self._record_inputs(kwargs.get("inputs"), node, step, type(tool).name == "Input")
        upstream = set()
        self.sources.update(_sources(kwargs))
        payload = self._to_payload(kwargs, upstream)
        for u in upstream:
            self.graph.add_edge(u, node)

        if self.cancel_token.is_set():
            with self._lock:
                self.graph.nodes[node].update(status="cancelled", message="Run cancelled")
            self._report_progress(label)
            raise _RunCancelled()

        failed = [
            u
            for u in upstream
            if self.graph.nodes[u]["status"] in ("failed", "skipped", "cancelled")
        ]
        if failed:
            logger.warning(f"Skipping {label}: upstream task failed.")
            self.graph.nodes[node]["status"] = "skipped"
            return TaskOutput(None, node)

        autosave = None
        save = getattr(tool, "_save", None)  # a workflow file's step: True, False, [n]
        formats = getattr(tool, "_formats", None)  # a workflow file's step: its own
        if formats:  # per kind: the step's own, else the run's (the workflow's)
            own = {f.kind for f in formats}
            formats = list(formats) + [f for f in self.save_formats if f.kind not in own]
        if self.autosave_dir and save is not False:
            autosave = {
                "directory": self.autosave_dir.joinpath(
                    *[path_name(t, replacements) for t in tag_list]
                ),
                "name": label,
                "formats": self.save_formats if formats is None else formats,
                # passed on: a task on a Dask worker names its files the same way
                "replacements": dict(replacements),
            }
            if isinstance(save, (list, tuple)):
                autosave["only"] = list(save)

        # tools write files they produce (e.g. models) next to the saved results
        tool._output_dir = autosave["directory"] if autosave else None

        # Prefect starts the task once the futures among its inputs are completed and
        # skips it (state NotReady) if one of them did not complete. Besides the
        # workflow's tags (which also name the results folders), every task is tagged
        # with its tool's name, so that concurrency limits on a tool apply everywhere;
        # also with its former names (limits set on them keep applying; deprecated,
        # removed in 0.8.0 with the former names) and its extra_tags.
        names = [tool.name, *getattr(tool, "former_names", ()), *getattr(tool, "extra_tags", ())]
        with tags(*dict.fromkeys(tag_list + names)):
            ref = run_tool.submit(tool, label, payload, autosave)
        with self._lock:
            self.graph.nodes[node]["ref"] = ref
        self._report_progress(label)
        ref.add_done_callback(lambda future, node=node: self._record(node))
        return TaskOutput(ref, node)

    def _record(self, node: str) -> None:
        """Record the final status of a finished task (once)."""
        with self._lock:
            attrs = self.graph.nodes[node]
            ref = attrs.get("ref")
            if not isinstance(ref, PrefectFuture):
                return  # already recorded
            # stores the final state, which `state` would otherwise read from the API
            ref.wait()
            state = ref.state
            if state.is_completed():
                # a message only if the tool warned (Tool.warn)
                attrs.update(status="completed", ref=ref.result(), message=state.message)
                attrs["resources"] = _granted(attrs.get("tool"))
            elif state.is_pending() and state.name == "NotReady":
                attrs.update(status="skipped", ref=None, message=state.message)
                logger.warning(f"Skipped {attrs['label']}: upstream task did not complete.")
            elif isinstance(exc := ref.result(raise_on_failure=False), TaskCancelled):
                attrs.update(status="cancelled", ref=None, message=str(exc) or "Cancelled")
                logger.info(f"{attrs['label']} cancelled: {attrs['message']}")
            else:
                attrs.update(status="failed", ref=None, message=state.message)
                logger.error(f"{attrs['label']} failed: {state.message}")
        self._report_progress(attrs["label"])

    def resources(self) -> List[tuple]:
        """Return (label, resources) of every completed task with known resources."""
        with self._lock:
            return [
                (a["label"], a["resources"])
                for _, a in self.graph.nodes(data=True)
                if a.get("resources")
            ]

    def _mark_running(self, node: str) -> None:
        """Mark a pending task as running."""
        with self._lock:
            attrs = self.graph.nodes[node]
            if attrs["status"] != "pending":
                return
            attrs["status"] = "running"
        self._report_progress(attrs["label"])

    def tasks(self) -> List[tuple]:
        """Return (label, status) of every task so far, in call order."""
        with self._lock:
            return [(a["label"], a["status"]) for _, a in self.graph.nodes(data=True) if "tool" in a]

    def _report_progress(self, label: str) -> None:
        """Call `on_progress`, if set, with the current task counts."""
        if self.on_progress is None:
            return
        with self._lock:
            tasks = [a for _, a in self.graph.nodes(data=True) if "tool" in a]
            done = sum(a["status"] in FINAL_STATUSES for a in tasks)
        try:
            self.on_progress(done, len(tasks), label, self.complete)
        except Exception:
            logger.exception("Progress callback failed")

    def wait(self) -> None:
        """Wait for all submitted tasks and record their final status."""
        for node, attrs in list(self.graph.nodes(data=True)):
            ref = attrs.get("ref")
            if isinstance(ref, PrefectFuture):
                ref.wait()
                self._record(node)

    def results(self) -> List[Any]:
        """Return the results of all completed tool calls, in call order."""
        return [
            attrs["ref"]
            for _, attrs in self.graph.nodes(data=True)
            if "tool" in attrs and attrs["status"] == "completed"
        ]

    def _labels(self, status: str) -> List[str]:
        """Return the labels of the nodes with a status."""
        return [a["label"] for _, a in self.graph.nodes(data=True) if a["status"] == status]

    @property
    def failed(self) -> List[str]:
        """The labels of the failed tasks."""
        return self._labels("failed")

    @property
    def warnings(self) -> List[tuple]:
        """The (label, message) of the completed tasks that reported warnings."""
        return [
            (a["label"], a["message"])
            for _, a in self.graph.nodes(data=True)
            if a.get("status") == "completed" and a.get("message")
        ]

    @property
    def cancelled(self) -> List[str]:
        """The labels of the cancelled tasks."""
        return self._labels("cancelled")

    def cancel(self) -> None:
        """Cancel the run.

        No new tasks start, and running tasks stop at their next
        `flim.core.tool.Tool.check_cancelled`.
        """
        self.cancel_token.set()

    def task_counts(self) -> Dict[str, int]:
        """Return the number of tasks per status (completed, failed, skipped, ...)."""
        counts = {}
        for _, attrs in self.graph.nodes(data=True):
            if "tool" in attrs:
                counts[attrs["status"]] = counts.get(attrs["status"], 0) + 1
        return counts

    @property
    def ui_url(self) -> Optional[str]:
        """Link to the flow run in the Prefect UI, None without a Prefect server."""
        if self.flow_run_id is None:
            return None
        from prefect.utilities.urls import url_for

        return url_for("flow-run", obj_id=self.flow_run_id)

    def write_summary(self) -> Optional[Path]:
        """Write `run_summary.txt` into the results folder, if there is one.

        The summary lists the run's name, state, times, Prefect link, results folder
        and task counts, the settings files and notes, and per task its status,
        resources and message.

        Returns:
            The path of the file, or None without a results folder.
        """
        if not self.autosave_dir:
            return None
        os.makedirs(self.autosave_dir, exist_ok=True)
        counts = self.task_counts()
        tasks = [a for _, a in self.graph.nodes(data=True) if "tool" in a]
        width = max([len(a["label"]) for a in tasks] + [4])
        lines = [
            "FLIMAnalyzer run summary",
            "",
            f"Flow:       {self.name}",
            f"State:      {self.state}",
            f"Started:    {self.start_time:%Y-%m-%d %H:%M:%S}",
            f"Finished:   {self.end_time:%Y-%m-%d %H:%M:%S}" if self.end_time else "Finished:",
            f"Elapsed:    {elapsed(self.start_time, self.end_time)}" if self.end_time else "Elapsed:",
            f"Prefect:    {self.ui_url or self.flow_run_id or '-'}",
            f"Results:    {self.autosave_dir}",
            "Tasks:      " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())),
            "",
        ]
        if self.settings_record:
            lines += ["Settings:"] + [f"  {line}" for line in self.settings_record] + [""]
        if self.versions:
            lines += ["Versions:"] + [f"  {k} {v}" for k, v in self.versions.items()] + [""]
        if self.execution:
            lines += ["Execution:"] + [f"  {k}: {v}" for k, v in self.execution.items()] + [""]
        if self.notes:
            lines += ["Notes:"] + [f"  {note}" for note in self.notes] + [""]
        lines += self._inputs_lines()
        granted = [a.get("resources") or "" for a in tasks]
        res_width = max([len(r) for r in granted] + [len("Resources")])
        # the step id (none for a tool run) and the results folder in the run
        steps = [a.get("step") or "-" for a in tasks]
        folders = [a.get("folder") or "-" for a in tasks]
        step_width = max([len(s) for s in steps] + [len("Step")])
        folder_width = max([len(f) for f in folders] + [len("Folder")])
        lines.append(
            f"{'Task'.ljust(width)}  {'Step'.ljust(step_width)}"
            f"  {'Folder'.ljust(folder_width)}  {'Status'.ljust(9)}"
            f"  {'Resources'.ljust(res_width)}  Message"
        )
        for a, step, folder, resources in zip(tasks, steps, folders, granted):
            message = (a.get("message") or "").replace("\n", " ")
            lines.append(
                f"{a['label'].ljust(width)}  {step.ljust(step_width)}"
                f"  {folder.ljust(folder_width)}  {a['status'].ljust(9)}"
                f"  {resources.ljust(res_width)}  {message}".rstrip()
            )
        path = self.autosave_dir / "run_summary.txt"
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        return path


def _granted(tool: Optional[Tool]) -> Optional[str]:
    """Return the device and threads a tool ran with, e.g. "cpu, 4 threads".

    None if not known: for nodes that are not tools (e.g. a workflow's input) and for
    tasks run in another process.
    """
    if tool is None or getattr(tool, "graph_kind", "tool") != "tool":
        return None  # e.g. a workflow's input
    context = vars(tool).get("context")
    if context is None or not hasattr(context, "device"):
        return None
    threads = f"{context.threads} thread{'s' if context.threads != 1 else ''}"
    note = f" ({context.note})" if context.note else ""
    return f"{context.device}, {threads}{note}"


def current_run() -> Optional[FlowRun]:
    """Return the FlowRun that is currently being executed, or None."""
    return _CURRENT_RUN.get()


def call_tool(
    tool: Tool,
    inputs: Sequence[Any],
    config: Optional["TaskConfig"] = None,
    task_tags: Optional[str | Sequence[str]] = None,
    after: Sequence[TaskOutput] = (),
    step: Optional[str] = None,
) -> Any:
    """Call a tool (`flim.core.tool.Tool`) with its inputs and config.

    During a dry run the call is traced (see `flim.core.validation`), inside a flow
    it is submitted as a task, otherwise the tool runs directly.

    Args:
        tool: The tool.
        inputs: The inputs: values, `TaskOutput` handles, or `unmapped` values.
        config: The config; None for the tool's default config.
        task_tags: The task's tags, one or several; None for none.
        after: Handles of tasks this one waits for although they are not its
            inputs, e.g. those whose results (model files) its config names. Used
            only inside a flow.
        step: The id of the workflow step the call belongs to (see `FlowRun.call`);
            None for none. Used only inside a flow.

    Returns:
        During a dry run, a `flim.core.validation.TraceOutput`; inside a flow, a
        `TaskOutput`; otherwise the tool's results by display name.
    """
    inputs = [v.value if isinstance(v, unmapped) else v for v in inputs]
    from flim.core.validation import current_tracer  # imports this module

    tracer = current_tracer()
    if tracer is not None:  # a dry run, see flim.core.validation
        return tracer.call(tool, inputs, config, task_tags)
    run = current_run()
    if run is None:
        return tool.run_task(inputs=_resolve(inputs), config=config)
    kwargs = {"inputs": inputs, "config": config}
    if after:
        kwargs[_AFTER] = list(after)
    return run.call(tool, kwargs, task_tags=task_tags, step=step)


def select(
    outputs: Sequence[Any],
    key_pattern: str = "(.*?)",
    value_pattern: Optional[str] = None,
) -> list:
    """Select result items whose key matches `key_pattern` from tool outputs.

    Waits for the results of `TaskOutput` handles. Outputs whose result is not a dict
    (e.g. of a task that did not complete) are skipped. If `value_pattern` is given,
    the matching items that are lists are flattened to the elements that match
    `value_pattern`; other items are skipped.

    Args:
        outputs: Tool results (dicts) or `TaskOutput` handles to them.
        key_pattern: A regular expression searched for in each key. Defaults to one
            that matches every key.
        value_pattern: A regular expression searched for in each list element (as
            text); None selects the items themselves.

    Returns:
        The selected items or elements; for handles, `TaskOutput` handles to them.
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
    logger.debug(f"select {key_pattern}, {value_pattern}: {len(selected)} items")
    return selected


_PENDING_FLOW = contextvars.ContextVar("flim_pending_flow", default=None)


def _flow_body() -> Optional[State]:
    """Run the workflow script of a flow and wait for its tasks; every flow's body.

    The run, the script and the start callback come from `_PENDING_FLOW`. A
    module-level function (not a closure) so that the flow object, which Prefect
    sends to Dask workers, can be pickled by reference.

    Returns:
        A `Cancelled` state if the run was cancelled, else None.
    """
    run, build, on_start = _PENDING_FLOW.get()
    context = FlowRunContext.get()
    if context is not None and context.flow_run is not None:
        run.flow_run_id = context.flow_run.id
    if on_start is not None:
        try:
            on_start(run)
        except Exception:
            logger.exception("Start callback failed")
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
        _record_run(run, task_runner)  # the input files are known now
    finally:
        _CURRENT_RUN.reset(token)
    if run.cancel_token.is_set():
        return Cancelled(message="Cancelled by the user")


def run_flow(
    name: str,
    build: Callable[[], Any],
    task_runner: Optional[TaskRunner] = None,
    autosave_dir: Optional[str | os.PathLike] = None,
    on_progress: Optional[Callable[[int, int, str, bool], None]] = None,
    cancel_token: Optional[CancelToken] = None,
    on_start: Optional[Callable[[FlowRun], None]] = None,
    notes: Sequence[str] = (),
    settings_record: Sequence[str] = (),
    save_formats: Sequence = (),
    run_dir: Optional[str | os.PathLike] = None,
    char_replacements: Optional[Mapping[str, str]] = None,
    input_origins: Sequence[tuple[Any, InputOrigin]] = (),
) -> FlowRun:
    """Run `build` as a Prefect flow; tool calls inside it become task runs.

    Args:
        name: The flow's name, shown in the Prefect UI.
        build: The callable that makes the tool calls.
        task_runner: The Prefect task runner; None uses `default_task_runner`.
        autosave_dir: If set, every task's results are saved below this folder
            (`<autosave_dir>/<timestamp>/<task tags>/`; `<timestamp>-2`, ... if
            the folder exists); the run summary is written there too.
        on_progress: See `FlowRun`.
        cancel_token: The `CancelToken` that cancels the run when set, e.g. from
            another thread; None for a new one.
        on_start: Called with the `FlowRun` once Prefect has created the flow run
            (`flow_run_id` and `ui_url` are known), before the first task. An
            exception it raises is logged.
        notes: Lines for the run summary, e.g. the guesses a validation applied.
        settings_record: Lines for the run summary naming the settings files used
            (`SettingsManager.record`).
        save_formats: The formats the tasks save their results in
            (`AutosaveConfig.formats`); a kind not listed is saved in its default
            format.
        run_dir: The run's folder, used as it is (e.g. `<output>/<date and
            time>/run-1` of a flimbatch call); None: a folder per run below
            `autosave_dir`.
        char_replacements: The text replaced in the names of the files and folders
            the tasks save into (`output.char_replacements`, with the defaults);
            None: the defaults. A workflow file's step may have its own.
        input_origins: Where values that enter the run come from: (value,
            origin) pairs, e.g. a table and the file it was read from; listed in the
            run summary's `Inputs` (see `InputOrigin`).

    Returns:
        The recorded task graph and results; `state` is completed, cancelled or
        failed (some tasks failed).

    Raises:
        Exception: The error that made the flow itself fail (e.g. one raised by
            `build`), after the run summary is written. Failed tasks do not raise;
            they are recorded in `run.graph`.
    """
    run = FlowRun(name, on_progress=on_progress, cancel_token=cancel_token)
    run.notes = list(notes)
    run.settings_record = list(settings_record)
    run.save_formats = list(save_formats)
    run.char_replacements = dict(char_replacements) if char_replacements else None
    run.input_origins = {id(value): origin for value, origin in input_origins}
    run._origin_values = [value for value, _ in input_origins]  # keeps their ids
    if run_dir:
        run.autosave_dir = Path(run_dir)
        run.autosave_dir.mkdir(parents=True, exist_ok=True)
    elif autosave_dir:
        run.autosave_dir = unique_run_folder(
            autosave_dir, run.start_time.strftime("%Y-%m-%d_%H-%M-%S")
        )

    if task_runner is None:
        task_runner = default_task_runner()
    forward_logs_to_prefect()
    prefect_flow = flow(name=name, validate_parameters=False, task_runner=task_runner)(
        _flow_body
    )
    token = _PENDING_FLOW.set((run, build, on_start))
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
