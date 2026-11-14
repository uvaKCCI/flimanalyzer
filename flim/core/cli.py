"""Command-line options shared by flimanalyzer and flimbatch: files, settings, log level."""

import argparse
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

from flim.core.execution import ExecutorSettings

# deprecated executor names and the names that replace them
OLD_EXECUTORS = {
    "LocalExecutor": "local",
    "LocalDaskExecutor": "dask-local",
    "DaskExecutor": "dask",
}
# the keys of each executor; dask executors take other keys as further Dask arguments
EXECUTOR_KEYS = {
    "local": ("workers",),
    "dask-local": ("workers", "scheduler"),
    "dask": ("address",),
}
EXECUTOR_HELP = """where and how tasks run:
  local[:workers=N]  threads in this process (default)
  dask-local[:workers=N,scheduler=threads|processes,KEY=VALUE...]
                     a Dask cluster on this machine
  dask:address=URL[,KEY=VALUE...]
                     an existing Dask cluster
other keys are further Dask arguments, e.g. threads_per_worker=2"""
LOG_LEVELS = ["debug", "info", "warning", "error", "critical"]


def add_file_options(
    parser: argparse.ArgumentParser,
    *,
    input_required: bool = False,
    input_help: str = "data files or folders",
    run_help: str = "",
) -> None:
    """Add the options of the data files and the workflow folders to an argument parser.

    `-i`, `-x` and `-w` take several values after one use, and can be repeated:
    `-i a.txt -i b.txt` and `-i a.txt b.txt` give both files.

    Args:
        parser: The argument parser of flimanalyzer or flimbatch.
        input_required: Whether `-i` is required. Defaults to False.
        input_help: The help text of `-i`.
        run_help: Text added to the help of `--run`, e.g. what the program shows first.
    """
    parser.add_argument(
        "-i", "--input", nargs="+", action="extend", required=input_required,
        metavar="PATH", help=input_help + " (repeatable)",
    )  # fmt: skip
    parser.add_argument(
        "-x", "--exclude", nargs="+", action="extend", default=[], metavar="NAME",
        help="files not to read, by name (repeatable)",
    )  # fmt: skip
    parser.add_argument(
        "-r", "--run", action="append", default=[], metavar="NAME",
        help="tool or workflow to run on the files (repeatable; runs in the order given):\n"
        "a registered name, or a workflow file: a path, or a file name ending in .json\n"
        "in the workflow search path" + (f";\n{run_help}" if run_help else ""),
    )  # fmt: skip
    parser.add_argument(
        "-w", "--workflow-path", nargs="+", action="extend", default=[], metavar="DIR",
        help="folders searched for workflow files, before FLIM_WORKFLOW_PATH\n"
        "(repeatable)",
    )  # fmt: skip


def add_log_option(parser: argparse.ArgumentParser) -> None:
    """Add the log level option, `-l`/`--log-level` (also `--log`), to an argument parser.

    Args:
        parser: The argument parser of flimanalyzer or flimbatch.
    """
    parser.add_argument(
        "-l", "--log-level", "--log", dest="log_level", choices=LOG_LEVELS, default=None,
        help="logging level (default: info)",
    )  # fmt: skip


def log_level(args: argparse.Namespace) -> str:
    """Return the log level given with `-l`, upper case; `INFO` if none is given.

    Args:
        args: The parsed arguments (`add_log_option`).

    Returns:
        The log level, e.g. `INFO`.
    """
    return (args.log_level or "info").upper()


def add_settings_options(
    parser: argparse.ArgumentParser, *, output_required: bool = False
) -> None:
    """Add the options that set app settings to an argument parser.

    Args:
        parser: The argument parser of flimanalyzer or flimbatch. Its formatter must
            keep line breaks in help texts (`argparse.RawTextHelpFormatter`) for the
            help of `-e` to be readable.
        output_required: Whether `-o` is required. Defaults to False.
    """
    parser.add_argument(
        "-s",
        "--settings",
        metavar="FILE",
        help="app settings file: a path, or a name in the app settings search path",
    )
    parser.add_argument("-c", "--config", metavar="FILE", help=argparse.SUPPRESS)
    parser.add_argument(
        "-o", "--output", metavar="DIR", required=output_required, help="results folder"
    )
    parser.add_argument(
        "-e", "--executor", metavar="NAME[:KEY=VALUE,...]", help=EXECUTOR_HELP
    )
    parser.add_argument("-a", "--execargs", help=argparse.SUPPRESS)
    parser.add_argument(
        "--prefect-server",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="use or start a local Prefect server (--prefect-server), or a temporary"
        " one\nfor each run (--no-prefect-server)",
    )
    parser.add_argument("--log-dir", metavar="DIR", help="folder of the log files")
    parser.add_argument("--cache-dir", metavar="DIR", help="cache folder")
    parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="workflows: columns not in the data are errors (--strict) or replaced by"
        " the closest match (--no-strict)",
    )


def settings_file(args: argparse.Namespace) -> tuple[Optional[str], list[str]]:
    """Return the app settings file given with `-s`, or with the deprecated `-c`.

    Args:
        args: The parsed arguments.

    Returns:
        The file name or path, or None; and the deprecation messages.

    Raises:
        ValueError: If both `-s` and `-c` are given.
    """
    if args.config is None:
        return args.settings, []
    if args.settings is not None:
        raise ValueError("-c/--config and -s/--settings: give only -s")
    return args.config, ["-c/--config is deprecated and is removed in 0.8.0; use -s/--settings"]


def _values(text: str) -> dict[str, int | str]:
    """Parse `KEY=VALUE,...`; integer values become int; raise ValueError otherwise."""
    values = {}
    for item in filter(None, (part.strip() for part in text.split(","))):
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"'{item}' is not KEY=VALUE")
        value = value.strip()
        try:
            values[key.strip()] = int(value)
        except ValueError:
            values[key.strip()] = value
    return values


def executor_settings(
    spec: Optional[str], execargs: Optional[str] = None
) -> tuple[dict[str, Any], list[str]]:
    """Parse the argument of `-e` (and the deprecated `-a`) into executor settings.

    `spec` is `NAME[:KEY=VALUE,...]`. The old names `LocalExecutor`,
    `LocalDaskExecutor` and `DaskExecutor`, and the keys of `-a` (`num_workers` for
    `workers`), are accepted with a deprecation message and keep their earlier
    behaviour: `DaskExecutor` without an address becomes `dask-local`, as it started
    a local cluster; `workers` that is not a positive integer, and keys the local
    executor does not use, are ignored with a message.

    Args:
        spec: The argument of `-e`; None for the default executor.
        execargs: The argument of the deprecated `-a`.

    Returns:
        The executor settings as a dict, validated; and the deprecation messages.

    Raises:
        ValueError: If the name is unknown, a key does not belong to the executor, a
            required key is missing or a value is invalid; the message names them.
    """
    notes = []
    name, _, rest = (spec or "local").partition(":")
    values = _values(rest)
    old = name in OLD_EXECUTORS
    if old:
        name = OLD_EXECUTORS[name]
    if execargs:
        extra = _values(execargs)
        if "num_workers" in extra:
            extra["workers"] = extra.pop("num_workers")
        values.update(extra)
    if name == "dask" and "address" not in values:
        if not old:
            raise ValueError("-e dask needs an address, e.g. -e dask:address=tcp://host:8786")
        name = "dask-local"
    if name not in EXECUTOR_KEYS:
        raise ValueError(f"unknown executor '{name}': use local, dask-local or dask")
    known = {k: v for k, v in values.items() if k in EXECUTOR_KEYS[name]}
    other = {k: v for k, v in values.items() if k not in EXECUTOR_KEYS[name]}
    if old or execargs:
        # the deprecated forms keep their earlier behaviour: invalid or unknown values
        # are ignored, not errors
        workers = known.get("workers")
        if workers is not None and not (isinstance(workers, int) and workers >= 1):
            known.pop("workers")
            notes.append(f"ignored workers={workers}: not a positive integer")
        if other and name == "local":
            notes.append(f"ignored {', '.join(other)}: not used by the local executor")
            other = {}
    if other and name == "local":
        keys = ", ".join(EXECUTOR_KEYS["local"])
        raise ValueError(f"-e local has no {', '.join(other)}; its keys: {keys}")
    settings = {"executor": name, **known, **({"kwargs": other} if other else {})}
    if old or execargs:
        keys = ",".join(f"{k}={v}" for k, v in {**known, **other}.items())
        notes.insert(
            0,
            "the -e names LocalExecutor, LocalDaskExecutor, DaskExecutor (removed in"
            " 1.0.0) and -a (removed in 0.8.0) are deprecated;"
            f" use -e {name}{':' + keys if keys else ''}",
        )
    try:
        validated = TypeAdapter(ExecutorSettings).validate_python(settings)
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'][1:]) or 'executor'}: {e['msg']}"
            for e in err.errors()
        )
        raise ValueError(f"-e {spec}: {problems}") from None
    return validated.model_dump(mode="json"), notes


def command_line_changes(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    """Return the settings set on the command line, as sections to apply.

    Only options that were given are returned. `--log-dir` and `--cache-dir` give the
    partial sections `{"log": {"dir": ...}}` and `{"cache": {"dir": ...}}`.

    Args:
        args: The parsed arguments (`add_settings_options`; `allow_guesses` of
            flimbatch's deprecated `--allow-guesses` if present).

    Returns:
        The sections to apply; and the deprecation messages.

    Raises:
        ValueError: If an option has an invalid value (see `executor_settings`), or
            `--allow-guesses` is given with `--strict` or `--no-strict`.
    """
    changes, notes = {}, []
    if args.output is not None:
        changes["results_dir"] = args.output
    if args.executor is not None or args.execargs:
        changes["execution"], notes = executor_settings(args.executor, args.execargs)
    if args.prefect_server is not None:
        changes["prefect_server"] = args.prefect_server
    if args.log_dir is not None:
        changes["log"] = {"dir": args.log_dir}
    if args.cache_dir is not None:
        changes["cache"] = {"dir": args.cache_dir}
    if getattr(args, "allow_guesses", False):
        if args.strict is not None:
            raise ValueError("--allow-guesses and --strict/--no-strict: give only --no-strict")
        notes.append("--allow-guesses is deprecated and is removed in 0.8.0; use --no-strict")
        args.strict = False
    if args.strict is not None:
        changes["strict"] = args.strict
    return changes, notes
