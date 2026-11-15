"""Workflow files: a workflow defined as data, in a file of its own.

A workflow file names its steps; each step is a tool with its own settings, so the
file alone decides what a run does::

    {"schema_version": 1, "name": "calc and aggregate", "tags": ["summaries"],
     "output": {"formats": [{"kind": "table", "format": "csv"}]},
     "steps": [
       {"id": "1", "tool": "Calculate", "config": {...},
        "processing": {"skippable": {"calculations": "some"}}},
       {"id": "2", "tool": "Summarize", "inputs": ["1"], "config": {...},
        "description": "Summary per cell",
        "output": {"save": true, "formats": [{"kind": "plot", "format": "svg"}]}}
     ]}

A step's `inputs` refer to earlier steps' outputs: `"4.1"` (output 1 of step 4), `"4"`
(the same), or `"input"` (the tables the run starts from, e.g. those Import Tables
read from files, or open tables). A step without `inputs` takes output 1 of the step
before it; the first step takes the run's tables. The outputs of a step are numbered
from 1 in the order its tool returns them. A step's `output` says what is saved:
`save` saves its outputs (`true`) or some of them (`["2.1"]`), in its `formats`, else
the workflow's `output.formats` (a kind not listed in its default format). A step's
`description` is a note for readers. A step's `config` may leave out `classname`
(`tool` names the tool); a `classname` of another tool is an error. A step's
`processing` (`flim.core.config.Processing`) says how it treats input that doesn't
match its settings: `strict` (columns not in the input are errors, or guessed),
`skippable` (per field: whether entries that don't apply may be skipped) and
`required` (the entries that have to apply). The workflow's `processing` applies to
every step; a step's fields take precedence, per key.

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
from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from flim import __version__
from flim.core.config import Processing, ProcessingRules
from flim.core.saving import Formats

if TYPE_CHECKING:
    from flim.core.workflow import Workflow

logger = logging.getLogger(__name__)

WORKFLOW_SCHEMA_VERSION = 1
INPUT = "input"  # the reference to the run's tables
IMPORT_CATEGORY = ["File", "Import"]  # the workflows File > Import Tables... offers
BUILT_IN = Path(__file__).resolve().parent.parent / "workflow" / "files"
WORKFLOW_PATH_VAR = "FLIM_WORKFLOW_PATH"


class StepOutput(BaseModel):
    """What a workflow step saves: its `output` section; every field is optional."""

    model_config = ConfigDict(extra="forbid")

    save: Union[bool, list[str]] = Field(
        default=False, description="Save the step's outputs, or those listed."
    )
    formats: Optional[Formats] = Field(
        default=None,
        description="The formats of the saved outputs, per kind; None: the workflow's.",
    )


class WorkflowOutput(BaseModel):
    """A workflow file's `output` section: the defaults of its steps."""

    model_config = ConfigDict(extra="forbid")

    formats: Formats = Field(
        default=[],
        description="The formats of saved outputs, per kind, for steps without their"
        " own; a kind not listed is saved in its default format.",
    )


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
    description: str = Field(default="", description="A note for readers.")
    config: dict = Field(default={}, description="The tool's settings; {}: its defaults.")
    output: StepOutput = Field(default_factory=StepOutput)
    processing: Processing = Field(
        default_factory=Processing,
        description="How the step treats input that doesn't match its settings;"
        " over the workflow's, per key.",
    )

    @field_validator("id", mode="before")
    @classmethod
    def _id_as_text(cls, value: Any) -> Any:
        """Accept a whole number from 1, given as a number or as text, as text."""
        text = str(value).strip() if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
        if not text.isdigit() or int(text) < 1:
            raise ValueError(f"{value!r} is not a whole number from 1")
        return str(int(text))


class WorkflowDefinition(BaseModel):
    """A workflow file's content."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = WORKFLOW_SCHEMA_VERSION
    name: str
    description: str = ""
    category: Union[str, list[str], None] = Field(
        default=None,
        description="Where the GUI shows the workflow: a menu, or a list of a menu and"
        " its submenus, e.g. ['Workflow', 'Summaries']; [] for no menu. None: the"
        " Workflow menu. File > Import Tables... offers the workflows in"
        " ['File', 'Import'].",
    )
    output: WorkflowOutput = Field(default_factory=WorkflowOutput)
    processing: Processing = Field(
        default_factory=Processing,
        description="How the steps treat input that doesn't match their settings;"
        " a step's own fields take precedence, per key.",
    )
    steps: list[WorkflowStep] = Field(min_length=1)

    def rules(self, step: WorkflowStep) -> ProcessingRules:
        """Return a step's `processing`, merged over the workflow's."""
        return ProcessingRules.of(self.processing, step.processing)


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
class WorkflowValidation:
    """The result of `validate_workflow_file`.

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


def _has_field(model: Any, path: str) -> bool:
    """Return whether a config class has a field at a dotted path, e.g. `training.grouping`."""
    from pydantic import BaseModel

    for name in path.split("."):
        fields = getattr(model, "model_fields", {})
        if name not in fields:
            return False
        annotation = fields[name].annotation
        model = annotation if isinstance(annotation, type) and issubclass(annotation, BaseModel) else None
    return True


def processing_issues(
    tool: Any, processing: Processing, config: Any, where: str
) -> tuple[list[str], list[str]]:
    """Validate a step's `processing` against its tool and settings.

    `strict` may name any field of the tool's config; `skippable` and `required` only
    the fields the tool declares (`Tool.skippable_fields`); each `required` entry has
    to be in the field's value (not validated for `features: all`). `strict: false` for
    a field the tool never guesses (`Tool.never_guessed`) is a warning.

    Args:
        tool: The tool class.
        processing: The step's `processing`.
        config: The step's validated config; None if it isn't valid.
        where: The step, for the messages, e.g. `step 02 (Summarize)`.

    Returns:
        The warnings and the errors.
    """
    from flim.core.tool import is_listed

    warnings, errors = [], []
    strict = processing.strict if isinstance(processing.strict, dict) else {}
    for key, value in strict.items():
        if not _has_field(tool.config_class, key):
            errors.append(f"{where}: processing.strict: {tool.name} has no field '{key}'")
        elif value is False and key.split(".")[0] in tool.never_guessed:
            warnings.append(
                f"{where}: processing.strict.{key}: {tool.name} never guesses {key};"
                " it stays strict"
            )
    can_skip = ", ".join(tool.skippable_fields)
    for group in ("skippable", "required"):
        for key in getattr(processing, group):
            if key not in tool.skippable_fields:
                errors.append(
                    f"{where}: processing.{group}: {tool.name} can't skip entries of"
                    f" '{key}' (it can skip entries of: {can_skip})"
                )
    for key, entries in processing.required.items():
        value = getattr(config, key, None) if key in tool.skippable_fields else None
        if value is None or value == "all":
            continue
        present = list(value) if isinstance(value, (list, tuple, dict, set)) else [value]
        for entry in entries:
            if not any(is_listed(p, [entry]) for p in present):
                errors.append(
                    f"{where}: processing.required.{key}: {entry!r} is not an entry of"
                    f" {key}"
                )
    return warnings, errors


def validate_definition(definition: WorkflowDefinition, validation: WorkflowValidation) -> None:
    """Validate a workflow's steps; the problems are added to `validation`.

    Validates that the ids are unique and not `input`, that the inputs refer to earlier
    steps, that the tools exist and their settings are valid, that `save` names
    outputs of its own step, that `output.formats` has only kinds the step's tool
    makes (at workflow level: kinds some step makes, see `step_kinds`), and that
    `processing` names fields of the step's tool (`processing_issues`; at workflow
    level: fields of some step's tool).

    Args:
        definition: The workflow.
        validation: The validation that collects the errors.
    """
    from flim.core.registry import tools

    seen = []
    width = id_width(definition)
    for number, step in enumerate(definition.steps, 1):
        where = f"step {int(step.id):0{width}d}"
        if step.id in seen or step.id == INPUT:
            validation.errors.append(f"{where}: the id '{step.id}' is used twice or reserved")
        inputs = step.inputs or ([seen[-1]] if seen else [INPUT])
        for reference in inputs:
            try:
                source, _ = parse_reference(reference)
            except ValueError as err:
                validation.errors.append(f"{where}: {err}")
                continue
            if source != INPUT and source not in seen:
                validation.errors.append(
                    f"{where}: '{reference}' is not an output of an earlier step"
                )
        seen.append(step.id)
        if step.tool not in tools:
            validation.errors.append(f"{where}: no tool or workflow named '{step.tool}'")
            continue
        tool = tools.get(step.tool)
        classname = step.config.get("classname")
        expected = f"{tool.__module__}.{tool.__qualname__}"
        if classname is not None and classname != expected:
            validation.errors.append(
                f"{where}: config.classname '{classname}' is not the class of"
                f" '{step.tool}' ({expected})"
            )
        config = None
        try:
            config = tool.config_class.model_validate(step.config)
        except ValidationError as err:
            reasons = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
            )
            validation.errors.append(f"{where} ({step.tool}): settings not valid: {reasons}")
        warnings, errors = processing_issues(
            tool, step.processing, config, f"{where} ({step.tool})"
        )
        validation.warnings.extend(warnings)
        validation.errors.extend(errors)
        kinds = tool.output_kinds()
        for options in step.output.formats or []:  # None: not set
            if options.kind not in kinds:
                validation.errors.append(
                    f"{where} ({step.tool}): output.formats: a format of kind"
                    f" '{options.kind}', which {step.tool} doesn't make (it makes:"
                    f" {', '.join(kinds)})"
                )
        save = step.output.save
        for reference in save if isinstance(save, list) else []:
            try:
                source, _ = parse_reference(reference)
            except ValueError as err:
                validation.errors.append(f"{where}: output.save: {err}")
                continue
            if source != step.id:
                validation.errors.append(f"{where}: output.save: '{reference}' is not this step's")
    if all(step.tool in tools for step in definition.steps):
        used = [tools.get(step.tool) for step in definition.steps]
        strict = definition.processing.strict
        for key in strict if isinstance(strict, dict) else {}:
            if not any(_has_field(t.config_class, key) for t in used):
                validation.errors.append(f"processing.strict: no step's tool has a field '{key}'")
        for group in ("skippable", "required"):
            for key in getattr(definition.processing, group):
                if not any(key in t.skippable_fields for t in used):
                    validation.errors.append(
                        f"processing.{group}: no step's tool can skip entries of '{key}'"
                    )
        kinds = step_kinds(definition)
        for options in definition.output.formats or []:
            if options.kind not in kinds:
                validation.errors.append(
                    f"output.formats: a format of kind '{options.kind}', which no step"
                    f" makes (the steps make: {', '.join(kinds)})"
                )


def validate_workflow_file(path: str | os.PathLike, *, tool_files: bool = False) -> WorkflowValidation:
    """Read and validate a workflow file, or with `tool_files` also a tool file.

    Args:
        path: The file.
        tool_files: Also accept a tool file (one tool's settings, written by a tool
            dialog's `Save Settings...`), as a workflow of one step (see
            `tool_file_workflow`). Defaults to False.

    Returns:
        The validation: the definition if there are no errors, else the errors.
    """
    from flim.core.settings import is_tool_file

    path = Path(path)
    validation = WorkflowValidation(path=path)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as err:
        validation.errors.append(f"{path.name}: can't be read ({err})")
        return validation
    if is_tool_file(data):
        if not tool_files:
            validation.errors.append(
                f"{path.name}: a tool file (the settings of {data['tool']}), not a"
                " workflow file"
            )
            return validation
        data = tool_file_workflow(data, validation)
    version = data.get("schema_version", WORKFLOW_SCHEMA_VERSION) if isinstance(data, dict) else None
    if not isinstance(version, int):
        validation.errors.append(f"{path.name}: not a workflow file")
        return validation
    if version > WORKFLOW_SCHEMA_VERSION:
        validation.errors.append(
            f"{path.name}: workflow file schema version {version} is not supported by"
            f" the installed FLIMAnalyzer {__version__} (up to schema version"
            f" {WORKFLOW_SCHEMA_VERSION}). Upgrade FLIMAnalyzer."
        )
        return validation
    try:
        definition = WorkflowDefinition.model_validate(data)
    except ValidationError as err:
        for e in err.errors():
            where = ".".join(str(p) for p in e["loc"])
            validation.errors.append(f"{path.name}: {where}: {e['msg']}")
        return validation
    validate_definition(definition, validation)
    if not validation.errors:
        validation.definition = definition
    return validation


def tool_save_warning(tool: str) -> str:
    """Return the warning for a tool run by flimbatch whose settings have `save: false`.

    Args:
        tool: The tool's name.

    Returns:
        The warning, e.g. `step 01, tool 'Summarize': output.save=false applies in the
        GUI only; flimbatch always saves the results of a tool run`.
    """
    return (
        f"step 01, tool '{tool}': output.save=false applies in the GUI only; flimbatch"
        " always saves the results of a tool run"
    )


def tool_file_workflow(data: dict, validation: WorkflowValidation) -> dict:
    """Return a tool file's data as a workflow file of one step, `1`.

    The workflow is named after the tool, and the step always saves its outputs, as
    `--run <tool>` does: a tool file with `save: false` gets a warning in `validation`.

    Args:
        data: The tool file's data (`tool`, `config`, `output`, `processing`).
        validation: Receives the warning.

    Returns:
        The workflow file's data.
    """
    tool = str(data["tool"])
    output = dict(data.get("output") or {})
    if output.get("save") is False:
        validation.warnings.append(tool_save_warning(tool))
    output["save"] = True
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "name": tool,
        "steps": [{
            "id": "1", "tool": tool, "config": data.get("config") or {}, "output": output,
            "processing": data.get("processing") or {},
        }],
    }  # fmt: skip


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


INPUT_DIM = "input"  # the dimension of the run's tables, before a step joins them


def _mappable(tool: Any, step: WorkflowStep) -> bool:
    """Return whether a step's output is a list of parts (`Tool.mappable_output`)."""
    try:
        return bool(tool.mappable_output(tool.config_class.model_validate(step.config)))
    except Exception:  # invalid settings: reported by the validation
        return False


def _dims(definition: WorkflowDefinition) -> tuple[dict, list[str]]:
    """Return each step's dimensions, the labels that key its outputs, and errors.

    The run's tables have one dimension, the input. A step that takes many tables
    (e.g. Concatenate) joins the input dimension; a step whose output is mappable
    adds a dimension of its own, its parts (`part <step id>`). Any other step maps
    over the dimensions of its source with the most; its other sources must have a
    leading part of those (they are passed whole to each call). Two sources with
    the parts of different steps are an error.

    Args:
        definition: The workflow.

    Returns:
        Step id -> its dimensions (a tuple, e.g. `("input", "part 2")`); and the
        errors.
    """
    from flim.core.registry import tools

    dims, errors, previous = {INPUT: (INPUT_DIM,)}, [], INPUT
    for step in definition.steps:
        references = step.inputs or [previous]
        sources = [dims.get(parse_reference(r)[0], (INPUT_DIM,)) for r in references]
        tool = tools.get(step.tool) if step.tool in tools else None
        if tool is not None and tool.inputs and tool.inputs[0].many:
            own = tuple(d for d in sources[0] if d != INPUT_DIM)
        else:
            own = max(sources, key=len)
            parts = {d for s in sources for d in s if d != INPUT_DIM}
            if any(s != own[: len(s)] for s in sources) and len(parts) > 1:
                errors.append(
                    f"step {step.id}: combines the parts of different steps; use the"
                    " parts of one step"
                )
        if tool is not None and _mappable(tool, step):
            own = own + (f"part {step.id}",)
        dims[step.id] = own
        previous = step.id
    return dims, errors


def part_configs(tool: Any, config: Any, schema: Any = None) -> list:
    """Return the configs of a mappable step's parts (`Tool.map_configs`).

    With `features: all`, the features are taken from the schema of the step's
    input (the columns of the role `feature`), so that there is one part per
    feature; if the schema isn't complete, there is one part with all features.

    Args:
        tool: The tool class.
        config: The step's config.
        schema: The `TableSchema` of the step's (first) input; None if not known.

    Returns:
        The configs, one per part.
    """
    if getattr(config, "features", None) == "all" and schema is not None and schema.complete:
        features = schema.by_role("feature")
        if features:
            config = config.model_copy(update={"features": features})
    return tool().map_configs(config)


def _step_schemas(definition: WorkflowDefinition, schemas: dict) -> dict:
    """Return each step's outputs' schemas, worked out from the run's tables.

    As `validate_steps` does, from the first table's schema; a mappable step's from its
    first part's config (each part has the outputs of one part).

    Args:
        definition: The workflow.
        schemas: The run's tables' schemas (TableSchema) by name.

    Returns:
        Step id -> its outputs' schemas, in order (`INPUT` -> the first table's).
    """
    from flim.core.registry import tools
    from flim.core.schema import TableSchema

    first = next(iter(schemas.values()), None)
    known, previous = {INPUT: [first]}, INPUT
    for step in definition.steps:
        tool = tools.get(step.tool) if step.tool in tools else None
        if tool is None:
            known[step.id] = []
            continue
        inputs = []
        for reference in step.inputs or [previous]:
            source, number = parse_reference(reference)
            outputs = known.get(source) or []
            inputs.append(outputs[number - 1] if number <= len(outputs) else None)
        if tool.inputs and tool.inputs[0].many:
            source = (step.inputs or [previous])[0]
            many = schemas if source == INPUT else {"Input": inputs[0]}
            inputs = [None if None in many.values() else many]
        try:
            config = tool.config_class.model_validate(step.config)
            if _mappable(tool, step):
                config = part_configs(tool, config, inputs[0] if inputs else None)[0]
            specs = list(tool.output_schema(config, inputs).values())
        except Exception:  # the outputs can't be worked out
            specs = []
        known[step.id] = [getattr(s, "schema", None) or TableSchema.unknown() for s in specs]
        previous = step.id
    return known


def id_width(definition: WorkflowDefinition) -> int:
    """Return the number of digits of a workflow's step ids in folder names.

    Args:
        definition: The workflow.

    Returns:
        The digits of the largest step id, at least 2, so that file listings sort
        the step folders by id.
    """
    return max(2, *(len(step.id) for step in definition.steps))


def step_folder(step: WorkflowStep, width: int = 2) -> str:
    """Return the name of a step's results folder, `<id>-<tool>`, e.g. `02-Summarize`.

    The id has leading zeros up to `width` digits (see `id_width`); the runner makes
    the folder name with `flim.core.paths.path_name` (e.g. `03-Order_Category_Values`).

    Args:
        step: The step.
        width: The digits of the id.

    Returns:
        The name.
    """
    return f"{int(step.id):0{width}d}-{step.tool}"


def _leaf(results: dict) -> Any:
    """Return a leaf step's outputs as the GUI takes them.

    One output (no dimension) as it is; else a dict by label, the keys' labels
    joined with ` / ` (e.g. `a.txt / FLIRR`).
    """
    if list(results) == [()]:
        return results[()]
    return {" / ".join(str(k) for k in key): value for key, value in results.items()}


def _saved(step: WorkflowStep) -> Union[bool, list[int]]:
    """A step's `save` as the runner takes it: True, False or output numbers."""
    save = step.output.save
    if isinstance(save, bool):
        return save
    return [parse_reference(r)[1] for r in save]


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
    from flim.core.schema import TableSchema
    from flim.core.types import InputSpec, TableType
    from flim.core.validation import ValidationReport, resolve_step
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
            """Return the errors of steps whose shapes don't fit (`_shapes`, `_dims`)."""
            errors = _shapes(cls.definition)[1] + _dims(cls.definition)[1]
            return [Issue(None, e) for e in errors]

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
            dims, _ = _dims(self.definition)
            # tables read by an earlier task (Import Tables) aren't known yet: unknown
            schemas = _step_schemas(
                self.definition,
                {
                    n: TableSchema.from_frame(t) if hasattr(t, "columns") else TableSchema.unknown()
                    for n, t in tables.items()
                },
            )
            # per step: its outputs keyed by labels, one per dimension (`_dims`), e.g.
            # ("a.txt",), ("a.txt", "FLIRR"), ("FLIRR",) after a join, or ()
            outputs = {
                INPUT: {(name,): workflow_input(t, name, save=False) for name, t in tables.items()}
            }
            previous = INPUT
            width = id_width(self.definition)
            for step in self.definition.steps:
                tool_class = tools.get(step.tool)
                step_config = tool_class.config_class.model_validate(step.config)
                references = step.inputs or [previous]
                sources = []  # (dimensions, outputs by key) per input
                for reference in references:
                    source, number = parse_reference(reference)
                    pick = (lambda v: v) if source == INPUT else (lambda v, n=number: v[Nth(n)])
                    sources.append(
                        (dims[source], {k: pick(v) for k, v in outputs[source].items()})
                    )
                mappable = _mappable(tool_class, step)
                configs = [step_config]
                notes: list[str] = []
                if mappable:
                    first = references[0]
                    source, number = parse_reference(first)
                    known = schemas.get(source) or []
                    schema = known[number - 1] if number <= len(known) else None
                    # missing entries guessed or removed before the parts are made
                    resolution = resolve_step(
                        tool_class, step_config, [schema], self.definition.rules(step)
                    )
                    if not resolution.errors:
                        step_config = resolution.config
                        notes = [f"{g} (guessed)" for g in resolution.guessed]
                        notes += [f"skipped {e}" for e in resolution.skipped]
                    configs = part_configs(tool_class, step_config, schema)

                def call(inputs: list[Any], config: Any, key: tuple) -> Any:
                    tool = tool_class()
                    tool._save = _saved(step)
                    tool._formats = step.output.formats  # None: the workflow's (the run's)
                    tool._processing = self.definition.rules(step)
                    tool._notes = notes  # applied before the run, reported by the run
                    # the results' folders: the step's, then its input and part
                    tags = [step_folder(step, width)] + [str(k) for k in key]
                    return tool(*inputs, config=config, task_tags=tags)

                def run(inputs: list[Any], key: tuple, results: dict) -> None:
                    if not mappable:
                        results[key] = call(inputs, step_config, key)
                        return
                    for config in configs:  # one call per part, keyed by its name
                        part = tool_class.output_prefix(config) or "all"
                        results[key + (part,)] = call(inputs, config, key + (part,))

                results: dict = {}
                if tool_class.inputs and tool_class.inputs[0].many:
                    # joins the input dimension; the parts, if any, stay
                    (source_dims, values) = sources[0]
                    at = source_dims.index(INPUT_DIM) if INPUT_DIM in source_dims else None
                    groups: dict = {}
                    for key, value in values.items():
                        rest = key[:at] + key[at + 1 :] if at is not None else key
                        label = key[at] if at is not None else "Input"
                        groups.setdefault(rest, {})[label] = value
                    for rest, tables_in in groups.items():
                        run([tables_in], rest, results)
                else:
                    # maps over the keys of the source with the most dimensions; the
                    # other sources are passed whole (by the leading part of the key)
                    widest = max(sources, key=lambda s: len(s[0]))
                    for key in widest[1]:
                        inputs = [values[key[: len(d)]] for d, values in sources]
                        run(inputs, key, results)
                outputs[step.id] = results
                previous = step.id
            # the results to show: the outputs no later step uses
            self.leaves = {
                step.id: _leaf(outputs[step.id]) for step in leaf_steps(self.definition)
            }

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
            # None: the Workflow menu (a file written by hand is not hidden silently)
            "category": definition.category if definition.category is not None else "Workflow",
            "output_kinds": classmethod(lambda cls: step_kinds(cls.definition)),
            "__module__": __name__,
        },
    )


def step_kinds(definition: WorkflowDefinition) -> list[str]:
    """Return the kinds of output a workflow's steps make: the union of their tools'.

    Args:
        definition: The workflow.

    Returns:
        The kinds without repeats, in the order of the steps; steps whose tool is
        not registered are passed over.
    """
    from flim.core.registry import tools

    kinds = [k for s in definition.steps if s.tool in tools for k in tools.get(s.tool).output_kinds()]
    return list(dict.fromkeys(kinds))


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
        validation = validate_workflow_file(reference)
        if validation.errors:
            raise ValueError(f"{reference}: " + "; ".join(validation.errors))
        return workflow_class(validation.definition, Path(reference))
    if reference not in tools or not issubclass(tools.get(reference), Workflow):
        raise ValueError(f"No workflow named '{reference}'")
    return tools.get(reference)


def import_workflows() -> list[type["Workflow"]]:
    """Return the workflows Import Tables offers.

    Returns:
        The registered workflow files in File > Import (`IMPORT_CATEGORY`), or all of
        them if none is, sorted by name.
    """
    from flim.core.registry import category_path, tools

    base = _file_workflow_base()
    files = sorted(
        (t for t in tools._tools.values() if issubclass(t, base)), key=lambda t: t.name
    )
    return [t for t in files if category_path(t) == IMPORT_CATEGORY] or files


def register_workflow_files(search_path: Iterable[Path] = ()) -> list[str]:
    """Register the built-in workflow files and those in the search path, by name.

    A file with errors, or whose name a tool or another workflow already has
    (ignoring case), is not registered; the messages are also logged as warnings. A
    file registered before from the same path is registered again. Tool files are
    passed over without a message: they are run by their path or file name.

    Args:
        search_path: The folders (see `workflow_path`).

    Returns:
        A message per file that was not registered.
    """
    from flim.core.registry import tools

    base = _file_workflow_base()
    messages = []
    for path in workflow_files(search_path):
        if _is_tool_file(path):
            continue
        validation = validate_workflow_file(path)
        if validation.errors:
            messages.append(f"{path}: not loaded: {'; '.join(validation.errors)}")
            continue
        name = validation.definition.name
        if name in tools and issubclass(tools.get(name), base) and tools.get(name).path == path:
            tools.unregister(name)  # read again, e.g. after the file changed
        try:
            tools.register(workflow_class(validation.definition, path))
        except ValueError as err:
            messages.append(f"{path}: not loaded: {err}")
    for message in messages:
        logger.warning(message)
    return messages


def _is_tool_file(path: Path) -> bool:
    """Return whether a file is a tool file; False if it can't be read as JSON."""
    from flim.core.settings import is_tool_file

    try:
        return is_tool_file(json.loads(path.read_text()))
    except (OSError, ValueError):
        return False


def validate_steps(definition: WorkflowDefinition, schemas: dict) -> list[str]:
    """Validate a workflow's steps against the tables it would run on, without running it.

    Each step's settings are validated against the columns it gets, as far as they are
    known, with the step's `processing` applied (`flim.core.validation.resolve_step`:
    guesses and skipped entries are not errors); each step's outputs are worked out
    from its inputs and resolved settings (see `Tool.output_schema`).

    Args:
        definition: The workflow.
        schemas: The run's tables' schemas (TableSchema) by name.

    Returns:
        The structure errors (see `_shapes`) and the steps' errors, each naming its
        step and tool.
    """
    from flim.core.registry import tools
    from flim.core.schema import TableSchema
    from flim.core.validation import resolve_step

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
        resolution = resolve_step(tool, config, inputs, definition.rules(step))
        errors += [f"step {step.id} ({step.tool}): {e}" for e in resolution.errors]
        config = resolution.config
        try:
            specs = list(tool.output_schema(config, inputs).values())
        except Exception:  # the outputs can't be worked out: not validated further
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


def save_issues(definition: WorkflowDefinition) -> tuple[list[str], list[str]]:
    """Return what a batch run would not keep of a workflow file's results.

    Args:
        definition: The workflow.

    Returns:
        The warnings: a step whose outputs no later step uses and that doesn't save
        them (its work reaches no one); and the errors: none of the steps saves
        anything (the run would leave only its summary).
    """
    width = id_width(definition)
    warnings = [
        f"step {int(step.id):0{width}d}, tool '{step.tool}': {_save_setting(step)} and no"
        " later step uses its outputs; its results are not saved"
        for step in leaf_steps(definition)
        if not step.output.save
    ]
    errors = []
    if not any(step.output.save for step in definition.steps):
        errors.append(
            f"workflow '{definition.name}': no step saves its outputs; set"
            ' "output": {"save": true} on the steps whose results are to be kept, or run'
            " flimbatch with --save-all"
        )
    return warnings, errors


def _save_setting(step: WorkflowStep) -> str:
    """Return a step's `output.save` as set in the file, or that it is not set."""
    if "output" in step.model_fields_set and "save" in step.output.model_fields_set:
        return "output.save=false"
    return "output.save not set (default: false)"


def saving_all(definition: WorkflowDefinition) -> WorkflowDefinition:
    """Return a workflow whose steps all save all their outputs (`--save-all`).

    Args:
        definition: The workflow.

    Returns:
        A copy with `output.save` true in every step.
    """
    steps = [
        step.model_copy(update={"output": step.output.model_copy(update={"save": True})})
        for step in definition.steps
    ]
    return definition.model_copy(update={"steps": steps})


def window_counts(definition: WorkflowDefinition, schemas: dict) -> dict:
    """Return how many result windows a run would open, by kind (table, plot, image).

    The windows are the leaf steps' outputs, once per table for steps that run per
    table, and once per part below a mappable step (`Tool.mappable_output`). The outputs are worked out from the tables' schemas (see `validate_steps`);
    an output whose kind is not known counts as a table.

    Args:
        definition: The workflow.
        schemas: The run's tables' schemas by name.

    Returns:
        Kind -> number of windows.
    """
    from flim.core.registry import tools
    from flim.core.schema import TableSchema

    dims, _ = _dims(definition)
    parts: dict = {}  # mappable step -> its number of parts
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
        if _mappable(tool, step):
            configs = part_configs(tool, config, inputs[0] if inputs else None)
            parts[step.id] = len(configs)
            config = configs[0]  # each part has the outputs of one part
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
        times = len(schemas) if INPUT_DIM in dims[step.id] else 1
        for dim in dims[step.id]:
            if dim != INPUT_DIM:
                times *= parts.get(dim.removeprefix("part "), 1)
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

    One line per step, e.g. `2. Drop Columns (may skip all drop)`; a step that saves
    its outputs is marked `saved`.
    """
    notes = {"some": "may skip some {}", "all": "may skip all {}"}
    lines = []
    for number, step in enumerate(definition.steps, 1):
        skippable = definition.rules(step).skippable
        extra = [notes[m].format(f) for f, m in skippable.items() if m in notes]
        if step.output.save:
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
        data.pop("version", None)  # the runtime's version is recorded by the run
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
        {"tool": "Rename Columns", "processing": {"skippable": {"replacements": "all"}}, "config": settings("Rename Columns", RenameColumnsConfig)},
        {"tool": "Drop Columns", "processing": {"skippable": {"drop": "all"}}, "config": settings("Drop Columns", DropColumnsConfig)},
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
        fuse.pop("version", None)
        steps.append({"tool": "Fuse Categories", "config": fuse})
    steps.append({"tool": "Calculate", "processing": {"skippable": {"calculations": "all"}}, "output": {"save": True},
                  "config": settings("Calculate", CalculateConfig)})  # fmt: skip
    for number, step in enumerate(steps, 1):
        step["id"] = str(number)
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "name": name,
        "description": "Imports as the import settings of a FLIMAnalyzer 0.6 settings file did.",
        "category": IMPORT_CATEGORY,
        "steps": steps,
    }
