"""FLIMAnalyzer: holds the importer, the preprocessor, the data and the execution
options."""

from typing import Optional

import pandas as pd
import logging

from flim.core.importer import dataimporter
from flim.core.preprocessor import defaultpreprocessor
from flim.core.execution import ExecutionOptions


class FLIMAnalyzer:
    def __init__(
        self,
        importer=dataimporter(),
        preprocessor=defaultpreprocessor(),
        executor="LocalExecutor",
        execargs="",
        execution: Optional[ExecutionOptions] = None,
        **kwargs,
    ):
        self.importer = importer
        self.preprocessor = preprocessor
        self.data = pd.DataFrame()
        # the executor: `execution` if given, else from the -e name and -a args of 0.6
        self.execution = execution or ExecutionOptions.from_legacy(executor, execargs)
        logging.info(f"Setting up {self.execution.execution.executor} executor: {self.execution}")
        logging.debug(
            f"Initialized {__name__}.FLIMAnalyzer with"
            f" {importer}, {preprocessor}"
        )

    def get_task_runner(self):
        """Returns the Prefect task runner for workflow execution.

        Returns:
            ``LocalExecutor``: a Prefect ``ThreadPoolTaskRunner`` with ``num_workers``
            threads (default: :func:`flim.core.runner.default_workers`;
            ``num_workers=1`` runs one task at a time). Otherwise a
            ``prefect_dask.DaskTaskRunner``: ``LocalDaskExecutor`` starts a local Dask
            cluster (args: ``num_workers``, ``scheduler=threads|processes``),
            ``DaskExecutor`` connects to an existing cluster (arg: ``address``) or,
            without an address, starts a local one.
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

