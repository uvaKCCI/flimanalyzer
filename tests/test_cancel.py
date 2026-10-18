import threading
import time

import numpy as np
import pandas as pd
import pytest
from prefect import get_client
from prefect.testing.utilities import prefect_test_harness

import flim.core.runner as runner
from flim.core.runner import CancelToken, TaskCancelled, default_task_runner, run_flow
from flim.plugin import AbstractPlugin


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    # temporary Prefect server and database, nothing is reported to a real server
    with prefect_test_harness():
        yield


class Base(AbstractPlugin):
    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []


class Counter(Base):
    """Counts its executions in a list shared by all copies."""

    def __init__(self, name="Counter", calls=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.calls = calls if calls is not None else []

    def execute(self):
        self.calls.append(self.name)
        return {f"{self.name} done": True}


class Looper(Counter):
    """Long task that checks for cancellation every 20 ms (for up to 10 s)."""

    def execute(self):
        self.calls.append(self.name)
        for _ in range(500):
            self.check_cancelled()
            time.sleep(0.02)
        return {"looped": True}


class Quitter(Counter):
    """Cancels itself."""

    def execute(self):
        self.calls.append(self.name)
        self.cancel("nothing to do")


class Boom(Counter):
    def execute(self):
        self.calls.append(self.name)
        raise RuntimeError("boom")


def _status(run):
    return {a["label"]: a["status"] for _, a in run.graph.nodes(data=True) if "plugin" in a}


def _prefect_flow_state(run):
    with get_client(sync_client=True) as client:
        return client.read_flow_run(run.flow_run_id).state


def test_cancel_outside_a_flow_raises():
    with pytest.raises(TaskCancelled, match="nothing to do"):
        Quitter().run(input={})


def test_cancel_before_the_run_starts_nothing():
    calls = []
    token = CancelToken()
    token.set()

    def build():
        Counter(name="A", calls=calls)(input={})
        Counter(name="B", calls=calls)(input={})

    run = run_flow("cancelled early", build, cancel_token=token)
    assert calls == []
    assert run.state == "cancelled"
    assert _status(run) == {"A": "cancelled"}  # the script stops at the first call
    assert _prefect_flow_state(run).is_cancelled()


def test_cancel_between_tasks():
    calls = []
    token = CancelToken()

    def build():
        first = Counter(name="A", calls=calls)(input={})
        first.value()  # wait for A
        token.set()
        Counter(name="B", calls=calls)(input={})
        Counter(name="C", calls=calls)(input={})

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
        Looper(name="Long", calls=calls)(input={})

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
        quit_ = Quitter(name="Quitter", calls=calls)(input={})
        Counter(name="Dependent", calls=calls)(input=quit_)
        Counter(name="Independent", calls=calls)(input={})

    task_runner = None
    if dask:
        from prefect_dask import DaskTaskRunner

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
        runner, "run_plugin", runner.run_plugin.with_options(retries=2, retry_delay_seconds=0)
    )
    calls = []

    def build():
        Quitter(name="Quitter", calls=calls)(input={})
        Boom(name="Boom", calls=calls)(input={})

    run = run_flow("retries", build)
    assert calls.count("Quitter") == 1
    assert calls.count("Boom") == 3  # other errors are retried as configured
    assert _status(run) == {"Quitter": "cancelled", "Boom": "failed"}


def test_run_summary_and_prefect_link(tmp_path):
    calls = []
    token = CancelToken()

    def build():
        Counter(name="A", calls=calls)(input={}, task_tags="first").value()
        Boom(name="Boom", calls=calls)(input={}).value()
        token.set()
        Counter(name="B", calls=calls)(input={})

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
        Counter(name="A")(input={})
        Counter(name="B")(input={})

    run_flow("progress", build, on_progress=lambda done, total, label: progress.append((done, total)))
    assert progress[-1] == (2, 2)
    assert all(done <= total for done, total in progress)


def test_autoencoder_training_stops_within_an_epoch(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("wx")
    from flim.analysis.aetraining import AETraining

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

    def build():
        AETraining()(
            input={"data": data},
            features=[f"f{i}" for i in range(4)],
            grouping=["FOV", "Cell"],
            timeseries="Treatment",
            working_dir=str(tmp_path),
            modelfile="AEModel",
            epoches=100000,
            checkpoint_interval=100000,
            batch_size=[32],
            create_plots=False,
            device="cpu",
        )

    threading.Timer(1.0, token.set).start()
    start = time.monotonic()
    run = run_flow("ae cancel", build, cancel_token=token)
    assert time.monotonic() - start < 30
    assert run.cancelled == ["Autoencoder: Train"]
    assert not list(tmp_path.glob("*.model"))


class MarkedLooper(Looper):
    """Looper that creates a marker file when it starts (also in other processes)."""

    def __init__(self, name="Marked", marker=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.marker = marker

    def execute(self):
        open(self.marker, "w").close()
        return super().execute()


def test_cancel_reaches_dask_worker_processes(tmp_path):
    from prefect_dask import DaskTaskRunner

    marker = tmp_path / "started"
    token = CancelToken()
    started = {}

    def cancel_once_started():
        while not marker.exists():
            time.sleep(0.05)
        started["at"] = time.monotonic()
        token.set()

    def build():
        MarkedLooper(name="Long", marker=str(marker))(input={})

    threading.Thread(target=cancel_once_started, daemon=True).start()
    task_runner = DaskTaskRunner(cluster_kwargs={"n_workers": 1, "processes": True})
    run = run_flow("cancel dask processes", build, task_runner, cancel_token=token)
    assert time.monotonic() - started["at"] < 5  # the task alone would take 10 s
    assert _status(run) == {"Long": "cancelled"}
    assert run.state == "cancelled"
