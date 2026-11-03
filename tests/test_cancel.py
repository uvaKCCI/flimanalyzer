import threading
import time

import numpy as np
import pandas as pd
import pytest
from prefect import get_client, unmapped

import flim.core.runner as runner
from flim.core.runner import CancelToken, TaskCancelled, default_task_runner, run_flow
from tests.fake_tools import WAIT, Counter, FakeConfig, Waiter


pytestmark = pytest.mark.usefixtures("prefect_harness")


class Quitter(Counter):
    """Cancels itself."""

    def run(self, *inputs, config):
        self.calls.append(self.name)
        self.cancel("nothing to do")


class Boom(Counter):
    def run(self, *inputs, config):
        self.calls.append(self.name)
        raise RuntimeError("boom")


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
    assert dict(run.tasks()) == {"A": "cancelled"}  # the script stops at the first call
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
    assert dict(run.tasks()) == {"A": "completed", "B": "cancelled"}
    assert run.state == "cancelled"
    assert run.results() == [{"A done": True}]  # completed results are kept


@pytest.mark.parametrize("workers", [1, 3])
def test_cancel_stops_a_running_task(workers):
    token = CancelToken()
    started = threading.Event()

    def build():
        Waiter(name="Long", started=started)()  # runs until cancelled
        started.wait(WAIT)
        token.set()

    start = time.monotonic()
    run = run_flow("cancel running", build, default_task_runner(workers), cancel_token=token)
    assert time.monotonic() - start < 5  # cancelled long before the Waiter gives up
    assert dict(run.tasks()) == {"Long": "cancelled"}
    assert run.cancelled == ["Long"] and run.failed == []
    assert run.state == "cancelled"


@pytest.mark.parametrize("dask", [False, True], ids=["threads", "dask"])
def test_task_cancelling_itself_skips_only_its_dependents(dask):
    calls = []

    def build():
        quit_ = Quitter(name="Quitter", calls=calls)()
        Counter(name="Dependent", calls=calls)(quit_)
        # an unmapped input is passed on as it is (also to Dask)
        Counter(name="Independent", calls=calls)(unmapped(pd.DataFrame({"x": [1.0]})))

    task_runner = None
    if dask:
        DaskTaskRunner = pytest.importorskip("prefect_dask").DaskTaskRunner

        task_runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": False})
    run = run_flow("self cancel", build, task_runner=task_runner)
    assert dict(run.tasks()) == {
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
    assert dict(run.tasks()) == {"Quitter": "cancelled", "Boom": "failed"}


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
        end = time.monotonic() + 3 * WAIT  # the Dask cluster starts first
        while not marker.exists() and time.monotonic() < end:
            time.sleep(0.05)
        started["at"] = time.monotonic()
        token.set()

    def build():
        # runs until cancelled (its events cannot be sent to a worker process)
        Waiter(name="Long")(config=FakeConfig(marker=str(marker)))

    threading.Thread(target=cancel_once_started, daemon=True).start()
    task_runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": True})
    run = run_flow("cancel dask processes", build, task_runner, cancel_token=token)
    assert time.monotonic() - started["at"] < 5  # the task gives up after WAIT s
    assert dict(run.tasks()) == {"Long": "cancelled"}
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
        Waiter(name="Long")().value()  # runs until cancelled (fails after WAIT s)

    run = run_flow("running", build, on_progress=on_progress, cancel_token=token, on_start=on_start)
    assert started == [run.flow_run_id] and run.flow_run_id is not None
    assert {"Long": "running"} in statuses
    assert run.tasks() == [("Long", "cancelled")]


class SlowPlot(Waiter):
    """Stands in for a plot tool: holds the plot lock until released."""

    draws_figures = True


def test_cancel_stops_plot_tasks_waiting_for_the_plot_lock():
    calls = []
    token = CancelToken()
    started, release = threading.Event(), threading.Event()

    def build():
        for i in range(4):
            SlowPlot(
                name=f"Plot{i}",
                calls=calls,
                started=started,
                release=release,
                cancellable=False,
            )()
        started.wait(WAIT)  # all four submitted, one holds the plot lock
        token.set()
        release.set()

    run = run_flow("plots", build, default_task_runner(4), cancel_token=token)
    # the first plot finishes, the three waiting for the lock don't run
    assert len(calls) == 1
    counts = run.task_counts()
    assert counts == {"completed": 1, "cancelled": 3}
