"""Execution options: where and how tasks run, kept out of the tool configs."""

import importlib.util
import logging
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, Self, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flim.core.saving import AutosaveConfig
from flim.core.config import BaseConfig

if TYPE_CHECKING:
    from prefect.task_runners import TaskRunner

logger = logging.getLogger(__name__)

# the deprecated executor names of -e (removed in 1.0.0) and the names that replace them
LEGACY_EXECUTORS = {
    "LocalExecutor": "local",
    "LocalDaskExecutor": "dask-local",
    "DaskExecutor": "dask",
}


class LocalExecutorSettings(BaseModel):
    """Tasks run in a pool of threads in this process."""

    model_config = ConfigDict(extra="forbid")
    executor: Literal["local"] = "local"
    workers: Optional[int] = Field(
        default=None, ge=1, description="Parallel tasks. None defaults to one per core."
    )


class DaskLocalExecutorSettings(BaseModel):
    """Tasks run on a Dask cluster started on this machine."""

    model_config = ConfigDict(extra="forbid")
    executor: Literal["dask-local"] = "dask-local"
    workers: Optional[int] = Field(
        default=None,
        ge=1,
        description="Dask workers. None: Dask's default for a local cluster (with"
        " threads, one worker with a thread per core).",
    )
    scheduler: Literal["threads", "processes"] = Field(
        default="threads", description="Workers as threads of one process, or processes."
    )
    kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Further arguments of the Dask cluster."
    )


class DaskClusterExecutorSettings(BaseModel):
    """Tasks run on an existing Dask cluster."""

    model_config = ConfigDict(extra="forbid")
    executor: Literal["dask"] = "dask"
    address: str = Field(..., description="Scheduler address of an existing Dask cluster.")
    kwargs: dict[str, Any] = Field(
        default_factory=dict, description="Further arguments of the Dask task runner."
    )


# the model is selected by the value of `executor`
ExecutorSettings = Annotated[
    Union[LocalExecutorSettings, DaskLocalExecutorSettings, DaskClusterExecutorSettings],
    Field(discriminator="executor"),
]
DASK = (DaskLocalExecutorSettings, DaskClusterExecutorSettings)


class ExecutionOptions(BaseConfig):
    """The executor of a run and the run's own options.

    Besides the executor (`execution`): whether, where and in which formats the run
    saves its results (`autosave`), the task tags, the device policy, and how many
    seconds the client waits for a Dask cluster (`server_timeout`, from the app
    setting of the same name).
    """

    execution: ExecutorSettings = Field(default_factory=LocalExecutorSettings)
    autosave: AutosaveConfig = Field(default_factory=AutosaveConfig)
    task_tags: list[str] = []
    device_policy: Literal["prefer", "cpu-only"] = "prefer"
    server_timeout: float = Field(default=60.0, gt=0)  # seconds, for a Dask cluster

    @model_validator(mode="after")
    def _validate_autosave(self) -> Self:
        """Reject autosave without a results folder."""
        if self.autosave.enabled and self.autosave.results_dir is None:
            raise ValueError("autosave needs a results_dir")
        return self

    @classmethod
    def from_legacy(
        cls, executor: str = "LocalExecutor", execargs: str = "", **kwargs: Any
    ) -> Self:
        """Create options from a deprecated `-e` executor name and `-a` args.

        The names are removed in 1.0.0, `-a` in 0.8.0; see `flim.core.cli` for the
        current `-e` forms.

        `execargs` is a string of `key=value` pairs separated by commas; pairs that are
        not `key=value` are skipped, and integer values are converted to int.
        `num_workers` sets `workers` if it is a positive integer, for the local
        executors only. `scheduler` is used only by a local Dask cluster; any value
        other than `processes` selects threads. `DaskExecutor` connects to the
        cluster at `address`; without an address it starts a local Dask cluster, as
        before this option took the address (`dask-local`). The other args go to
        `kwargs` of the Dask executors and are ignored by `LocalExecutor`.

        Args:
            executor: `LocalExecutor`, `LocalDaskExecutor` or `DaskExecutor`. An
                unknown name is logged and selects `LocalExecutor`.
            execargs: The executor's args, e.g. `"num_workers=4,scheduler=processes"`.
            **kwargs: Further options of the run, e.g. `autosave`.

        Returns:
            The execution options.
        """
        args = {}
        for item in (execargs or "").split(","):
            parts = item.split("=")
            if len(parts) != 2:
                continue
            key, value = parts[0].strip(), parts[1].strip()
            try:
                value = int(value)
            except ValueError:
                pass
            args[key] = value
        if executor not in LEGACY_EXECUTORS:
            logger.warning(f"Unknown executor {executor}, using LocalExecutor")
        name = LEGACY_EXECUTORS.get(executor, "local")
        num_workers = args.pop("num_workers", None)
        if not isinstance(num_workers, int) or num_workers < 1:
            num_workers = None
        if name == "dask" and "address" not in args:
            logger.info("DaskExecutor without an address: starting a local Dask cluster")
            name = "dask-local"
        if name == "local":
            settings = LocalExecutorSettings(workers=num_workers)
        elif name == "dask-local":
            scheduler = args.pop("scheduler", "threads")
            settings = DaskLocalExecutorSettings(
                workers=num_workers,
                scheduler="processes" if scheduler == "processes" else "threads",
                kwargs=args,
            )
        else:
            address = str(args.pop("address"))
            args.pop("scheduler", None)
            settings = DaskClusterExecutorSettings(address=address, kwargs=args)
        return cls(execution=settings, **kwargs)

    def check_available(self) -> None:
        """Deprecated: use `validate_available`; removed in 0.8.0."""
        warnings.warn(
            "flim.core.execution.ExecutionOptions.check_available is deprecated and is"
            " removed in 0.8.0; use flim.core.execution.ExecutionOptions.validate_available",
            DeprecationWarning,
            stacklevel=2,
        )
        self.validate_available()

    def validate_available(self) -> None:
        """Validate that the packages the executor needs are installed.

        Raises:
            RuntimeError: If a Dask executor is selected and `prefect_dask` is not
                installed.
        """
        if isinstance(self.execution, DASK) and importlib.util.find_spec("prefect_dask") is None:
            raise RuntimeError(
                f"The {self.execution.executor} executor needs the optional Dask support:"
                " uv sync --extra dask (or pip install flimanalyzer[dask])"
            )

    def validate_cluster(self) -> Optional[str]:
        """Validate that the Dask cluster of the `dask` executor answers, within the timeout.

        Connects to the cluster's address, waiting at most `server_timeout` seconds,
        and disconnects. Other executors have no cluster to validate.

        Returns:
            None if the cluster answers (or there is none), else the problem.
        """
        if not isinstance(self.execution, DaskClusterExecutorSettings):
            return None
        try:
            from distributed import Client

            with Client(self.execution.address, timeout=self.server_timeout):
                return None
        except Exception as err:  # e.g. OSError: timed out connecting
            return f"the Dask cluster at {self.execution.address} doesn't answer ({err})"

    def task_runner(self) -> "TaskRunner":
        """Create the Prefect task runner of the executor.

        `local`: a `ThreadPoolTaskRunner` with `workers` threads. `dask-local`: a
        `DaskTaskRunner` that starts a local Dask cluster with `workers` workers,
        as threads or processes. `dask`: a `DaskTaskRunner` connected to the cluster at
        `address`.

        Returns:
            The task runner. The client of `dask` waits `server_timeout` seconds for the
            cluster, unless `kwargs` set `client_kwargs` with a `timeout`.

        Raises:
            RuntimeError: If a Dask executor is selected and `prefect_dask` is not
                installed.
        """
        settings = self.execution
        if isinstance(settings, LocalExecutorSettings):
            from flim.core.runner import default_task_runner

            return default_task_runner(settings.workers)
        self.validate_available()
        from prefect_dask import DaskTaskRunner

        if isinstance(settings, DaskClusterExecutorSettings):
            kwargs = dict(settings.kwargs)
            # how long the client waits for the cluster; a timeout in client_kwargs takes precedence
            client_kwargs = {"timeout": self.server_timeout, **kwargs.pop("client_kwargs", {})}
            return DaskTaskRunner(address=settings.address, client_kwargs=client_kwargs, **kwargs)
        return DaskTaskRunner(cluster_kwargs=self._cluster_kwargs())

    def _cluster_kwargs(self) -> dict[str, Any]:
        """Return the arguments of the local Dask cluster of the `dask-local` executor."""
        settings = self.execution
        cluster_kwargs: dict[str, Any] = {"processes": settings.scheduler == "processes"}
        if settings.workers is not None:
            cluster_kwargs["n_workers"] = settings.workers
        return {**cluster_kwargs, **settings.kwargs}

    @contextmanager
    def started(self) -> Iterator[tuple[Self, Optional[str]]]:
        """Start the executor's local Dask cluster once, for several runs.

        With `dask-local`, starts a local Dask cluster and gives options of the `dask`
        executor connected to it; the cluster stops when the context ends. Other
        executors are given unchanged: `local` creates its threads per run, and `dask`
        connects to its existing cluster.

        Yields:
            The options for the runs, and a note on the started cluster (e.g.
            `executor dask-local: one Dask cluster for all runs, at tcp://127.0.0.1:
            51234 (4 workers, threads)`), or None if no cluster was started.

        Raises:
            RuntimeError: If a Dask executor is selected and `prefect_dask` is not
                installed.
        """
        settings = self.execution
        if not isinstance(settings, DaskLocalExecutorSettings):
            yield self, None
            return
        self.validate_available()
        from distributed import LocalCluster

        with LocalCluster(**self._cluster_kwargs()) as cluster:
            address = cluster.scheduler_address
            workers = len(cluster.workers)
            logger.info(f"Started a local Dask cluster at {address} ({workers} workers)")
            shared = self.model_copy(
                update={"execution": DaskClusterExecutorSettings(address=address)}
            )
            yield shared, (
                f"executor dask-local: one Dask cluster for all runs, at {address}"
                f" ({workers} workers, {settings.scheduler})"
            )
