"""The FLIMAnalyzer class: the data and execution options of a session."""

from typing import TYPE_CHECKING, Any, Optional

import pandas as pd
import logging

from flim.core.execution import ExecutionOptions

if TYPE_CHECKING:
    from prefect.task_runners import TaskRunner

logger = logging.getLogger(__name__)


class FLIMAnalyzer:
    """The data and the execution options of a session.

    Args:
        executor: A deprecated `-e` executor name (`LocalExecutor`,
            `LocalDaskExecutor` or `DaskExecutor`, removed in 1.0.0); used if
            `execution` is None.
        execargs: The deprecated `-a` executor args (removed in 0.8.0), e.g.
            `num_workers=4`; used if `execution` is None.
        execution: The execution options (`-e local`, `dask-local` or `dask`, see
            `flim.core.cli`); None to make them from `executor` and `execargs` (see
            `ExecutionOptions.from_legacy`).
        **kwargs: Ignored.
    """

    def __init__(
        self,
        executor: str = "LocalExecutor",
        execargs: str = "",
        execution: Optional[ExecutionOptions] = None,
        **kwargs: Any,
    ) -> None:
        """Create the session; the arguments are described in the class docstring."""
        self.data = pd.DataFrame()
        # the executor: `execution` if given, else from the deprecated -e name and -a
        # args of 0.6
        self.execution = execution or ExecutionOptions.from_legacy(executor, execargs)
        logger.info(f"Setting up {self.execution.execution.executor} executor: {self.execution}")

    def get_task_runner(self) -> "TaskRunner":
        """Return the Prefect task runner for workflow execution.

        See `ExecutionOptions.task_runner`.

        Returns:
            `local`: a Prefect `ThreadPoolTaskRunner` with `workers` threads
            (default: `flim.core.runner.default_workers`; `workers=1` runs one task
            at a time). Otherwise a `prefect_dask.DaskTaskRunner`: `dask-local`
            starts a local Dask cluster (`workers`, `scheduler=threads|processes`),
            `dask` connects to an existing cluster (`address`).

        Raises:
            RuntimeError: If a Dask executor is selected and `prefect_dask` is not
                installed.
        """
        return self.execution.task_runner()

    def get_data(self) -> pd.DataFrame:
        """Return the data."""
        return self.data

