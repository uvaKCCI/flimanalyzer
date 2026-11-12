"""The FLIMAnalyzer class: the importer, preprocessor, data and execution options."""

from typing import TYPE_CHECKING, Any, Optional

import pandas as pd
import logging

from flim.core.importer import dataimporter
from flim.core.preprocessor import defaultpreprocessor
from flim.core.execution import ExecutionOptions

if TYPE_CHECKING:
    from prefect.task_runners import TaskRunner

logger = logging.getLogger(__name__)


class FLIMAnalyzer:
    """The importer, the preprocessor, the data and the execution options of a session.

    Args:
        importer: The data importer.
        preprocessor: The preprocessor.
        executor: The command line's `-e` executor name: `LocalExecutor`,
            `LocalDaskExecutor` or `DaskExecutor`; used if `execution` is None.
        execargs: The command line's `-a` executor args, e.g. `num_workers=4`; used
            if `execution` is None.
        execution: The execution options; None to make them from `executor` and
            `execargs` (see `ExecutionOptions.from_legacy`).
        **kwargs: Ignored.
    """

    def __init__(
        self,
        importer: dataimporter = dataimporter(),
        preprocessor: defaultpreprocessor = defaultpreprocessor(),
        executor: str = "LocalExecutor",
        execargs: str = "",
        execution: Optional[ExecutionOptions] = None,
        **kwargs: Any,
    ) -> None:
        """Create the session; the arguments are described in the class docstring."""
        self.importer = importer
        self.preprocessor = preprocessor
        self.data = pd.DataFrame()
        # the executor: `execution` if given, else from the -e name and -a args of 0.6
        self.execution = execution or ExecutionOptions.from_legacy(executor, execargs)
        logger.info(f"Setting up {self.execution.execution.executor} executor: {self.execution}")
        logger.debug(
            f"Initialized {__name__}.FLIMAnalyzer with"
            f" {importer}, {preprocessor}"
        )

    def get_task_runner(self) -> "TaskRunner":
        """Return the Prefect task runner for workflow execution.

        See `ExecutionOptions.task_runner`.

        Returns:
            `LocalExecutor`: a Prefect `ThreadPoolTaskRunner` with `num_workers`
            threads (default: `flim.core.runner.default_workers`; `num_workers=1`
            runs one task at a time). Otherwise a `prefect_dask.DaskTaskRunner`:
            `LocalDaskExecutor` starts a local Dask cluster (args: `num_workers`,
            `scheduler=threads|processes`), `DaskExecutor` connects to an existing
            cluster (arg: `address`) or, without an address, starts a local one.

        Raises:
            RuntimeError: If a Dask executor is selected and `prefect_dask` is not
                installed.
        """
        return self.execution.task_runner()

    def get_data(self) -> pd.DataFrame:
        """Return the data."""
        return self.data

    def get_importer(self) -> dataimporter:
        """Return the data importer."""
        return self.importer

    def set_importer(self, imp: Optional[dataimporter]) -> None:
        """Set the data importer; None keeps the current one."""
        if imp is not None:
            self.importer = imp

    def get_preprocessor(self) -> defaultpreprocessor:
        """Return the preprocessor."""
        return self.preprocessor

    def set_preprocessor(self, pp: Optional[defaultpreprocessor]) -> None:
        """Set the preprocessor; None keeps the current one."""
        if pp is not None:
            self.preprocessor = pp

