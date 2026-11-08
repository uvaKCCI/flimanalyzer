import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError
from prefect.task_runners import ThreadPoolTaskRunner

from flim.core.execution import (
    DaskClusterExecutorSettings,
    DaskLocalExecutorSettings,
    ExecutionOptions,
    LocalExecutorSettings,
)

HAS_DASK = importlib.util.find_spec("prefect_dask") is not None


def test_defaults():
    opts = ExecutionOptions()
    assert opts.executor == LocalExecutorSettings(num_workers=None)
    assert opts.device_policy == "prefer" and not opts.autosave


def test_the_executor_name_selects_the_settings():
    opts = ExecutionOptions(executor={"executor": "dask-local", "num_workers": 2})
    assert opts.executor == DaskLocalExecutorSettings(num_workers=2)
    opts = ExecutionOptions(executor={"executor": "dask", "address": "tcp://h:8786"})
    assert opts.executor == DaskClusterExecutorSettings(address="tcp://h:8786")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"executor": {"executor": "ray"}},
        {"executor": {"executor": "local", "num_workers": 0}},
        # settings of another executor
        {"executor": {"executor": "local", "address": "tcp://h:8786"}},
        {"executor": {"executor": "dask-local", "address": "tcp://h:8786"}},
        {"executor": {"executor": "local", "dask_kwargs": {"x": 1}}},
        {"executor": {"executor": "dask"}},  # a cluster needs its address
        {"executor": {"executor": "local", "adress": "x"}},  # misspelled
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
        ("LocalExecutor", "", LocalExecutorSettings()),
        ("LocalExecutor", "num_workers=3", LocalExecutorSettings(num_workers=3)),
        # the local executor ignores everything but an integer num_workers
        ("LocalExecutor", "num_workers=x,foo=1", LocalExecutorSettings()),
        ("Unknown", "num_workers=2", LocalExecutorSettings(num_workers=2)),
        (
            "LocalDaskExecutor",
            "num_workers=4,scheduler=processes,threads_per_worker=2",
            DaskLocalExecutorSettings(
                num_workers=4, scheduler="processes", dask_kwargs={"threads_per_worker": 2}
            ),
        ),
        ("LocalDaskExecutor", "scheduler=bogus", DaskLocalExecutorSettings()),
        (
            "DaskExecutor",
            "address=tcp://10.0.0.1:8786",
            DaskClusterExecutorSettings(address="tcp://10.0.0.1:8786"),
        ),
        # without an address: a local Dask cluster, as before the address was required
        ("DaskExecutor", "num_workers=2", DaskLocalExecutorSettings(num_workers=2)),
        ("LocalExecutor", "malformed,=,a=b=c", LocalExecutorSettings()),
    ],
)
def test_from_legacy(executor, execargs, expected):
    assert ExecutionOptions.from_legacy(executor, execargs).executor == expected


def test_from_legacy_passes_kwargs(tmp_path):
    opts = ExecutionOptions.from_legacy(
        "LocalExecutor", "", autosave=True, results_dir=tmp_path
    )
    assert opts.autosave and opts.results_dir == Path(tmp_path)


def test_local_task_runner():
    runner = ExecutionOptions(executor=LocalExecutorSettings(num_workers=2)).task_runner()
    assert isinstance(runner, ThreadPoolTaskRunner)
    assert runner._max_workers == 2
    assert ExecutionOptions().task_runner()._max_workers >= 1


@pytest.mark.skipif(HAS_DASK, reason="prefect-dask is installed")
def test_dask_needs_extra():
    with pytest.raises(RuntimeError, match="extra dask"):
        ExecutionOptions(executor=DaskLocalExecutorSettings()).task_runner()


@pytest.mark.skipif(not HAS_DASK, reason="needs the dask extra")
def test_dask_task_runners():
    local = ExecutionOptions(
        executor=DaskLocalExecutorSettings(
            num_workers=2, scheduler="processes", dask_kwargs={"threads_per_worker": 1}
        )
    ).task_runner()
    assert local.cluster_kwargs == {
        "processes": True,
        "n_workers": 2,
        "threads_per_worker": 1,
    }
    remote = ExecutionOptions(
        executor=DaskClusterExecutorSettings(address="tcp://h:8786")
    ).task_runner()
    assert remote.address == "tcp://h:8786"
