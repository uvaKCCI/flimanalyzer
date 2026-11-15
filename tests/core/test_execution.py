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
    assert opts.execution == LocalExecutorSettings(workers=None)
    assert opts.device_policy == "prefer" and not opts.autosave.enabled


def test_the_executor_name_selects_the_settings():
    opts = ExecutionOptions(execution={"executor": "dask-local", "workers": 2})
    assert opts.execution == DaskLocalExecutorSettings(workers=2)
    opts = ExecutionOptions(execution={"executor": "dask", "address": "tcp://h:8786"})
    assert opts.execution == DaskClusterExecutorSettings(address="tcp://h:8786")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"execution": {"executor": "ray"}},
        {"execution": {"executor": "local", "workers": 0}},
        # settings of another executor
        {"execution": {"executor": "local", "address": "tcp://h:8786"}},
        {"execution": {"executor": "dask-local", "address": "tcp://h:8786"}},
        {"execution": {"executor": "local", "kwargs": {"x": 1}}},
        {"execution": {"executor": "dask"}},  # a cluster needs its address
        {"execution": {"executor": "local", "adress": "x"}},  # misspelled
        {"autosave": {"enabled": True}},  # no results_dir
        {"autosave": {"formats": [{"kind": "table", "format": "xlsx"}]}},
        {"autosave": {"formats": [{"kind": "movie"}]}},
        {"device_policy": "gpu-only"},
        {"bogus": 1},
    ],
)
def test_invalid(kwargs):
    with pytest.raises(ValidationError):
        ExecutionOptions(**kwargs)


def test_autosave_with_dir(tmp_path):
    opts = ExecutionOptions(autosave={"enabled": True, "results_dir": tmp_path})
    assert opts.autosave.results_dir == tmp_path


@pytest.mark.parametrize(
    "executor, execargs, expected",
    [
        ("LocalExecutor", "", LocalExecutorSettings()),
        ("LocalExecutor", "num_workers=3", LocalExecutorSettings(workers=3)),
        # the local executor ignores everything but an integer num_workers (-a)
        ("LocalExecutor", "num_workers=x,foo=1", LocalExecutorSettings()),
        ("Unknown", "num_workers=2", LocalExecutorSettings(workers=2)),
        (
            "LocalDaskExecutor",
            "num_workers=4,scheduler=processes,threads_per_worker=2",
            DaskLocalExecutorSettings(
                workers=4, scheduler="processes", kwargs={"threads_per_worker": 2}
            ),
        ),
        ("LocalDaskExecutor", "scheduler=bogus", DaskLocalExecutorSettings()),
        (
            "DaskExecutor",
            "address=tcp://10.0.0.1:8786",
            DaskClusterExecutorSettings(address="tcp://10.0.0.1:8786"),
        ),
        # without an address: a local Dask cluster, as before the address was required
        ("DaskExecutor", "num_workers=2", DaskLocalExecutorSettings(workers=2)),
        ("LocalExecutor", "malformed,=,a=b=c", LocalExecutorSettings()),
    ],
)
def test_from_legacy(executor, execargs, expected):
    assert ExecutionOptions.from_legacy(executor, execargs).execution == expected


def test_from_legacy_passes_kwargs(tmp_path):
    opts = ExecutionOptions.from_legacy(
        "LocalExecutor", "", autosave={"enabled": True, "results_dir": tmp_path}
    )
    assert opts.autosave.enabled and opts.autosave.results_dir == Path(tmp_path)


def test_local_task_runner():
    runner = ExecutionOptions(execution=LocalExecutorSettings(workers=2)).task_runner()
    assert isinstance(runner, ThreadPoolTaskRunner)
    assert runner._max_workers == 2
    assert ExecutionOptions().task_runner()._max_workers >= 1


@pytest.mark.skipif(HAS_DASK, reason="prefect-dask is installed")
def test_dask_needs_extra():
    with pytest.raises(RuntimeError, match="extra dask"):
        ExecutionOptions(execution=DaskLocalExecutorSettings()).task_runner()


@pytest.mark.skipif(not HAS_DASK, reason="needs the dask extra")
def test_dask_task_runners():
    local = ExecutionOptions(
        execution=DaskLocalExecutorSettings(
            workers=2, scheduler="processes", kwargs={"threads_per_worker": 1}
        )
    ).task_runner()
    assert local.cluster_kwargs == {
        "processes": True,
        "n_workers": 2,
        "threads_per_worker": 1,
    }
    remote = ExecutionOptions(
        execution=DaskClusterExecutorSettings(address="tcp://h:8786")
    ).task_runner()
    assert remote.address == "tcp://h:8786"
    assert remote.client_kwargs["timeout"] == 60  # the default server_timeout
    remote = ExecutionOptions(
        execution=DaskClusterExecutorSettings(address="tcp://h:8786"), server_timeout=7
    ).task_runner()
    assert remote.client_kwargs["timeout"] == 7
    # a timeout in the executor's own client_kwargs takes precedence
    remote = ExecutionOptions(
        execution=DaskClusterExecutorSettings(
            address="tcp://h:8786", kwargs={"client_kwargs": {"timeout": 3}}
        ),
        server_timeout=7,
    ).task_runner()
    assert remote.client_kwargs["timeout"] == 3


def test_started_gives_local_and_dask_unchanged():
    for execution in (LocalExecutorSettings(), DaskClusterExecutorSettings(address="tcp://h:8786")):
        opts = ExecutionOptions(execution=execution)
        with opts.started() as (started, note):
            assert started is opts and note is None


@pytest.mark.skipif(not HAS_DASK, reason="needs the dask extra")
def test_started_runs_one_local_dask_cluster_until_the_end():
    opts = ExecutionOptions(execution=DaskLocalExecutorSettings(workers=1), server_timeout=5)
    with opts.started() as (started, note):
        address = started.execution.address
        assert started.execution.executor == "dask"
        assert started.server_timeout == 5
        assert note.startswith(f"executor dask-local: one Dask cluster for all runs, at {address}")
        assert "(1 workers, threads)" in note
        assert started.check_cluster() is None  # the cluster answers
    assert started.check_cluster() is not None  # stopped with the context
