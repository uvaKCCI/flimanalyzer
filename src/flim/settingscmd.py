"""The flimsettings command: lists, shows and validates settings without the GUI.

`flimsettings OBJECT ACTION`, one action per call:

- `tool`: `--list` (tools by name, and tool files in the workflow search path),
  `--show FILE|NAME` (prints a tool file, or a tool's default settings as a tool
  file), `--validate FILE` (validates a tool file), `--resolve FILE` (prints it with
  every setting stated), `--update FILE` (rewrites a file of an older version).
- `workflow`: `--list` (workflows defined in code, and workflow files),
  `--show FILE|NAME` (prints a workflow file, or the default settings of a workflow
  defined in code as a tool file), `--validate FILE` (validates a workflow file),
  `--resolve FILE` (prints it with every setting of every step stated).

- `app`: `--list` (the app settings files in the search path), `--show` (the app
  settings of flimanalyzer and of flimbatch, and where each value comes from), `--validate FILE`
  (an app settings file), `--update FILE` (rewrites a file of an older version in the
  current one, keeping the original).
- `user`: `--show` (the user settings file).
- `env`: `--list` (the `FLIM_*` variables FLIMAnalyzer reads), `--show` (those that
  are set, with unknown names and invalid values).

A FILE is a path, or a file name in the workflow search path; a file of another kind
is an error. A file takes precedence over a tool or workflow of the same name.
`--show` only reads.

The output goes to standard output, and problems go to standard error. The exit code is 1 if a validation finds a problem, 2 for
invalid arguments, 0 otherwise. Only `FLIM_*` variables are shown, never others
(e.g. Prefect's). wxPython is not imported.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence

from flim.core.batchrun import BatchError
from flim.core.cli import DRY_RUN_VAR, LOG_LEVEL_VAR, LOG_LEVELS, flag_source
from flim.core.registry import TOOLS_GROUP, discover, tools
from flim.core.settings import settings_kind
from flim.core.settingsmgr import (
    APP_SETTINGS_PATH_VAR,
    ENV_NAMES,
    OPTION_NAMES,
    USER_SETTINGS_VAR,
    UserSettingsFile,
    app_settings_files,
    app_settings_path,
    environment_changes,
    session_settings,
    user_settings_path,
)
from flim.core.workflowfile import WORKFLOW_PATH_VAR

if TYPE_CHECKING:
    from flim.core.tool import Tool
    from flim.core.workflowfile import Overrides

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
    LOG_LEVEL_VAR: (f"log level: {', '.join(LOG_LEVELS)} (-l)", [GUI, BATCH]),
    DRY_RUN_VAR: ("true: a dry run (--dry-run)", [BATCH]),
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
    actions.add_argument(
        "--show", metavar="FILE|NAME",
        help=f"print a tool file ({file_help}), or a tool's default settings as a tool file",
    )  # fmt: skip
    actions.add_argument("--validate", metavar="FILE", help=f"validate a tool file: {file_help}")
    actions.add_argument(
        "--resolve", metavar="FILE",
        help=f"print a tool file with every setting stated, as flimbatch runs it: {file_help}",
    )  # fmt: skip
    actions.add_argument(
        "--update", metavar="FILE",
        help="rewrite a tool file of an older version in the current one; the original\n"
        f"is kept next to it as <name>.v<version>.json: {file_help}",
    )  # fmt: skip
    _add_workflow_path(sub)

    sub, actions = add("workflow", "workflows and workflow files")
    actions.add_argument(
        "--list", action="store_true", help="workflows defined in code, and workflow files"
    )
    actions.add_argument(
        "--show", metavar="FILE|NAME",
        help=f"print a workflow file ({file_help}), or the default settings of a workflow"
        " defined in code as a tool file",
    )  # fmt: skip
    actions.add_argument("--validate", metavar="FILE", help=f"validate a workflow file: {file_help}")
    actions.add_argument(
        "--resolve", metavar="FILE",
        help="print a workflow file with every setting of every step stated, as flimbatch"
        f" runs it: {file_help}",
    )  # fmt: skip
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
    actions.add_argument(
        "--update", metavar="FILE",
        help="rewrite an app settings file of an older version in the current one; the\n"
        "original is kept next to it as <name>.v<version>.json",
    )  # fmt: skip
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
    """Add `-w`, and `--override` for `--resolve`, to a subcommand's parser."""
    parser.add_argument(
        "-w", "--workflow-path", action="extend", nargs="+", default=[], metavar="DIR",
        help=f"folders searched for workflow and tool files (also {WORKFLOW_PATH_VAR})",
    )  # fmt: skip
    parser.add_argument(
        "--override", action="append", default=[], metavar="GROUP.FIELD=VALUE",
        help="with --resolve: a setting over the file's, as with flimbatch --override",
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
    args.action = next(
        a for a in ("list", "show", "validate", "resolve", "update") if getattr(args, a, None)
    )
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
        BatchError: If the file is not of the kind required, or if the name is the
            name of a tool or of a workflow defined in code (except for `--show` of
            the same kind).
        _Defaults: If there is no such file, the action is `--show` and the name is
            the name of a tool (`tool`) or of a workflow defined in code
            (`workflow`).
        FileNotFoundError: If there is no such file.
        ValueError: If the file is not JSON.
    """
    from flim.core.workflowfile import BUILT_IN, find_workflow_file

    search_path = _register(args)
    try:  # the built-in workflow files after the search path
        path = find_workflow_file(name, [*search_path, BUILT_IN])
    except FileNotFoundError:
        try:
            found = _kind(tools.get(name))
        except KeyError:
            found = ""
        if found in ("tool", "workflow"):
            what = "a tool" if found == "tool" else "a workflow defined in code"
            if found == kind and args.action == "show":
                raise _Defaults(tools.get(name)) from None
            if args.action == "show":
                hint = f"flimsettings {found} --show '{name}' prints its default settings"
            else:
                hint = f"--validate takes a file; flimsettings {kind} --list lists the {kind} files"
            raise BatchError(f"'{name}' is {what}, not a {kind} file; {hint}") from None
        raise FileNotFoundError(
            f"No {kind} file '{name}' at this path, in the workflow search path or built in"
        ) from None
    data = json.loads(path.read_text())
    found = settings_kind(data)
    if found != kind:
        names = {"tool": "a tool file", "workflow": "a workflow file", "app": "an app settings file"}
        command = f"{found} --{args.action} {name}"
        if found == "app" and args.action == "show":
            command = f"app --show -s {name}"  # app --show takes the file with -s
        hint = f" (flimsettings {command})" if found in names else ""
        what = f"{names[found]}, not" if found in names else "not"
        raise BatchError(f"{path}: {what} a {kind} file{hint}")
    return path, data


class _Defaults(Exception):
    """Raised by `_file` for `--show` with the name of a tool or a workflow defined in code."""

    def __init__(self, tool: type["Tool"]) -> None:
        super().__init__(tool.name)
        self.tool = tool


def _show(args: argparse.Namespace, kind: str) -> int:
    """Print a tool or workflow file as it is (the file is only read), or the default
    settings of a tool or of a workflow defined in code, as a tool file."""
    from flim.core.settings import tool_file_data, tool_settings

    try:
        path, _ = _file(args.show, args, kind)
    except _Defaults as defaults:
        tool = defaults.tool
        data = tool_file_data(tool, tool_settings(tool.config_class()))
        print(json.dumps(data, indent=2))
        return 0
    print(path.read_text().rstrip())
    return 0


def _tool_show(args: argparse.Namespace) -> int:
    """Print a tool file as it is, or a tool's default settings as a tool file."""
    return _show(args, "tool")


def _workflow_show(args: argparse.Namespace) -> int:
    """Print a workflow file as it is, or the default settings of a workflow defined in
    code as a tool file."""
    return _show(args, "workflow")


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
    from flim.core.workflowfile import validate_workflow_file

    path, data = _file(args.validate, args, "tool")
    validation = validate_workflow_file(path, tool_files=True)
    return _report(str(path), validation.errors, validation.warnings, f"{path}: a valid tool file of {data['tool']}")


def _workflow_validate(args: argparse.Namespace) -> int:
    """Validate a workflow file as flimbatch validates it before a run (also `save_issues`)."""
    from flim.core.workflowfile import validate_workflow_file, save_issues

    path, _ = _file(args.validate, args, "workflow")
    validation = validate_workflow_file(path)
    warnings, errors = list(validation.warnings), list(validation.errors)
    if validation.definition is not None:
        more_warnings, more_errors = save_issues(validation.definition)
        warnings += more_warnings
        errors += more_errors
    name = validation.definition.name if validation.definition is not None else ""
    return _report(str(path), errors, warnings, f"{path}: a valid workflow file ({name})")


def _tool_resolve(args: argparse.Namespace) -> int:
    """Print a tool file with every setting stated (data-dependent settings excepted)."""
    from flim.core.config import ProcessingRules
    from flim.core.workflowfile import resolved_tool_data, validate_workflow_file, workflow_class

    path, _ = _file(args.resolve, args, "tool")
    validation = validate_workflow_file(path, tool_files=True)
    if validation.errors:
        return _report(str(path), validation.errors, validation.warnings, "")
    run = validation.workflow or workflow_class(validation.definition, path)
    overrides = _overrides(args, run, path)
    if overrides is None:
        return 1
    if validation.workflow is not None:  # a workflow defined in code
        tool, entry = validation.workflow, validation.workflow.settings_entry
        config = tool.config_class.model_validate(entry.config or {})
        rules = ProcessingRules.of(entry.processing, overrides.processing)
        data = resolved_tool_data(tool, config, overrides.formats_over(entry.output.formats), rules)
    else:  # a tool, run as a workflow of one step
        definition = validation.definition
        (step,) = definition.steps
        tool = tools.get(step.tool)
        config = tool.config_class.model_validate(step.config)
        own = overrides.for_step(step.id)
        formats = own.formats_over(step.output.formats or [])
        data = resolved_tool_data(tool, config, formats, definition.rules(step, overrides))
    print(json.dumps(data, indent=2))
    return 0


def _workflow_resolve(args: argparse.Namespace) -> int:
    """Print a workflow file with every setting of every step stated.

    The settings that depend on the data (`features: all`, guessed columns, skipped
    entries) stay as in the file; flimbatch pins them in `resolved.json`.
    """
    from flim.core.workflowfile import (
        overridden,
        resolve_definition,
        resolved_data,
        validate_workflow_file,
        workflow_class,
    )

    path, _ = _file(args.resolve, args, "workflow")
    validation = validate_workflow_file(path)
    if validation.errors:
        return _report(str(path), validation.errors, validation.warnings, "")
    overrides = _overrides(args, workflow_class(validation.definition, path), path)
    if overrides is None:
        return 1
    definition = overridden(validation.definition, overrides)
    print(json.dumps(resolved_data(resolve_definition(definition, overrides)), indent=2))
    return 0


def _overrides(args: argparse.Namespace, run: Any, path: Path) -> Optional["Overrides"]:
    """Return the `--override` arguments of `--resolve` for the file, as one run.

    Prints the errors of their scopes (`override_problems`) and returns None if
    there are any.
    """
    from flim.core.workflowfile import override_problems, parse_overrides

    overrides = parse_overrides(args.override)
    errors = override_problems(overrides, [run])
    if errors:
        _report(str(path), errors, [], "")
        return None
    return overrides.for_run(1)


# --- app and user settings ---


def _app_list(args: argparse.Namespace) -> int:
    """Print the app settings files in the search path."""
    search_path = app_settings_path()
    files, others = app_settings_files(search_path)
    lines = ["App settings files (-s NAME or -s FILE):"]
    lines += [f"  {p.stem}  ({p.parent})" for p in files] or ["  none"]
    if others:
        lines += [
            "",
            f"Other JSON files in these folders, not listed: {len(others)} (tool or"
            " workflow files, or not readable as JSON; flimsettings tool --list lists"
            " tool files in the workflow search path)",
        ]
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
    from flim.core.settings import validate_app_settings

    if args.settings:
        return args.settings, "-s"
    default = user.get("default_app_settings")
    if default and Path(default).is_file() and validate_app_settings(default).error is None:
        return str(default), "the default app settings file"
    return None, ""


def _managers(args: argparse.Namespace) -> tuple[dict, str]:
    """Return the settings managers of flimanalyzer and flimbatch (None if refused).

    Each command's layers: flimanalyzer the built-in defaults, the user settings file,
    its app settings file and the environment; flimbatch the defaults, `-s` (every
    setting usable and validated) and the environment. Problems are printed.

    Returns:
        The managers by command, and how the GUI's app settings file is chosen (see
        `_gui_settings_file`).
    """
    import flim.tools  # noqa: F401  (registers the tools: their settings are validated)
    import flim.workflow  # noqa: F401
    from flim.core.workflowfile import register_workflow_files

    discover(TOOLS_GROUP)
    register_workflow_files()  # the built-in ones: a settings file may have their sections
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


def _update(path: Path) -> int:
    """Rewrite a settings file of an older version in the current one; print the result."""
    import flim.tools  # noqa: F401  (registers the tools: their settings are validated)
    import flim.workflow  # noqa: F401
    from flim.core.settings import update_settings_file

    discover(TOOLS_GROUP)
    try:
        backup = update_settings_file(path)
    except ValueError as err:
        print(f"{PROG}: {err}", file=sys.stderr)
        return 1
    print(f"{path}: updated to the current format; the original is kept as {backup}")
    return 0


def _app_update(args: argparse.Namespace) -> int:
    """Rewrite an app settings file of an older version in the current one."""
    from flim.core.settingsmgr import find_app_settings

    return _update(find_app_settings(args.update, app_settings_path()))


def _tool_update(args: argparse.Namespace) -> int:
    """Rewrite a tool file of an older version in the current one."""
    path, _ = _file(args.update, args, "tool")
    return _update(path)


def _app_validate(args: argparse.Namespace) -> int:
    """Validate an app settings file, as the GUI and flimbatch read it.

    The GUI refuses a file with settings that can't be used (unknown or invalid) and
    keeps the settings of tools that aren't installed; flimbatch refuses both.
    """
    import flim.tools  # noqa: F401  (registers the tools: their settings are validated)
    import flim.workflow  # noqa: F401
    from flim.core.settings import validate_app_settings
    from flim.core.workflowfile import register_workflow_files

    discover(TOOLS_GROUP)
    register_workflow_files()  # the built-in ones: a settings file may have their sections
    validation = validate_app_settings(args.validate)
    print(validation.summary())
    if validation.error or validation.invalid or validation.unknown:
        print(
            f"{PROG}: {args.validate}: settings that can't be used; the GUI and flimbatch"
            " refuse it",
            file=sys.stderr,
        )
        return 1
    if validation.not_validated:
        print(
            f"{PROG}: {args.validate}: settings of tools that aren't installed; the GUI"
            " uses it and keeps them, flimbatch refuses it (every setting must be usable"
            " and validated)",
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
    try:
        flag_source(False, "--dry-run", DRY_RUN_VAR)
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
