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


# --- running workflow files ---------------------------------------------------------

MAPPED, SINGLE = "per table", "one table"


def _shapes(definition: WorkflowDefinition) -> tuple[dict, list[str]]:
    """Work out, per step, whether it runs once per table (mapped) or once, and the
    errors of steps that combine the two. The run's tables are mapped; a step whose
    input takes many tables (e.g. Concatenate) makes one table of them."""
    from flim.core.registry import tools
    from flim.core.workflow import Workflow

    shapes, errors, previous = {INPUT: MAPPED}, [], INPUT
    for step in definition.steps:
        references = step.inputs or [previous]
        sources = {shapes.get(parse_reference(r)[0], MAPPED) for r in references}
        tool = tools.get(step.tool) if step.tool in tools else None
        if tool is not None and issubclass(tool, Workflow):
            errors.append(f"step {step.id}: workflows as steps are not supported yet")
        if tool is not None and tool.inputs and tool.inputs[0].many:
            if len(references) != 1:
                errors.append(f"step {step.id}: {step.tool} takes one input, the tables")
            shapes[step.id] = SINGLE
        elif len(sources) > 1:
            errors.append(
                f"step {step.id}: combines tables per file with a single table;"
                " reduce them first (e.g. Concatenate)"
            )
            shapes[step.id] = SINGLE
        else:
            shapes[step.id] = sources.pop()
        previous = step.id
    return shapes, errors


def _saved(step: WorkflowStep):
    """A step's `save` as the runner takes it: True, False or output numbers."""
    if isinstance(step.save, bool):
        return step.save
    return [parse_reference(r)[1] for r in step.save]


def _file_workflow_base():
    """The base class of workflows defined by files (created on first use: it needs
    the Workflow class, which imports much of the core)."""
    global FileWorkflow
    if "FileWorkflow" in globals():
        return FileWorkflow
    from flim.configs.workflow import WorkflowConfig
    from flim.core.config import Issue
    from flim.core.registry import tools
    from flim.core.runner import Nth
    from flim.core.types import InputSpec, TableType
    from flim.core.validation import ValidationReport
    from flim.core.workflow import Workflow, workflow_input

    class FileWorkflowConfig(WorkflowConfig):
        """A workflow file's run settings: the steps carry their own."""

        hidden_fields = frozenset({"prefix", "strict", "grouping", "features"})

    class _FileWorkflow(Workflow[FileWorkflowConfig]):
        """A workflow defined by a workflow file (`definition`)."""

        definition = None  # WorkflowDefinition, set per file
        path = None  # the file
        inputs = (InputSpec("tables", TableType, many=True),)

        @classmethod
        def is_strict(cls, config, default=None) -> bool:
            return True  # workflow files never guess columns

        @classmethod
        def structure_issues(cls) -> list:
            return [Issue(None, e) for e in _shapes(cls.definition)[1]]

        def resolve(self, config, inputs, strict=None):
            return ValidationReport(config=config, issues=self.structure_issues())

        @classmethod
        def validate(cls, config, inputs, strict=None):
            return cls.structure_issues()

        def build(self, tables, *, config):
            if not isinstance(tables, dict):
                tables = {"Input": tables}
            shapes, _ = _shapes(self.definition)
            outputs = {
                INPUT: {name: workflow_input(t, name, save=False) for name, t in tables.items()}
            }
            previous = INPUT
            for step in self.definition.steps:
                tool_class = tools.get(step.tool)
                step_config = tool_class.config_class.model_validate(step.config)
                sources = []
                for reference in step.inputs or [previous]:
                    source, number = parse_reference(reference)
                    value = outputs[source]
                    pick = (lambda v: v) if source == INPUT else (lambda v, n=number: v[Nth(n)])
                    if isinstance(value, dict):
                        sources.append({k: pick(v) for k, v in value.items()})
                    else:
                        sources.append(pick(value))

                def call(inputs, tags):
                    tool = tool_class()
                    tool._save = _saved(step)
                    tool._processing = step.processing
                    return tool(*inputs, config=step_config, task_tags=tags)

                if tool_class.inputs and tool_class.inputs[0].many:
                    (source,) = sources
                    tables_in = source if isinstance(source, dict) else {"Input": source}
                    outputs[step.id] = call([tables_in], [step.id])
                elif shapes[step.id] == MAPPED:
                    names = list(sources[0])
                    outputs[step.id] = {
                        name: call([s[name] for s in sources], [name]) for name in names
                    }
                else:
                    outputs[step.id] = call(sources, [step.id])
                previous = step.id

    FileWorkflow = _FileWorkflow
    return FileWorkflow


def workflow_class(definition: WorkflowDefinition, path: Optional[Path] = None):
    """Return a workflow class (a tool) that runs a workflow file's steps.

    Args:
        definition: The workflow.
        path: Its file.
    """
    base = _file_workflow_base()
    name = "".join(c for c in definition.name.title() if c.isalnum()) or "Workflow"
    return type(
        f"{name}FileWorkflow",
        (base,),
        {
            "name": definition.name,
            "description": definition.description or f"Workflow file {getattr(path, 'name', '')}",
            "definition": definition,
            "path": path,
            "__module__": __name__,
        },
    )


def register_workflow_files(search_path=()) -> list[str]:
    """Register the built-in workflow files and those in the search path, by name.

    A file with errors, or whose name a tool or another workflow already has
    (ignoring case), is not registered.

    Args:
        search_path: The folders (see `workflow_path`).

    Returns:
        A message per file that was not registered.
    """
    from flim.core.registry import tools

    base = _file_workflow_base()
    messages = []
    for path in workflow_files(search_path):
        check = check_workflow_file(path)
        if check.errors:
            messages.append(f"{path}: not loaded: {'; '.join(check.errors)}")
            continue
        name = check.definition.name
        if name in tools and issubclass(tools.get(name), base) and tools.get(name).path == path:
            tools.unregister(name)  # read again, e.g. after the file changed
        try:
            tools.register(workflow_class(check.definition, path))
        except ValueError as err:
            messages.append(f"{path}: not loaded: {err}")
    for message in messages:
        logger.warning(message)
    return messages
