"""Command-line options of the app settings, shared by flimanalyzer and flimbatch."""

import argparse
from typing import Optional

from pydantic import TypeAdapter, ValidationError

from flim.core.execution import ExecutorSettings

# executor names before 0.7.0 (deprecated)
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


def add_settings_options(parser: argparse.ArgumentParser, *, output_required=False) -> None:
    """Add the options that set app settings to an argument parser.

    Args:
        parser: The argument parser of flimanalyzer or flimbatch. Its formatter must
            keep line breaks in help texts (`argparse.RawTextHelpFormatter`) for the
            help of `-e` to be readable.
        output_required: Whether `-o` is required.
    """
    parser.add_argument(
        "-s",
        "--settings",
        metavar="FILE",
        help="app settings file: a path, or a name in the app settings folders",
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
        "--no-prefect-server",
        action="store_true",
        help="don't start a local Prefect server; flows use a temporary one",
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


def settings_file(args) -> tuple[Optional[str], list[str]]:
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
    return args.config, ["-c/--config is deprecated; use -s/--settings"]


def _values(text: str) -> dict:
    """Parse `KEY=VALUE,...`; integer values become int."""
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


def executor_settings(spec: Optional[str], execargs: Optional[str] = None) -> tuple[dict, list[str]]:
    """Parse the argument of `-e` (and the deprecated `-a`) into executor settings.

    `spec` is `NAME[:KEY=VALUE,...]`. The old names `LocalExecutor`,
    `LocalDaskExecutor` and `DaskExecutor`, and the keys of `-a` (`num_workers` for
    `workers`), are accepted with a deprecation message and work as before 0.7.0:
    `DaskExecutor` without an address becomes `dask-local`, as it started a local
    cluster; `workers` that is not a positive integer, and keys the local executor
    does not use, are ignored with a message.

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
        # the deprecated forms keep their 0.6 behaviour: invalid or unknown values
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
            "the -e names LocalExecutor, LocalDaskExecutor, DaskExecutor and -a are"
            f" deprecated; use -e {name}{':' + keys if keys else ''}",
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


def command_line_changes(args) -> tuple[dict, list[str]]:
    """Return the settings set on the command line, as sections to apply.

    Only options that were given are returned. `--cache-dir` gives the partial section
    `{"cache": {"dir": ...}}`.

    Args:
        args: The parsed arguments (`add_settings_options`; `allow_guesses` of
            flimbatch's deprecated `--allow-guesses` if present).

    Returns:
        The sections to apply; and the deprecation messages.

    Raises:
        ValueError: If an option has an invalid value (see `executor_settings`).
    """
    changes, notes = {}, []
    if args.output is not None:
        changes["results_dir"] = args.output
    if args.executor is not None or args.execargs:
        changes["execution"], notes = executor_settings(args.executor, args.execargs)
    if args.no_prefect_server:
        changes["prefect_server"] = False
    if args.log_dir is not None:
        changes["log_dir"] = args.log_dir
    if args.cache_dir is not None:
        changes["cache"] = {"dir": args.cache_dir}
    if getattr(args, "allow_guesses", False):
        notes.append("--allow-guesses is deprecated; use --no-strict")
        if args.strict is None:
            args.strict = False
    if args.strict is not None:
        changes["strict"] = args.strict
    return changes, notes
