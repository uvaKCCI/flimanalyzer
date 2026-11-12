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

from flim.core.saving import AutosaveConfig

logger = logging.getLogger(__name__)

WORKFLOW_SCHEMA_VERSION = 1
INPUT = "input"  # the reference to the run's tables
IMPORT_TAG = "import"  # the tag of the workflows File > Import... offers
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
    tags: list[str] = Field(
        default=[],
        description="Words that group the workflow: the GUI's File > Import... lists the"
        " workflows tagged 'import'; the Workflow menu groups workflow files by their"
        " first tag.",
    )
    autosave: AutosaveConfig = Field(default_factory=AutosaveConfig)
    steps: list[WorkflowStep] = Field(min_length=1)


def panel_group(definition: WorkflowDefinition, groups) -> Optional[str]:
    """Return the tool panel group a workflow file's tags name, or None.

    Args:
        definition: The workflow.
        groups: The group names, e.g. `File` and the tool categories.

    Returns:
        The first group named by a tag (case is ignored), or None if no tag names
        one.
    """
    by_name = {g.lower(): g for g in groups}
    return next((by_name[t.lower()] for t in definition.tags if t.lower() in by_name), None)


def workflow_group(definition: WorkflowDefinition, groups=()) -> str:
    """Return the label of a workflow file's submenu in the Workflow menu.

    Args:
        definition: The workflow.
        groups: Tags to pass over because they name a tool panel group (see
            `panel_group`).

    Returns:
        The first other tag, with a capital first letter, or `Workflow Files` if
        there is none.
    """
    skip = {g.lower() for g in groups}
    tag = next((t for t in definition.tags if t.lower() not in skip), None)
    if tag is None:
        return "Workflow Files"
    return tag[:1].upper() + tag[1:]


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
            # the results to show: the outputs no later step uses
            self.leaves = {step.id: outputs[step.id] for step in leaf_steps(self.definition)}

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


def resolve_workflow(reference: str):
    """Return the workflow a name or a workflow file's path refers to.

    Args:
        reference: The name of a registered workflow, or the path of a workflow file
            (ending in `.json`).

    Returns:
        The workflow (a tool class).

    Raises:
        ValueError: If no workflow has the name, or the file has errors.
    """
    from flim.core.registry import tools
    from flim.core.workflow import Workflow

    if reference.lower().endswith(".json"):
        check = check_workflow_file(reference)
        if check.errors:
            raise ValueError(f"{reference}: " + "; ".join(check.errors))
        return workflow_class(check.definition, Path(reference))
    if reference not in tools or not issubclass(tools.get(reference), Workflow):
        raise ValueError(f"No workflow named '{reference}'")
    return tools.get(reference)


def import_workflows() -> list:
    """Return the workflows Import Tables offers: the registered workflow files tagged
    `import`, or all of them if none is tagged, by name."""
    from flim.core.registry import tools

    base = _file_workflow_base()
    files = sorted(
        (t for group in tools.by_category().values() for t in group if issubclass(t, base)),
        key=lambda t: t.name,
    )
    return [t for t in files if IMPORT_TAG in t.definition.tags] or files


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


def check_steps(definition: WorkflowDefinition, schemas: dict) -> list[str]:
    """Check a workflow's steps against the tables it would run on, without running
    it: each step's settings against the columns it gets, as far as they are known
    (each step's outputs are worked out from its inputs, see Tool.output_schema).

    Args:
        definition: The workflow.
        schemas: The run's tables' schemas (TableSchema) by name.

    Returns:
        The errors, each naming its step and tool.
    """
    from flim.core.registry import tools
    from flim.core.schema import TableSchema

    shapes, errors = _shapes(definition)
    first = next(iter(schemas.values()), None)
    known = {INPUT: [first]}  # per step: its outputs' schemas, in order
    previous = INPUT
    for step in definition.steps:
        tool = tools.get(step.tool)
        config = tool.config_class.model_validate(step.config)
        inputs = []
        for reference in step.inputs or [previous]:
            source, number = parse_reference(reference)
            outputs = known.get(source) or []
            inputs.append(outputs[number - 1] if number <= len(outputs) else None)
        if tool.inputs and tool.inputs[0].many:
            source = (step.inputs or [previous])[0]
            many = schemas if source == INPUT else {"Input": inputs[0]}
            inputs = [None if None in many.values() else many]
        for issue in tool.validate(config, inputs):
            if issue.severity == "error":
                where = f"{issue.field}: " if issue.field else ""
                errors.append(f"step {step.id} ({step.tool}): {where}{issue.message}")
        try:
            specs = list(tool.output_schema(config, inputs).values())
        except Exception:  # the outputs can't be worked out: not checked further
            specs = []
        known[step.id] = [getattr(s, "schema", None) or TableSchema.unknown() for s in specs]
        previous = step.id
    return errors


def leaf_steps(definition: WorkflowDefinition) -> list[WorkflowStep]:
    """The steps whose outputs no later step uses: the results a run shows."""
    used, previous = set(), INPUT
    for step in definition.steps:
        for reference in step.inputs or [previous]:
            used.add(parse_reference(reference)[0])
        previous = step.id
    return [s for s in definition.steps if s.id not in used]


def window_counts(definition: WorkflowDefinition, schemas: dict) -> dict:
    """How many result windows a run would open, by kind (table, plot, image): the
    leaf steps' outputs, once per table for steps that run per table. The outputs are
    worked out from the tables' schemas (see check_steps); an output whose kind is not
    known counts as a table.

    Args:
        definition: The workflow.
        schemas: The run's tables' schemas by name.

    Returns:
        Kind -> number of windows.
    """
    from flim.core.registry import tools
    from flim.core.schema import TableSchema

    shapes, _ = _shapes(definition)
    first = next(iter(schemas.values()), None)
    known, previous = {INPUT: [(first, "table")]}, INPUT
    for step in definition.steps:
        tool = tools.get(step.tool)
        config = tool.config_class.model_validate(step.config)
        inputs = []
        for reference in step.inputs or [previous]:
            source, number = parse_reference(reference)
            outputs = known.get(source) or []
            inputs.append(outputs[number - 1][0] if number <= len(outputs) else None)
        if tool.inputs and tool.inputs[0].many:
            source = (step.inputs or [previous])[0]
            many = schemas if source == INPUT else {"Input": inputs[0]}
            inputs = [None if None in many.values() else many]
        try:
            specs = list(tool.output_schema(config, inputs).values())
        except Exception:
            specs = list(tool.outputs)
        known[step.id] = [
            (getattr(s, "schema", None) or TableSchema.unknown(), getattr(s.type, "kind", "table"))
            for s in specs
        ] or [(TableSchema.unknown(), "table")]
        previous = step.id
    counts: dict = {}
    for step in leaf_steps(definition):
        times = len(schemas) if shapes[step.id] == MAPPED else 1
        for _, kind in known[step.id]:
            counts[kind] = counts.get(kind, 0) + times
    return counts


def too_many_windows(counts: dict, limits: dict) -> list[str]:
    """The kinds over their limit, as messages, e.g. `300 tables (most: 10)`."""
    return [
        f"{n} {kind}s (most: {limits[kind]})"
        for kind, n in counts.items()
        if kind in limits and n > limits[kind]
    ]


def describe_steps(definition: WorkflowDefinition) -> str:
    """The steps of a workflow as text, one line each, e.g. `2. Drop Columns (may
    apply nothing)`, for showing a workflow before it runs."""
    notes = {"allow_partial": "may apply only some settings", "allow_none": "may apply nothing"}
    lines = []
    for number, step in enumerate(definition.steps, 1):
        extra = [notes[step.processing]] if step.processing in notes else []
        if step.save:
            extra.append("saved")
        lines.append(f"{number}. {step.tool}" + (f" ({', '.join(extra)})" if extra else ""))
    return "\n".join(lines)


def import_read_settings(section: dict) -> dict:
    """Return how a FLIMAnalyzer 0.6 settings file's `import` section read the files.

    Args:
        section: The `import` section (version 1).

    Returns:
        The read settings that differ from the defaults (`delimiter`, `exclude`), in
        the format of Import Tables' settings.
    """
    settings = {}
    if section.get("delimiter", "\t,") != "\t,":
        settings["delimiter"] = section["delimiter"]
    if section.get("exclude_files"):
        settings["exclude"] = list(section["exclude_files"])
    return settings


def import_workflow_data(section: dict, tools_data: dict, name: str) -> dict:
    """The content of a workflow file that processes tables as the `import` settings
    of a FLIMAnalyzer 0.6 settings file did: rename and drop columns, join the files'
    tables, take the categories of its filename parser from the paths, fuse its
    column combinations, calculate. How the files are read is `import_read_settings`.

    Args:
        section: The file's `import` section (version 1).
        tools_data: The file's `tools` section (current version): the Rename Columns,
            Drop Columns and Calculate settings; defaults where it has none.
        name: The workflow's name.

    Returns:
        The workflow file's content (JSON data).
    """
    from flim.configs import (
        CalculateConfig, ConcatConfig, DropColumnsConfig, FuseCategoriesConfig,
        RenameColumnsConfig, SeparateCategoriesConfig,
    )  # fmt: skip
    from flim.configs.data import CategoryPattern
    from flim.core.parser import PATTERN_CATEGORY, PATTERN_REGEX, PATTERN_USE, instantiate_parser

    def settings(tool, config_class):
        config = (tools_data.get(tool) or {}).get("config")
        try:
            value = config_class.model_validate(config) if config else config_class()
        except ValidationError:
            value = config_class()
        data = value.model_dump(mode="json")
        for key in ("classname", "version"):
            data.pop(key, None)
        return data

    parser_section = section.get("filename_parser") or {}
    patterns = list(parser_section.get("patterns") or [])
    if not patterns:
        parser = instantiate_parser(f"flim.core.parser.{parser_section.get('parser', 'defaultparser')}")
        patterns = parser.get_regexpatterns() if parser is not None else []
    patterns = [p for p in patterns if p.get(PATTERN_USE, True)]
    steps = [
        {"tool": "Rename Columns", "processing": "allow_none", "config": settings("Rename Columns", RenameColumnsConfig)},
        {"tool": "Drop Columns", "processing": "allow_none", "config": settings("Drop Columns", DropColumnsConfig)},
        {"tool": "Concatenate", "config": settings("", ConcatConfig) | {"add_input": False}},
    ]
    if patterns:
        separate = SeparateCategoriesConfig(
            column="Source", mode="patterns",
            patterns=[CategoryPattern(name=p[PATTERN_CATEGORY], regex=p[PATTERN_REGEX]) for p in patterns],
        ).model_dump(mode="json")  # fmt: skip
        separate.pop("classname", None)
        separate.pop("version", None)
        steps.append({"tool": "Separate Categories", "config": separate})
    for pair in section.get("category_combinations") or []:
        fuse = FuseCategoriesConfig(grouping=list(pair)).model_dump(mode="json")
        fuse.pop("classname", None)
        fuse.pop("version", None)
        steps.append({"tool": "Fuse Categories", "config": fuse})
    steps.append({"tool": "Calculate", "processing": "allow_none", "save": True,
                  "config": settings("Calculate", CalculateConfig)})  # fmt: skip
    for number, step in enumerate(steps, 1):
        step["id"] = str(number)
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "name": name,
        "description": "Imports as the import settings of a FLIMAnalyzer 0.6 settings file did.",
        "tags": [IMPORT_TAG],
        "steps": steps,
    }
