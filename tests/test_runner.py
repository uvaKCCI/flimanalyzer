import os

import matplotlib.figure
import pandas as pd
import pytest
from prefect import unmapped

from flim.configs import FilterConfig, SortConfig, SummaryConfig
from flim.core.config import TaskConfig
from flim.core.graph import WorkflowGraph
from flim.core.runner import TaskOutput, run_flow, select
from flim.core.tool import Tool
from flim.core.workflow import workflow_input
from flim.tools.data import Filter, Sort
from flim.tools.statistics import Summarize


pytestmark = pytest.mark.usefixtures("prefect_harness")


class Boom(Tool[TaskConfig]):
    name = "Boom"
    category = "Data"

    def run(self, *inputs, config):
        raise RuntimeError("boom")


def _sort(feature):
    return SortConfig(features=[feature])


def test_call_outside_flow_runs_directly(flim_data):
    results = Sort()(flim_data, config=_sort("NAD(P)H t1"))
    assert results["Table: Sorted"]["NAD(P)H t1"].is_monotonic_increasing


def test_chained_calls_and_item_access(flim_data):
    outputs = {}

    def build():
        data = workflow_input(flim_data)
        assert isinstance(data, TaskOutput)
        filtered = Filter()(
            data, config=FilterConfig(category_filters={"Treatment": ["WT"]})
        )
        outputs["summary"] = Summarize()(
            filtered["Table: Filtered"],
            config=SummaryConfig(
                grouping=["Treatment"], features=["NAD(P)H t1"], aggs=["count"]
            ),
        )

    run = run_flow("test chain", build)
    assert run.failed == []
    (summary,) = outputs["summary"].value().values()
    assert summary["NAD(P)H t1\ncount"].tolist() == [30]

    labels = {a["label"]: (n, a["kind"]) for n, a in run.graph.nodes(data=True)}
    assert labels["Input"][1] == "output"
    assert labels["Filter"][1] == "tool"
    assert labels["Table: Filtered"][1] == "output"
    # Input -> Filter -> "Table: Filtered" -> Summarize
    path = ["Input", "Filter", "Table: Filtered", "Summarize"]
    for u, v in zip(path, path[1:]):
        assert run.graph.has_edge(labels[u][0], labels[v][0])
    assert len(run.results()) == 3


def test_calls_with_unmapped_input(flim_data):
    def build():
        data = workflow_input(flim_data)
        for feature, tag in (("NAD(P)H t1", "t1"), ("NAD(P)H t2", "t2")):
            Sort()(unmapped(data), config=_sort(feature), task_tags=tag)

    run = run_flow("test map", build)
    sorted_tables = [r["Table: Sorted"] for r in run.results() if isinstance(r, dict)]
    assert len(sorted_tables) == 2
    assert sorted_tables[0]["NAD(P)H t1"].is_monotonic_increasing
    assert sorted_tables[1]["NAD(P)H t2"].is_monotonic_increasing


def test_failed_task_skips_downstream(flim_data):
    def build():
        failed = Boom()(flim_data)
        Sort()(failed, config=_sort("NAD(P)H t1"))
        Sort()(flim_data, config=_sort("NAD(P)H t1"))

    run = run_flow("test failure", build)
    status = {a["label"]: a["status"] for _, a in run.graph.nodes(data=True)}
    assert status == {"Boom": "failed", "Sort": "skipped", "Sort-1": "completed"}
    assert run.failed == ["Boom"]


def test_select_from_outputs(flim_data):
    picked = {}

    def build():
        outs = [
            Sort()(flim_data, config=_sort(f)) for f in ("NAD(P)H t1", "NAD(P)H t2")
        ]
        picked["tables"] = select(outs, "Sorted")

    run_flow("test select", build)
    assert len(picked["tables"]) == 2
    assert all(isinstance(t.value(), pd.DataFrame) for t in picked["tables"])


def test_autosave(flim_data, tmp_path):
    def build():
        Summarize()(
            flim_data,
            config=SummaryConfig(
                grouping=["Treatment"], features=["NAD(P)H t1"], aggs=["mean"]
            ),
            task_tags="Stats",
        )

    run_flow("test autosave", build, autosave_dir=str(tmp_path))
    (rundir,) = os.listdir(tmp_path)  # timestamped folder
    saved = os.listdir(tmp_path / rundir / "Stats")
    assert "pickled" in saved
    assert any(f.endswith(".txt") for f in saved)


def test_workflow_graph_plot(flim_data):
    def build():
        Sort()(workflow_input(flim_data), config=_sort("NAD(P)H t1"))

    fig, ax = WorkflowGraph(run_flow("test graph", build)).get_plot()
    assert isinstance(fig, matplotlib.figure.Figure)
    # arrows are drawn as empty annotations
    assert {t.get_text() for t in ax.texts if t.get_text()} == {"Input", "Sort"}


def test_dask_task_runner(flim_data):
    DaskTaskRunner = pytest.importorskip("prefect_dask").DaskTaskRunner

    def build():
        for feature in ("NAD(P)H t1", "NAD(P)H t2"):
            Sort()(unmapped(flim_data), config=_sort(feature))

    runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": False})
    run = run_flow("test dask", build, task_runner=runner)
    assert run.failed == []
    assert len(run.results()) == 2
