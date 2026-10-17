import matplotlib.figure
import pandas as pd
import pytest
from prefect.testing.utilities import prefect_test_harness

from flim.core.graph import WorkflowGraph
from flim.workflow.basicflow import BasicFLIRRWorkFlow


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def flirr_data(flim_data):
    df = flim_data.copy()
    df["FLIRR"] = df["NAD(P)H a2[%]"] / df["FAD a1[%]"]
    return df


def test_basic_flirr_workflow(flirr_data, tmp_path):
    features = ["FLIRR", "NAD(P)H t1", "FAD a1[%]", "NAD(P)H a2[%]"]
    wf = BasicFLIRRWorkFlow()
    wf.configure(
        input={"data": flirr_data},
        grouping=["Treatment", "FOV", "Cell"],
        features=features,
        working_dir=str(tmp_path),
    )
    run = wf.run_flow(autosave_dir=str(tmp_path / wf.name))

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
    # one mapped line plot and KDE per feature; the workflow creates its plugins with
    # name=None, so their labels are the class names
    labels = [a["label"] for _, a in run.graph.nodes(data=True)]
    assert sum(l.startswith("KDE") for l in labels) == len(features)
    assert sum(l.startswith("LinePlot") for l in labels) == len(features)

    fig, _ = WorkflowGraph(run).get_plot()
    assert isinstance(fig, matplotlib.figure.Figure)
    assert any((tmp_path / wf.name).rglob("*.txt"))
