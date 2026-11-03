"""
Created on Fri May  4 02:42:45 2018

@author: khs3z
"""

import pandas as pd
import logging

from flim.core.importer import dataimporter
from flim.core.preprocessor import defaultpreprocessor
from flim.core.execution import DASK, LEGACY_EXECUTORS, ExecutionOptions

DASK_EXECUTORS = tuple(k for k, v in LEGACY_EXECUTORS.items() if v in DASK)


def check_executor_available(executor: str) -> None:
    """Raises RuntimeError if ``executor`` needs packages that are not installed."""
    import importlib.util

    if executor in DASK_EXECUTORS and importlib.util.find_spec("prefect_dask") is None:
        raise RuntimeError(
            f"{executor} needs the optional Dask support: uv sync --extra dask"
            " (or pip install flimanalyzer[dask])"
        )


class FLIMAnalyzer:
    def __init__(
        self,
        importer=dataimporter(),
        preprocessor=defaultpreprocessor(),
        executor="LocalExecutor",
        execargs="",
        **kwargs,
    ):
        self.importer = importer
        self.preprocessor = preprocessor
        self.data = pd.DataFrame()
        self.execution = ExecutionOptions.from_legacy(executor, execargs)
        logging.info(f"Setting up {self.execution.executor} executor: {self.execution}")
        logging.debug(
            f"Initialized {__name__}.FLIMAnalyzer with"
            f" {importer}, {preprocessor}"
        )

    def get_task_runner(self):
        """Returns the Prefect task runner for workflow execution.

        Returns:
            ``LocalExecutor``: a Prefect ``ThreadPoolTaskRunner`` with ``num_workers``
            threads (default: :func:`flim.core.runner.default_max_workers`;
            ``num_workers=1`` runs one task at a time). Otherwise a
            ``prefect_dask.DaskTaskRunner``: ``LocalDaskExecutor`` starts a local Dask
            cluster (args: ``num_workers``, ``scheduler=threads|processes``),
            ``DaskExecutor`` connects to an existing cluster (arg: ``address``).
        """
        return self.execution.task_runner()

    def get_data(self):
        return self.data

    def get_importer(self):
        return self.importer

    def set_importer(self, imp):
        if imp is not None:
            self.importer = imp

    def get_preprocessor(self):
        return self.preprocessor

    def set_preprocessor(self, pp):
        if pp is not None:
            self.preprocessor = pp

