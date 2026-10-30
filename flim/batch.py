"""Batch mode: import data files and run tools or workflows without the GUI.

``flimbatch -i <files or folders> -o <folder> [-c settings.json] [--run NAME]``

1. Reads the settings (any version, see flim.core.settings), else the defaults.
2. Imports the files as the GUI's Import does: delimiter, filename parser and its
   patterns, renamed and dropped columns, and the range filters if they are used.
   The table is saved as ``Imported.txt`` in the output folder.
3. Runs each ``--run`` tool or workflow on it, with its settings from the settings
   file; the results are saved in ``<output>/<name>/``. Workflow columns that are not
   in the data are errors unless ``--allow-guesses`` is given.

The exit code is 0 if everything ran, 1 otherwise. Only the core is imported (no wx).
"""

import argparse
import logging
import os
import sys
from typing import Optional

import numpy as np
import pandas as pd

from flim.core.execution import ExecutionOptions
from flim.core.filter import RangeFilter
from flim.core.importer import dataimporter
from flim.core.parser import instantiate_parser
from flim.core.preprocessor import defaultpreprocessor
from flim.core.registry import TOOLS_GROUP, discover, tools
from flim.core.schema import TableSchema
from flim.core.settings import AppSettings, load_settings

IMPORTED = "Imported.txt"


class BatchError(Exception):
    """A batch step that cannot be done, with the reason for the user."""


def import_table(files, settings: AppSettings, exclude=()) -> pd.DataFrame:
    """Imports data files and folders with the import, preprocess and filter
    settings."""
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
    """The rows that pass the selected range filters (as the data windows show)."""
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
    output_dir: str,
    execution: Optional[ExecutionOptions] = None,
    allow_guesses: bool = False,
):
    """Runs a tool or workflow on ``data`` with its saved settings; its results are
    saved in ``<output_dir>/<name>/``.

    Returns:
        flim.core.runner.FlowRun
    """
    from flim.core.runner import run_flow
    from flim.core.workflow import Workflow, WorkflowValidationError

    if name not in tools:
        raise BatchError(f"No tool or workflow named '{name}'")
    tool = tools.get(name)
    required = [spec for spec in tool.inputs if not spec.optional]
    if len(required) > 1 and not issubclass(tool, Workflow):
        raise BatchError(f"{name} needs {len(required)} input tables; batch runs give one")
    config = settings.tool_settings.config(tool)
    execution = execution or ExecutionOptions()
    autosave_dir = os.path.join(output_dir, tool.name)
    task_runner = execution.task_runner()
    if issubclass(tool, Workflow):
        inputs = [data] * len(tool.inputs)  # e.g. training data and data: the same
        try:
            return tool().run_flow(
                *inputs,
                config=config,
                task_runner=task_runner,
                autosave_dir=autosave_dir,
                strict=not allow_guesses,
            )
        except WorkflowValidationError as err:
            raise BatchError(f"{name}:\n{err}") from None
    many = tool.inputs[0].many  # e.g. Concatenate: a dict of tables
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

    return run_flow(tool.name, build, task_runner=task_runner, autosave_dir=autosave_dir)


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        prog="flimbatch",
        description="Imports FLIM data files and runs tools or workflows on them.",
    )
    parser.add_argument(
        "-i", "--input", nargs="+", required=True, help="data files or folders"
    )
    parser.add_argument(
        "-x", "--exclude", nargs="+", default=[], help="files not to import"
    )
    parser.add_argument("-o", "--output", required=True, help="folder for the results")
    parser.add_argument(
        "-c",
        "--settings",
        "--config",
        dest="settings",
        help="settings file (saved by the application; any version)",
    )
    parser.add_argument(
        "-r",
        "--run",
        action="append",
        default=[],
        metavar="NAME",
        help="tool or workflow to run on the imported data (repeatable)",
    )
    parser.add_argument(
        "--allow-guesses",
        action="store_true",
        help="workflows: use the closest columns for columns not in the data",
    )
    parser.add_argument(
        "-e",
        "--executor",
        default="LocalExecutor",
        help="LocalExecutor, LocalDaskExecutor or DaskExecutor",
    )
    parser.add_argument(
        "-a", "--execargs", default="", help="executor arguments, e.g. num_workers=4"
    )
    parser.add_argument(
        "--no-prefect-server",
        action="store_true",
        help="don't start a local Prefect server; flows use a temporary one",
    )
    parser.add_argument(
        "-l",
        "--log",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="logging level",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_arguments(argv)
    logging.basicConfig(
        level=args.log.upper(), format="%(levelname)s %(message)s", force=True
    )
    import flim.tools  # noqa: F401  (registers the tools)
    import flim.workflow  # noqa: F401  (registers the workflows)
    from flim.core.prefect_server import use_prefect_server
    from flim.core.tools import check_executor_available

    discover(TOOLS_GROUP)  # tools of other packages
    try:
        check_executor_available(args.executor)
        settings = load_settings(args.settings) if args.settings else AppSettings.default()
        os.makedirs(args.output, exist_ok=True)
        data = import_table(args.input, settings, exclude=args.exclude)
        path = os.path.join(args.output, IMPORTED)
        data.to_csv(path, sep="\t", index=False)
        logging.info(f"Saved {path}")
        execution = ExecutionOptions.from_legacy(args.executor, args.execargs)
        failed = []
        with use_prefect_server(start=not args.no_prefect_server):
            for name in args.run:
                run = run_tool(
                    name, data, settings, args.output, execution, args.allow_guesses
                )
                if run.failed or run.state != "completed":
                    failed.append(f"{name}: {', '.join(run.failed) or run.state}")
                logging.info(f"{name}: {run.state}; results in {run.autosave_dir}")
    except (BatchError, RuntimeError, OSError, ValueError) as err:
        print(f"flimbatch: {err}", file=sys.stderr)
        return 1
    if failed:
        print("flimbatch: failed tasks\n" + "\n".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
