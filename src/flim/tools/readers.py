"""Readers: tools that read data files (Open Tables), and Import Tables.

Import Tables reads data files and runs a workflow on the tables.
"""

import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Optional, Union

from flim.configs.data import ImportTablesConfig, TableReaderConfig
from flim.core.columns import unique_name
from flim.core.config import Issue
from flim.core.reader import READER, find_files, read_file
from flim.core.registry import register_tool
from flim.core.runner import Nth
from flim.core.tool import Tool
from flim.core.types import FileType, InputSpec, OutputSpec, TableType
from flim.core.validation import ValidationReport
from flim.core.workflow import Workflow

READ_STEP = "read"  # Import Tables' results without a workflow: the tables read


@register_tool
class TableReader(Tool[TableReaderConfig]):
    """Reads one data file into a table (see `flim.core.reader.read_file`)."""

    name = "Open Tables"
    short_name = READER  # in renamed columns, e.g. "Source (before Read)"
    category = "File"
    description = (
        "Reads a data file into a table: the column headers from its first line, and"
        " the columns Source, Directory and File first."
    )
    icon = "fileopen.png"
    inputs = (InputSpec("file", FileType, description="A data file."),)
    outputs = (OutputSpec("Table", TableType),)

    def run(
        self, file: str | os.PathLike, *, config: TableReaderConfig
    ) -> dict[str, Any]:
        """Read a data file into a table.

        Warnings of the reader, e.g. renamed columns, are reported with `warn`.

        Args:
            file: The data file.
            config: The read settings: the delimiter, the encoding, and whether the
                file's own Source, Directory and File columns are kept or renamed.

        Returns:
            `Table`: the table.

        Raises:
            ValueError: If the file can't be read as a table.
        """
        table, warnings = read_file(file, config.read_settings())
        for message in warnings:
            self.warn(message)
        return {"Table": table}


def data_files(
    paths: Iterable[str | os.PathLike], config: TableReaderConfig
) -> tuple[dict[str, Path], dict[str, str]]:
    """Return the data files among files and folders, by table name.

    Args:
        paths: Files and folders (with their subfolders).
        config: The read settings (file types, files left out).

    Returns:
        The files by table name (the file name, numbered if two files have the same
        name), and why a path was skipped, by path.
    """
    found, skipped = find_files(paths, config.read_settings())
    files = {}
    for path in found:
        files[unique_name(path.name, path.name, files)] = path
    return files, skipped


@register_tool
class ImportTables(Workflow[ImportTablesConfig]):
    """Read data files and run a workflow on the tables.

    Each file is read with Open Tables, in a task of its own. Each step of the
    workflow runs once per table until a step joins the tables. Without a workflow,
    the results are the tables read.
    """

    name = "Import Tables"
    output_types = (TableType,)
    short_name = "ImportTab"
    category = "File"
    description = (
        "Reads data files, one table per file, and runs a workflow on the tables, for"
        " example one that joins them and takes categories from the file names."
    )
    icon = "import.png"
    inputs = (InputSpec("files", FileType, many=True, description="Data files and folders."),)

    @classmethod
    def workflow_issues(cls, config: ImportTablesConfig) -> list[Issue]:
        """Check the chosen workflow: it must exist and be a workflow file.

        Args:
            config: The config; its `workflow` is a workflow's name or file, or None.

        Returns:
            One issue for `workflow` if it can't be resolved or is not defined by a
            workflow file; none without a workflow.
        """
        if not config.workflow:
            return []
        from flim.core.workflowfile import resolve_workflow

        try:
            workflow = resolve_workflow(config.workflow)
        except ValueError as err:
            return [Issue("workflow", str(err))]
        if getattr(workflow, "definition", None) is None:
            return [Issue("workflow", f"'{config.workflow}' is not a workflow file")]
        return []

    def resolve(
        self,
        config: ImportTablesConfig,
        inputs: Sequence[Any],
        strict: Optional[bool] = None,
    ) -> ValidationReport:
        """Return a report with the config unchanged and the workflow's issues.

        The inputs are files, not tables, so no columns are checked or guessed.
        """
        return ValidationReport(config=config, issues=self.workflow_issues(config))

    @classmethod
    def validate(
        cls,
        config: ImportTablesConfig,
        inputs: Sequence[Any],
        strict: Optional[bool] = None,
    ) -> list[Issue]:
        """Check the config: only the workflow is checked (see `workflow_issues`)."""
        return cls.workflow_issues(config)

    def chosen_workflow(self, config: ImportTablesConfig) -> Optional[type[Workflow]]:
        """Return the workflow class `config.workflow` names, or None without one.

        Raises:
            ValueError: If no workflow has the name, or the file has errors.
        """
        from flim.core.workflowfile import resolve_workflow

        return resolve_workflow(config.workflow) if config.workflow else None

    def build(
        self,
        files: Union[str, os.PathLike, Iterable[str | os.PathLike]],
        *,
        config: ImportTablesConfig,
    ) -> None:
        """Build the flow: one Open Tables task per data file, then the workflow.

        The files' reads are not saved. The paths skipped (not found, or left out by
        the read settings) are kept in `skipped`. Without a workflow, the flow's leaves
        are the reads, under the step `read`.

        Args:
            files: A data file or folder, or several; folders are searched with their
                subfolders.
            config: The read settings and the workflow.

        Raises:
            ValueError: If the workflow can't be resolved.
        """
        if isinstance(files, (str, Path)):
            files = [files]
        found, self.skipped = data_files(files, config)
        reader_config = TableReaderConfig(**config.read_settings().model_dump())
        reads = {}
        for name, path in found.items():
            reader = TableReader()
            reader._save = False  # the files themselves are the data
            reads[name] = reader(path, config=reader_config, task_tags=[name])
        workflow_class = self.chosen_workflow(config)
        if workflow_class is None:
            self.definition = None
            self.leaves = {READ_STEP: reads}
            return
        workflow = workflow_class()
        tables = {name: read[Nth(1)] for name, read in reads.items()}  # the tables
        workflow.build(tables, config=workflow.config_class())
        self.definition = getattr(workflow, "definition", None)
        self.leaves = getattr(workflow, "leaves", {})
