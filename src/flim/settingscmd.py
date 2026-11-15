"""The flimsettings command: lists, shows and validates settings without the GUI.

`flimsettings OBJECT ACTION`, one action per call:

- `tool`: `--list` (tools by name, and tool files in the workflow search path),
  `--show FILE` (prints a tool file), `--validate FILE` (validates a tool file).
- `workflow`: `--list` (workflows defined in code, and workflow files),
  `--show FILE` (prints a workflow file), `--validate FILE` (validates a workflow file).

A FILE is a path, or a file name in the workflow search path; a file of another kind
is an error. `--show` only reads.
- `app`: `--list` (the app settings files in the search path), `--show` (the app
  settings of flimanalyzer and of flimbatch, and where each value comes from), `--validate FILE`
  (an app settings file).
- `user`: `--show` (the user settings file).
- `env`: `--list` (the `FLIM_*` variables FLIMAnalyzer reads), `--show` (those that
  are set, with unknown names and invalid values).

The output goes to standard output, and problems go to standard error. The exit code is 1 if a validation finds a problem, 2 for
invalid arguments, 0 otherwise. Only `FLIM_*` variables are shown, never others
(e.g. Prefect's). wxPython is not imported.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

from flim.core.batchrun import BatchError
from flim.core.cli import DRY_RUN_VAR, LOG_LEVEL_VAR, LOG_LEVELS, SAVE_ALL_VAR, flag_source
from flim.core.registry import TOOLS_GROUP, discover, tools
from flim.core.settingsmgr import (
    APP_SETTINGS_PATH_VAR,
    ENV_NAMES,
    OPTION_NAMES,
    USER_SETTINGS_VAR,
    UserSettingsFile,
    app_settings_path,
    environment_changes,
    list_app_settings,
    session_settings,
    user_settings_path,
)
from flim.core.workflowfile import WORKFLOW_PATH_VAR

if TYPE_CHECKING:
    from flim.core.tool import Tool

PROG = "flimsettings"
GUI, BATCH, SETTINGS = "flimanalyzer", "flimbatch", "flimsettings"

# the FLIM_* variables: what each sets and which commands read it
ENV_VARIABLES = {
    ENV_NAMES["results_dir"]: (f"results folder ({OPTION_NAMES['results_dir']})", [GUI]),
    ENV_NAMES["execution"]: (
        "executor as JSON, or its fields as FLIM_EXECUTION__<FIELD>, e.g."
        f" FLIM_EXECUTION__EXECUTOR=dask-local ({OPTION_NAMES['execution']})",
        [GUI, BATCH],
    ),
    ENV_NAMES["prefect_server"]: (
        f"use or start a local Prefect server ({OPTION_NAMES['prefect_server']})",
        [GUI, BATCH],
    ),
    ENV_NAMES["server_timeout"]: (
        "seconds to wait for Prefect server responses (and Dask cluster responses, if"
        f" used) ({OPTION_NAMES['server_timeout']})",
        [GUI, BATCH],
    ),
    ENV_NAMES["log"]: (f"folder of the log files ({OPTION_NAMES['log']})", [GUI, BATCH]),
    ENV_NAMES["cache"]: (f"cache folder ({OPTION_NAMES['cache']})", [GUI, BATCH]),
    ENV_NAMES["strict"]: (
        f"workflows: columns not in the data are errors ({OPTION_NAMES['strict']})",
        [GUI, BATCH],
    ),
    LOG_LEVEL_VAR: (f"log level: {', '.join(LOG_LEVELS)} (-l)", [GUI, BATCH]),
    DRY_RUN_VAR: ("true: a dry run (--dry-run)", [BATCH]),
    SAVE_ALL_VAR: ("true: every workflow step saves all its outputs (--save-all)", [BATCH]),
    WORKFLOW_PATH_VAR: (
        f"folders searched for workflow and tool files, separated by {os.pathsep!r} (-w)",
        [GUI, BATCH, SETTINGS],
    ),
    APP_SETTINGS_PATH_VAR: (
        f"folders searched for app settings files, separated by {os.pathsep!r}",
        [GUI, BATCH, SETTINGS],
    ),
    USER_SETTINGS_VAR: ("the user settings file", [GUI, SETTINGS]),
}
# the fields of FLIM_EXECUTION__<FIELD>
EXECUTION_FIELDS = ("EXECUTOR", "WORKERS", "SCHEDULER", "ADDRESS", "KWARGS")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser of flimsettings.

    Returns:
        The parser, with a subcommand per object and its action options, of which
        exactly one is given.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Lists, shows and validates FLIMAnalyzer settings: of tools, workflows,"
        " the app, the user and the environment.",
    )
    objects = parser.add_subparsers(dest="object", required=True, metavar="OBJECT")

    def add(name: str, help: str) -> argparse._MutuallyExclusiveGroup:
        sub = objects.add_parser(name, help=help, description=help)
        return sub, sub.add_mutually_exclusive_group(required=True)

    file_help = "a path, or a file name in the workflow search path (see -w)"
    sub, actions = add("tool", "tools and tool files")
    actions.add_argument("--list", action="store_true", help="tools by name, and tool files")
    actions.add_argument("--show", metavar="FILE", help=f"print a tool file: {file_help}")
    actions.add_argument("--validate", metavar="FILE", help=f"validate a tool file: {file_help}")
    _add_workflow_path(sub)

    sub, actions = add("workflow", "workflows and workflow files")
    actions.add_argument(
        "--list", action="store_true", help="workflows defined in code, and workflow files"
    )
    actions.add_argument("--show", metavar="FILE", help=f"print a workflow file: {file_help}")
    actions.add_argument("--validate", metavar="FILE", help=f"validate a workflow file: {file_help}")
    _add_workflow_path(sub)

    sub, actions = add("app", "app settings")
    actions.add_argument(
        "--list", action="store_true", help="the app settings files in the search path"
    )
    actions.add_argument(
        "--show", action="store_true",
        help="the app settings of flimanalyzer and flimbatch, and where each value comes"
        " from",
    )  # fmt: skip
    actions.add_argument("--validate", metavar="FILE", help="validate an app settings file")
    _add_settings_file(sub)

    sub, actions = add("user", "the user settings file (settings changed in the GUI)")
    actions.add_argument("--show", action="store_true", help="its path and content")

    sub, actions = add("env", "the FLIM_* environment variables")
    actions.add_argument(
        "--list", action="store_true", help="the variables FLIMAnalyzer reads"
    )
    actions.add_argument(
        "--show", action="store_true",
        help="the variables that are set, with unknown names and invalid values",
    )  # fmt: skip
    return parser


def _add_settings_file(parser: argparse.ArgumentParser) -> None:
    """Add `-s` to a subcommand's parser."""
    parser.add_argument(
        "-s", "--settings", metavar="FILE",
        help="app settings file: a path, or a name in the app settings search path",
    )  # fmt: skip


def _add_workflow_path(parser: argparse.ArgumentParser) -> None:
    """Add `-w` to a subcommand's parser."""
    parser.add_argument(
        "-w", "--workflow-path", action="extend", nargs="+", default=[], metavar="DIR",
        help=f"folders searched for workflow and tool files (also {WORKFLOW_PATH_VAR})",
    )  # fmt: skip


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run flimsettings.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The exit code: 1 if a validation found a problem or the action cannot be done, 0
        otherwise.

    Raises:
        SystemExit: If the arguments are invalid (exit code 2, from `argparse`).
    """
    args = build_parser().parse_args(argv)
    args.action = next(a for a in ("list", "show", "validate") if getattr(args, a, None))
    handler = globals()[f"_{args.object}_{args.action}"]
    try:
        return handler(args)
    except (BatchError, OSError, ValueError) as err:  # incl. FileNotFoundError
        print(f"{PROG}: {err}", file=sys.stderr)
        return 1


# --- tools and workflows ---


def _register(args: argparse.Namespace) -> list[Path]:
    """Register the tools, workflows and workflow files; return the workflow search path."""
    import flim.tools  # noqa: F401  (registers the tools)
    import flim.workflow  # noqa: F401  (registers the workflows)
    from flim.core.workflowfile import register_workflow_files, workflow_path

    discover(TOOLS_GROUP)  # the tools of other installed packages
    # as flimbatch: from -w or FLIM_WORKFLOW_PATH, not from a settings file
    search_path = workflow_path(folders=args.workflow_path)
    for message in register_workflow_files(search_path):
        _warn(message)
    return search_path


def _kind(cls: type["Tool"]) -> str:
    """Return `tool`, `workflow` (defined in code) or `file` (a workflow file)."""
    from flim.core.workflow import Workflow

    if getattr(cls, "definition", None) is not None:
        return "file"
    return "workflow" if issubclass(cls, Workflow) else "tool"


def _tool_list(args: argparse.Namespace) -> int:
    """Print the tools by menu, those in no menu, and the tool files."""
    from flim.core.workflowfile import _is_tool_file, workflow_files

    search_path = _register(args)
    lines = ["Tools by menu (flimbatch --run NAME; quote names with spaces):"]
    for category, group in tools.by_category().items():
        names = [cls.name for cls in group if _kind(cls) == "tool"]
        if names:
            lines.append(f"  {category}: {', '.join(names)}")
    hidden = [f"  {cls.name}" for cls in tools.hidden() if _kind(cls) == "tool"]
    lines += ["", "Not in the menus (by name or as a workflow step):"] + (hidden or ["  none"])
    tool_files = [p for p in workflow_files(search_path) if _is_tool_file(p)]
    lines += ["", "Tool files (flimbatch --run FILE, by path or file name):"]
    lines += [f"  {p.name}  ({p.parent})" for p in tool_files] or ["  none"]
    lines += ["", "Workflow search path:"] + [f"  {f}" for f in search_path]
    print("\n".join(lines))
    return 0


def _workflow_list(args: argparse.Namespace) -> int:
    """Print the workflows defined in code and the workflow files."""
    from flim.core.registry import category_path
    from flim.core.workflowfile import BUILT_IN

    search_path = _register(args)
    code, files = [], []
    registered = [c for group in tools.by_category().values() for c in group] + tools.hidden()
    for cls in sorted(registered, key=lambda c: c.name):
        kind = _kind(cls)
        if kind == "workflow":
            menu = " > ".join(category_path(cls)) or "not in the menus"
            code.append(f"  {cls.name}  (built-in, {menu})")
        elif kind == "file":
            where = "built-in" if Path(cls.path).parent == BUILT_IN else str(cls.path)
            files.append(f"  {cls.name}  ({where})")
    lines = ["Workflows defined in code (flimbatch --run NAME):"] + (code or ["  none"])
    lines += ["", "Workflow files (flimbatch --run NAME, or by path or file name):"]
    lines += files or ["  none"]
    lines += ["", "Workflow search path:"] + [f"  {f}" for f in search_path]
    print("\n".join(lines))
    return 0


def _file(name: str, args: argparse.Namespace, kind: str) -> tuple[Path, dict]:
    """Return a tool or workflow file given to `--show` or `--validate`, and its data.

    Args:
        name: A path, or a file name (with or without `.json`) in the workflow search
            path or among the built-in workflow files.
        args: The parsed arguments, with `-w`.
        kind: The kind of file required: `tool` or `workflow`.

    Returns:
        The file and its data.

    Raises:
        BatchError: If the file is not of the kind required.
        FileNotFoundError: If there is no such file.
        ValueError: If the file is not JSON.
    """
    from flim.core.workflowfile import BUILT_IN, find_workflow_file

    search_path = _register(args)
    try:  # the built-in workflow files after the search path
        path = find_workflow_file(name, [*search_path, BUILT_IN])
    except FileNotFoundError:
        raise FileNotFoundError(
            f"No {kind} file '{name}' at this path, in the workflow search path or built in"
        ) from None
    data = json.loads(path.read_text())
    found = _file_kind(data)
    if found != kind:
        names = {"tool": "a tool file", "workflow": "a workflow file", "app": "an app settings file"}
        command = f"{found} --{args.action} {name}"
        if found == "app" and args.action == "show":
            command = f"app --show -s {name}"  # app --show takes the file with -s
        hint = f" (flimsettings {command})" if found in names else ""
        what = f"{names[found]}, not" if found in names else "not"
        raise BatchError(f"{path}: {what} a {kind} file{hint}")
    return path, data


def _file_kind(data: object) -> Optional[str]:
    """Return the kind of a settings file's data: `tool`, `workflow`, `app` or None.

    The kinds are tested in this order, and the first match is returned (tool and
    workflow files also have `schema_version`):

    1. `tool`: a tool file (`schema_version` and `tool`, see `is_tool_file`).
    2. `workflow`: has `steps`.
    3. `app`: has `schema_version`, `tools` or a key of `AppSettings`; also an app
       settings file of an older version, which has other keys too.

    Args:
        data: The data read from the file.

    Returns:
        The kind, or None for other data (e.g. not a JSON object, or a config alone
        with `classname`).
    """
    from flim.core.settings import AppSettings, is_tool_file

    if not isinstance(data, dict) or "classname" in data:  # a config alone is none
        return None
    if is_tool_file(data):
        return "tool"
    if "steps" in data:
        return "workflow"
    if set(data) & ({"schema_version", "tools"} | set(AppSettings.model_fields)):
        return "app"  # also of older versions, which have other sections too
    return None


def _tool_show(args: argparse.Namespace) -> int:
    """Print a tool file as it is; the file is only read."""
    path, _ = _file(args.show, args, "tool")
    print(path.read_text().rstrip())
    return 0


def _workflow_show(args: argparse.Namespace) -> int:
    """Print a workflow file as it is; the file is only read."""
    path, _ = _file(args.show, args, "workflow")
    print(path.read_text().rstrip())
    return 0


def _report(name: str, errors: Sequence[str], warnings: Sequence[str], ok: str) -> int:
    """Print a validation's warnings and errors, or `ok`; return the exit code."""
    for message in warnings:
        _warn(message)
    if errors:
        print(f"{PROG}: {name}:\n" + "\n".join(f"  {e}" for e in errors), file=sys.stderr)
        return 1
    print(ok)
    return 0


def _tool_validate(args: argparse.Namespace) -> int:
    """Validate a tool file as flimbatch validates it before a run."""
    from flim.core.workflowfile import check_workflow_file

    path, data = _file(args.validate, args, "tool")
    check = check_workflow_file(path, tool_files=True)
    return _report(str(path), check.errors, check.warnings, f"{path}: a valid tool file of {data['tool']}")


def _workflow_validate(args: argparse.Namespace) -> int:
    """Validate a workflow file as flimbatch validates it before a run (also `save_issues`)."""
    from flim.core.workflowfile import check_workflow_file, save_issues

    path, _ = _file(args.validate, args, "workflow")
    check = check_workflow_file(path)
    warnings, errors = list(check.warnings), list(check.errors)
    if check.definition is not None:
        more_warnings, more_errors = save_issues(check.definition)
        warnings += more_warnings
        errors += more_errors
    name = check.definition.name if check.definition is not None else ""
    return _report(str(path), errors, warnings, f"{path}: a valid workflow file ({name})")


# --- app and user settings ---


def _app_list(args: argparse.Namespace) -> int:
    """Print the app settings files in the search path."""
    search_path = app_settings_path()
    files = list_app_settings(search_path)
    lines = ["App settings files (-s NAME or -s FILE):"]
    lines += [f"  {p.stem}  ({p.parent})" for p in files] or ["  none"]
    lines += ["", "App settings search path:"] + [f"  {f}" for f in search_path]
    print("\n".join(lines))
    return 0


class _ReadOnlyUserFile(UserSettingsFile):
    """The user settings file, only read: an unreadable file is not renamed."""

    unreadable: Optional[str] = None  # why the file cannot be read; None if it can

    def _set_aside(self, reason: str) -> None:
        """Record the reason; unlike the GUI, leave the file as it is."""
        self.unreadable = reason

    def merge(self, changes: dict) -> None:
        """Write nothing."""


def _gui_settings_file(args: argparse.Namespace, user: dict) -> tuple[Optional[str], str]:
    """Return the app settings file the GUI starts with, and how it is chosen.

    `-s FILE` if given; otherwise the user settings file's `default_app_settings`, if
    it exists and can be used (the GUI asks to pick another otherwise).
    """
    from flim.core.settings import check_app_settings

    if args.settings:
        return args.settings, "-s"
    default = user.get("default_app_settings")
    if default and Path(default).is_file() and check_app_settings(default).error is None:
        return str(default), "the default app settings file"
    return None, ""


def _managers(args: argparse.Namespace) -> tuple[dict, str]:
    """Return the settings managers of flimanalyzer and flimbatch (None if refused).

    Each command's layers: flimanalyzer the built-in defaults, the user settings file,
    its app settings file and the environment; flimbatch the defaults, `-s` (every
    setting usable and checked) and the environment. Problems are printed.

    Returns:
        The managers by command, and how the GUI's app settings file is chosen (see
        `_gui_settings_file`).
    """
    user_file = _ReadOnlyUserFile(user_settings_path())
    user = user_file.read()
    if user_file.unreadable:
        _warn(f"{user_file.path}: cannot be read ({user_file.unreadable}); not used")
    gui_file, how = _gui_settings_file(args, user)
    managers = {}
    for command, call in (
        (GUI, lambda: session_settings(gui_file, {}, user_file=user_file)),
        (BATCH, lambda: session_settings(args.settings, {}, complete=True)),
    ):
        try:
            managers[command] = call()
        except (OSError, ValueError) as err:
            print(f"{PROG}: {command}: {err}", file=sys.stderr)
            managers[command] = None
    if managers[GUI] is not None and how == "the default app settings file":
        managers[GUI].origins = {
            k: "default app settings file" if v == "app settings file" else v
            for k, v in managers[GUI].origins.items()
        }
    return managers, how


def _app_show(args: argparse.Namespace) -> int:
    """Print the app settings of flimanalyzer and flimbatch, and where each value comes from.

    A setting with the same value and origin in both commands takes one line;
    otherwise each command has its own line. Command-line options are not included.
    """
    from flim.core.settingsview import overview

    managers, gui_how = _managers(args)
    if not any(managers.values()):
        return 1
    rows = {c: {r.name: r for r in overview(m)} for c, m in managers.items() if m is not None}
    lines = [
        "App settings of flimanalyzer and flimbatch, without command-line options.",
        "Order of precedence, highest first: command line, environment, app settings file",
        "(-s), user settings file (flimanalyzer only), built-in defaults.",
        "",
    ]
    for command, manager in managers.items():
        source = "refused, see above" if manager is None else (
            manager.source or "none, set at runtime with -s <FILE>"
        )
        how = gui_how if command == GUI and gui_how != "-s" and manager else ""
        lines.append(f"App settings file of {command}: {source}" + (f" ({how})" if how else ""))
    lines += [f"User settings file (flimanalyzer only): {user_settings_path()}", ""]
    width = max(len(GUI), len(BATCH))
    first = next(iter(rows.values()))
    for name, row in first.items():
        shown = {}
        for command, by_name in rows.items():
            other = by_name[name]
            if command == BATCH and name == "results_dir":
                shown[command] = "not used: flimbatch saves under -o"
            else:
                shown[command] = f"{other.value}  (from {other.origin})"
        lines.append(f"  {row.title}:")
        if len(set(shown.values())) == 1:
            lines.append(f"      {next(iter(shown.values()))}")
        else:
            lines += [f"      {c + ':':<{width + 1}} {v}" for c, v in shown.items()]
        lines.append(f"      set with {row.change}")
    print("\n".join(lines))
    return 0


def _app_validate(args: argparse.Namespace) -> int:
    """Validate an app settings file, as the GUI and flimbatch read it."""
    import flim.tools  # noqa: F401  (registers the tools: their settings are checked)
    import flim.workflow  # noqa: F401
    from flim.core.settings import check_app_settings

    discover(TOOLS_GROUP)
    check = check_app_settings(args.validate)
    print(check.summary())
    if check.error or check.invalid:
        print(f"{PROG}: {args.validate}: cannot be used", file=sys.stderr)
        return 1
    if check.unknown or check.not_checked:
        print(
            f"{PROG}: {args.validate}: the GUI uses it without the settings listed;"
            " flimbatch refuses it (all settings must be usable and checked)",
            file=sys.stderr,
        )
        return 1
    return 0


def _user_show(args: argparse.Namespace) -> int:
    """Print the user settings file's path and content; the file is only read."""
    path = user_settings_path()
    if not path.is_file():
        print(f"No user settings file: {path}")
        return 0
    text = path.read_text()
    try:
        text = json.dumps(json.loads(text), indent=2)
    except ValueError:
        _warn(f"{path}: not valid JSON; the GUI sets such a file aside")
    print(f"User settings file: {path}\n{text.rstrip()}")
    return 0


# --- the environment ---


def _env_list(args: argparse.Namespace) -> int:
    """Print the FLIM_* variables FLIMAnalyzer reads."""
    lines = [
        "Environment variables FLIMAnalyzer reads.",
        "A command-line option takes precedence over its environment variable; an",
        "environment variable takes precedence over the settings files and the built-in",
        "defaults. Order of precedence of the app settings, highest first: command line,",
        "environment, app settings file (-s), user settings file (flimanalyzer only),",
        "built-in defaults.",
        "",
    ]
    for name, (what, commands) in sorted(ENV_VARIABLES.items()):
        lines += [f"  {name}", f"      {what}; read by {', '.join(commands)}"]
    print("\n".join(lines))
    return 0


def _known(name: str) -> bool:
    """Return whether FLIMAnalyzer reads the variable `name`."""
    prefix = ENV_NAMES["execution"] + "__"
    if name.startswith(prefix):
        return name[len(prefix):] in EXECUTION_FIELDS
    return name in ENV_VARIABLES


def _env_show(args: argparse.Namespace) -> int:
    """Print the FLIM_* variables that are set; unknown names and invalid values are problems."""
    found = {k: v for k, v in sorted(os.environ.items()) if k.startswith("FLIM_")}
    lines = ["FLIM_* environment variables that are set:"]
    lines += [f"  {k}={v}" for k, v in found.items()] or ["  none"]
    print("\n".join(lines))
    problems = [
        f"{k}: FLIMAnalyzer does not read this variable; check the name" for k in found if not _known(k)
    ]
    try:
        environment_changes()
    except ValueError as err:
        problems.append(str(err))
    level = os.environ.get(LOG_LEVEL_VAR, "").strip()
    if level and level.lower() not in LOG_LEVELS:
        problems.append(f"Invalid environment variable: {LOG_LEVEL_VAR}={level}")
    for option, variable in (("--dry-run", DRY_RUN_VAR), ("--save-all", SAVE_ALL_VAR)):
        try:
            flag_source(False, option, variable)
        except ValueError as err:
            problems.append(str(err))
    if problems:
        print(f"{PROG}: problems:\n" + "\n".join(f"  {p}" for p in problems), file=sys.stderr)
        return 1
    return 0


def _warn(message: str) -> None:
    """Print a warning to standard error, as `flimsettings: warning: <message>`."""
    print(f"{PROG}: warning: {message}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
