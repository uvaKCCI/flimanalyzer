import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError
from prefect.task_runners import ThreadPoolTaskRunner

from flim.core.execution import ExecutionOptions

HAS_DASK = importlib.util.find_spec("prefect_dask") is not None


def test_defaults():
    opts = ExecutionOptions()
    assert opts.executor == "local" and opts.num_workers is None
    assert opts.device_policy == "prefer" and not opts.autosave


@pytest.mark.parametrize(
    "kwargs",
    [
        {"executor": "ray"},
        {"num_workers": 0},
        {"address": "tcp://h:8786"},  # local executor
        {"executor": "dask-local", "address": "tcp://h:8786"},
        {"dask_kwargs": {"x": 1}},  # local executor
        {"autosave": True},  # no results_dir
        {"device_policy": "gpu-only"},
        {"bogus": 1},
    ],
)
def test_invalid(kwargs):
    with pytest.raises(ValidationError):
        ExecutionOptions(**kwargs)


def test_autosave_with_dir(tmp_path):
    opts = ExecutionOptions(autosave=True, results_dir=tmp_path)
    assert opts.results_dir == tmp_path


@pytest.mark.parametrize(
    "executor, execargs, expected",
    [
        ("LocalExecutor", "", {"executor": "local", "num_workers": None}),
        ("LocalExecutor", "num_workers=3", {"executor": "local", "num_workers": 3}),
        # the local executor ignores everything but an integer num_workers
        (
            "LocalExecutor",
            "num_workers=x,foo=1",
            {"executor": "local", "num_workers": None},
        ),
        ("Unknown", "num_workers=2", {"executor": "local", "num_workers": 2}),
        (
            "LocalDaskExecutor",
            "num_workers=4,scheduler=processes,threads_per_worker=2",
            {
                "executor": "dask-local",
                "num_workers": 4,
                "scheduler": "processes",
                "dask_kwargs": {"threads_per_worker": 2},
            },
        ),
        (
            "LocalDaskExecutor",
            "scheduler=bogus",
            {"scheduler": "threads", "dask_kwargs": {}},
        ),
        (
            "DaskExecutor",
            "address=tcp://10.0.0.1:8786",
            {"executor": "dask", "address": "tcp://10.0.0.1:8786", "dask_kwargs": {}},
        ),
        ("LocalExecutor", "malformed,=,a=b=c", {"executor": "local"}),
    ],
)
def test_from_legacy(executor, execargs, expected):
    opts = ExecutionOptions.from_legacy(executor, execargs)
    for key, value in expected.items():
        assert getattr(opts, key) == value


def test_from_legacy_passes_kwargs(tmp_path):
    opts = ExecutionOptions.from_legacy(
        "LocalExecutor", "", autosave=True, results_dir=tmp_path
    )
    assert opts.autosave and opts.results_dir == Path(tmp_path)


def test_local_task_runner():
    runner = ExecutionOptions(num_workers=2).task_runner()
    assert isinstance(runner, ThreadPoolTaskRunner)
    assert runner._max_workers == 2
    assert ExecutionOptions().task_runner()._max_workers >= 1


@pytest.mark.skipif(HAS_DASK, reason="prefect-dask is installed")
def test_dask_needs_extra():
    with pytest.raises(RuntimeError, match="extra dask"):
        ExecutionOptions(executor="dask-local").task_runner()


@pytest.mark.skipif(not HAS_DASK, reason="needs the dask extra")
def test_dask_task_runners():
    local = ExecutionOptions(
        executor="dask-local",
        num_workers=2,
        scheduler="processes",
        dask_kwargs={"threads_per_worker": 1},
    ).task_runner()
    assert local.cluster_kwargs == {
        "processes": True,
        "n_workers": 2,
        "threads_per_worker": 1,
    }
    remote = ExecutionOptions(executor="dask", address="tcp://h:8786").task_runner()
    assert remote.address == "tcp://h:8786"
