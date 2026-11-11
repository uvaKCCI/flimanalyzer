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
from pathlib import Path
import sys
import threading
import typing
from dataclasses import dataclass, field, replace
from typing import Any, ClassVar, Generic, Optional, Sequence, TypeVar

from flim.core.config import Issue, TaskConfig, column_references, requirement_issues
from flim.core.registry import API_VERSION
from flim.core.schema import TableSchema
from flim.core.types import DataType, InputSpec, OutputSpec, TableType

logger = logging.getLogger(__name__)

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
    """Threads for ``preferred`` (-1: all cores), at least 1 and at most the number
    of cores."""
    cores = os.cpu_count() or 1
    return cores if preferred == -1 else max(1, min(preferred, cores))


@dataclass
class RunContext:
    """The device and threads a task runs with (from its config's resources and this
    machine), the run's cancel signal, the folder for its files and its warnings."""

    device: str = "cpu"
    threads: int = 1
    note: Optional[str] = None  # e.g. why the preferred device was not used
    cancel_token: Any = None  # flim.core.runner.CancelToken
    # where tools write files they produce (e.g. models); None: not set by the caller
    output_dir: Optional[Path] = None
    # warnings of this run (Tool.warn): the task's message in the run summary
    warnings: list = field(default_factory=list)
    # parts of the settings applied and skipped (Tool.applied, Tool.skip), for a
    # workflow file step's `processing`
    applied: int = 0
    skipped: list = field(default_factory=list)

    @classmethod
    def for_config(
        cls, config: TaskConfig, cancel_token=None, output_dir=None
    ) -> "RunContext":
        device, note = resolve_device(config.resources.preferred_device)
        if note:
            logger.info(note)
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
    # a short form of the name where space is tight, e.g. in column names a tool
    # writes ("Source (before Import)"); at most SHORT_NAME_LENGTH characters; empty:
    # the name
    short_name: ClassVar[str] = ""
    category: ClassVar[str] = ""
    description: ClassVar[str] = ""
    icon: ClassVar[Optional[str]] = None  # resource name; the GUI loads the bitmap
    api_version: ClassVar[int] = API_VERSION
    graph_kind: ClassVar[str] = "tool"  # node style in the workflow graph
    # False: not in the tool menus and the tool panel (e.g. Import, run from the
    # File menu)
    in_menus: ClassVar[bool] = True
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

    @classmethod
    def short(cls) -> str:
        """The short name, or the name if the tool has none."""
        return cls.short_name or cls.name

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
        """Runs the tool as one task and returns the results by display name, with
        the config's prefix.

        Uses the default config if ``config`` is None, checks the config's type and
        the number of features and grouping columns it selects, and resolves the
        resources. Tools that draw figures hold ``pyplot_lock`` while they run; result
        figures are then removed from pyplot's registry.

        Raises:
            TypeError: ``config`` is not an instance of the tool's config class.
            ValueError: the config selects fewer features or grouping columns than
                the tool needs.
        """
        config = self.config_class() if config is None else config
        if not isinstance(config, self.config_class):
            raise TypeError(
                f"{self.name} needs a {self.config_class.__name__},"
                f" not a {type(config).__name__}"
            )
        check_requirements(self.name, config, inputs)
        self.context = RunContext.for_config(
            config,
            cancel_token=getattr(self, "_cancel_token", None),
            output_dir=getattr(self, "_output_dir", None),
        )
        with pyplot_lock if self.draws_figures else contextlib.nullcontext():
            results = self.display_names(self.run(*inputs, config=config))
        self.check_processing()
        release_figures(results)
        if config.prefix:
            results = {f"{config.prefix}{k}": v for k, v in results.items()}
        return results

    def applied(self, count: int = 1) -> None:
        """Reports parts of the settings that were applied to the data (e.g. a
        calculation that was made), for a workflow file step's `processing`."""
        context = getattr(self, "context", None)
        if context is not None:
            context.applied += count

    def skip(self, message: str, warn: bool = False) -> None:
        """Reports a part of the settings that does not apply to the data (e.g. a
        calculation whose columns are missing). In a workflow file step it is a
        skipped part for the step's `processing`, and a warning in the run summary;
        otherwise it is logged only (e.g. the default filters on channels many data
        sets don't have), unless `warn`."""
        if warn or getattr(self, "_processing", None) is not None:
            self.warn(message)
        else:
            logger.info(f"{self.name}: {message}")
        context = getattr(self, "context", None)
        if context is not None:
            context.skipped.append(message)

    def check_processing(self) -> None:
        """Fails the run if a workflow file step's `processing` doesn't allow what
        was skipped: `require_all` no skipped part, `allow_partial` at least one
        applied part (if any were skipped), `allow_none` anything.

        Raises:
            ValueError: If the step's processing doesn't allow it.
        """
        processing = getattr(self, "_processing", None)
        context = getattr(self, "context", None)
        if processing is None or context is None or not context.skipped:
            return
        skipped = len(context.skipped)
        if processing == "require_all":
            raise ValueError(
                f"{self.name}: {skipped} part(s) of the settings don't apply"
                " (processing: require_all): " + "; ".join(context.skipped)
            )
        if processing == "allow_partial" and context.applied == 0:
            raise ValueError(
                f"{self.name}: none of the settings apply (processing: allow_partial)"
            )

    def warn(self, message: str) -> None:
        """Reports a warning of this run: logged now, and listed with the task in the
        run summary (and as its message in the Prefect UI)."""
        logger.warning(f"{self.name}: {message}")
        context = getattr(self, "context", None)
        if context is not None:
            context.warnings.append(message)

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
        override it. If an input schema is unknown, the tool draws figures, or the run
        on the samples fails, the result holds only the declared ``outputs``, with
        their table schemas marked unknown.
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
            logger.debug(f"{cls.name}: no output schema from sample data: {err}")
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
    def example(cls, config: ConfigT, tables: Sequence[Any]) -> Optional[str]:
        """Return one line that shows what the tool does with the first row of the
        input, for its dialog, e.g. `FOV 1, Cell 2 -> FOV:Cell 1:2`.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames).

        Returns:
            The line; None if the tool shows none (the default).
        """
        return None

    @classmethod
    def dialog_config(cls, config: ConfigT) -> ConfigT:
        """Return the config the tool's dialog opens with, from its stored settings.

        Args:
            config: The stored config.

        Returns:
            The config; by default the stored one.
        """
        return config

    @classmethod
    def proposals(cls, config: ConfigT, tables: Sequence[Any]) -> dict[str, Any]:
        """Return values the dialog fills into empty fields once the input tables are
        known, e.g. the new names of columns in the way of the tool's.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames).

        Returns:
            Field name -> value; none by default.
        """
        return {}

    @classmethod
    def validate_data(cls, config: ConfigT, tables: Sequence[Any]) -> list[Issue]:
        """Check the config against the input tables' values (`validate` checks it
        against their columns), for the dialog; the run makes the same checks.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames).

        Returns:
            The issues, usually warnings; none by default.
        """
        return []

    @classmethod
    def validate(cls, config: ConfigT, inputs: Sequence[Any]) -> list[Issue]:
        """Checks the config against the input schemas: the number of features and
        grouping columns it selects, and that the columns it names exist and have the
        right role. The columns are not checked if an input schema is unknown or
        incomplete. A text column named as a feature is a warning."""
        schemas = _flat_schemas(inputs)
        # the number of features and grouping columns the tool needs
        issues = requirement_issues(config, schemas)
        if not schemas or any(s is None or not s.complete for s in schemas):
            return issues
        columns = {c.name: c for s in schemas for c in s.columns}
        for path, name, role in column_references(config):
            column = columns.get(name)
            if column is None:
                issues.append(Issue(path, f"Column '{name}' is not in the input"))
            elif column.role == "other" and role == "feature":
                # e.g. a text column: some tools take it (min, max), others fail
                message = f"'{name}' is a text column, not a feature"
                issues.append(Issue(path, message, severity="warning"))
            elif role == "label":
                if column.role not in ("category", "other"):
                    message = f"'{name}' is not a category or text column"
                    issues.append(Issue(path, message))
            elif column.role != role:
                issues.append(Issue(path, f"'{name}' is not a {role} column"))
        return issues


def check_requirements(name: str, config: TaskConfig, inputs: Sequence[Any]) -> None:
    """Raises ValueError if the config selects fewer features or grouping columns than
    the tool needs for ``inputs`` (DataFrames or TableSchemas)."""
    import pandas as pd

    schemas = [
        TableSchema.from_frame(i) if isinstance(i, pd.DataFrame) else i
        for i in _flat_schemas(inputs)
    ]
    issues = requirement_issues(config, schemas)
    if issues:
        raise ValueError(f"{name}: " + "; ".join(i.message.lower() for i in issues))


def _flat_schemas(inputs: Sequence[Any]) -> list:
    flat = []
    for i in inputs:
        flat.extend(i.values() if isinstance(i, dict) else [i])
    return flat


def _unknown(output: OutputSpec) -> OutputSpec:
    if output.type is TableType:
        return replace(output, schema=TableSchema.unknown())
    return output
