"""Workflow files: a workflow defined as data, in a file of its own.

A workflow file names its steps; each step is a tool with its own settings, so the
file alone decides what a run does::

    {"schema_version": 1, "name": "calc and aggregate", "tags": ["summaries"],
     "autosave": {"formats": []},
     "steps": [
       {"id": "1", "tool": "Calculate", "config": {...}, "processing": "allow_partial"},
       {"id": "2", "tool": "Summarize", "inputs": ["1"], "config": {...}, "save": true}
     ]}

A step's `inputs` refer to earlier steps' outputs: `"4.1"` (output 1 of step 4), `"4"`
(the same), or `"input"` (the tables the run starts from, e.g. those Import Tables
read from files, or open tables). A step without `inputs` takes output 1 of the step
before it; the first step takes the run's tables. The outputs of a step are numbered
from 1 in the order its tool returns them. `outputs` optionally names them (for
readers; not checked). `save` saves a step's outputs (`true`) or some of them
(`["2.1"]`). `processing` says how much of its
settings a step must apply to the data: `require_all` (default), `allow_partial` (at
least one part) or `allow_none`.

Workflow files are registered by their `name` like tools: the built-in files (in
`flim/workflow/files`) and those in the folders of the `workflow_paths` setting.
"""

import itertools
import json
import logging
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from flim.core.saving import AutosaveConfig

if TYPE_CHECKING:
    from flim.core.workflow import Workflow

logger = logging.getLogger(__name__)

WORKFLOW_SCHEMA_VERSION = 1
INPUT = "input"  # the reference to the run's tables
IMPORT_TAG = "import"  # the tag of the workflows File > Import Tables... offers
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
        default={}, description="Names of the outputs by number, for readers; not checked."
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
    def _id_as_text(cls, value: Any) -> Any:
        """Accept a number as the id, as text."""
        return str(value) if isinstance(value, int) else value


class WorkflowDefinition(BaseModel):
    """A workflow file's content."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = WORKFLOW_SCHEMA_VERSION
    name: str
    description: str = ""
    tags: list[str] = Field(
        default=[],
        description="Words that group the workflow. File > Import Tables... lists the"
        " workflows tagged 'import'; a tag naming a menu (file, data, analysis, plot,"
        " workflow) puts the workflow in that menu, else in Workflow; the next tag names"
        " its submenu.",
    )
    autosave: AutosaveConfig = Field(default_factory=AutosaveConfig)
    steps: list[WorkflowStep] = Field(min_length=1)


def panel_group(definition: WorkflowDefinition, groups: Iterable[str]) -> Optional[str]:
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


def workflow_group(definition: WorkflowDefinition, groups: Iterable[str] = ()) -> str:
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

    Args:
        reference: `<step id>.<output number>`, `<step id>` (output 1), or `input`.

    Returns:
        The step id (`input` for the run's tables) and the output number, from 1.

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
    """Check a workflow's steps; the problems are added to `check`.

    Checks that the ids are unique and not `input`, that the inputs refer to earlier
    steps, that the tools exist and their settings are valid, and that `save` names
    outputs of its own step.

    Args:
        definition: The workflow.
        check: The check that collects the errors.
    """
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


def workflow_path(
    user_path: Iterable[str | os.PathLike] = (),
    folders: Iterable[str | os.PathLike] = (),
) -> list[Path]:
    """Return the folders searched for workflow files, in order.

    Args:
        user_path: The `workflow_paths` of the user settings file.
        folders: The folders given with `-w`/`--workflow-path`.

    Returns:
        `folders` if not empty; otherwise the folders of `FLIM_WORKFLOW_PATH` if it is
        set (separated by `os.pathsep`); otherwise `user_path` if it is not empty;
        otherwise the folder `workflows` in the platform's settings folder. `~` is
        expanded.
    """
    chosen = [Path(p) for p in folders]
    if not chosen:
        value = os.environ.get(WORKFLOW_PATH_VAR)
        if value:
            chosen = [Path(p) for p in value.split(os.pathsep) if p]
        else:
            chosen = [Path(p) for p in user_path] or [default_workflow_dir()]
    return [f.expanduser() for f in chosen]


def is_workflow_file(name: str | os.PathLike) -> bool:
    """Return whether a `--run` argument names a workflow file rather than a tool.

    Args:
        name: The argument.

    Returns:
        True if it contains a folder separator or ends with `.json` (any case).
    """
    text = str(name)
    separators = {"/", os.sep} | ({os.altsep} if os.altsep else set())
    return text.lower().endswith(".json") or any(s in text for s in separators)


def default_workflow_dir() -> Path:
    """Return the folder `workflows` in the platform's settings folder."""
    from platformdirs import user_config_dir

    from flim.core.settingsmgr import APP_NAME

    return Path(user_config_dir(APP_NAME, appauthor=False)) / "workflows"


def find_workflow_file(
    name: str | os.PathLike, search_path: Iterable[Path] = ()
) -> Path:
    """Resolve a workflow file given to `--run`: a path, or a file name in the search path.

    Args:
        name: The path of a file (`~` is expanded), or a file name, with or without
            `.json`, in a folder of the search path.
        search_path: The folders, searched in order.

    Returns:
        The file.

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


def workflow_files(search_path: Iterable[Path] = ()) -> list[Path]:
    """Return the built-in workflow files and those in the search path's folders.

    Args:
        search_path: The folders; a folder that doesn't exist is passed over.

    Returns:
        The `.json` files, the built-in ones first, sorted by name per folder.
    """
    files = sorted(BUILT_IN.glob("*.json")) if BUILT_IN.is_dir() else []
    for folder in search_path:
        if folder.is_dir():
            files += sorted(folder.glob("*.json"))
    return files


# --- running workflow files ---------------------------------------------------------

MAPPED, SINGLE = "per table", "one table"


def _shapes(definition: WorkflowDefinition) -> tuple[dict, list[str]]:
    """Return per step whether it runs once per table (mapped) or once, and errors.

    The errors are those of steps that are workflows, that give a tool taking many
    tables more than one input, or that combine the two shapes. The run's tables
    are mapped; a step whose input takes many tables (e.g. Concatenate) makes one
    table of them.
    """
    from flim.core.registry import tools
    from flim.core.workflow import Workflow

    shapes, errors, previous = {INPUT: MAPPED}, [], INPUT
    for step in definition.steps:
        references = step.inputs or [previous]
        sources = {shapes.get(parse_reference(r)[0], MAPPED) for r in references}
        tool = tools.get(step.tool) if step.tool in tools else None
        if tool is not None and issubclass(tool, Workflow):
            errors.append(f"step {step.id}: a step can't be a workflow")
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


def _saved(step: WorkflowStep) -> Union[bool, list[int]]:
    """A step's `save` as the runner takes it: True, False or output numbers."""
    if isinstance(step.save, bool):
        return step.save
    return [parse_reference(r)[1] for r in step.save]


def _file_workflow_base() -> type["Workflow"]:
    """Return the base class of workflows defined by files, created on first use.

    It is created on first use because it needs the Workflow class, which imports
    much of the core.
    """
    global FileWorkflow
    if "FileWorkflow" in globals():
        return FileWorkflow
    from flim.configs.workflow import WorkflowConfig
    from flim.core.config import Issue, TaskConfig
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
        def is_strict(
            cls, config: TaskConfig, default: Optional[bool] = None
        ) -> bool:
            """Return True: workflow files never guess columns."""
            return True  # workflow files never guess columns

        @classmethod
        def structure_issues(cls) -> list[Issue]:
            """Return the errors of steps whose shapes don't fit (see `_shapes`)."""
            return [Issue(None, e) for e in _shapes(cls.definition)[1]]

        def resolve(
            self,
            config: FileWorkflowConfig,
            inputs: Sequence[Any],
            strict: Optional[bool] = None,
        ) -> ValidationReport:
            """Return a report of the structure errors; the steps are not traced."""
            return ValidationReport(config=config, issues=self.structure_issues())

        @classmethod
        def validate(
            cls,
            config: FileWorkflowConfig,
            inputs: Sequence[Any],
            strict: Optional[bool] = None,
        ) -> list[Issue]:
            """Return the structure errors (see `structure_issues`)."""
            return cls.structure_issues()

        def build(self, tables: Any, *, config: FileWorkflowConfig) -> None:
            """Call the steps' tools, per table or once; `leaves` gets the results.

            `tables` is a dict of tables by name, or one table.
            """
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

                def call(inputs: list[Any], tags: list[str]) -> Any:
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


def workflow_class(
    definition: WorkflowDefinition, path: Optional[Path] = None
) -> type["Workflow"]:
    """Return a workflow class (a tool) that runs a workflow file's steps.

    Args:
        definition: The workflow.
        path: Its file; None if it has none.

    Returns:
        A new class, named after the workflow, with its name and description.
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


def resolve_workflow(reference: str) -> type["Workflow"]:
    """Return the workflow a name or a workflow file's path refers to.

    Args:
        reference: The name of a registered workflow, or the path of a workflow file
            (with the extension `.json`).

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


def import_workflows() -> list[type["Workflow"]]:
    """Return the workflows Import Tables offers.

    Returns:
        The registered workflow files tagged `import`, or all of them if none is
        tagged, sorted by name.
    """
    from flim.core.registry import tools

    base = _file_workflow_base()
    files = sorted(
        (t for group in tools.by_category().values() for t in group if issubclass(t, base)),
        key=lambda t: t.name,
    )
    return [t for t in files if IMPORT_TAG in t.definition.tags] or files


def register_workflow_files(search_path: Iterable[Path] = ()) -> list[str]:
    """Register the built-in workflow files and those in the search path, by name.

    A file with errors, or whose name a tool or another workflow already has
    (ignoring case), is not registered; the messages are also logged as warnings. A
    file registered before from the same path is registered again.

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
    """Check a workflow's steps against the tables it would run on, without running it.

    Each step's settings are checked against the columns it gets, as far as they are
    known (each step's outputs are worked out from its inputs, see
    `Tool.output_schema`).

    Args:
        definition: The workflow.
        schemas: The run's tables' schemas (TableSchema) by name.

    Returns:
        The structure errors (see `_shapes`) and the steps' errors, each naming its
        step and tool.
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
    """Return the steps whose outputs no later step uses: the results a run shows."""
    used, previous = set(), INPUT
    for step in definition.steps:
        for reference in step.inputs or [previous]:
            used.add(parse_reference(reference)[0])
        previous = step.id
    return [s for s in definition.steps if s.id not in used]


def window_counts(definition: WorkflowDefinition, schemas: dict) -> dict:
    """Return how many result windows a run would open, by kind (table, plot, image).

    The windows are the leaf steps' outputs, once per table for steps that run per
    table. The outputs are worked out from the tables' schemas (see `check_steps`);
    an output whose kind is not known counts as a table.

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
    """Return the kinds over their limit, as messages, e.g. `300 tables (most: 10)`.

    Args:
        counts: The number of windows by kind (see `window_counts`).
        limits: The most windows by kind; a kind not listed has no limit.

    Returns:
        A message per kind over its limit.
    """
    return [
        f"{n} {kind}s (most: {limits[kind]})"
        for kind, n in counts.items()
        if kind in limits and n > limits[kind]
    ]


def describe_steps(definition: WorkflowDefinition) -> str:
    """Return the steps of a workflow as text, for showing it before it runs.

    One line per step, e.g. `2. Drop Columns (may apply nothing)`; a step that saves
    its outputs is marked `saved`.
    """
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


# the built-in Separate Categories preset of each filename parser of 0.6
PARSER_PRESETS = {
    "celltype_compartment_fov_treatment_cell_parser": "Cell line, Compartment, FOV, Treatment, Cell",
    "compartment_fov_treatment_cell_parser": "Compartment, FOV, Treatment, Cell",
    "compartment_treatment_fov_cell_parser": "Compartment, Treatment, FOV, Cell",
    "fov_time_well_parser": "FOV, Time, Well",
    "fov_treatment_cell_parser": "FOV, Treatment, Cell",
    "treatment_fov_cell_parser": "Treatment, FOV, Cell",
    "treatment_fov_time_parser": "Treatment, FOV, Time",
    "treatment_time_parser": "Treatment, Time",
}


def import_workflow_data(section: dict, tools_data: dict, name: str) -> dict:
    """Return a workflow file that processes tables as a 0.6 settings file's `import`.

    The workflow does what the `import` settings of a FLIMAnalyzer 0.6 settings file
    did: rename and drop columns, join the files' tables, take the categories of its
    filename parser from the paths, fuse its column combinations, calculate. An
    empty `category_combinations` list fuses all pairs of the parser's categories
    (0.6 took all pairs of the text category columns of the first file). How the
    files are read is `import_read_settings`.

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
    from flim.core.categories import separate_presets

    def settings(tool: str, config_class: type[BaseModel]) -> dict[str, Any]:
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
    # a pattern of a 0.6 file: {"Use": bool, "Category": column, "Regex": regex}
    patterns = [
        {"name": p["Category"], "regex": p["Regex"]}
        for p in parser_section.get("patterns") or []
        if p.get("Use", True)
    ]
    if not patterns:
        preset = PARSER_PRESETS.get(parser_section.get("parser", "defaultparser"))
        presets = {p["name"]: p["settings"]["patterns"] for p in separate_presets()}
        patterns = list(presets.get(preset, []))
    steps = [
        {"tool": "Rename Columns", "processing": "allow_none", "config": settings("Rename Columns", RenameColumnsConfig)},
        {"tool": "Drop Columns", "processing": "allow_none", "config": settings("Drop Columns", DropColumnsConfig)},
        {"tool": "Concatenate", "config": settings("", ConcatConfig) | {"add_input": False}},
    ]
    if patterns:
        separate = SeparateCategoriesConfig(
            column="Source", mode="pattern",
            patterns=[CategoryPattern(**p) for p in patterns],
        ).model_dump(mode="json")  # fmt: skip
        separate.pop("classname", None)
        separate.pop("version", None)
        steps.append({"tool": "Separate Categories", "config": separate})
    pairs = section.get("category_combinations")
    if pairs == []:  # in 0.6: all pairs of the category columns
        pairs = list(itertools.combinations([p["name"] for p in patterns], 2))
    for pair in pairs or []:
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
