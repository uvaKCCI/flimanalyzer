"""Workflows: tools whose run is a Prefect flow of other tools.

A workflow is registered like a tool (category "Workflow") and configured with a
:class:`flim.configs.workflow.WorkflowConfig`. Its :meth:`Workflow.build` calls the
tools of its steps, each with its step config, inside a flow; :meth:`Workflow.run_flow`
runs that flow and returns the :class:`flim.core.runner.FlowRun` (task graph, results,
run summary).
"""

from typing import Any, ClassVar, Optional

from flim.core.config import TaskConfig
from flim.core.tool import ConfigT, Tool


class Workflow(Tool[ConfigT]):
    category: ClassVar[str] = "Workflow"
    icon: ClassVar[Optional[str]] = "workflow.png"

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
    ):
        """Runs the workflow as a Prefect flow; see :func:`flim.core.runner.run_flow`.

        Returns:
            flim.core.runner.FlowRun: task graph and results.
        """
        from flim.core.runner import run_flow

        config = self.config_class() if config is None else config
        return run_flow(
            self.name,
            lambda: self.build(*inputs, config=config),
            task_runner=task_runner,
            autosave_dir=autosave_dir,
            on_progress=on_progress,
            cancel_token=cancel_token,
            on_start=on_start,
        )

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
