"""Readers: tools that read data files (Open Tables), and Import Tables, which reads
them and runs a workflow on the tables."""

from pathlib import Path

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
    in_menus = False  # File > Open Tables...
    inputs = (InputSpec("file", FileType, description="A data file."),)
    outputs = (OutputSpec("Table", TableType),)

    def run(self, file, *, config):
        table, warnings = read_file(file, config.read_settings())
        for message in warnings:
            self.warn(message)
        return {"Table": table}


def data_files(paths, config: TableReaderConfig) -> tuple[dict, dict]:
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
    """Reads data files with Open Tables, one task per file, and runs a workflow on
    the tables (each step once per table until a step joins them), or returns the
    tables if no workflow is chosen."""

    name = "Import Tables"
    short_name = "ImportTab"
    category = "File"
    description = (
        "Reads data files, one table per file, and runs a workflow on the tables, for"
        " example one that joins them and takes categories from the file names."
    )
    icon = "import.png"
    in_menus = False  # File > Import Tables...
    inputs = (InputSpec("files", FileType, many=True, description="Data files and folders."),)

    @classmethod
    def workflow_issues(cls, config) -> list:
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

    def resolve(self, config, inputs, strict=None):
        return ValidationReport(config=config, issues=self.workflow_issues(config))

    @classmethod
    def validate(cls, config, inputs, strict=None):
        return cls.workflow_issues(config)

    def chosen_workflow(self, config):
        """Return the workflow of `config.workflow` (a tool class), or None."""
        from flim.core.workflowfile import resolve_workflow

        return resolve_workflow(config.workflow) if config.workflow else None

    def build(self, files, *, config):
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
