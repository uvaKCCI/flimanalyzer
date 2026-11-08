"""Batch mode: import data files and run tools or workflows without the GUI.

``flimbatch -i <files or folders> -o <folder> [-c settings.json] [--run NAME]``

1. Reads the settings (any version, see flim.core.settings), else the defaults.
2. Imports the files as the GUI's Import does: delimiter, filename parser and its
   patterns, renamed and dropped columns, and the range filters if they are used.
   The table is saved as ``Imported.txt`` in the output folder.
3. Runs each ``--run`` tool or workflow on it, with its settings from the settings
   file; the results are saved in ``<output>/<name>/``. Workflow columns that are not
   in the data are errors unless ``--allow-guesses`` is given.

The exit code is 0 if the import and every run completed without failed tasks, 1
otherwise. wxPython is not imported.
"""

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from flim.core.execution import ExecutionOptions
from flim.core.filter import RangeFilter
from flim.core.importer import dataimporter
from flim.core.parser import instantiate_parser
from flim.core.paths import canonical_folder, folder_problem
from flim.core.preprocessor import defaultpreprocessor
from flim.core.registry import TOOLS_GROUP, discover, tools
from flim.core.schema import TableSchema
from flim.core.cli import add_settings_options, command_line_changes, settings_file
from flim.core.settings import AppSettings
from flim.core.settingsmgr import session_settings
from flim.results import write_table

IMPORTED = "Imported.txt"


class BatchError(Exception):
    """A batch step that cannot be done, with the reason for the user."""


def import_table(files, settings: AppSettings, exclude=()) -> pd.DataFrame:
    """Imports data files and folders with the import, preprocess and filter
    settings. The range filters are applied only if ``settings.filters.use`` is set.

    Raises:
        BatchError: the filename parser is unknown, no data files were found, or none
            of the files could be read.
    """
    imported = settings.import_
    parser = instantiate_parser(f"flim.core.parser.{imported.filename_parser.parser}")
    if parser is None:
        raise BatchError(f"Unknown filename parser {imported.filename_parser.parser}")
    if imported.filename_parser.patterns:
        parser.set_regexpatterns(imported.filename_parser.patterns)
    preprocessor = defaultpreprocessor()
    preprocessor.set_replacementheaders(settings.preprocess.rename)
    preprocessor.set_dropcolumns(settings.preprocess.drop)

    importer = dataimporter()
    importer.set_delimiter(imported.delimiter)
    importer.add_files(list(files), exclude=list(exclude) + imported.exclude_files)
    if not importer.get_files():
        raise BatchError("No data files found")
    importer.set_parser(parser)
    importer.set_column_combos(imported.category_combinations)
    importer.set_preprocessor(preprocessor)
    data, filenames, _ = importer.import_data()
    if data is None or not filenames:
        raise BatchError("None of the files could be read")
    logging.info(f"Imported {len(filenames)} file(s): {data.shape[0]} rows")
    if settings.filters.use:
        data = filtered(data, settings.filters.range_filters)
    return data


def filtered(data: pd.DataFrame, range_filters) -> pd.DataFrame:
    """``data`` without the rows that the selected range filters drop, renumbered
    from 0."""
    dropped = [RangeFilter(params=p).get_dropped(data) for p in range_filters]
    dropped = [rows for rows, p in zip(dropped, range_filters) if p.get("selected")]
    rows = np.unique(np.concatenate([np.asarray(r, dtype=int) for r in dropped] or [[]]))
    if len(rows):
        logging.info(f"Range filters dropped {len(rows)} rows")
    return data.drop(data.index[rows.astype(int)]).reset_index(drop=True)


def run_tool(
    name: str,
    data: pd.DataFrame,
    settings: AppSettings,
    output_dir: str | os.PathLike,
    execution: Optional[ExecutionOptions] = None,
    strict: bool = True,
    settings_record: Sequence[str] = (),
):
    """Runs the tool or workflow named ``name`` on ``data`` with the tool's config
    stored in ``settings`` (the config's defaults if none is stored or the stored one
    is not valid). The results are saved in ``<output_dir>/<tool name>/``; the tool's
    stored autosave and results folder settings are not used. A workflow gets
    ``data`` as every input; columns its config names that are not in ``data`` stop
    the run if ``strict`` (the default for a workflow whose own ``strict`` is None),
    otherwise they are replaced by guessed columns. `settings_record` names the
    settings files in the run summary.

    Returns:
        flim.core.runner.FlowRun

    Raises:
        BatchError: If the named tool or workflow does not exist, if the tool needs
            more than one input table, or if its config is not valid for ``data``.
    """
    from flim.core.runner import run_flow
    from flim.core.workflow import Workflow, WorkflowValidationError

    if name not in tools:
        raise BatchError(f"No tool or workflow named '{name}'")
    tool = tools.get(name)
    required = [spec for spec in tool.inputs if not spec.optional]
    if len(required) > 1 and not issubclass(tool, Workflow):
        raise BatchError(f"{name} needs {len(required)} input tables; batch runs give one")
    config = settings.tools.config(tool)
    execution = execution or ExecutionOptions()
    autosave_dir = Path(output_dir) / tool.name
    task_runner = execution.task_runner()
    if issubclass(tool, Workflow):
        inputs = [data] * len(tool.inputs)  # every input gets the imported table
        try:
            return tool().run_flow(
                *inputs,
                config=config,
                task_runner=task_runner,
                autosave_dir=autosave_dir,
                strict=strict,
                settings_record=settings_record,
            )
        except WorkflowValidationError as err:
            raise BatchError(f"{name}:\n{err}") from None
    many = tool.inputs[0].many  # the tool takes a dict of tables (e.g. Concatenate)
    schema = TableSchema.from_frame(data)
    schemas = [{"Imported": schema} if many else schema]
    errors = [i for i in tool.validate(config, schemas) if i.severity == "error"]
    if errors:
        lines = [f"{i.field}: {i.message}" if i.field else i.message for i in errors]
        raise BatchError(f"{name}:\n" + "\n".join(lines))

    def build():
        table = {"Imported": data} if many else data
        for each in tool().map_configs(config):
            tool()(table, config=each, task_tags=tool.name)

    return run_flow(
        tool.name,
        build,
        task_runner=task_runner,
        autosave_dir=autosave_dir,
        settings_record=settings_record,
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser of flimbatch.

    Returns:
        The parser, with the input and exclude files, the shared app settings options
        (`flim.core.cli`; `-o` required), the runs and the log level.
    """
    parser = argparse.ArgumentParser(
        prog="flimbatch",
        description="Imports FLIM data files and runs tools or workflows on them.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input", nargs="+", required=True, help="data files or folders"
    )
    parser.add_argument(
        "-x", "--exclude", nargs="+", default=[], help="files not to import"
    )
    add_settings_options(parser, output_required=True)
    parser.add_argument(
        "-r",
        "--run",
        action="append",
        default=[],
        metavar="NAME",
        help="tool or workflow to run on the imported data (repeatable)",
    )
    parser.add_argument("--allow-guesses", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "-l",
        "--log",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="logging level",
    )
    return parser


def parse_arguments(argv=None):
    """Parse the command line of flimbatch.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The parsed arguments.
    """
    return build_parser().parse_args(argv)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log.upper(), format="%(levelname)s %(message)s", force=True
    )
    import flim.tools  # noqa: F401  (registers the tools)
    import flim.workflow  # noqa: F401  (registers the workflows)
    from flim.core.prefect_server import checked_prefect_server, use_prefect_server

    discover(TOOLS_GROUP)  # registers the tools of other installed packages
    try:
        name, notes = settings_file(args)
        changes, more = command_line_changes(args)
        for note in notes + more:
            print(f"flimbatch: warning: {note}", file=sys.stderr)
        # no user settings file: batch results don't depend on settings changed in the GUI
        # every setting of the file must be usable: results don't depend on ignored
        # settings or on which tools are installed
        manager = session_settings(name, changes, complete=True)
        settings = manager.settings
        execution = ExecutionOptions(execution=settings.execution)
        execution.check_available()
        output = canonical_folder(args.output)
        if problem := folder_problem(output):
            raise BatchError(f"--output: {problem}")
        os.makedirs(output, exist_ok=True)
        data = import_table(args.input, settings, exclude=args.exclude)
        path = os.path.join(output, IMPORTED)
        write_table(data, path)
        logging.info(f"Saved {path}")
        strict = True if settings.strict is None else settings.strict
        failed = []
        with use_prefect_server(start=settings.prefect_server):
            for name in args.run:
                with checked_prefect_server():
                    run = run_tool(
                    name, data, settings, output, execution, strict, manager.record()
                )
                if run.failed or run.state != "completed":
                    failed.append(f"{name}: {', '.join(run.failed) or run.state}")
                logging.info(f"{name}: {run.state}; results in {run.autosave_dir}")
    except (BatchError, RuntimeError, OSError, ValueError) as err:  # incl. FileNotFoundError
        print(f"flimbatch: {err}", file=sys.stderr)
        return 1
    if failed:
        print("flimbatch: failed tasks\n" + "\n".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
