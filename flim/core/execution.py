"""Execution options: *where and how* tasks run, kept out of the tool configs."""

import importlib.util
import logging
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, model_validator

from flim.core.config import BaseConfig

# executor names of the command line (-e) and of saved settings before ExecutionOptions
LEGACY_EXECUTORS = {
    "LocalExecutor": "local",
    "LocalDaskExecutor": "dask-local",
    "DaskExecutor": "dask",
}
DASK = ("dask-local", "dask")


class ExecutionOptions(BaseConfig):
    executor: Literal["local", "dask-local", "dask"] = "local"
    # parallel tasks; None = flim.core.runner.default_max_workers()
    num_workers: Optional[int] = Field(default=None, ge=1)
    scheduler: Literal["threads", "processes"] = "threads"  # dask-local only
    address: Optional[str] = None  # dask only: scheduler of an existing cluster
    dask_kwargs: dict[str, Any] = {}  # further DaskTaskRunner / cluster arguments
    autosave: bool = False
    results_dir: Optional[Path] = None
    task_tags: list[str] = []
    device_policy: Literal["prefer", "cpu-only"] = "prefer"

    @model_validator(mode="after")
    def _check_executor_args(self):
        if self.address is not None and self.executor != "dask":
            raise ValueError("address is only used by the dask executor")
        if self.dask_kwargs and self.executor not in DASK:
            raise ValueError("dask_kwargs are only used by the dask executors")
        if self.autosave and self.results_dir is None:
            raise ValueError("autosave needs a results_dir")
        return self

    @classmethod
    def from_legacy(cls, executor: str = "LocalExecutor", execargs: str = "", **kwargs):
        """Options from the command line's ``-e`` executor name and ``"k=v,k=v"`` args.

        As before, an unknown executor runs locally and the local executor uses only an
        integer ``num_workers``; for Dask, unknown args go to the Dask task runner.
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
        name = LEGACY_EXECUTORS.get(executor, "local")
        if executor not in LEGACY_EXECUTORS:
            logging.warning(f"Unknown executor {executor}, using LocalExecutor")
        num_workers = args.pop("num_workers", None)
        if not isinstance(num_workers, int) or num_workers < 1:
            num_workers = None
        options = {"executor": name, "num_workers": num_workers, **kwargs}
        if name == "dask-local" and "scheduler" in args:
            scheduler = args.pop("scheduler")
            options["scheduler"] = (
                "processes" if scheduler == "processes" else "threads"
            )
        if name == "dask" and "address" in args:
            options["address"] = str(args.pop("address"))
        if name in DASK:
            options["dask_kwargs"] = args
        return cls(**options)

    def check_available(self) -> None:
        """Raises RuntimeError if the executor needs packages that are not installed."""
        if self.executor in DASK and importlib.util.find_spec("prefect_dask") is None:
            raise RuntimeError(
                f"The {self.executor} executor needs the optional Dask support:"
                " uv sync --extra dask (or pip install flimanalyzer[dask])"
            )

    def task_runner(self):
        """The Prefect task runner.

        ``local``: a ``ThreadPoolTaskRunner`` with ``num_workers`` threads.
        ``dask-local``: a ``DaskTaskRunner`` starting a local Dask cluster.
        ``dask``: a ``DaskTaskRunner`` connecting to the cluster at ``address`` (or
        starting a local one if no address is given).
        """
        if self.executor == "local":
            from flim.core.runner import default_task_runner

            return default_task_runner(self.num_workers)
        self.check_available()
        from prefect_dask import DaskTaskRunner

        if self.executor == "dask":
            args = dict(self.dask_kwargs)
            if self.address is not None:
                args["address"] = self.address
            return DaskTaskRunner(**args)
        cluster_kwargs = {"processes": self.scheduler == "processes"}
        if self.num_workers is not None:
            cluster_kwargs["n_workers"] = self.num_workers
        return DaskTaskRunner(cluster_kwargs={**cluster_kwargs, **self.dask_kwargs})
