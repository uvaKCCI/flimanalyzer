"""Workflows: tools whose run is a Prefect flow of other tools.

A workflow is registered like a tool (category "Workflow") and configured with a
:class:`flim.configs.workflow.WorkflowConfig`. Its :meth:`Workflow.build` calls the
tools of its steps, each with its step config, inside a flow; :meth:`Workflow.run_flow`
runs that flow and returns the :class:`flim.core.runner.FlowRun` (task graph, results,
run summary).
"""

from typing import Any, ClassVar, Optional

import pandas as pd

from flim.core.config import TaskConfig
from flim.core.schema import TableSchema
from flim.core.tool import ConfigT, Tool
from flim.core.validation import DefaultWorkflowValidator, ValidationReport


class WorkflowValidationError(ValueError):
    """The workflow's config has errors for its inputs (see ``report``)."""

    def __init__(self, report: ValidationReport):
        self.report = report
        lines = [
            f"{i.step}: {i.message}" if i.step else i.message for i in report.errors
        ]
        super().__init__("\n".join(lines))


class Workflow(Tool[ConfigT]):
    category: ClassVar[str] = "Workflow"
    icon: ClassVar[Optional[str]] = "workflow.png"
    # checks the config and its steps against the inputs; replaceable, e.g. by one
    # with lab-specific naming rules (see flim.core.validation.WorkflowValidator)
    validator: ClassVar = DefaultWorkflowValidator()

    def build(self, *inputs, config: ConfigT) -> None:
        """Calls the tools of the workflow's steps (inside a flow, see run_flow).

        Inputs are the workflow's input tables; tool calls return
        :class:`flim.core.runner.TaskOutput` handles to pass on to other calls.
        """
        raise NotImplementedError

    def run_flow(
        self,
        *inputs,
        config: Optional[ConfigT] = None,
        task_runner=None,
        autosave_dir: Optional[str] = None,
        on_progress=None,
        cancel_token=None,
        on_start=None,
        strict: Optional[bool] = None,
    ):
        """Runs the workflow as a Prefect flow; see :func:`flim.core.runner.run_flow`.

        The config is validated first (:meth:`resolve`); the run uses it with the
        guessed columns, which the run summary lists.

        Args:
            strict: the default for a config whose ``strict`` is None; None: strict
                (no guesses), as in batch runs. The GUI passes False.

        Raises:
            WorkflowValidationError: the config has errors for these inputs.

        Returns:
            flim.core.runner.FlowRun: task graph and results.
        """
        from flim.core.runner import run_flow

        config = self.config_class() if config is None else config
        report = self.resolve(config, inputs, strict)
        if report.errors:
            raise WorkflowValidationError(report)
        config = report.config
        notes = [
            f"{i.step + ': ' if i.step else ''}{i.field}: '{i.old}' -> '{i.suggestion}'"
            " (guessed)"
            for i in report.guesses
        ]
        return run_flow(
            self.name,
            lambda: self.build(*inputs, config=config),
            task_runner=task_runner,
            autosave_dir=autosave_dir,
            on_progress=on_progress,
            cancel_token=cancel_token,
            on_start=on_start,
            notes=notes,
        )

    @classmethod
    def is_strict(cls, config, default: Optional[bool] = None) -> bool:
        """Whether columns missing from the inputs are errors (else guessed)."""
        strict = getattr(config, "strict", None)
        if strict is None:
            strict = default
        return True if strict is None else strict

    def resolve(self, config, inputs, strict: Optional[bool] = None):
        """Validates the config for input tables (or their schemas): the report's
        config has the guesses applied."""
        schemas = [
            TableSchema.from_frame(i) if isinstance(i, pd.DataFrame) else i
            for i in inputs
        ]
        return self.validator.validate(
            type(self), config, schemas, self.is_strict(config, strict)
        )

    @classmethod
    def validate(cls, config, inputs):
        """Issues of the config and of its steps for the input schemas; columns
        missing from the inputs are guessed unless the config is strict (dialogs)."""
        strict = cls.is_strict(config, False)
        return cls.validator.validate(cls, config, list(inputs), strict).issues

    def run(self, *inputs, config: ConfigT) -> dict[str, Any]:
        """Runs the flow (without saving) and returns the results of all its tasks."""
        results = {}
        for result in self.run_flow(*inputs, config=config).results():
            if isinstance(result, dict):
                results.update(result)
        return results

    @classmethod
    def output_schema(cls, config, inputs):
        return {}  # many, known once the flow is built


class _Input(Tool[TaskConfig]):
    """A workflow's input table, as a node of its graph (not registered)."""

    name = "Input"
    graph_kind = "output"

    def run_task(self, inputs, config=None):
        return inputs[0]  # the table itself, for the steps that use it


def workflow_input(data, name: str = "Input", task_tags=None):
    """The input table of a workflow, the first node of its graph."""
    step = _Input()
    step.name = name
    return step(data, task_tags=task_tags or name)
