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
   results are saved in one folder per call, `<output>/<date and time>/`, with a
   folder per `--run`, `run-<n>`, holding its run summary and a folder per step,
   `<id>-<tool>` (e.g. `01-Summarize`), then per table and part.

With `--dry-run` (or `FLIM_DRY_RUN=true`) nothing runs: the first rows of each file
are read and every run is validated against them; the first and the last line of the
output say that it is a dry run and what made it one. The exit code is 0 if every run completed without failed
tasks (with `--dry-run`: if the validation found no error), 1 otherwise. wxPython is not
imported.
"""

import argparse
import datetime
import logging
import os
import sys
from typing import TYPE_CHECKING, Optional, Sequence

import matplotlib

from flim.core.execution import ExecutionOptions
from flim.core.paths import (
    canonical_folder,
    folder_problem,
    set_char_replacements,
    unique_run_folder,
)
from flim.core.registry import TOOLS_GROUP, discover
from flim.core.workflowfile import parse_overrides
from flim.core import logs
from flim.core.batchrun import (
    BatchError,
    validate_run,
    file_run,
    ignored_settings,
    read_settings,
    resolve_run,
    run_on_tables,
    settings_file_issues,
)
from flim.core.cli import (
    DRY_RUN_VAR,
    add_file_options,
    add_log_option,
    add_settings_options,
    command_line_changes,
    flag_source,
    log_level,
    settings_file,
)
from flim.core.reader import ReadSettings, read_tables
from flim.core.settings import AppSettings
from flim.core.settingsmgr import session_settings

if TYPE_CHECKING:
    import pandas as pd

    from flim.core.tool import Tool

logger = logging.getLogger(__name__)

DRY_RUN_ROWS = 20  # rows read of each file for --dry-run (column names and types)
CALL_LOG = "flimbatch.log"  # a call's log, in its results folder


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
        help="read the first rows of the files, validate the runs against them, run\n"
        "nothing; also FLIM_DRY_RUN=true",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="GROUP.FIELD=VALUE",
        help="set a field for every step of the runs, over the files' settings, e.g.\n"
        "output.save=true, output.formats=table:csv,plot:svg,\n"
        "processing.strict=false, processing.skippable.features=some; repeatable",
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
        `--dry-run`: if the validation found no error), 1 otherwise.

    Raises:
        SystemExit: If the arguments are invalid, or no `--run` is given, or `-o`
            is missing without `--dry-run`, or `FLIM_LOG_LEVEL` or `FLIM_DRY_RUN` is
            invalid (exit code 2, from `argparse`).
    """
    # tools draw their figures in worker threads, into files: a backend without
    # windows (macOS' default backend fails outside the main thread)
    matplotlib.use("Agg")
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
        # --allow-guesses first: an explicit --override of processing.strict wins
        given = (["processing.strict=false"] if args.allow_guesses else []) + args.override
        args.overrides = parse_overrides(given)
    except ValueError as err:
        parser.error(str(err))
    args.dry_run = dry_run is not None
    if not args.output:  # also for a dry run: it validates the folder, and logs there
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
        See `flag_source`.

    Raises:
        ValueError: If `FLIM_DRY_RUN` is not a boolean.
    """
    return flag_source(args.dry_run, "--dry-run", DRY_RUN_VAR)


def _session(args: argparse.Namespace, memory: "logging.Handler") -> int:
    """Read the settings and the files, and run or validate the runs (see `main`).

    Args:
        args: The parsed arguments; `dry_run` also set by `FLIM_DRY_RUN`.
        memory: The handler that keeps the log records until the log file opens.

    Returns:
        The exit code of `main`.
    """
    import flim.tools  # noqa: F401  (registers the tools)
    import flim.workflow  # noqa: F401  (registers the workflows)
    from flim.core.prefect_server import checked_prefect_server, use_prefect_server
    from flim.core.workflowfile import register_workflow_files, save_issues, workflow_path

    discover(TOOLS_GROUP)  # registers the tools of other installed packages
    try:
        name, notes = settings_file(args)
        changes, more = command_line_changes(args)
        if args.allow_guesses:
            notes.append(
                "--allow-guesses is deprecated and is removed in 0.8.0; use"
                " --override processing.strict=false"
            )
        for note in notes + more:
            print(f"flimbatch: warning: {note}", file=sys.stderr)
        # no user settings file: batch results don't depend on settings changed in the GUI
        # every setting of the file must be usable: results don't depend on ignored
        # settings or on which tools are installed
        # the built-in workflow files first: a settings file may have their sections
        register_workflow_files()
        manager = session_settings(name, changes, complete=True)
        settings = manager.settings
        for notice in manager.notices:  # e.g. keys of the user settings file only
            _warn(notice)
        set_char_replacements(settings.char_replacements)  # file and folder names
        if getattr(manager.validation, "import_workflow", None):
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
        warnings, errors = settings_file_issues(runs, settings, manager.source)
        for message in warnings:
            _warn(message)
        if errors:
            raise BatchError("\n".join(errors))
        output = canonical_folder(args.output) if args.output else None
        for message in ignored_settings(runs, settings, output):
            _warn(message)
        runs = [file_run(tool, settings) for tool in runs]
        if not args.overrides.save:  # results a workflow file's run would not keep
            for tool, _ in runs:
                definition = getattr(tool, "definition", None)
                for message in save_issues(definition)[0] if definition is not None else []:
                    _warn(message)
        if args.dry_run:
            return _dry_run(runs, args, settings, memory)
        execution = ExecutionOptions(
            execution=settings.execution, server_timeout=settings.server_timeout
        )
        execution.check_available()
        output = canonical_folder(args.output)
        if problem := folder_problem(output):
            raise BatchError(f"--output: {problem}")
        os.makedirs(output, exist_ok=True)
        # one folder per call, named after its start; a folder per --run inside
        start = datetime.datetime.now()
        call_dir = unique_run_folder(output, start.strftime("%Y-%m-%d_%H-%M-%S"))
        # the call's log goes with its results, unless a log folder is set (there it
        # is named after the call's start and the process, the folder being shared)
        if settings.log.dir:
            log_file, notice = logs.open_log_file(
                "flimbatch", settings.log.dir.expanduser(), memory, start=start
            )
        else:
            log_file, notice = logs.open_log_file(
                "flimbatch", call_dir, memory, start=start, name=CALL_LOG
            )
        if notice:
            print(f"flimbatch: warning: {notice}", file=sys.stderr)
        logger.info(f"Log file: {log_file}")
        logger.info(f"Results: {call_dir}")
        failed = []
        with (
            use_prefect_server(start=settings.prefect_server, timeout=settings.server_timeout),
            execution.started() as (execution, note),  # dask-local: one cluster per call
        ):
            for number, (tool, read) in enumerate(runs, 1):
                tables = _read(args.input, read_settings(read, args.exclude))
                with checked_prefect_server():
                    run = run_on_tables(
                        tool, tables, settings, call_dir / f"run-{number}", execution,
                        args.overrides, manager.record(), notes=[note] if note else [],
                    )  # fmt: skip
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
    memory: Optional["logging.Handler"] = None,
) -> int:
    """Validate the environment and every run against the first rows of the files; run nothing.

    The environment: the output folder (reachable and writable; the dry run's log is
    written there, or into the log folder setting), the executor (its packages, and a
    Dask cluster answering within `server_timeout`) and the Prefect server (see
    `flim.core.prefect_server.server_status`). Each check that waits logs what it
    checks first.

    Args:
        runs: The tools and workflows of `--run`, and how their files are read.
        args: The parsed arguments.
        settings: The session's settings.
        memory: The handler that keeps the log records until the log file opens; None
            for no log file.

    Returns:
        0 if the validation found no problem, else 1.
    """
    from flim.core.prefect_server import server_status

    errors = 0

    def report(what: str, problem: Optional[str], found: str = "OK") -> None:
        nonlocal errors
        if problem:
            errors += 1
            print(f"{what}: {problem}", file=sys.stderr)
        else:
            print(f"{what}: {found}")

    output = canonical_folder(args.output)
    problem = folder_problem(output)
    report(f"Output folder {output}", problem)
    if memory is not None and (settings.log.dir or not problem):
        if not settings.log.dir:
            os.makedirs(output, exist_ok=True)
        folder = settings.log.dir.expanduser() if settings.log.dir else output
        log_file, notice = logs.open_log_file("flimbatch", folder, memory)
        if notice:
            _warn(notice)
        logger.info(f"Log file: {log_file}")
    execution = ExecutionOptions(execution=settings.execution, server_timeout=settings.server_timeout)
    name = settings.execution.executor
    try:
        execution.check_available()
        if name == "dask":
            logger.info(
                f"Checking the Dask cluster at {settings.execution.address}"
                f" (timeout {settings.server_timeout:g} s)"
            )
        problem = execution.check_cluster()
    except RuntimeError as err:
        problem = str(err)
    report(f"Executor {name}", problem)
    if settings.prefect_server:
        logger.info(f"Checking the Prefect server (timeout {settings.server_timeout:g} s)")
    ok, found = server_status(start=settings.prefect_server, timeout=settings.server_timeout)
    report("Prefect server", None if ok else found, found)
    for tool, read in runs:
        tables = _read(args.input, read_settings(read, args.exclude), nrows=DRY_RUN_ROWS)
        problems = validate_run(tool, tables, settings, args.overrides)
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
