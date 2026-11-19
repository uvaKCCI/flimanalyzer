"""Base class of tools: stateless operations configured by a Pydantic config.

A tool is called with its inputs and a config::

    results = Summarize()(table, config=SummaryConfig(grouping=["Treatment"]))

Inside `flim.core.runner.run_flow` the call becomes a Prefect task and returns a
`flim.core.runner.TaskOutput` handle; outside a flow it returns the results.
Results are keyed by display name (`Table: Summary`), with the config's prefix.
"""

import contextlib
import logging
import os
from pathlib import Path
import sys
import threading
import typing
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Optional, Sequence, TypeVar, Union

from pydantic import BaseModel

from flim.core.config import Issue, TaskConfig, column_references, requirement_issues
from flim.core.deprecation import deprecated_names
from flim.core.registry import API_VERSION
from flim.core.schema import TableSchema
from flim.core.types import DataType, InputSpec, OutputSpec, TableType

if TYPE_CHECKING:
    import pandas as pd

    from flim.core.runner import TaskOutput

logger = logging.getLogger(__name__)

# names of 0.6 that were renamed: still importable, with a DeprecationWarning
__getattr__ = deprecated_names(
    __name__, {"check_requirements": (__name__, "validate_requirements", "0.8.0")}
)

ConfigT = TypeVar("ConfigT", bound=TaskConfig)

# pyplot's figure registry and current-figure state are shared by all threads: tasks
# that draw figures take turns, all other tasks run concurrently
pyplot_lock = threading.RLock()


def release_figures(results: Any) -> None:
    """Remove the result figures from pyplot's registry.

    pyplot keeps every figure it created until the figure is closed. The figures
    stay usable (saving, showing). Does nothing if pyplot is not imported.

    Args:
        results: The results of a task, keyed by name; values that are not
            matplotlib figures, and results that are not a dict, are ignored.
    """
    if not isinstance(results, dict) or "matplotlib.pyplot" not in sys.modules:
        return
    import matplotlib.figure
    import matplotlib.pyplot as plt

    figures = [v for v in results.values() if isinstance(v, matplotlib.figure.Figure)]
    with pyplot_lock:
        for figure in figures:
            plt.close(figure)


class TaskCancelled(Exception):
    """Raised by `Tool.cancel` to stop the running task.

    Prefect handles it like any other exception (the task run ends Failed and tasks
    that depend on it are not run); the runner records the task as cancelled.
    """


def resolve_device(preferred: str) -> tuple[str, Optional[str]]:
    """Return the device to use for `preferred` on this machine.

    `auto` picks a CUDA GPU, then the Apple GPU (`mps`), then the CPU. torch is
    imported only for devices other than the CPU.

    Args:
        preferred: The preferred device: `cpu`, `cuda`, `mps` or `auto`.

    Returns:
        The device, and a note why it differs from the preferred one; the note is
        None if the preferred device is used or `auto` was preferred.
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
    """Return the number of threads to use for `preferred`.

    Args:
        preferred: The preferred number of threads; -1 for all cores.

    Returns:
        The number of cores for -1; otherwise `preferred`, at least 1 and at most
        the number of cores.
    """
    cores = os.cpu_count() or 1
    return cores if preferred == -1 else max(1, min(preferred, cores))


@dataclass
class RunContext:
    """The device and threads a task runs with, its cancel signal, folder and warnings.

    The device and threads come from the config's resources and this machine.
    """

    device: str = "cpu"
    threads: int = 1
    note: Optional[str] = None  # e.g. why the preferred device was not used
    cancel_token: Any = None  # flim.core.runner.CancelToken
    # where tools write files they produce (e.g. models); None: not set by the caller
    output_dir: Optional[Path] = None
    # warnings of this run (Tool.warn): the task's message in the run summary
    warnings: list = field(default_factory=list)
    # entries of the settings applied and skipped (Tool.applied, Tool.skip), for a
    # workflow file step's `processing`; skipped: (field, entry, why) per entry
    applied: int = 0
    skipped: list = field(default_factory=list)

    @classmethod
    def for_config(
        cls,
        config: TaskConfig,
        cancel_token: Any = None,
        output_dir: Optional[Path] = None,
    ) -> "RunContext":
        """Return the context for a config's resources on this machine.

        A note why the preferred device is not used is logged.

        Args:
            config: The task's config; its `resources` give the preferred device
                and threads.
            cancel_token: The run's cancel signal (`flim.core.runner.CancelToken`);
                None outside a flow.
            output_dir: The folder for files the tool writes; None if not set.

        Returns:
            The context.
        """
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


# tools already warned about for declaring no output types (see Tool.output_kinds)
_UNDECLARED: set[type] = set()


class Tool(Generic[ConfigT]):
    """Base of all tools.

    Subclasses set the class attributes, name their config class as the generic
    parameter (`class Sort(Tool[SortConfig])`) and implement `run`.
    """

    name: ClassVar[str] = ""
    # earlier names, under which settings may have been saved
    former_names: ClassVar[tuple[str, ...]] = ()
    # a short form of the name where space is tight, e.g. in column names a tool
    # writes ("Source (before Import)"); at most SHORT_NAME_LENGTH characters; empty:
    # the name
    short_name: ClassVar[str] = ""
    # where the GUI shows the tool: a menu (`"Analysis"`), or a list of a menu and its
    # submenus (`["Analysis", "Autoencoder"]`); None or empty: in no menu and not in
    # the tool panel (still runnable by name and as a workflow step)
    category: ClassVar[Union[str, list[str], None]] = None
    # more Prefect tags of the tool's tasks, besides its name and former names (so
    # that concurrency limits set on them apply), e.g. a workflow's name on its step;
    # the former names of a tool named here are tags too (see `runner.task_names`)
    extra_tags: ClassVar[tuple[str, ...]] = ()
    description: ClassVar[str] = ""
    icon: ClassVar[Optional[str]] = None  # resource name; the GUI loads the bitmap
    api_version: ClassVar[int] = API_VERSION
    graph_kind: ClassVar[str] = "tool"  # node style in the workflow graph
    # True if the whole task draws with pyplot (see pyplot_lock)
    draws_figures: ClassVar[bool] = False
    inputs: ClassVar[tuple[InputSpec, ...]] = (InputSpec("data", TableType),)
    # outputs whose names don't depend on config or input; see output_schema
    outputs: ClassVar[tuple[OutputSpec, ...]] = ()
    # the types of all outputs, also of those whose names depend on the settings
    # (e.g. Summarize: one table per feature); fixed by the tool, see output_kinds
    output_types: ClassVar[tuple[type[DataType], ...]] = ()
    # config fields whose entries `processing.skippable` may let a step skip: the
    # column lists of the base config (the runner removes their missing entries) and
    # the rule lists a tool counts itself (`applied`, `skip`)
    skippable_fields: ClassVar[tuple[str, ...]] = ("grouping", "features")
    # config fields whose missing columns are never guessed: always strict
    never_guessed: ClassVar[tuple[str, ...]] = ()
    config_class: ClassVar[type[TaskConfig]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Set `config_class` from the generic parameter of the class's base."""
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            origin = typing.get_origin(base)  # Tool, or a generic subclass of it
            if isinstance(origin, type) and issubclass(origin, Tool):
                (config_class,) = typing.get_args(base)
                if isinstance(config_class, type):
                    cls.config_class = config_class

    def __init__(self) -> None:
        """Create the tool with a default run context."""
        self.context = RunContext()

    @classmethod
    def output_kinds(cls) -> list[str]:
        """Return the kinds of output the tool makes, e.g. `["table"]`.

        The kinds are a fixed property of the tool, whatever its settings: those of
        `outputs` and `output_types`, in that order. They bound the tool's
        `output.formats`: the GUI offers formats for these kinds only, and the validation
        of tool and workflow files refuses formats of other kinds. A tool that
        declares neither (a plugin tool written for an earlier version) makes any
        kind: a `DeprecationWarning` is given once, and `output_types` is required
        from 0.8.0.

        Returns:
            The kinds without repeats; for a tool that declares none, all kinds with
            save options.
        """
        kinds = [o.type.kind for o in cls.outputs] + [t.kind for t in cls.output_types]
        if kinds:
            return list(dict.fromkeys(kinds))
        if cls not in _UNDECLARED:
            import warnings

            _UNDECLARED.add(cls)
            warnings.warn(
                f"{cls.name} ({cls.__module__}.{cls.__qualname__}) declares no output"
                " types: set output_types (e.g. (TableType,)); tools without them are"
                " not accepted from FLIMAnalyzer 0.8.0",
                DeprecationWarning,
                stacklevel=2,
            )
        from flim.core.saving import save_options_classes

        return sorted(save_options_classes(), key=lambda k: (k != "table", k))

    @classmethod
    def short(cls) -> str:
        """Return the short name, or the name if the tool has none."""
        return cls.short_name or cls.name

    def __repr__(self) -> str:
        """Return the class name and the tool's name."""
        return f"<{type(self).__name__}>: {self.name}"

    # --- the computation ---

    def run(self, *inputs: Any, config: ConfigT) -> dict[str, Any]:
        """Compute the results; subclasses implement it.

        Args:
            *inputs: The inputs, one per entry of `inputs` (e.g. DataFrames; a dict
                of them for an input with `many=True`).
            config: The config.

        Returns:
            The results, keyed by output name (e.g. `Summary`).

        Raises:
            NotImplementedError: Always, in the base class.
        """
        raise NotImplementedError

    def map_configs(self, config: ConfigT) -> list[ConfigT]:
        """Return the configs of the smallest independent calls, e.g. one per feature.

        Args:
            config: The config.

        Returns:
            The configs; by default `config` alone.
        """
        return [config]

    @classmethod
    def mappable_output(cls, config: ConfigT) -> bool:
        """Return whether the tool's output is a list of parts with this config.

        True in the tool's per-part mode, the mode in which `map_configs` splits
        (e.g. Summarize without `single_table`), whatever the number of parts: one
        feature still gives a list of one part. Each part is a call with one
        config of `map_configs`; later steps of a workflow map over the parts.

        Args:
            config: The config.

        Returns:
            False by default.
        """
        return False

    @classmethod
    def output_prefix(cls, config: ConfigT) -> str:
        """Return the name of the part a config of `map_configs` makes.

        A name only (e.g. the feature); the runner decides where it is used, e.g.
        for the part's folder.

        Args:
            config: One config of `map_configs`.

        Returns:
            The part's name; empty by default.
        """
        return ""

    # --- calling ---

    def __call__(
        self,
        *inputs: Any,
        config: Optional[ConfigT] = None,
        task_tags: Optional[str | Sequence[str]] = None,
        after: Sequence["TaskOutput"] = (),
        step: Optional[str] = None,
    ) -> Any:
        """Call the tool: run it directly, submit it as a task, or trace it.

        See `flim.core.runner.call_tool`.

        Args:
            *inputs: The inputs (values, or `TaskOutput` handles inside a flow).
            config: The config; None for the default config.
            task_tags: The tags of the task, one or several; None for none.
            after: Handles of tasks this one waits for although they are not its
                inputs, e.g. those whose results (model files) its config names.
            step: The id of the workflow step the call belongs to, e.g. `03`, which
                names its results folder (`03-<tool>`); None for none.

        Returns:
            Outside a flow, the results by display name (see `run_task`); inside a
            flow, a `TaskOutput` handle; during a dry run, a
            `flim.core.validation.TraceOutput`.
        """
        from flim.core.runner import call_tool

        return call_tool(self, inputs, config, task_tags=task_tags, after=after, step=step)

    def run_task(
        self, inputs: Sequence[Any], config: Optional[ConfigT] = None
    ) -> dict[str, Any]:
        """Run the tool as one task.

        Uses the default config if `config` is None, validates the config's type and
        the number of features and grouping columns it selects, and resolves the
        resources. Tools that draw figures hold `pyplot_lock` while they run; result
        figures are then removed from pyplot's registry. Afterwards the parts of the
        settings that were skipped are validated against the step's `processing` (see
        `validate_processing`). In a workflow file step, the step's `processing` is
        applied to the config first (`_resolve`).

        Args:
            inputs: The inputs, passed to `run` in this order.
            config: The config; None for the default config.

        Returns:
            The results by display name, each prefixed with the config's `prefix`,
            for example `Table: Summary`.

        Raises:
            TypeError: If `config` is not an instance of the tool's config class.
            ValueError: If the config selects fewer features or grouping columns than
                the tool needs, if a column it names is missing and the step's
                `processing` neither guesses nor skips it, or if the step's
                `processing` does not allow the skipped entries.
        """
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
        if getattr(self, "_processing", None) is not None:
            config = self._resolve(config, inputs)
        validate_requirements(self.name, config, inputs)
        with pyplot_lock if self.draws_figures else contextlib.nullcontext():
            results = self.display_names(self.run(*inputs, config=config))
        self.validate_processing()
        release_figures(results)
        if config.prefix:
            results = {f"{config.prefix}{k}": v for k, v in results.items()}
        return results

    def _resolve(self, config: ConfigT, inputs: Sequence[Any]) -> ConfigT:
        """Apply a workflow file step's `processing` to the config for the inputs.

        See `flim.core.validation.resolve_step`. The guesses and the skipped
        entries, also those applied before the run (`_notes`), are warnings of the
        run.

        Raises:
            ValueError: If a column the config names is not in the inputs and the
                step's `processing` neither guesses nor skips it, or if fewer
                entries apply than the tool needs.
        """
        from flim.core.validation import resolve_step

        def schema(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: schema(v) for k, v in value.items()}
            return TableSchema.from_frame(value) if hasattr(value, "columns") else None

        resolution = resolve_step(type(self), config, [schema(i) for i in inputs], self._processing)
        if resolution.errors:
            raise ValueError(f"{self.name}: " + "; ".join(resolution.errors))
        for note in list(getattr(self, "_notes", ())) + [
            f"{g} (guessed)" for g in resolution.guessed
        ] + [f"skipped {s}" for s in resolution.skipped]:
            self.warn(note)
        return resolution.config

    def applied(self, count: int = 1) -> None:
        """Report parts of the settings that were applied to the data.

        For example a calculation that was made; counted for a workflow file step's
        `processing`.

        Args:
            count: The number of parts. Defaults to 1.
        """
        context = getattr(self, "context", None)
        if context is not None:
            context.applied += count

    def skip(
        self, message: str, warn: bool = False, field: str = "", entry: Any = None
    ) -> None:
        """Report an entry of the settings that does not apply to the data.

        For example a calculation whose columns are missing. The entry is recorded as
        skipped for a workflow file step's `processing`. In a workflow file step, or
        with `warn`, it is a warning in the run summary; otherwise it is only logged
        (e.g. the default filters on channels many data sets don't have).

        Args:
            message: What was skipped and why.
            warn: Whether to report it as a warning outside a workflow file step too.
                Defaults to False.
            field: The config field of the entry, one of `skippable_fields`; empty
                for the tool's rule list (its last skippable field).
            entry: The entry (a list element, or a dict key), for
                `processing.required`; None if not known.
        """
        if warn or getattr(self, "_processing", None) is not None:
            self.warn(message)
        else:
            logger.info(f"{self.name}: {message}")
        context = getattr(self, "context", None)
        if context is not None:
            context.skipped.append((field or self.skippable_fields[-1], entry, message))

    def validate_processing(self) -> None:
        """Fail the run if a workflow file step's `processing` doesn't allow the skips.

        Per field with skipped entries: `none` (the default) allows no skipped entry,
        `some` needs at least one applied entry, `all` allows any; an entry listed in
        `processing.required` is never skipped. Does nothing outside a workflow file
        step or if nothing was skipped.

        Raises:
            ValueError: If the step's `processing` doesn't allow what was skipped.
        """
        rules = getattr(self, "_processing", None)
        context = getattr(self, "context", None)
        if rules is None or context is None or not context.skipped:
            return
        by_field: dict[str, list] = {}
        for field_name, entry, message in context.skipped:
            by_field.setdefault(field_name, []).append((entry, message))
        for field_name, skipped in by_field.items():
            required = rules.required.get(field_name, [])
            missing = [m for e, m in skipped if e is not None and is_listed(e, required)]
            if missing:
                raise ValueError(
                    f"{self.name}: required entries of {field_name} don't apply"
                    f" (processing.required): {'; '.join(missing)}"
                )
            mode = rules.skip(field_name)
            if mode == "none":
                raise ValueError(
                    f"{self.name}: {len(skipped)} entries of {field_name} don't apply:"
                    f" {'; '.join(m for _, m in skipped)}. Set"
                    f' processing.skippable.{field_name} to "some" or "all" to skip'
                    " them"
                )
            if mode == "some" and context.applied == 0:
                raise ValueError(
                    f"{self.name}: no entry of {field_name} applies"
                    f' (processing.skippable.{field_name} is "some": at least one has to'
                    " apply)"
                )

    def warn(self, message: str) -> None:
        """Report a warning of this run.

        The warning is logged now and listed with the task in the run summary (and
        as its message in the Prefect UI).

        Args:
            message: The warning.
        """
        if getattr(self, "_quiet", False):  # an example for the dialog (`preview`)
            return
        logger.warning(f"{self.name}: {message}")
        context = getattr(self, "context", None)
        if context is not None:
            context.warnings.append(message)

    @staticmethod
    def display_names(results: dict[str, Any]) -> dict[str, Any]:
        """Return the results keyed by display name, e.g. `Summary` → `Table: Summary`.

        Args:
            results: The results, keyed by output name.

        Returns:
            The same values; names of values of an unknown data type are kept.
        """
        named = {}
        for name, value in results.items():
            data_type = DataType.of(value)
            named[data_type.display_name(name) if data_type else name] = value
        return named

    # --- cancellation ---

    def cancel(self, message: str = "Cancelled") -> typing.NoReturn:
        """Stop this task; call it only from `run`.

        Inside a flow, the task is recorded as cancelled and tasks that use its results
        are not run; other tasks continue. Outside a flow, the exception reaches the
        caller.

        Args:
            message: The reason. Defaults to `Cancelled`.

        Raises:
            TaskCancelled: Always.
        """
        raise TaskCancelled(message)

    def check_cancelled(self) -> None:
        """Stop this task if the user cancelled the run.

        Call it regularly from long-running `run` methods. Does nothing outside a
        flow.

        Raises:
            TaskCancelled: If the run was cancelled.
        """
        # the runner sets _cancel_token before the task starts, the context once it runs
        token = self.context.cancel_token or getattr(self, "_cancel_token", None)
        if token is not None and token.is_set():
            self.cancel("Run cancelled by the user")

    # --- schemas and validation, without the data ---

    @classmethod
    def output_schema(
        cls, config: ConfigT, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return the outputs for `config` and the input schemas, keyed by output name.

        The default runs the tool on a few sample rows built from the input schemas;
        tools for which that is expensive or wrong override it. If an input schema is
        unknown, the tool draws figures, or the run on the samples fails, the result
        holds only the declared `outputs`, with their table schemas marked unknown.

        Args:
            config: The config.
            inputs: One `TableSchema` per input (a dict of them for an input with
                `many=True`), or None if unknown.

        Returns:
            The output specs, with the table schema of each table output.
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
    def example(
        cls, config: ConfigT, tables: Sequence[Any]
    ) -> Union[str, "pd.DataFrame", None]:
        """Return an example of what the tool does with the input, for its dialog.

        A table of a few rows: the input columns next to the columns the tool makes
        (see `example_table`), e.g. `FOV`, `Cell` and `→ FOV:Cell`; or one line,
        e.g. `no columns dropped` or why the settings give no result.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames).

        Returns:
            The table or the line; None if the tool shows none (the default).
        """
        return None

    @classmethod
    def used_config(cls, config: ConfigT, tables: Sequence[Any]) -> ConfigT:
        """Return the config with the values the tool uses on the tables filled in.

        It is the record of a run: the task's settings artifact shows it. For
        example, columns found by name at run time are filled in.

        Args:
            config: The config the task runs with.
            tables: The input tables (DataFrames).

        Returns:
            The config; by default the one given.
        """
        return config

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
        """Return values the dialog fills into empty fields once the tables are known.

        For example the new names of columns in the way of the tool's.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames).

        Returns:
            Field name -> value; none by default.
        """
        return {}

    @classmethod
    def inapplicable_fields(cls, config: ConfigT, tables: Sequence[Any]) -> set[str]:
        """Return the fields that don't apply to the input tables.

        The dialog hides them, e.g. how to rename a column the tables don't have.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames); empty if not known.

        Returns:
            The field names; none by default.
        """
        return set()

    @classmethod
    def validate_data(cls, config: ConfigT, tables: Sequence[Any]) -> list[Issue]:
        """Validate the config against the input tables' values, for the dialog.

        `validate` validates it against their columns; the run makes the same validations.

        Args:
            config: The config.
            tables: The selected input tables (DataFrames).

        Returns:
            The issues, usually warnings; none by default.
        """
        return []

    @classmethod
    def validate(cls, config: ConfigT, inputs: Sequence[Any]) -> list[Issue]:
        """Validate the config against the input schemas.

        Validates the number of features and grouping columns it selects, and that the
        columns it names exist and have the right role. The columns are not validated
        if an input schema is unknown or incomplete. A text column named as a feature
        is a warning.

        Args:
            config: The config.
            inputs: One `TableSchema` per input (a dict of them for an input with
                `many=True`), or None if unknown.

        Returns:
            The issues; empty if the config is valid.
        """
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


def is_listed(entry: Any, entries: Sequence[Any]) -> bool:
    """Return whether an entry of a config field is one of `entries`.

    An entry equals a listed entry, or, for a model (e.g. a calculation), a listed
    dict whose items it has: `{"name": "FLIRR"}` lists the calculation `FLIRR`.

    Args:
        entry: A list element or dict key of a config field.
        entries: The listed entries, as in a settings file.

    Returns:
        Whether it is listed.
    """
    as_json = entry.model_dump(mode="json") if isinstance(entry, BaseModel) else None
    for listed in entries:
        if listed == entry:
            return True
        if isinstance(as_json, dict) and isinstance(listed, dict) and listed:
            if all(k in as_json and as_json[k] == v for k, v in listed.items()):
                return True
    return False


def validate_requirements(name: str, config: TaskConfig, inputs: Sequence[Any]) -> None:
    """Validate that the config selects enough features and grouping columns.

    Args:
        name: The tool's name, for the message.
        config: The config.
        inputs: The inputs: DataFrames or `TableSchema`s (a dict of them for an
            input with `many=True`).

    Raises:
        ValueError: If the config selects fewer features or grouping columns than
            the tool needs for `inputs`.
    """
    import pandas as pd

    schemas = [
        TableSchema.from_frame(i) if isinstance(i, pd.DataFrame) else i
        for i in _flat_schemas(inputs)
    ]
    issues = requirement_issues(config, schemas)
    if issues:
        raise ValueError(f"{name}: " + "; ".join(i.message.lower() for i in issues))


def _flat_schemas(inputs: Sequence[Any]) -> list[Any]:
    """Return the inputs with the values of dict inputs in their place."""
    flat = []
    for i in inputs:
        flat.extend(i.values() if isinstance(i, dict) else [i])
    return flat


def _unknown(output: OutputSpec) -> OutputSpec:
    """Return the output spec with its table schema marked unknown."""
    if output.type is TableType:
        return replace(output, schema=TableSchema.unknown())
    return output


# --- examples for the dialogs (`Tool.example`) ---

EXAMPLE_ROWS = 4  # the rows of an example table
EXAMPLE_COLUMNS = 3  # the input columns of an example table, e.g. features
MADE = "\u2192 "  # marks a column the tool makes, e.g. `→ FOV:Cell`


def example_table(
    before: "pd.DataFrame", after: "pd.DataFrame", caption: str = ""
) -> "pd.DataFrame":
    """Return an example: input columns next to the columns a tool makes from them.

    The rows are paired by position. The columns the tool makes are marked with
    `MADE`, e.g. `→ FOV:Cell`; the lines of column labels with several header
    lines are joined with ` / `, e.g. `FLIRR / ctrl`.

    Args:
        before: The input rows, with the columns the tool reads; may have no
            columns (e.g. a reshaping tool, whose rows don't pair).
        after: The columns the tool makes, for the same rows.
        caption: A note shown above the table, e.g. which rows are shown; empty for
            none.

    Returns:
        The table; its `attrs["caption"]` holds the caption.
    """
    import pandas as pd

    def labels(table: pd.DataFrame, mark: str = "") -> list[str]:
        return [
            mark + (" / ".join(map(str, c)) if isinstance(c, tuple) else str(c)).replace("\n", " / ")
            for c in table.columns
        ]

    before = before.reset_index(drop=True)
    after = after.reset_index(drop=True)
    table = pd.concat(
        [before.set_axis(labels(before), axis=1), after.set_axis(labels(after, MADE), axis=1)],
        axis=1,
    )
    table.attrs["caption"] = caption
    return table


def distinct_rows(
    table: "pd.DataFrame", columns: Sequence[Any], count: int = EXAMPLE_ROWS
) -> "pd.DataFrame":
    """Return the first rows of a table with distinct values in some columns.

    Rows with a missing value in one of the columns are left out.

    Args:
        table: The table.
        columns: The columns whose values differ from row to row.
        count: The most rows returned. Defaults to `EXAMPLE_ROWS`.

    Returns:
        The rows, in the table's order.
    """
    columns = list(columns)
    return table.dropna(subset=columns).drop_duplicates(subset=columns).head(count)


def preview(tool: type[Tool], config: TaskConfig, *inputs: Any) -> dict[str, Any]:
    """Run a tool for an example: its warnings are neither logged nor reported.

    Args:
        tool: The tool class.
        config: The config.
        *inputs: The inputs.

    Returns:
        The results of `Tool.run`.
    """
    instance = tool()
    instance._quiet = True
    return instance.run(*inputs, config=config)
