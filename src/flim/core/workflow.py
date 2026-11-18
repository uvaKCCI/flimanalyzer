"""Workflows: tools whose run is a Prefect flow of other tools.

A workflow is registered like a tool (category "Workflow") and configured with a
`flim.configs.workflow.WorkflowConfig`. Its `Workflow.build` calls the tools of its
steps, each with its step config, inside a flow; `Workflow.run_flow` runs that flow
and returns the `flim.core.runner.FlowRun` (task graph, results, run summary).
"""

from typing import TYPE_CHECKING, Any, Callable, ClassVar, Mapping, Optional, Sequence
import os

import pandas as pd

from flim.core.config import Issue, ProcessingRules, TaskConfig, requirement_issues
from flim.core.schema import TableSchema
from flim.core.tool import ConfigT, Tool, validate_requirements
from flim.core.types import OutputSpec
from flim.core.validation import (
    DefaultWorkflowValidator,
    ValidationReport,
    resolution_notes,
)

if TYPE_CHECKING:
    from prefect.task_runners import TaskRunner

    from flim.core.runner import CancelToken, FlowRun


class WorkflowValidationError(ValueError):
    """The workflow's config has errors for its inputs (see `report`)."""

    def __init__(self, report: ValidationReport) -> None:
        """Create the error; its message has one line per error of the report.

        Args:
            report: The validation report; each error line starts with its step, if
                it has one.
        """
        self.report = report
        lines = [
            f"{i.step}: {i.message}" if i.step else i.message for i in report.errors
        ]
        super().__init__("\n".join(lines))


class Workflow(Tool[ConfigT]):
    """A tool whose run is a Prefect flow of other tools; subclasses implement `build`.

    The class attribute `validator` validates the config and its steps against the
    inputs before a run (see `resolve` and `validate`).
    """

    category: ClassVar[str] = "Workflow"
    icon: ClassVar[Optional[str]] = "workflow.png"
    # validates the config and its steps against the inputs; replaceable, e.g. by one
    # with lab-specific naming rules (see flim.core.validation.WorkflowValidator)
    validator: ClassVar = DefaultWorkflowValidator()

    def build(self, *inputs: Any, config: ConfigT) -> None:
        """Call the tools of the workflow's steps, inside a flow (see `run_flow`).

        Inside the flow, tool calls return `flim.core.runner.TaskOutput` handles to
        pass on to other calls.

        Args:
            *inputs: The workflow's input tables.
            config: The workflow's config.

        Raises:
            NotImplementedError: Always; subclasses implement it.
        """
        raise NotImplementedError

    def run_flow(
        self,
        *inputs: Any,
        config: Optional[ConfigT] = None,
        task_runner: Optional["TaskRunner"] = None,
        autosave_dir: Optional[str | os.PathLike] = None,
        on_progress: Optional[Callable[[int, int, str, bool], None]] = None,
        cancel_token: Optional["CancelToken"] = None,
        on_start: Optional[Callable[["FlowRun"], None]] = None,
        processing: Optional[ProcessingRules] = None,
        settings_record: Sequence[str] = (),
        save_formats: Sequence[Any] = (),
        run_dir: Optional[str | os.PathLike] = None,
        notes: Sequence[str] = (),
        char_replacements: Optional[Mapping[str, str]] = None,
        input_origins: Sequence[tuple[Any, Any]] = (),
    ) -> "FlowRun":
        """Run the workflow as a Prefect flow; see `flim.core.runner.run_flow`.

        The config is validated first (`resolve`); the run uses it with the guessed
        columns, which the run summary lists.

        Args:
            *inputs: The workflow's input tables.
            config: The workflow's config; None for the default config.
            task_runner: The Prefect task runner; None for
                `flim.core.runner.default_task_runner`.
            autosave_dir: The folder below which the tasks' results are saved, in a
                folder per run; None saves nothing.
            on_progress: Called with the task counts; see `flim.core.runner.FlowRun`.
            cancel_token: The signal that cancels the run when set; None for a new
                one.
            on_start: Called with the `flim.core.runner.FlowRun` once Prefect has
                created the flow run, before the first task.
            processing: How the run treats input that doesn't match the config
                (the tool's `processing`); None: strict, nothing skipped.
            settings_record: Lines for the run summary naming the settings files
                used.
            save_formats: The formats all steps save their results in.
            char_replacements: The text replaced in the names of saved files and
                folders (`output.char_replacements`); None: the defaults.
            input_origins: Where the inputs come from, e.g. the file a table was
                read from (`flim.core.runner.InputOrigin`), for the run summary.
            run_dir: The run's folder, used as it is; None: a folder per run below
                `autosave_dir`.
            notes: Lines for the run summary, besides the guessed columns and
                skipped entries.

        Returns:
            The run: its task graph, results and state.

        Raises:
            ValueError: If the config selects fewer features or grouping columns than
                the workflow needs.
            WorkflowValidationError: If the config has errors for these inputs.
        """
        from flim.core.runner import run_flow

        config = self.config_class() if config is None else config
        report = self.resolve(config, inputs, processing)
        if report.errors:
            raise WorkflowValidationError(report)
        config = report.config
        validate_requirements(self.name, config, inputs)  # after skipped entries
        notes = list(notes) + resolution_notes(report)
        return run_flow(
            self.name,
            lambda: self.build(*inputs, config=config),
            task_runner=task_runner,
            autosave_dir=autosave_dir,
            on_progress=on_progress,
            cancel_token=cancel_token,
            on_start=on_start,
            notes=notes,
            settings_record=settings_record,
            save_formats=save_formats,
            run_dir=run_dir,
            char_replacements=char_replacements,
            input_origins=input_origins,
        )

    def resolve(
        self,
        config: ConfigT,
        inputs: Sequence[Any],
        processing: Optional[ProcessingRules] = None,
    ) -> ValidationReport:
        """Validate the config for the input tables, or their schemas.

        Args:
            config: The workflow's config.
            inputs: The input tables (DataFrames) or their schemas (`TableSchema`).
            processing: How missing columns are treated (the tool's `processing`);
                None: strict, nothing skipped.

        Returns:
            The report of the class's `validator`; its config has the guesses
            applied.
        """
        schemas = [
            TableSchema.from_frame(i) if isinstance(i, pd.DataFrame) else i
            for i in inputs
        ]
        return self.validator.validate(
            type(self), config, schemas, processing or ProcessingRules()
        )

    @classmethod
    def validate(
        cls,
        config: ConfigT,
        inputs: Sequence[Any],
        processing: Optional[ProcessingRules] = None,
    ) -> list[Issue]:
        """Validate the config and its steps against the input schemas.

        Args:
            config: The workflow's config.
            inputs: The schemas of the input tables.
            processing: How missing columns are treated (the tool's `processing`);
                None: strict, nothing skipped.

        Returns:
            The issues of the config (the number of features and grouping columns it
            selects) and of its steps.
        """
        rules = processing or ProcessingRules()
        report = cls.validator.validate(cls, config, list(inputs), rules)
        return requirement_issues(report.config, list(inputs)) + report.issues

    def run(self, *inputs: Any, config: ConfigT) -> dict[str, Any]:
        """Run the flow, without saving, and return its results.

        Args:
            *inputs: The workflow's input tables.
            config: The workflow's config.

        Returns:
            The results of the completed tasks, merged into one dict; for equal
            names, the result of the later task.
        """
        results = {}
        for result in self.run_flow(*inputs, config=config).results():
            if isinstance(result, dict):
                results.update(result)
        return results

    @classmethod
    def output_schema(
        cls, config: ConfigT, inputs: Sequence[Any]
    ) -> dict[str, OutputSpec]:
        """Return no outputs: they are known only once the flow has been built."""
        return {}  # the outputs are known only once the flow has been built


class _Input(Tool[TaskConfig]):
    """A workflow's input table, as a node of its graph (not registered)."""

    name = "Input"
    graph_kind = "output"

    def run_task(
        self, inputs: Sequence[Any], config: Optional[TaskConfig] = None
    ) -> Any:
        """Return the input table itself."""
        return inputs[0]  # the table itself, for the steps that use it


def workflow_input(
    data: Any,
    name: str = "Input",
    task_tags: Optional[str | Sequence[str]] = None,
    save: Optional[bool] = None,
    step: Optional[str] = None,
) -> Any:
    """Add the input table of a workflow, the first node of its graph.

    Args:
        data: The table.
        name: The node's name. Defaults to `Input`.
        task_tags: The tags of the node's task; None for the name.
        save: False: the table is not saved with the run's results (workflow files
            save only what their steps' `save` says); None or True: it is saved if
            the run saves its results.
        step: The step id of the input, e.g. `00` (folder `00-Input`); None for none.
            With a step, the name is a folder below it only if it isn't `Input`.

    Returns:
        Inside a flow, a `flim.core.runner.TaskOutput` handle to the table;
        otherwise, also during a dry run, `data` itself.
    """
    node = _Input()
    node.name = name
    node._save = save
    if task_tags is None:
        task_tags = ([] if name == _Input.name else [name]) if step else name
    return node(data, task_tags=task_tags, step=step)
