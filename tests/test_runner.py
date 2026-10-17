import os

import matplotlib.figure
import pandas as pd
import pytest
from prefect import unmapped
from prefect.testing.utilities import prefect_test_harness

from flim.core.graph import WorkflowGraph
from flim.core.runner import TaskOutput, run_flow, select
from flim.analysis.summarystats import SummaryStats
from flim.data.filterdata import Filter
from flim.data.sortdata import Sort
from flim.plugin import AbstractPlugin, DataBucket


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    # temporary Prefect server and database, nothing is reported to a real server
    with prefect_test_harness():
        yield


class Boom(AbstractPlugin):
    def __init__(self, name="Boom", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def execute(self):
        raise RuntimeError("boom")


def test_call_outside_flow_runs_directly(flim_data):
    results = Sort()(input={"data": flim_data}, features=["NAD(P)H t1"])
    assert results["Table: Sorted"]["NAD(P)H t1"].is_monotonic_increasing


def test_chained_calls_and_item_access(flim_data):
    outputs = {}

    def build():
        data = DataBucket(name="Input")(input={"data": flim_data}, input_select=[0])
        assert isinstance(data, TaskOutput)
        filtered = Filter()(input=data, category_filters={"Treatment": ["WT"]})
        outputs["summary"] = SummaryStats()(
            input=filtered["Table: Filtered"],
            grouping=["Treatment"],
            features=["NAD(P)H t1"],
            aggs=["count"],
        )

    run = run_flow("test chain", build)
    assert run.failed == []
    (summary,) = outputs["summary"].value().values()
    assert summary["NAD(P)H t1\ncount"].tolist() == [30]

    labels = {a["label"]: (n, a["kind"]) for n, a in run.graph.nodes(data=True)}
    assert labels["Input"][1] == "output"
    assert labels["Filter"][1] == "plugin"
    assert labels["Table: Filtered"][1] == "output"
    # Input -> Filter -> "Table: Filtered" -> Summarize
    path = ["Input", "Filter", "Table: Filtered", "Summarize"]
    for u, v in zip(path, path[1:]):
        assert run.graph.has_edge(labels[u][0], labels[v][0])
    assert len(run.results()) == 3


def test_map_with_unmapped(flim_data):
    def build():
        data = DataBucket(name="Input")(input={"data": flim_data}, input_select=[0])
        Sort().map(
            input=unmapped(data),
            features=[["NAD(P)H t1"], ["NAD(P)H t2"]],
            task_tags=["t1", "t2"],
        )

    run = run_flow("test map", build)
    sorted_tables = [r["Table: Sorted"] for r in run.results() if isinstance(r, dict)]
    assert len(sorted_tables) == 2
    assert sorted_tables[0]["NAD(P)H t1"].is_monotonic_increasing
    assert sorted_tables[1]["NAD(P)H t2"].is_monotonic_increasing


def test_map_rejects_unequal_lengths(flim_data):
    def build():
        Sort().map(input=[{"a": flim_data}], features=[["x"], ["y"]])

    with pytest.raises(ValueError, match="differ in length"):
        run_flow("test map lengths", build)


def test_failed_task_skips_downstream(flim_data):
    def build():
        failed = Boom()(input={"data": flim_data})
        Sort()(input=failed, features=["NAD(P)H t1"])
        Sort()(input={"data": flim_data}, features=["NAD(P)H t1"])

    run = run_flow("test failure", build)
    status = {a["label"]: a["status"] for _, a in run.graph.nodes(data=True)}
    assert status == {"Boom": "failed", "Sort": "skipped", "Sort-1": "completed"}
    assert run.failed == ["Boom"]


def test_select_from_outputs(flim_data):
    picked = {}

    def build():
        outs = Sort().map(
            input=[{"a": flim_data}, {"b": flim_data}],
            features=[["NAD(P)H t1"], ["NAD(P)H t2"]],
        )
        picked["tables"] = select(outs, "Sorted")

    run_flow("test select", build)
    assert len(picked["tables"]) == 2
    assert all(isinstance(t.value(), pd.DataFrame) for t in picked["tables"])


def test_autosave(flim_data, tmp_path):
    def build():
        SummaryStats()(
            input={"data": flim_data},
            grouping=["Treatment"],
            features=["NAD(P)H t1"],
            aggs=["mean"],
            task_tags="Stats",
        )

    run_flow("test autosave", build, autosave_dir=str(tmp_path))
    (rundir,) = os.listdir(tmp_path)  # timestamped folder
    saved = os.listdir(tmp_path / rundir / "Stats")
    assert "pickled" in saved
    assert any(f.endswith(".txt") for f in saved)


def test_workflow_graph_plot(flim_data):
    def build():
        data = DataBucket(name="Input")(input={"data": flim_data}, input_select=[0])
        Sort()(input=data, features=["NAD(P)H t1"])

    fig, ax = WorkflowGraph(run_flow("test graph", build)).get_plot()
    assert isinstance(fig, matplotlib.figure.Figure)
    # arrows are drawn as empty annotations
    assert {t.get_text() for t in ax.texts if t.get_text()} == {"Input", "Sort"}


def test_dask_task_runner(flim_data):
    from prefect_dask import DaskTaskRunner

    def build():
        Sort().map(
            input=unmapped({"data": flim_data}),
            features=[["NAD(P)H t1"], ["NAD(P)H t2"]],
        )

    runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": False})
    run = run_flow("test dask", build, task_runner=runner)
    assert run.failed == []
    assert len(run.results()) == 2
