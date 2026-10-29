"""Base class of tools: stateless operations configured by a Pydantic config.

A tool is called with its inputs and a config::

    results = Summarize()(table, config=SummaryConfig(grouping=["Treatment"]))

Inside :func:`flim.core.runner.run_flow` the call becomes a Prefect task and returns a
:class:`~flim.core.runner.TaskOutput` handle; outside a flow it returns the results.
Results are keyed by display name (``"Table: Summary"``), with the config's prefix.
"""

import contextlib
import logging
import os
import sys
import threading
import typing
from dataclasses import dataclass, replace
from typing import Any, ClassVar, Generic, Optional, Sequence, TypeVar

from flim.core.config import Issue, TaskConfig, column_references
from flim.core.registry import API_VERSION
from flim.core.schema import TableSchema
from flim.core.types import DataType, InputSpec, OutputSpec, TableType

ConfigT = TypeVar("ConfigT", bound=TaskConfig)

# pyplot's figure registry and current-figure state are shared by all threads: tasks
# that draw figures take turns, all other tasks run concurrently
pyplot_lock = threading.RLock()


def release_figures(results):
    """Removes result figures from pyplot's registry, which keeps every figure it
    created until it is closed. The figures stay usable (saving, showing)."""
    if not isinstance(results, dict) or "matplotlib.pyplot" not in sys.modules:
        return
    import matplotlib.figure
    import matplotlib.pyplot as plt

    figures = [v for v in results.values() if isinstance(v, matplotlib.figure.Figure)]
    with pyplot_lock:
        for figure in figures:
            plt.close(figure)


class TaskCancelled(Exception):
    """Raised by :meth:`Tool.cancel` to stop the running task.

    Prefect handles it like any other exception (the task run ends Failed and tasks
    that depend on it are not run); the runner records the task as cancelled.
    """


def resolve_device(preferred: str) -> tuple[str, Optional[str]]:
    """The device to use for ``preferred`` on this machine, and why it differs (if so).

    "auto" picks a CUDA GPU, then the Apple GPU (mps), then the CPU. torch is only
    imported for devices other than the CPU.
    """
    if preferred == "cpu":
        return "cpu", None
    try:
        import torch
    except ImportError:
        return "cpu", f"preferred {preferred}, ran on cpu: torch is not installed"
    available = {
        "cuda": torch.cuda.is_available(),
        "mps": bool(
            getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()
        ),
    }
    if preferred == "auto":
        return next((d for d in ("cuda", "mps") if available[d]), "cpu"), None
    if available.get(preferred):
        return preferred, None
    return "cpu", f"preferred {preferred}, ran on cpu: no {preferred} device here"


def resolve_threads(preferred: int) -> int:
    """Threads for ``preferred`` (-1: all cores), at most the number of cores."""
    cores = os.cpu_count() or 1
    return cores if preferred == -1 else max(1, min(preferred, cores))


@dataclass
class RunContext:
    """What the executor granted a task, and the run's cancel signal."""

    device: str = "cpu"
    threads: int = 1
    note: Optional[str] = None  # e.g. why the preferred device was not used
    cancel_token: Any = None  # flim.core.runner.CancelToken
    # where tools write files they produce (e.g. models); None: not set by the caller
    output_dir: Optional[str] = None

    @classmethod
    def for_config(
        cls, config: TaskConfig, cancel_token=None, output_dir=None
    ) -> "RunContext":
        device, note = resolve_device(config.resources.preferred_device)
        if note:
            logging.info(note)
        return cls(
            device=device,
            threads=resolve_threads(config.resources.preferred_threads),
            note=note,
            cancel_token=cancel_token,
            output_dir=output_dir,
        )


class Tool(Generic[ConfigT]):
    """Base of all tools.

    Subclasses set the class attributes, name their config class as the generic
    parameter (``class Sort(Tool[SortConfig])``) and implement :meth:`run`.
    """

    name: ClassVar[str] = ""
    # earlier names, under which settings may have been saved
    former_names: ClassVar[tuple[str, ...]] = ()
    category: ClassVar[str] = ""
    description: ClassVar[str] = ""
    icon: ClassVar[Optional[str]] = None  # resource name; the GUI loads the bitmap
    api_version: ClassVar[int] = API_VERSION
    graph_kind: ClassVar[str] = "plugin"  # node style in the workflow graph
    # True if the whole task draws with pyplot (see pyplot_lock)
    draws_figures: ClassVar[bool] = False
    inputs: ClassVar[tuple[InputSpec, ...]] = (InputSpec("data", TableType),)
    # outputs whose names don't depend on config or input; see output_schema
    outputs: ClassVar[tuple[OutputSpec, ...]] = ()
    config_class: ClassVar[type[TaskConfig]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            origin = typing.get_origin(base)  # Tool, or a generic subclass of it
            if isinstance(origin, type) and issubclass(origin, Tool):
                (config_class,) = typing.get_args(base)
                if isinstance(config_class, type):
                    cls.config_class = config_class

    def __init__(self):
        self.context = RunContext()

    def __repr__(self):
        return f"<{type(self).__name__}>: {self.name}"

    # --- the computation ---

    def run(self, *inputs, config: ConfigT) -> dict[str, Any]:
        """Computes the results, keyed by output name (e.g. ``"Summary"``)."""
        raise NotImplementedError

    def map_configs(self, config: ConfigT) -> list[ConfigT]:
        """Configs of the smallest independent calls, e.g. one per feature."""
        return [config]

    # --- calling ---

    def __call__(
        self, *inputs, config: Optional[ConfigT] = None, task_tags=None, after=()
    ):
        from flim.core.runner import call_tool

        return call_tool(self, inputs, config, task_tags=task_tags, after=after)

    def run_task(self, inputs: Sequence, config: Optional[ConfigT] = None) -> dict:
        """Runs the tool as one task: resolves the resources, validates the config
        type and returns the results by display name, with the config's prefix."""
        config = self.config_class() if config is None else config
        if not isinstance(config, self.config_class):
            raise TypeError(
                f"{self.name} needs a {self.config_class.__name__},"
                f" not a {type(config).__name__}"
            )
        self.context = RunContext.for_config(
            config,
            cancel_token=getattr(self, "_cancel_token", None),
            output_dir=getattr(self, "_output_dir", None),
        )
        with pyplot_lock if self.draws_figures else contextlib.nullcontext():
            results = self.display_names(self.run(*inputs, config=config))
        release_figures(results)
        if config.prefix:
            results = {f"{config.prefix}{k}": v for k, v in results.items()}
        return results

    @staticmethod
    def display_names(results: dict[str, Any]) -> dict[str, Any]:
        """Results keyed by display name, e.g. ``"Summary"`` → ``"Table: Summary"``."""
        named = {}
        for name, value in results.items():
            data_type = DataType.of(value)
            named[data_type.display_name(name) if data_type else name] = value
        return named

    # --- cancellation ---

    def cancel(self, message: str = "Cancelled"):
        """Stops this task (call it only from :meth:`run`).

        Inside a flow, the task is recorded as cancelled and tasks that use its results
        are not run; other tasks continue. Outside a flow, the exception reaches the
        caller.
        """
        raise TaskCancelled(message)

    def check_cancelled(self):
        """Stops this task if the user cancelled the run; call it regularly from long
        running :meth:`run` methods. Does nothing outside a flow."""
        # the runner sets _cancel_token before the task starts, the context once it runs
        token = self.context.cancel_token or getattr(self, "_cancel_token", None)
        if token is not None and token.is_set():
            self.cancel("Run cancelled by the user")

    # --- schemas and validation, without the data ---

    @classmethod
    def output_schema(
        cls, config: ConfigT, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """The outputs for ``config`` and the input schemas, keyed by output name.

        ``inputs`` holds one TableSchema per input (a dict of them for an input with
        ``many=True``), or None if unknown. The default runs the tool on a few sample
        rows built from the input schemas; tools for which that is expensive or wrong
        override it. If it cannot run, the tables' schemas are marked unknown.
        """
        schemas = _flat_schemas(inputs)
        if cls.draws_figures or None in schemas:
            return {o.name: _unknown(o) for o in cls.outputs}
        samples = [
            {k: s.sample() for k, s in i.items()} if isinstance(i, dict) else i.sample()
            for i in inputs
        ]
        try:
            results = cls().run(*samples, config=config)
        except Exception as err:
            logging.debug(f"{cls.name}: no output schema from sample data: {err}")
            return {o.name: _unknown(o) for o in cls.outputs}
        outputs = {}
        for name, value in results.items():
            data_type = DataType.of(value) or DataType
            schema = None
            if data_type is TableType:
                schema = TableSchema.from_frame(value, rows=False, inputs=schemas)
            outputs[name] = OutputSpec(name, data_type, schema=schema)
        return outputs

    @classmethod
    def validate(cls, config: ConfigT, inputs: Sequence[Any]) -> list[Issue]:
        """Checks the config against the input schemas: the columns it names exist and
        have the right role. Unknown inputs are not checked."""
        schemas = _flat_schemas(inputs)
        if not schemas or any(s is None or not s.complete for s in schemas):
            return []
        columns = {c.name: c for s in schemas for c in s.columns}
        issues = []
        for path, name, role in column_references(config):
            column = columns.get(name)
            if column is None:
                issues.append(Issue(path, f"Column '{name}' is not in the input"))
            elif column.role != role:
                issues.append(Issue(path, f"'{name}' is not a {role} column"))
        return issues


def _flat_schemas(inputs: Sequence[Any]) -> list:
    flat = []
    for i in inputs:
        flat.extend(i.values() if isinstance(i, dict) else [i])
    return flat


def _unknown(output: OutputSpec) -> OutputSpec:
    if output.type is TableType:
        return replace(output, schema=TableSchema.unknown())
    return output
