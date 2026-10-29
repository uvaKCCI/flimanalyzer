import threading
import time

import matplotlib.figure
import pandas as pd
import pytest
from prefect.testing.utilities import prefect_test_harness

from flim.core.runner import default_max_workers, default_task_runner, run_flow
from flim.plugin import AbstractPlugin, DataBucket

SLEEP = 0.4


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    # temporary Prefect server and database, nothing is reported to a real server
    with prefect_test_harness():
        yield


class Sleeper(AbstractPlugin):
    """Records when it runs; the record is shared by all copies of the plugin."""

    def __init__(self, name="Sleeper", record=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.record = record if record is not None else []

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def execute(self):
        start = time.monotonic()
        time.sleep(SLEEP)
        self.record.append((start, time.monotonic()))
        return {"done": True}


class Drawer(Sleeper):
    """Counts how many figure-drawing tasks run at the same time."""

    draws_figures = True
    active = 0
    max_active = 0
    lock = threading.Lock()

    def execute(self):
        with Drawer.lock:
            Drawer.active += 1
            Drawer.max_active = max(Drawer.max_active, Drawer.active)
        try:
            return super().execute()
        finally:
            with Drawer.lock:
                Drawer.active -= 1


def _overlapping(record):
    spans = sorted(record)
    return any(b[0] < a[1] for a, b in zip(spans, spans[1:]))


def _run_sleepers(n, task_runner=None, task_tags=None, plugin_class=Sleeper):
    record = []

    def build():
        for _ in range(n):
            plugin_class(record=record)(input={}, task_tags=task_tags)

    run = run_flow("sleepers", build, task_runner=task_runner)
    assert run.failed == []
    assert len(record) == n
    return record


def test_default_max_workers_is_bounded():
    assert 1 <= default_max_workers() <= 1024


def test_independent_tasks_run_concurrently():
    record = _run_sleepers(3, default_task_runner(3))
    assert _overlapping(record)


def test_one_worker_runs_one_task_at_a_time():
    record = _run_sleepers(3, default_task_runner(1))
    assert not _overlapping(record)


def test_tasks_that_draw_figures_take_turns():
    Drawer.max_active = 0
    record = _run_sleepers(3, default_task_runner(3), plugin_class=Drawer)
    assert Drawer.max_active == 1
    assert not _overlapping(record)


def test_tag_concurrency_limit_is_applied():
    from prefect import get_client

    with get_client(sync_client=True) as client:
        client.create_concurrency_limit(tag="one-at-a-time", concurrency_limit=1)
    try:
        record = _run_sleepers(3, default_task_runner(3), task_tags="one-at-a-time")
        assert not _overlapping(record)
    finally:
        with get_client(sync_client=True) as client:
            client.delete_concurrency_limit_by_tag("one-at-a-time")


def test_downstream_task_waits_for_its_input(flim_data):
    record = []

    def build():
        data = DataBucket(name="Input")(input={"data": flim_data}, input_select=[0])
        first = Sleeper(name="First", record=record)(input=data)
        Sleeper(name="Second", record=record)(input=first)

    run = run_flow("chain", build, task_runner=default_task_runner(4))
    assert run.failed == []
    (first, second) = record
    assert second[0] >= first[1]


@pytest.fixture
def flirr_data(flim_data):
    df = flim_data.copy()
    df["FLIRR"] = df["NAD(P)H a2[%]"] / df["FAD a1[%]"]
    return df


def _basic_flirr(flirr_data, tmp_path, workers):
    from flim.configs.workflow import BasicFLIRRConfig
    from flim.workflow.basicflow import BasicFLIRR

    config = BasicFLIRRConfig(
        grouping=["Treatment", "FOV", "Cell"],
        features=["FLIRR", "NAD(P)H t1", "FAD a1[%]", "NAD(P)H a2[%]"],
    )
    run = BasicFLIRR().run_flow(
        flirr_data, config=config, task_runner=default_task_runner(workers)
    )
    assert run.failed == []
    tables, figures = {}, {}
    for label, result in zip(
        [a["label"] for _, a in run.graph.nodes(data=True) if a.get("status") == "completed"],
        run.results(),
    ):
        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, pd.DataFrame):
                    tables[(label, key)] = value
                elif isinstance(value, matplotlib.figure.Figure):
                    figures[(label, key)] = value
    return tables, figures


def test_workflow_results_do_not_depend_on_worker_count(flirr_data, tmp_path):
    tables_1, figures_1 = _basic_flirr(flirr_data, tmp_path / "w1", 1)
    tables_n, figures_n = _basic_flirr(flirr_data, tmp_path / "wn", 6)
    assert tables_1.keys() == tables_n.keys() and tables_1
    for key in tables_1:
        pd.testing.assert_frame_equal(tables_1[key], tables_n[key])
    assert figures_1.keys() == figures_n.keys() and figures_1
    for key in figures_1:
        axes_1, axes_n = figures_1[key].get_axes(), figures_n[key].get_axes()
        assert len(axes_1) == len(axes_n)
        assert [a.get_title() for a in axes_1] == [a.get_title() for a in axes_n]


def test_result_figures_are_released_from_pyplot(flim_data):
    import matplotlib.pyplot as plt

    from flim.analysis.kde import KDE

    plt.close("all")

    def build():
        KDE()(input={"data": flim_data}, grouping=["Treatment"], features=["NAD(P)H t1"])

    run = run_flow("figures", build)
    (result,) = run.results()
    figures = [v for v in result.values() if isinstance(v, matplotlib.figure.Figure)]
    assert figures and plt.get_fignums() == []
    figures[0].savefig(__import__("io").BytesIO())  # still usable


def test_dask_executors_need_the_dask_extra(monkeypatch):
    import importlib.util
    import sys

    import flim.analyzerapp as analyzerapp
    from flim.core.tools import FLIMAnalyzer, check_executor_available

    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a: None if name == "prefect_dask" else real_find_spec(name, *a),
    )
    check_executor_available("LocalExecutor")  # needs nothing extra
    for executor in ("LocalDaskExecutor", "DaskExecutor"):
        with pytest.raises(RuntimeError, match="uv sync --extra dask"):
            check_executor_available(executor)
        with pytest.raises(RuntimeError, match="optional Dask support"):
            FLIMAnalyzer(executor=executor).get_task_runner()

    # the command line stops with the message instead of an import error
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "-e", "LocalDaskExecutor"])
    with pytest.raises(SystemExit, match="LocalDaskExecutor needs the optional Dask support"):
        analyzerapp.main()
