"""Running tools and workflows on tables outside the GUI, as flimbatch does.

Resolves what a run names (a tool, a workflow defined in code, a workflow file or a
tool file), validates a run against the tables before it starts, and runs it into its
folder. Used by the commands and the GUI; prints nothing.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence

from flim.core.config import ProcessingRules
from flim.core.execution import ExecutionOptions
from flim.core.paths import same_names
from flim.core.reader import ReadSettings
from flim.core.registry import tools
from flim.core.schema import TableSchema
from flim.core.settings import AppSettings, ToolSettings

if TYPE_CHECKING:
    import pandas as pd

    from flim.core.runner import FlowRun
    from flim.core.tool import Tool
    from flim.core.workflowfile import Overrides

logger = logging.getLogger(__name__)


class BatchError(Exception):
    """A batch step that cannot be done, with the reason for the user."""


def workflow_settings(
    tool: type["Tool"], settings: AppSettings
) -> tuple[Any, Optional[ToolSettings]]:
    """Return the config and the settings a workflow defined in code runs with.

    Those of its tool file (`settings_entry`, see
    `flim.core.workflowfile.settings_workflow`), else those in `settings`.

    Args:
        tool: The workflow class.
        settings: The session's settings.

    Returns:
        The config, and the tool's settings (None if none are stored).
    """
    entry = getattr(tool, "settings_entry", None)
    if entry is None:
        return settings.tools.config(tool), settings.tools.entry(tool)
    return tool.config_class.model_validate(entry.config or {}), entry


def resolve_run(
    name: str,
    search_path: Sequence[str | os.PathLike] = (),
    warn: Callable[[str], None] = logger.warning,
) -> type["Tool"]:
    """Return the tool or workflow class of a `--run` argument.

    An argument that contains a folder separator or ends with `.json` is a workflow
    file, or a tool file (run as a workflow of one step): a path, or a file name in
    the search path or, after it, among the built-in workflow files. Any other argument is a
    registered name: a tool, a workflow defined in code, or a workflow file by the
    `name` in it.

    Args:
        name: The argument of `--run`.
        search_path: The folders searched for workflow files.
        warn: Called with each warning of the file's validation, e.g. a tool file with
            `save: false`. Defaults to logging it.

    Returns:
        The class; for a workflow file, a workflow class that runs its steps.

    Raises:
        BatchError: If there is no such tool, workflow or file, or the file has
            errors.
    """
    from flim.core.workflowfile import (
        BUILT_IN,
        validate_workflow_file,
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
        path = find_workflow_file(name, [*search_path, BUILT_IN])  # built-in ones last
    except FileNotFoundError as err:
        raise BatchError(str(err)) from None
    validation = validate_workflow_file(path, tool_files=True)  # a tool file: one step
    if validation.errors:
        raise BatchError(f"{path}:\n" + "\n".join(validation.errors))
    for message in validation.warnings:
        warn(message)
    if validation.workflow is not None:  # a tool file of a workflow defined in code
        return validation.workflow
    return workflow_class(validation.definition, path)


def file_run(
    tool: type["Tool"], settings: AppSettings
) -> tuple[type["Tool"], ReadSettings]:
    """Return the tool to run on the files' tables, and how the files are read.

    Import Tables reads with its own settings and runs the workflow they name (the
    settings of its tool file, or of the `-s` file); every other tool or workflow runs
    on the files read with Open Tables' settings.

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

    if not issubclass(tool, ImportTables):
        return tool, settings.tools.config(TableReader).read_settings()
    config, _ = workflow_settings(tool, settings)  # a tool file's, else the -s file's
    if not config.workflow:
        raise BatchError(
            "Import Tables: the settings name no workflow; set `workflow` in its"
            " settings (a tool file of Import Tables, or its section of the settings"
            " file), or run the workflow file with --run"
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


RESOLVED = "resolved.json"  # the run's settings with every setting stated


def _write_resolved(run_dir: str | os.PathLike, data: dict) -> None:
    """Write a run's resolved settings into its folder, as `resolved.json`.

    Args:
        run_dir: The run's folder; created if needed.
        data: The resolved workflow or tool file's content.
    """
    import json

    folder = Path(run_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / RESOLVED).write_text(json.dumps(data, indent=2) + "\n")


def validate_run(
    tool: type["Tool"],
    tables: dict[str, "pd.DataFrame"],
    settings: AppSettings,
    overrides: Optional["Overrides"] = None,
) -> list[str]:
    """Validate a run against the tables (or their first rows) without running it.

    Two tables whose names become the same folder name (`path_name`) are an error.
    A workflow file's steps are validated against the tables' columns, and so is a
    tool, as the workflow of one step it runs as (`tool_workflow`); a tool (not a
    workflow) that needs more than one input table is an error. A workflow defined
    in code is validated on each table, with its `processing`. Missing columns are
    errors unless the `processing` guesses or skips them.

    Args:
        tool: The tool or workflow class.
        tables: The tables by name.
        settings: The session's settings; a tool or workflow is validated with its
            settings from them.
        overrides: Settings over the tool's or the steps' (`flimbatch --override`),
            of this run (`Overrides.for_run`); None: none. Unless they make every
            step save, a workflow file none of whose steps saves is an error (see
            `save_issues`).

    Returns:
        The errors, each with the tool and the table; empty if there are none.
    """
    from flim.core.workflow import Workflow
    from flim.core.workflowfile import Overrides, overridden, save_issues, validate_steps

    overrides = overrides or Overrides()

    names = [
        f"the inputs '{a}' and '{b}' get the same folder name" for a, b in same_names(tables)
    ]
    schemas = {name: TableSchema.from_frame(t) for name, t in tables.items()}
    required = [spec for spec in tool.inputs if not spec.optional]
    if getattr(tool, "definition", None) is None and not issubclass(tool, Workflow):
        if len(required) > 1:
            return names + [f"{tool.name} needs {len(required)} input tables; use a workflow file"]
        tool = tool_workflow(tool, settings)
    definition = getattr(tool, "definition", None)
    if definition is not None:
        definition = overridden(definition, overrides)
        unsaved = save_issues(definition)[1]
        return names + unsaved + validate_steps(definition, schemas, overrides)
    config, entry = workflow_settings(tool, settings)
    rules = ProcessingRules.of(entry.processing if entry else None, overrides.processing)
    targets = [(name, [schema] * max(1, len(tool.inputs))) for name, schema in schemas.items()]
    errors = names
    for name, inputs in targets:
        for issue in tool.validate(config, inputs, rules):
            if issue.severity == "error":
                where = f"{issue.field}: " if issue.field else ""
                errors.append(f"{tool.name} on {name}: {where}{issue.message}")
    return errors


def run_on_tables(
    tool: type["Tool"],
    tables: dict[str, "pd.DataFrame"],
    settings: AppSettings,
    run_dir: str | os.PathLike,
    execution: Optional[ExecutionOptions] = None,
    overrides: Optional["Overrides"] = None,
    settings_record: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> "FlowRun":
    """Run a tool or workflow on the tables read from the files, as one run.

    A workflow file runs as its steps say. A tool runs as a workflow of one step,
    `1`, with its settings from `settings` and saving on (`tool_workflow`). A workflow
    defined in code runs once per table, all in this run, its results below a folder
    per table. The results go into `run_dir`, with the run summary and the run's
    settings with every setting stated, `resolved.json` (a workflow file, or for a
    workflow defined in code a tool file; see
    `flim.core.workflowfile.resolve_definition`); rerun, it gives the same run.

    Args:
        tool: The tool or workflow class.
        tables: The tables by name.
        settings: The app settings (the tools' settings and save formats).
        run_dir: The run's folder, e.g. `<output>/<date and time>/run-1`.
        execution: The executor; None for the default `ExecutionOptions`.
        overrides: Settings over the tool's or the steps' (`flimbatch --override`),
            of this run (`Overrides.for_run`), listed in the run summary; None: none.
        settings_record: The settings files, for the run summary.
        notes: Notes for the run summary, e.g. on the executor.

    Returns:
        The run.

    Raises:
        BatchError: If the run's settings don't fit the tables, or two tables' names
            become the same folder name (see `validate_run`), or a workflow defined in
            code has errors for a table.
    """
    from flim.core.runner import run_flow, tag_prefix
    from flim.core.tool import validate_requirements
    from flim.core.validation import resolution_notes
    from flim.core.workflow import Workflow, WorkflowValidationError

    from flim.core.workflowfile import (
        Overrides,
        overridden,
        resolve_definition,
        resolved_data,
        resolved_tool_data,
        workflow_class,
    )

    overrides = overrides or Overrides()
    errors = validate_run(tool, tables, settings, overrides)
    if errors:
        raise BatchError(f"{tool.name}:\n" + "\n".join(errors))
    execution = execution or ExecutionOptions()
    notes = list(notes) + [f"--override {given}" for given in overrides.given]
    if getattr(tool, "definition", None) is None and not issubclass(tool, Workflow):
        tool = tool_workflow(tool, settings)
    definition = getattr(tool, "definition", None)
    if definition is not None:  # a workflow file, or a tool as one
        if overrides.given:
            definition = overridden(definition, overrides)
            tool = workflow_class(definition, getattr(tool, "path", None), overrides)
        schemas = {name: TableSchema.from_frame(t) for name, t in tables.items()}
        resolved = resolve_definition(definition, overrides, schemas)
        _write_resolved(run_dir, resolved_data(resolved))
        return tool().run_flow(
            tables,
            task_runner=execution.task_runner(),
            run_dir=run_dir,  # the steps' `save` decides what is written
            settings_record=settings_record,
            save_formats=definition.output.formats,
            notes=notes,
        )
    # a workflow defined in code: validated per table, then all tables in one run
    config, entry = workflow_settings(tool, settings)
    rules = ProcessingRules.of(entry.processing if entry else None, overrides.processing)
    configs = {}
    for name, table in tables.items():
        inputs = [table] * len(tool.inputs)
        report = tool().resolve(config, inputs, rules)
        if report.errors:
            raise BatchError(f"{tool.name} on {name}:\n{WorkflowValidationError(report)}")
        try:
            validate_requirements(tool.name, report.config, inputs)  # after skipped entries
        except ValueError as err:
            raise BatchError(f"{tool.name} on {name}: {err}") from None
        configs[name] = report.config
        notes += resolution_notes(report, f"{name}: ")

    first = next(iter(configs.values()), config)
    formats = overrides.formats_over(entry.output.formats if entry else [])
    _write_resolved(run_dir, resolved_tool_data(tool, first, formats, rules))

    def build() -> None:
        for name, table in tables.items():
            with tag_prefix(name):  # its results below a folder per table
                tool().build(*[table] * len(tool.inputs), config=configs[name])

    return run_flow(
        tool.name,
        build,
        task_runner=execution.task_runner(),
        run_dir=run_dir,
        notes=notes,
        settings_record=settings_record,
        save_formats=formats,
    )


def tool_workflow(tool: type["Tool"], settings: AppSettings) -> type["Tool"]:
    """Return a tool as a workflow of one step, `1`, as `--run <tool>` runs it.

    The step has the tool's settings from `settings` (else its defaults), with their
    `processing`, and always saves, in the tool's formats; its results go into the folder `01-<tool>`.

    Args:
        tool: The tool class.
        settings: The session's settings.

    Returns:
        The workflow class.
    """
    from flim.core.workflowfile import WorkflowDefinition, workflow_class

    entry = settings.tools.entry(tool)
    config = settings.tools.config(tool).model_dump(mode="json", exclude={"classname", "version"})
    formats = [f.model_dump(mode="json") for f in entry.output.formats] if entry else []
    definition = WorkflowDefinition.model_validate({
        "name": tool.name,
        "steps": [{"id": "1", "tool": tool.name, "config": config,
                   "output": {"save": True, "formats": formats},
                   "processing": entry.processing.model_dump() if entry else {}}],
    })  # fmt: skip
    return workflow_class(definition)


def settings_file_issues(
    runs: Sequence[type["Tool"]], settings: AppSettings, source: Optional[str | os.PathLike]
) -> tuple[list[str], list[str]]:
    """Return the problems of tools run by name that take their settings from `-s`.

    A tool or a workflow defined in code given to `--run` by name takes its settings
    from the app settings file's `tools` section. That is deprecated (removed in
    0.8.0): a tool file states the tool and its settings together. A file without a
    section for the tool is an error, since the run would otherwise take the tool's
    defaults without saying so. Workflow and tool files given to `--run` carry their
    own settings and are not affected; without an app settings file, a tool takes
    its defaults.

    Args:
        runs: The tools and workflows of `--run`.
        settings: The session's settings.
        source: The app settings file (`-s`); None if none is given.

    Returns:
        The warnings (a section is used, deprecated) and the errors (no section).
    """
    warnings, errors = [], []
    if source is None:
        return warnings, errors
    advice = (
        "give the tool's settings as a tool file (the GUI writes one with Save Settings"
        " in the tool's dialog)"
    )
    for tool in runs:
        if getattr(tool, "definition", None) is not None or hasattr(tool, "settings_entry"):
            continue  # a workflow or tool file
        if settings.tools.entry(tool) is None:
            errors.append(
                f"--run {tool.name}: the app settings file {source} has no settings of"
                f" {tool.name}; {advice}"
            )
        else:
            warnings.append(
                f"--run {tool.name}: taking the tool's settings from the app settings file"
                f" {source} is deprecated and is removed in 0.8.0; {advice}"
            )
    return warnings, errors


def ignored_settings(
    runs: Sequence[type["Tool"]], settings: AppSettings, output: Optional[str | os.PathLike]
) -> list[str]:
    """Return a message for each setting of a `--run` tool that flimbatch doesn't use.

    A tool given to `--run` runs as a workflow of one step, `01`, with its settings
    from the settings file. flimbatch saves only under `-o` and always saves, so the
    tool's `output.results_dir` and an `output.save` of false are not used. Workflow
    files have no such settings.

    Args:
        runs: The tools and workflows of `--run`.
        settings: The session's settings.
        output: The folder of `-o`; None if not given (a dry run).

    Returns:
        The messages, one per setting. For example
        `step 01, tool 'Summarize': output.results_dir=summaries superseded by -o /data/results`.
    """
    target = f"-o {output}" if output else "-o"
    messages = []
    for tool in runs:
        if getattr(tool, "definition", None) is not None or hasattr(tool, "settings_entry"):
            continue  # a workflow or tool file
        entry = settings.tools.entry(tool)
        if entry is None:
            continue
        where = f"step 01, tool '{tool.name}'"
        if entry.output.results_dir is not None:
            messages.append(
                f"{where}: output.results_dir={entry.output.results_dir} superseded by {target}"
            )
        if not entry.output.save:
            from flim.core.workflowfile import tool_save_warning

            messages.append(tool_save_warning(tool.name))
    return messages
