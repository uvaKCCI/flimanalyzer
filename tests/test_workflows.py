import matplotlib.figure
import pandas as pd
import pytest
from prefect.testing.utilities import prefect_test_harness

from flim.core.graph import WorkflowGraph
from flim.configs.workflow import BasicFLIRRConfig
from flim.workflow.basicflow import BasicFLIRR


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def flirr_data(flim_data):
    df = flim_data.copy()
    df["FLIRR"] = df["NAD(P)H a2[%]"] / df["FAD a1[%]"]
    return df


FEATURES = ["FLIRR", "NAD(P)H t1", "FAD a1[%]", "NAD(P)H a2[%]"]
CONFIG = BasicFLIRRConfig(grouping=["Treatment", "FOV", "Cell"], features=FEATURES)


def test_basic_flirr_workflow(flirr_data, tmp_path):
    wf = BasicFLIRR()
    run = wf.run_flow(flirr_data, config=CONFIG, autosave_dir=str(tmp_path / wf.name))

    assert run.failed == []
    statuses = {a["status"] for _, a in run.graph.nodes(data=True) if "plugin" in a}
    assert statuses == {"completed"}
    tables = [
        v for r in run.results() if isinstance(r, dict) for v in r.values()
        if isinstance(v, pd.DataFrame)
    ]
    figures = [
        v for r in run.results() if isinstance(r, dict) for v in r.values()
        if isinstance(v, matplotlib.figure.Figure)
    ]
    assert any("Stats-" in k for r in run.results() if isinstance(r, dict) for k in r)
    assert len(tables) > 0 and len(figures) > 0
    # one line plot and KDE per feature, after the input
    labels = [a["label"] for _, a in run.graph.nodes(data=True)]
    assert labels[0] == "Input"
    assert sum(l.startswith("KDE") for l in labels) == len(FEATURES)
    assert sum(l.startswith("Line Plot") for l in labels) == len(FEATURES)

    fig, _ = WorkflowGraph(run).get_plot()
    assert isinstance(fig, matplotlib.figure.Figure)
    assert any((tmp_path / wf.name).rglob("*.txt"))
    (summary,) = (tmp_path / wf.name).rglob("run_summary.txt")
    assert "State:      completed" in summary.read_text()


def test_workflow_run_returns_all_results(flirr_data):
    results = BasicFLIRR().run(flirr_data, config=CONFIG)
    assert "Stats-Table: Summary" in results
    assert any(k.startswith("Plot: KDE") for k in results)
