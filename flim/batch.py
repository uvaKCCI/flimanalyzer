"""Batch mode: read data files and run tools or workflows on them without the GUI.

`flimbatch -i <files or folders> -o <folder> [-s settings.json] --run NAME ...`

1. Reads the settings file given with `-s` (any version, see `flim.core.settings`),
   else the defaults; the user settings file is not used, so batch results don't
   depend on settings changed in the GUI.
2. Reads each data file into a table, with `Source` (the file as a URI); nothing
   else is done to the data before the runs.
3. Runs each `--run`, in the order given (a tool, a code-defined workflow, or a
   workflow file by its name, path or file name) on the tables: a tool once per table
   (a tool that takes many tables, e.g. Concatenate, once on all), a workflow file as
   its steps say (each step once per table until a step joins them). A tool uses its
   settings from the settings file; a workflow file's steps carry their own. The
   results are saved in `<output>/<name>/`.

With `--dry-run` (or `FLIM_DRY_RUN=true`) nothing runs: the first rows of each file
are read and every run is checked against them; the first and the last line of the
output say that it is a dry run and what made it one. The exit code is 0 if every run completed without failed
tasks (with `--dry-run`: if no check found an error), 1 otherwise. wxPython is not
imported.
"""

import argparse
import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Callable, Optional, Sequence

from flim.core.execution import ExecutionOptions
from flim.core.paths import canonical_folder, folder_problem
from flim.core.registry import TOOLS_GROUP, discover, tools
from flim.core.schema import TableSchema
from flim.core import logs
from flim.core.cli import (
    add_file_options,
    add_log_option,
    add_settings_options,
    command_line_changes,
    log_level,
    settings_file,
)
from flim.core.reader import ReadSettings, read_tables
from flim.core.settings import AppSettings
from flim.core.settingsmgr import session_settings

if TYPE_CHECKING:
    import pandas as pd

    from flim.core.runner import FlowRun
    from flim.core.tool import Tool

logger = logging.getLogger(__name__)

DRY_RUN_ROWS = 20  # rows read of each file for --dry-run (column names and types)
DRY_RUN_VAR = "FLIM_DRY_RUN"  # true: a dry run, as --dry-run


class BatchError(Exception):
    """A batch step that cannot be done, with the reason for the user."""


def resolve_run(
    name: str,
    search_path: Sequence[str | os.PathLike] = (),
    warn: Callable[[str], None] = logger.warning,
) -> type["Tool"]:
    """Return the tool or workflow class of a `--run` argument.

    An argument that contains a folder separator or ends with `.json` is a workflow
    file, or a tool file (run as a workflow of one step): a path, or a file name in
    the search path. Any other argument is a
    registered name: a tool, a workflow defined in code, or a workflow file by the
    `name` in it.

    Args:
        name: The argument of `--run`.
        search_path: The folders searched for workflow files.
        warn: Called with each warning of the file's check, e.g. a tool file with
            `save: false`. Defaults to logging it.

    Returns:
        The class; for a workflow file, a workflow class that runs its steps.

    Raises:
        BatchError: If there is no such tool, workflow or file, or the file has
            errors.
    """
    from flim.core.workflowfile import (
        check_workflow_file,
        find_workflow_file,
        is_workflow_file,
        workflow_class,
    )

    if not is_workflow_file(name):
        if name not in tools:
            raise BatchError(
                f"No tool or workflow named '{name}' (a workflow file is given by its"
                " path, or by its file name ending in .json)"
            )
        return tools.get(name)
    try:
        path = find_workflow_file(name, search_path)
    except FileNotFoundError as err:
        raise BatchError(str(err)) from None
    check = check_workflow_file(path, tool_files=True)  # a tool file: one step
    if check.errors:
        raise BatchError(f"{path}:\n" + "\n".join(check.errors))
    for message in check.warnings:
        warn(message)
    return workflow_class(check.definition, path)


def file_run(
    tool: type["Tool"], settings: AppSettings
) -> tuple[type["Tool"], ReadSettings]:
    """Return the tool to run on the files' tables, and how the files are read.

    Import Tables reads with its own settings and runs the workflow they name; every
    other tool or workflow runs on the files read with Open Tables' settings.

    Args:
        tool: The tool or workflow of `--run`.
        settings: The session's settings (the `-s` file and the defaults).

    Returns:
        The tool or workflow, and the settings the files are read with.

    Raises:
        BatchError: If Import Tables' settings name no workflow, or one that is not
            found.
    """
    from flim.core.workflowfile import resolve_workflow
    from flim.tools.readers import ImportTables, TableReader

    if tool is not ImportTables:
        return tool, settings.tools.config(TableReader).read_settings()
    config = settings.tools.config(ImportTables)
    if not config.workflow:
        raise BatchError(
            "Import Tables: the settings name no workflow; set `workflow` in its"
            " section of the settings file, or run the workflow file with --run"
        )
    try:
        return resolve_workflow(config.workflow), config.read_settings()
    except ValueError as err:
        raise BatchError(f"Import Tables: {err}") from None


def read_settings(read: ReadSettings, exclude: Sequence[str] = ()) -> ReadSettings:
    """Return the read settings of a run with `-x` added to the files left out.

    Args:
        read: The read settings.
        exclude: The file names of `-x`.

    Returns:
        A copy of `read` whose `exclude` also has the names of `exclude`.
    """
    return read.model_copy(update={"exclude": list(read.exclude) + list(exclude)})


def check_run(
    tool: type["Tool"], tables: dict[str, "pd.DataFrame"], settings: AppSettings
) -> list[str]:
    """Check a run against the tables (or their first rows) without running it.

    A workflow file's steps are checked against the tables' columns. A tool that
    takes many tables is checked once on all of them, any other tool or workflow on
    each table. A tool (not a workflow) that needs more than one input table is an
    error.

    Args:
        tool: The tool or workflow class.
        tables: The tables by name.
        settings: The session's settings; a tool or workflow is checked with its
            settings from them.

    Returns:
        The errors, each with the tool and the table; empty if there are none.
    """
    from flim.core.workflow import Workflow
    from flim.core.workflowfile import check_steps

    schemas = {name: TableSchema.from_frame(t) for name, t in tables.items()}
    definition = getattr(tool, "definition", None)
    if definition is not None:
        return check_steps(definition, schemas)
    required = [spec for spec in tool.inputs if not spec.optional]
    if len(required) > 1 and not issubclass(tool, Workflow):
        return [f"{tool.name} needs {len(required)} input tables; use a workflow file"]
    config = settings.tools.config(tool)
    if tool.inputs and tool.inputs[0].many:
        checks = [("all tables", [schemas])]
    else:
        checks = [(name, [schema] * max(1, len(tool.inputs))) for name, schema in schemas.items()]
    errors = []
    for name, inputs in checks:
        for issue in tool.validate(config, inputs):
            if issue.severity == "error":
                where = f"{issue.field}: " if issue.field else ""
                errors.append(f"{tool.name} on {name}: {where}{issue.message}")
    return errors


def run_on_tables(
    tool: type["Tool"],
    tables: dict[str, "pd.DataFrame"],
    settings: AppSettings,
    output_dir: str | os.PathLike,
    execution: Optional[ExecutionOptions] = None,
    strict: bool = True,
    settings_record: Sequence[str] = (),
) -> list["FlowRun"]:
    """Run a tool or workflow on the tables read from the files.

    A workflow file runs as its steps say. A tool runs once per table (one that takes
    many tables, e.g. Concatenate, once on all of them), with its settings from
    `settings`; a code-defined workflow runs once per table. Results are saved in
    `<output_dir>/<name>/`.

    Args:
        tool: The tool or workflow class.
        tables: The tables by name.
        settings: The app settings (the tools' settings and save formats).
        output_dir: The results folder.
        execution: The executor; None for the default `ExecutionOptions`.
        strict: Code-defined workflows: whether columns not in the data are errors.
            Defaults to True.
        settings_record: The settings files, for the run summary.

    Returns:
        The runs: one per table for a code-defined workflow, else one.

    Raises:
        BatchError: If the run's settings don't fit the tables (see `check_run`), or
            a code-defined workflow's config has errors for a table.
    """
    from flim.core.runner import run_flow
    from flim.core.workflow import Workflow, WorkflowValidationError

    errors = check_run(tool, tables, settings)
    if errors:
        raise BatchError(f"{tool.name}:\n" + "\n".join(errors))
    execution = execution or ExecutionOptions()
    autosave_dir = Path(output_dir) / tool.name
    definition = getattr(tool, "definition", None)
    if definition is not None:  # a workflow file
        return [
            tool().run_flow(
                tables,
                task_runner=execution.task_runner(),
                autosave_dir=autosave_dir,  # the steps' `save` decides what is written
                settings_record=settings_record,
                save_formats=definition.output.formats,
            )
        ]
    config = settings.tools.config(tool)
    entry = settings.tools.entry(tool)
    formats = entry.output.formats if entry else []  # the tool's save formats
    if issubclass(tool, Workflow):
        runs = []
        for name, table in tables.items():
            try:
                runs.append(
                    tool().run_flow(
                        *[table] * len(tool.inputs),
                        config=config,
                        task_runner=execution.task_runner(),
                        autosave_dir=autosave_dir / name if len(tables) > 1 else autosave_dir,
                        strict=strict,
                        settings_record=settings_record,
                        save_formats=formats,
                    )
                )
            except WorkflowValidationError as err:
                raise BatchError(f"{tool.name} on {name}:\n{err}") from None
        return runs

    def build() -> None:
        if tool.inputs and tool.inputs[0].many:
            for each in tool().map_configs(config):
                tool()(dict(tables), config=each, task_tags=tool.name)
            return
        for name, table in tables.items():
            tags = [name] if len(tables) > 1 else []
            for each in tool().map_configs(config):
                tool()(table, config=each, task_tags=tags + [tool.name])

    return [
        run_flow(
            tool.name,
            build,
            task_runner=execution.task_runner(),
            autosave_dir=autosave_dir,
            settings_record=settings_record,
            save_formats=formats,
        )
    ]


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser of flimbatch.

    Returns:
        The parser, with the shared options of the files, the runs and the workflow
        folders, of the app settings and of the log level (`flim.core.cli`), and
        `--dry-run`.
    """
    parser = argparse.ArgumentParser(
        prog="flimbatch",
        description="Reads FLIM data files and runs tools or workflows on them.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    add_file_options(parser, input_required=True)
    add_settings_options(parser)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read the first rows of the files, check the runs against them, run\n"
        "nothing; also FLIM_DRY_RUN=true",
    )
    parser.add_argument("--allow-guesses", action="store_true", help=argparse.SUPPRESS)
    add_log_option(parser)
    return parser


def parse_arguments(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line of flimbatch.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The parsed arguments.
    """
    return build_parser().parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run flimbatch: read the data files and run the tools and workflows on them.

    The steps are described in the module docstring. Errors of the settings, the
    files or the runs are printed to standard error.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The exit code: 0 if every run completed without failed tasks (with
        `--dry-run`: if no check found an error), 1 otherwise.

    Raises:
        SystemExit: If the arguments are invalid, or no `--run` is given, or `-o`
            is missing without `--dry-run`, or `FLIM_LOG_LEVEL` or `FLIM_DRY_RUN` is
            invalid (exit code 2, from `argparse`).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.run:
        parser.error(
            "give --run NAME (e.g. --run Import to join the files"
            " into one table with the FLIM features)"
        )
    try:
        level = log_level(args)
        dry_run = dry_run_source(args)
    except ValueError as err:
        parser.error(str(err))
    args.dry_run = dry_run is not None
    if not args.output and not args.dry_run:
        parser.error("the following arguments are required: -o/--output")
    # the console as before; the log file opens once the output folder is known
    memory = logs.begin(level)
    logging.getLogger().addHandler(logs.console_handler(level))
    if dry_run:  # first and last line: a variable left set by mistake is seen
        print(f"flimbatch: dry run (set by {dry_run}): nothing is run", file=sys.stderr)
    try:
        return _session(args, memory)
    finally:
        if dry_run:
            sys.stdout.flush()  # the report first: this is the last line
            print(f"flimbatch: dry run (set by {dry_run}): nothing was run", file=sys.stderr)


def dry_run_source(args: argparse.Namespace) -> Optional[str]:
    """Return what makes this a dry run: `--dry-run`, `FLIM_DRY_RUN`, or None.

    Args:
        args: The parsed arguments.

    Returns:
        `--dry-run` if given, else `FLIM_DRY_RUN` if it is set to true, else None.

    Raises:
        ValueError: If `FLIM_DRY_RUN` is not a boolean (e.g. `true`, `false`, `1`,
            `0`).
    """
    from pydantic import TypeAdapter, ValidationError

    if args.dry_run:
        return "--dry-run"
    value = os.environ.get(DRY_RUN_VAR, "").strip()
    if not value:
        return None
    try:
        return DRY_RUN_VAR if TypeAdapter(bool).validate_python(value) else None
    except ValidationError:
        raise ValueError(
            f"Invalid environment variable: {DRY_RUN_VAR}={value}; use true or false"
        ) from None


def _session(args: argparse.Namespace, memory: "logging.Handler") -> int:
    """Read the settings and the files, and run or check the runs (see `main`).

    Args:
        args: The parsed arguments; `dry_run` also set by `FLIM_DRY_RUN`.
        memory: The handler that keeps the log records until the log file opens.

    Returns:
        The exit code of `main`.
    """
    import flim.tools  # noqa: F401  (registers the tools)
    import flim.workflow  # noqa: F401  (registers the workflows)
    from flim.core.prefect_server import checked_prefect_server, use_prefect_server
    from flim.core.workflowfile import register_workflow_files, workflow_path

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
        if getattr(manager.check, "import_workflow", None):
            print(
                "flimbatch: warning: the settings file's import settings (FLIMAnalyzer"
                " 0.6) are not used; to keep them, open the file in the GUI (File >"
                " Import Settings...) and save them as a workflow file",
                file=sys.stderr,
            )
        # from -w or FLIM_WORKFLOW_PATH only: a settings file doesn't decide which
        # workflow file a name refers to
        search_path = workflow_path(folders=args.workflow_path)
        for message in register_workflow_files(search_path):
            print(f"flimbatch: warning: {message}", file=sys.stderr)
        runs = [resolve_run(n, search_path, warn=_warn) for n in args.run]
        runs = [file_run(tool, settings) for tool in runs]
        if args.dry_run:
            return _dry_run(runs, args, settings)
        execution = ExecutionOptions(
            execution=settings.execution, server_timeout=settings.server_timeout
        )
        execution.check_available()
        output = canonical_folder(args.output)
        if problem := folder_problem(output):
            raise BatchError(f"--output: {problem}")
        os.makedirs(output, exist_ok=True)
        # the log goes with the results, unless a log folder is set
        log_dir = settings.log.dir.expanduser() if settings.log.dir else output
        log_file, notice = logs.open_log_file("flimbatch", log_dir, memory)
        if notice:
            print(f"flimbatch: warning: {notice}", file=sys.stderr)
        logger.info(f"Log file: {log_file}")
        strict = True if settings.strict is None else settings.strict
        failed = []
        with use_prefect_server(start=settings.prefect_server, timeout=settings.server_timeout):
            for tool, read in runs:
                tables = _read(args.input, read_settings(read, args.exclude))
                with checked_prefect_server():
                    results = run_on_tables(
                        tool, tables, settings, output, execution, strict, manager.record()
                    )
                for run in results:
                    if run.failed or run.state != "completed":
                        failed.append(f"{tool.name}: {', '.join(run.failed) or run.state}")
                    logger.info(f"{tool.name}: {run.state}; results in {run.autosave_dir}")
    except (BatchError, RuntimeError, OSError, ValueError) as err:  # incl. FileNotFoundError
        print(f"flimbatch: {err}", file=sys.stderr)
        return 1
    if failed:
        print("flimbatch: failed tasks\n" + "\n".join(failed), file=sys.stderr)
        return 1
    return 0


def _warn(message: str) -> None:
    """Print a warning to standard error, as `flimbatch: warning: <message>`."""
    print(f"flimbatch: warning: {message}", file=sys.stderr)


def _read(
    paths: Sequence[str | os.PathLike],
    settings: ReadSettings,
    nrows: Optional[int] = None,
) -> dict[str, "pd.DataFrame"]:
    """Read the data files; raises `BatchError` if none could be read."""
    reading = read_tables(paths, settings, nrows=nrows)
    for path, reason in reading.skipped.items():
        print(f"flimbatch: warning: not read: {path}: {reason}", file=sys.stderr)
    for message in reading.warnings:
        print(f"flimbatch: warning: {message}", file=sys.stderr)
    if not reading.tables:
        raise BatchError("No data files could be read")
    logger.info(f"Read {len(reading.tables)} file(s)")
    return reading.tables


def _dry_run(
    runs: Sequence[tuple[type["Tool"], ReadSettings]],
    args: argparse.Namespace,
    settings: AppSettings,
) -> int:
    """Check every run against the first rows of the files; report; run nothing."""
    errors = 0
    for tool, read in runs:
        tables = _read(args.input, read_settings(read, args.exclude), nrows=DRY_RUN_ROWS)
        problems = check_run(tool, tables, settings)
        if problems:
            errors += len(problems)
            print(f"{tool.name}: {len(problems)} problem(s)", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
        else:
            print(f"{tool.name}: OK ({len(tables)} file(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
