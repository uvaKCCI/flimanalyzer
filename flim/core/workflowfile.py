"""Workflow files: a workflow defined as data, in a file of its own.

A workflow file names its steps; each step is a tool with its own settings, so the
file alone decides what a run does::

    {"schema_version": 1, "name": "calc and aggregate",
     "read": {"delimiter": "\\t,"},
     "autosave": {"enabled": true, "formats": []},
     "steps": [
       {"id": "1", "tool": "Calculate", "config": {...}, "processing": "allow_partial"},
       {"id": "2", "tool": "Summarize", "inputs": ["1"], "config": {...}, "save": true}
     ]}

A step's `inputs` refer to earlier steps' outputs: `"4.1"` (output 1 of step 4), `"4"`
(the same), or `"input"` (the tables the run starts from: the files read, or an open
table). A step without `inputs` takes output 1 of the step before it; the first step
takes the run's tables. The outputs of a step are numbered from 1 in the order its
tool returns them. `outputs` optionally names them, as a check. `save` saves a step's
outputs (`true`) or some of them (`["2.1"]`). `processing` says how much of its
settings a step must apply to the data: `require_all` (default), `allow_partial` (at
least one part) or `allow_none`.

Workflow files are registered by their `name` like tools: the built-in files (in
`flim/workflow/files`) and those in the folders of the `workflow_paths` setting.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from flim.core.reader import ReadSettings
from flim.core.saving import AutosaveConfig

logger = logging.getLogger(__name__)

WORKFLOW_SCHEMA_VERSION = 1
INPUT = "input"  # the reference to the run's tables
BUILT_IN = Path(__file__).resolve().parent.parent / "workflow" / "files"
WORKFLOW_PATH_VAR = "FLIM_WORKFLOW_PATH"


class WorkflowStep(BaseModel):
    """One step of a workflow file: a tool with its settings."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="An identifier that never changes, e.g. a number.")
    tool: str = Field(description="The tool's (or workflow's) name.")
    inputs: list[str] = Field(
        default=[],
        description="Output references, e.g. '4.1', '4' (output 1) or 'input' (the"
        " run's tables); empty: output 1 of the step before.",
    )
    config: dict = Field(default={}, description="The tool's settings; {}: its defaults.")
    outputs: dict[str, str] = Field(
        default={}, description="The names of the outputs by number, as a check."
    )
    save: Union[bool, list[str]] = Field(
        default=False, description="Save the step's outputs, or those listed."
    )
    processing: Literal["require_all", "allow_partial", "allow_none"] = Field(
        default="require_all",
        description="require_all: every part of the settings must apply;"
        " allow_partial: at least one; allow_none: the table may pass unchanged.",
    )

    @field_validator("id", mode="before")
    @classmethod
    def _id_as_text(cls, value):
        return str(value) if isinstance(value, int) else value


class WorkflowDefinition(BaseModel):
    """A workflow file's content."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = WORKFLOW_SCHEMA_VERSION
    name: str
    description: str = ""
    read: ReadSettings = Field(default_factory=ReadSettings)
    autosave: AutosaveConfig = Field(default_factory=AutosaveConfig)
    steps: list[WorkflowStep] = Field(min_length=1)


def parse_reference(reference: str) -> tuple[str, int]:
    """Return the step id and output number of a reference ('4.1', '4', 'input').

    Raises:
        ValueError: If the output number is not a number from 1.
    """
    if reference == INPUT:
        return INPUT, 1
    step, _, number = reference.partition(".")
    if not number:
        return step, 1
    if not number.isdigit() or int(number) < 1:
        raise ValueError(f"'{reference}': the output number must be 1 or more")
    return step, int(number)


@dataclass
class WorkflowCheck:
    """The result of `check_workflow_file`.

    Attributes:
        path: The file.
        definition: The workflow, if the file could be read and has no errors.
        errors: Problems that stop the workflow from running.
        warnings: Problems that don't, e.g. a step with its tool's defaults.
    """

    path: Optional[Path]
    definition: Optional[WorkflowDefinition] = None
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def check_definition(definition: WorkflowDefinition, check: WorkflowCheck) -> None:
    """Check a workflow's steps: unique ids, references to earlier steps, the tools
    and their settings. Problems are added to `check`."""
    from flim.core.registry import tools

    seen = []
    for number, step in enumerate(definition.steps, 1):
        where = f"step {step.id}"
        if step.id in seen or step.id == INPUT:
            check.errors.append(f"{where}: the id '{step.id}' is used twice or reserved")
        inputs = step.inputs or ([seen[-1]] if seen else [INPUT])
        for reference in inputs:
            try:
                source, _ = parse_reference(reference)
            except ValueError as err:
                check.errors.append(f"{where}: {err}")
                continue
            if source != INPUT and source not in seen:
                check.errors.append(
                    f"{where}: '{reference}' is not an output of an earlier step"
                )
        seen.append(step.id)
        if step.tool not in tools:
            check.errors.append(f"{where}: no tool or workflow named '{step.tool}'")
            continue
        tool = tools.get(step.tool)
        try:
            tool.config_class.model_validate(step.config)
        except ValidationError as err:
            reasons = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
            )
            check.errors.append(f"{where} ({step.tool}): settings not valid: {reasons}")
        for reference in step.save if isinstance(step.save, list) else []:
            try:
                source, _ = parse_reference(reference)
            except ValueError as err:
                check.errors.append(f"{where}: save: {err}")
                continue
            if source != step.id:
                check.errors.append(f"{where}: save: '{reference}' is not this step's")


def check_workflow_file(path: str | os.PathLike) -> WorkflowCheck:
    """Read and check a workflow file.

    Args:
        path: The file.

    Returns:
        The check: the definition if there are no errors, else the errors.
    """
    path = Path(path)
    check = WorkflowCheck(path=path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        check.errors.append(f"{path.name}: can't be read ({err})")
        return check
    version = data.get("schema_version", WORKFLOW_SCHEMA_VERSION) if isinstance(data, dict) else None
    if not isinstance(version, int):
        check.errors.append(f"{path.name}: not a workflow file")
        return check
    if version > WORKFLOW_SCHEMA_VERSION:
        check.errors.append(
            f"{path.name}: workflow file version {version} is newer than this"
            f" FLIMAnalyzer (version {WORKFLOW_SCHEMA_VERSION}): update FLIMAnalyzer"
        )
        return check
    try:
        definition = WorkflowDefinition.model_validate(data)
    except ValidationError as err:
        for e in err.errors():
            where = ".".join(str(p) for p in e["loc"])
            check.errors.append(f"{path.name}: {where}: {e['msg']}")
        return check
    check_definition(definition, check)
    if not check.errors:
        check.definition = definition
    return check


def workflow_path(user_path=()) -> list[Path]:
    """Return the folders searched for workflow files, in order.

    Args:
        user_path: The `workflow_paths` of the user settings file.

    Returns:
        The folders of `FLIM_WORKFLOW_PATH` if it is set (separated by `os.pathsep`),
        otherwise `user_path` if it is not empty, otherwise the folder `workflows` in
        the platform's settings folder.
    """
    value = os.environ.get(WORKFLOW_PATH_VAR)
    if value:
        folders = [Path(p) for p in value.split(os.pathsep) if p]
    else:
        folders = [Path(p) for p in user_path] or [default_workflow_dir()]
    return [f.expanduser() for f in folders]


def default_workflow_dir() -> Path:
    """The folder `workflows` in the platform's settings folder."""
    from platformdirs import user_config_dir

    from flim.core.settingsmgr import APP_NAME

    return Path(user_config_dir(APP_NAME, appauthor=False)) / "workflows"


def find_workflow_file(name: str | os.PathLike, search_path=()) -> Path:
    """Resolve the argument of `--workflow`: a path, or a file name in the search path.

    Raises:
        FileNotFoundError: If there is no such file.
    """
    path = Path(name).expanduser()
    if path.is_file():
        return path
    for folder in search_path:
        for candidate in (folder / path, folder / f"{path}.json"):
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"No workflow file '{name}'")


def workflow_files(search_path=()) -> list[Path]:
    """The built-in workflow files and those in the search path's folders."""
    files = sorted(BUILT_IN.glob("*.json")) if BUILT_IN.is_dir() else []
    for folder in search_path:
        if folder.is_dir():
            files += sorted(folder.glob("*.json"))
    return files
