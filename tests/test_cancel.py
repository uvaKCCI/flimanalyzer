import threading
import time
from typing import Optional

import numpy as np
import pandas as pd
import pytest
from prefect import get_client

import flim.core.runner as runner
from flim.core.config import TaskConfig
from flim.core.runner import CancelToken, TaskCancelled, default_task_runner, run_flow
from flim.core.tool import Tool


pytestmark = pytest.mark.usefixtures("prefect_harness")


class LoopConfig(TaskConfig):
    seconds: float = 10.0
    marker: Optional[str] = None  # file created when the task starts


class Counter(Tool[LoopConfig]):
    """Counts its runs in a list shared by all copies."""

    name = "Counter"
    category = "Data"

    def __init__(self, name=None, calls=None):
        super().__init__()
        if name:
            self.name = name
        self.calls = calls if calls is not None else []

    def run(self, *inputs, config):
        self.calls.append(self.name)
        return {f"{self.name} done": True}


class Looper(Counter):
    """Long task that checks for cancellation every 20 ms (for up to 10 s)."""

    def run(self, *inputs, config):
        self.calls.append(self.name)
        if config.marker:
            open(config.marker, "w").close()  # also in other processes
        for _ in range(int(config.seconds / 0.02)):
            self.check_cancelled()
            time.sleep(0.02)
        return {"looped": True}


class Quitter(Counter):
    """Cancels itself."""

    def run(self, *inputs, config):
        self.calls.append(self.name)
        self.cancel("nothing to do")


class Boom(Counter):
    def run(self, *inputs, config):
        self.calls.append(self.name)
        raise RuntimeError("boom")


def _status(run):
    return {a["label"]: a["status"] for _, a in run.graph.nodes(data=True) if "tool" in a}


def _prefect_flow_state(run):
    with get_client(sync_client=True) as client:
        return client.read_flow_run(run.flow_run_id).state


def test_cancel_outside_a_flow_raises():
    with pytest.raises(TaskCancelled, match="nothing to do"):
        Quitter()()


def test_cancel_before_the_run_starts_nothing():
    calls = []
    token = CancelToken()
    token.set()

    def build():
        Counter(name="A", calls=calls)()
        Counter(name="B", calls=calls)()

    run = run_flow("cancelled early", build, cancel_token=token)
    assert calls == []
    assert run.state == "cancelled"
    assert _status(run) == {"A": "cancelled"}  # the script stops at the first call
    assert _prefect_flow_state(run).is_cancelled()


def test_cancel_between_tasks():
    calls = []
    token = CancelToken()

    def build():
        first = Counter(name="A", calls=calls)()
        first.value()  # wait for A
        token.set()
        Counter(name="B", calls=calls)()
        Counter(name="C", calls=calls)()

    run = run_flow("cancelled between", build, cancel_token=token)
    assert calls == ["A"]
    assert _status(run) == {"A": "completed", "B": "cancelled"}
    assert run.state == "cancelled"
    assert run.results() == [{"A done": True}]  # completed results are kept


@pytest.mark.parametrize("workers", [1, 3])
def test_cancel_stops_a_running_task(workers):
    calls = []
    token = CancelToken()

    def build():
        Looper(name="Long", calls=calls)()

    threading.Timer(0.3, token.set).start()
    start = time.monotonic()
    run = run_flow("cancel running", build, default_task_runner(workers), cancel_token=token)
    assert time.monotonic() - start < 5  # instead of 10 s
    assert _status(run) == {"Long": "cancelled"}
    assert run.cancelled == ["Long"] and run.failed == []
    assert run.state == "cancelled"


@pytest.mark.parametrize("dask", [False, True], ids=["threads", "dask"])
def test_task_cancelling_itself_skips_only_its_dependents(dask):
    calls = []

    def build():
        quit_ = Quitter(name="Quitter", calls=calls)()
        Counter(name="Dependent", calls=calls)(quit_)
        Counter(name="Independent", calls=calls)()

    task_runner = None
    if dask:
        DaskTaskRunner = pytest.importorskip("prefect_dask").DaskTaskRunner

        task_runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": False})
    run = run_flow("self cancel", build, task_runner=task_runner)
    assert _status(run) == {
        "Quitter": "cancelled",
        "Dependent": "skipped",
        "Independent": "completed",
    }
    assert "Dependent" not in calls
    assert run.failed == []
    assert run.state == "completed"  # the run itself was not cancelled
    assert _prefect_flow_state(run).is_completed()


def test_cancelled_task_is_never_retried(monkeypatch):
    monkeypatch.setattr(
        runner, "run_tool", runner.run_tool.with_options(retries=2, retry_delay_seconds=0)
    )
    calls = []

    def build():
        Quitter(name="Quitter", calls=calls)()
        Boom(name="Boom", calls=calls)()

    run = run_flow("retries", build)
    assert calls.count("Quitter") == 1
    assert calls.count("Boom") == 3  # other errors are retried as configured
    assert _status(run) == {"Quitter": "cancelled", "Boom": "failed"}


def test_run_summary_and_prefect_link(tmp_path):
    calls = []
    token = CancelToken()

    def build():
        Counter(name="A", calls=calls)(task_tags="first").value()
        Boom(name="Boom", calls=calls)().value()
        token.set()
        Counter(name="B", calls=calls)()

    run = run_flow("summary", build, autosave_dir=str(tmp_path), cancel_token=token)
    assert run.state == "cancelled"
    assert run.ui_url and run.ui_url.endswith(str(run.flow_run_id))
    (summary,) = tmp_path.rglob("run_summary.txt")
    assert summary.parent == tmp_path / run.start_time.strftime("%Y-%m-%d_%H-%M-%S")
    text = summary.read_text()
    assert "State:      cancelled" in text
    assert run.ui_url in text
    assert "1 cancelled" in text and "1 completed" in text and "1 failed" in text
    assert "boom" in text  # failure message of Boom


def test_progress_callback():
    progress = []

    def build():
        Counter(name="A")()
        Counter(name="B")()

    run_flow(
        "progress",
        build,
        on_progress=lambda done, total, label, complete: progress.append((done, total, complete)),
    )
    assert progress[-1] == (2, 2, True)
    assert all(done <= total for done, total, _ in progress)
    # all tasks are known once the script has made its calls
    first_complete = next(i for i, p in enumerate(progress) if p[2])
    assert all(p[2] for p in progress[first_complete:])
    assert {p[1] for p in progress[first_complete:]} == {2}


def test_autoencoder_training_stops_within_an_epoch(tmp_path):
    pytest.importorskip("torch")
    from flim.configs import AETrainConfig
    from flim.tools.autoencoder import AETraining

    rng = np.random.default_rng(0)
    n = 400
    data = pd.DataFrame(
        {
            "FOV": pd.Categorical(rng.integers(1, 4, n).astype(str)),
            "Cell": pd.Categorical(np.arange(n).astype(str)),
            "Treatment": pd.Categorical(rng.choice(["ctrl", "drug"], n)),
            **{f"f{i}": rng.random(n).astype(np.float32) for i in range(4)},
        }
    )
    token = CancelToken()

    config = AETrainConfig(
        features=[f"f{i}" for i in range(4)],
        grouping=["FOV", "Cell"],
        timeseries="Treatment",
        model_name="AEModel",
        epochs=100000,
        checkpoint_interval=100000,
        batch_sizes=[32],
        create_plots=False,
        resources={"preferred_device": "cpu"},
    )

    def build():
        AETraining()(data, config=config)

    threading.Timer(1.0, token.set).start()
    start = time.monotonic()
    # models are saved in the results folder
    run = run_flow("ae cancel", build, autosave_dir=str(tmp_path), cancel_token=token)
    assert time.monotonic() - start < 30
    assert run.cancelled == ["Autoencoder: Train"]
    assert not list(tmp_path.rglob("*.model"))


def test_cancel_reaches_dask_worker_processes(tmp_path):
    DaskTaskRunner = pytest.importorskip("prefect_dask").DaskTaskRunner

    marker = tmp_path / "started"
    token = CancelToken()
    started = {}

    def cancel_once_started():
        while not marker.exists():
            time.sleep(0.05)
        started["at"] = time.monotonic()
        token.set()

    def build():
        Looper(name="Long")(config=LoopConfig(marker=str(marker)))

    threading.Thread(target=cancel_once_started, daemon=True).start()
    task_runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": True})
    run = run_flow("cancel dask processes", build, task_runner, cancel_token=token)
    assert time.monotonic() - started["at"] < 5  # the task alone would take 10 s
    assert _status(run) == {"Long": "cancelled"}
    assert run.state == "cancelled"


def test_tasks_report_running_and_start_callback():
    started, statuses = [], []
    holder = {}

    def on_start(run):
        started.append(run.flow_run_id)
        holder["run"] = run

    token = CancelToken()

    def on_progress(done, total, label, complete):
        statuses.append(dict(holder["run"].tasks()))
        if "running" in statuses[-1].values():
            token.set()  # cancel once it runs (busy machines start it late)

    def build():
        Looper(name="Long")().value()  # loops ~10 s unless cancelled

    threading.Timer(10, token.set).start()  # in case it is never reported running
    run = run_flow("running", build, on_progress=on_progress, cancel_token=token, on_start=on_start)
    assert started == [run.flow_run_id] and run.flow_run_id is not None
    assert {"Long": "running"} in statuses
    assert run.tasks() == [("Long", "cancelled")]


class SlowPlot(Counter):
    """Stands in for a plot tool: holds the plot lock for one second; sets ``started``
    when it gets the lock."""

    draws_figures = True

    def __init__(self, name=None, calls=None, started=None):
        super().__init__(name, calls)
        self.started = started

    def run(self, *inputs, config):
        self.calls.append(self.name)
        self.started.set()
        time.sleep(1.0)
        return {f"{self.name} done": True}


def test_cancel_stops_plot_tasks_waiting_for_the_plot_lock():
    calls = []
    token = CancelToken()
    started = threading.Event()

    def build():
        for i in range(4):
            SlowPlot(name=f"Plot{i}", calls=calls, started=started)()
        started.wait(10)  # all four submitted, one holds the plot lock
        token.set()

    run = run_flow("plots", build, default_task_runner(4), cancel_token=token)
    # the first plot finishes, the three waiting for the lock don't run
    assert len(calls) == 1
    counts = run.task_counts()
    assert counts == {"completed": 1, "cancelled": 3}
