"""Every task is tagged with its tool's name, besides the workflow's tags."""

import os

import pytest

import flim.tools  # noqa: F401  (registers the tools)
from flim.configs import SummaryConfig
from flim.core.runner import run_flow
from flim.core.workflow import workflow_input
from flim.tools.statistics import Summarize

pytestmark = pytest.mark.usefixtures("prefect_harness")


def _prefect_tags(run):
    """The tags Prefect recorded for each task run of ``run``, by task run name."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterId

    flow_runs = FlowRunFilter(id=FlowRunFilterId(any_=[run.flow_run_id]))
    with get_client(sync_client=True) as client:
        task_runs = client.read_task_runs(flow_run_filter=flow_runs)
    return {task_run.name: set(task_run.tags) for task_run in task_runs}


def test_tasks_are_tagged_with_their_tool_name(flim_data, tmp_path):
    def build():
        data = workflow_input(flim_data)
        config = SummaryConfig(grouping=["Treatment"], features=["FAD a1[%]"])
        Summarize()(data, config=config, task_tags="Step 1")

    run = run_flow("tags", build, autosave_dir=str(tmp_path))
    assert run.state == "completed"
    assert _prefect_tags(run) == {"Input": {"Input"}, "Summarize": {"Step 1", "Summarize"}}
    # the results folders are named by the workflow's tags only
    assert sorted(os.listdir(run.autosave_dir)) == ["Input", "Step 1", "run_summary.txt"]
