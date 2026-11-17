"""Validation of workflows before they run.

The default validator (`DefaultWorkflowValidator`) does a dry run of the
workflow's `build`: on
sample tables made from the input schemas, with every tool call traced instead of run.
Each step's config is validated against the schemas of its inputs (`Tool.validate`),
and its output schemas (`Tool.output_schema`) are passed to the steps that use them.

Columns the workflow config names that are not in the input are replaced by a guess
(the closest column of the same role) where the tool's `processing` isn't strict, or
removed where it lets the field skip them; the run then uses the resolved config. Steps whose inputs are not known before the run (e.g. the
models a training step saves) are not validated.
"""

import ast
import contextvars
import dataclasses
import difflib
import re
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional, Protocol, Union

import pandas as pd

from flim.core.config import Issue, TaskConfig, column_references
from flim.core.runner import TaskOutput
from flim.core.schema import TableSchema

if TYPE_CHECKING:
    from flim.core.config import ProcessingRules
    from flim.core.tool import Tool
    from flim.core.workflow import Workflow

_TRACER: contextvars.ContextVar = contextvars.ContextVar("flim_tracer", default=None)


@dataclass
class StepReport:
    """The validation of one step (tool call) of a workflow in a dry run.

    Attributes:
        name: The tool's name, with the step's tags.
        tool: The tool class.
        config: The step's config.
        inputs: The schemas of the step's inputs; None for an unknown one.
        outputs: The step's outputs: output name (with the config's prefix) ->
            `OutputSpec`.
        issues: The problems of the step's config.
    """

    name: str  # the tool's name, with the step's tags
    tool: type
    config: Optional[TaskConfig]
    inputs: list  # input schemas (None: unknown)
    outputs: dict  # output name -> OutputSpec
    issues: list[Issue] = field(default_factory=list)


@dataclass
class ValidationReport:
    """The result of validating a workflow.

    Attributes:
        config: The workflow config, with the guesses applied.
        issues: The issues of the workflow and its steps.
        steps: The validated steps; empty if an input is unknown.
    """

    config: TaskConfig  # the workflow config, with the guesses applied
    issues: list[Issue] = field(default_factory=list)  # of the workflow and its steps
    steps: list[StepReport] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        """Return the issues of severity `error`."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def guesses(self) -> list[Issue]:
        """Return the issues of severity `guessed`: replaced columns."""
        return [i for i in self.issues if i.severity == "guessed"]

    @property
    def skipped(self) -> list[Issue]:
        """Return the issues of severity `skipped`: removed entries."""
        return [i for i in self.issues if i.severity == "skipped"]


def resolution_notes(report: ValidationReport, prefix: str = "") -> list[str]:
    """Return the run summary's lines for a report's guesses and skipped entries.

    Args:
        report: The report.
        prefix: Text before each line, e.g. the table's name and a colon.

    Returns:
        The lines, e.g. ``features[0]: 'FAD a1' -> 'FAD a1%' (guessed)`` and
        ``features[2]: 'FLIRR' (skipped, not in the input)``.
    """
    def where(issue: Issue) -> str:
        return f"{prefix}{issue.step + ': ' if issue.step else ''}{issue.field}"

    return [f"{where(i)}: '{i.old}' -> '{i.suggestion}' (guessed)" for i in report.guesses] + [
        f"{where(i)}: '{i.old}' (skipped, not in the input)" for i in report.skipped
    ]


class WorkflowValidator(Protocol):
    """The interface of a workflow's validator (`Workflow.validator`)."""

    def validate(
        self,
        workflow: type["Workflow"],
        config: TaskConfig,
        inputs: list[Optional[TableSchema]],
        processing: "ProcessingRules",
    ) -> ValidationReport:
        """Validate a workflow config against the schemas of the input tables.

        Args:
            workflow: The workflow class.
            config: The workflow's config.
            inputs: The schemas of the input tables; None for an unknown one.
            processing: How columns missing from the inputs are treated (the
                tool's `processing`): errors, guesses or skipped entries.

        Returns:
            The report, with the config the run uses.
        """
        ...


# --- guesses ---

# the fields whose missing entries are removed before a tool runs (`processing.skippable`)
REMOVED_ENTRIES = ("grouping", "features")
_MISSING = re.compile(r"Column '(.*)' is not in the input")


def _field_of(path: str) -> str:
    """Return the top-level field of a path, e.g. `features` of `features[2]`."""
    return re.split(r"[\[.]", path, maxsplit=1)[0]


def _key(name: str) -> str:
    """Return a column name in lower case without spaces, brackets, `_` and `-`.

    Names with the same key are the same column apart from case and punctuation:
    `FAD a1[%]` and `fad a1%` are the same, `FAD a1` is not.
    """
    return re.sub(r"[\s\[\](){}_\-]", "", str(name).lower())


def guess_column(name: str, candidates: list[str]) -> tuple[Optional[str], str]:
    """Return the column of `candidates` that `name` most likely means.

    The guess is the one candidate that is the same name apart from case, spaces and
    punctuation (`FAD a1%`, `FAD a1[%]`), else the closest name with a similarity
    ratio of at least 0.75, unless the second closest is about as similar (a
    difference of the ratios below 0.02).

    Args:
        name: The column name that is not in the input.
        candidates: The input's column names of the same role.

    Returns:
        The guess and an empty text; or None and why there is no guess.
    """
    same = [c for c in candidates if _key(c) == _key(name)]
    if len(same) == 1:
        return same[0], ""
    if len(same) > 1:
        return None, f"several columns match: {', '.join(same)}"
    close = difflib.get_close_matches(str(name), candidates, n=2, cutoff=0.75)
    if not close:
        return None, "no similar column"
    if len(close) > 1:
        ratios = [difflib.SequenceMatcher(None, str(name), c).ratio() for c in close]
        if abs(ratios[0] - ratios[1]) < 0.02:
            return None, f"ambiguous: {close[0]} or {close[1]}"
    return close[0], ""


_PATH = re.compile(r"\.?([A-Za-z_]\w*)|\[(\d+)\]|\[('(?:[^']|\\')*'|\"[^\"]*\")\]")


def replace_at(config: TaskConfig, path: str, value: str) -> TaskConfig:
    """Return a copy of a config with the column named at a path replaced.

    The new name is set without validation. A dict key is replaced in place of the
    old key, so the order of the dict is kept.

    Args:
        config: The config (not changed).
        path: The path of the column name, as `column_references` gives it, e.g.
            `features[2]`, `training.grouping[0]` or `ranges['FLIRR']` (a dict key).
        value: The new column name.

    Returns:
        The changed copy.
    """
    config = config.model_copy(deep=True)
    parts = [m.groups() for m in _PATH.finditer(path)]
    target = config
    for attr, index, key in parts[:-1]:
        if attr:
            target = getattr(target, attr)
        elif index is not None:
            target = target[int(index)]
        else:
            target = target[ast.literal_eval(key)]  # repr()'d, see column_references
    attr, index, key = parts[-1]
    if attr:
        object.__setattr__(target, attr, value)  # no validation: a column name
    elif index is not None:
        target[int(index)] = value
    else:
        old = ast.literal_eval(key)
        items = list(target.items())
        target.clear()
        target.update({value if k == old else k: v for k, v in items})
    return config


# --- dry runs ---


class TraceOutput(TaskOutput):
    """The outputs of a traced tool call: their schemas, not their values."""

    def __init__(self, outputs: dict, node: str, keys: tuple = ()) -> None:
        """Create the handle of a traced call's outputs.

        Args:
            outputs: Output name -> `OutputSpec`.
            node: The step's name.
            keys: The keys selected so far, e.g. `("Summary",)`.
        """
        super().__init__(outputs, node, keys)

    def __getitem__(self, key: Any) -> "TraceOutput":
        """Return the handle of an item of the outputs."""
        return TraceOutput(self.ref, self.node, self.keys + (key,))

    def value(self) -> Any:
        """Return the output names, each with the value None, or None for an item."""
        # the names of the outputs are known (for select), their values are not
        if not self.keys:
            return {name: None for name in self.ref}
        return None

    def schema(self) -> Optional[TableSchema]:
        """Return the schema of a selected output; None if it is not known."""
        if len(self.keys) != 1 or self.keys[0] not in self.ref:
            return None
        return self.ref[self.keys[0]].schema


class Tracer:
    """Records the tool calls of a dry run (see `flim.core.runner.call_tool`)."""

    def __init__(self, samples: dict[int, TableSchema]) -> None:
        """Create a tracer.

        Args:
            samples: `id()` of a sample input table -> its schema.
        """
        self.samples = samples  # id(sample table) -> its schema
        self.steps: list[StepReport] = []

    def schema_of(self, value: Any) -> Any:
        """Return the schema of a step's input.

        Args:
            value: A traced output, a table, or a dict of them.

        Returns:
            The schema (of a table that is not a sample: from its columns, not
            complete); for a dict, its keys -> the schemas of its values; None for
            other values.
        """
        if isinstance(value, TraceOutput):
            return value.schema()
        if isinstance(value, pd.DataFrame):
            known = self.samples.get(id(value))
            return known if known is not None else TableSchema.from_frame(value, False)
        if isinstance(value, dict):
            return {k: self.schema_of(v) for k, v in value.items()}
        return None

    def call(
        self,
        tool: "Tool",
        inputs: list[Any],
        config: Optional[TaskConfig],
        task_tags: Optional[Union[str, Sequence[str]]] = None,
    ) -> Any:
        """Validate a tool call and record it as a step, instead of running it.

        The config is validated against the input schemas (`Tool.validate`); the
        output schemas (`Tool.output_schema`) are empty if they can't be derived
        before the run.

        Args:
            tool: The tool.
            inputs: The call's inputs.
            config: The call's config; None: the tool's default config.
            task_tags: The step's tags, added to its name.

        Returns:
            The input table itself for the workflow's input step; else a
            `TraceOutput` with the output schemas.
        """
        from flim.core.workflow import _Input

        if isinstance(tool, _Input):  # the workflow's input table itself
            return inputs[0]
        tags = task_tags if isinstance(task_tags, str) else ", ".join(task_tags or [])
        name = f"{tool.name} ({tags})" if tags and tags != tool.name else tool.name
        if config is None:
            config = tool.config_class()
        schemas = [self.schema_of(i) for i in inputs]
        issues = [
            dataclasses.replace(i, step=name)
            for i in tool.validate(config, schemas)
        ]
        try:
            specs = tool.output_schema(config, schemas)
        except Exception:  # unknown before the run
            specs = {}
        # by the names the run gives them (see Tool.run_task)
        prefix = getattr(config, "prefix", None) or ""
        outputs = {f"{prefix}{spec.display_name}": spec for spec in specs.values()}
        self.steps.append(StepReport(name, type(tool), config, schemas, outputs, issues))
        return TraceOutput(outputs, name)


def current_tracer() -> Optional[Tracer]:
    """Return the tracer of the current dry run; None outside a dry run."""
    return _TRACER.get()


class DefaultWorkflowValidator:
    """Guesses missing columns of the workflow config, then validates each step.

    Missing columns are guessed or skipped as the tool's `processing` allows; the
    steps are validated in a dry run of the workflow.
    """

    def validate(
        self,
        workflow: type["Workflow"],
        config: TaskConfig,
        inputs: list[Optional[TableSchema]],
        processing: "ProcessingRules",
    ) -> ValidationReport:
        """Validate a workflow config against the schemas of the input tables.

        Columns are resolved only if all known input schemas are complete; the
        steps are validated only if every input is known and complete. An error while
        the workflow is built is reported as an issue. A step's issue about a
        column that is already reported for the workflow config, or the same issue
        again (steps that run per feature), is left out.

        Args:
            workflow: The workflow class.
            config: The workflow's config.
            inputs: The schemas of the input tables; None for an unknown one.
            processing: How columns missing from the inputs are treated (the
                tool's `processing`): errors, guesses or skipped entries.

        Returns:
            The report, with the config the run uses.
        """
        schemas = list(inputs)
        known = [s for s in schemas if s is not None]
        issues: list[Issue] = []
        if known and all(s.complete for s in known):
            config, issues = self.resolve_columns(config, known, processing, workflow)
        report = ValidationReport(config, issues)
        if any(s is None or not s.complete for s in schemas) or len(schemas) < len(
            workflow.inputs
        ):
            return report  # steps are not validated while an input is unknown
        samples = [s.sample() for s in schemas]
        tracer = Tracer({id(t): s for t, s in zip(samples, schemas)})
        token = _TRACER.set(tracer)
        try:
            workflow().build(*samples, config=config)
        except Exception as err:  # the workflow cannot be built with these inputs
            report.issues.append(Issue(None, f"{workflow.name}: {err}"))
        finally:
            _TRACER.reset(token)
        report.steps = tracer.steps
        # columns reported for the workflow config are not reported again per step
        seen = {(None, None, f"Column '{i.old}' is not in the input") for i in issues}
        missing = {
            m.group(1)
            for i in report.errors
            for m in [re.match(r"Column '(.*)' is not in the input", i.message)]
            if m
        }
        own = {i.message for i in issues}  # the workflow config's, e.g. bound fields
        for step in tracer.steps:  # one issue per message (steps run per feature)
            for issue in step.issues:
                m = re.match(r"Column '(.*)' is not in the input", issue.message)
                if (m and m.group(1) in missing) or issue.message in own:
                    continue
                if (issue.step, issue.field, issue.message) not in seen:
                    seen.add((issue.step, issue.field, issue.message))
                    report.issues.append(issue)
        return report

    @staticmethod
    def resolve_columns(
        config: TaskConfig,
        schemas: list[TableSchema],
        processing: "ProcessingRules",
        workflow: Optional[type["Workflow"]] = None,
    ) -> tuple[TaskConfig, list[Issue]]:
        """Replace or remove the columns a config names that the inputs lack.

        Per missing column: replaced by the closest column of the same role if its
        field isn't strict and the workflow guesses it (`Tool.never_guessed`); else,
        in `grouping` or `features`, removed if the field is skippable and the entry
        isn't required; else an error. Fields that the workflow copies into its
        steps (`bound_fields`) are validated at the workflow's level only. A column
        that is in the input with another role is an error. If there are issues, the
        config's `_share_fields` (if any) is called, which copies the guesses and
        removals into the steps' bound fields.

        Args:
            config: The workflow's config; a change replaces it with a copy.
            schemas: The schemas of the input tables.
            processing: How missing columns are treated (the tool's `processing`).
            workflow: The workflow class, for its `never_guessed`; None: none.

        Returns:
            The config with the guesses and removals applied, and the issues:
            guesses (`guessed`), removed entries (`skipped`) and errors.
        """
        from flim.core.tool import is_listed

        never = getattr(workflow, "never_guessed", ())
        columns = {c.name: c.role for s in schemas for c in s.columns}
        # fields the workflow copies into its steps are validated once, at the top
        bound = {
            f"{step}.{name}"
            for step, names in getattr(config, "bound_fields", {}).items()
            for name in names
        }
        issues = []
        removed: dict[str, list[str]] = {}
        for path, name, role in list(column_references(config)):
            if any(path == b or path.startswith((b + "[", b + ".")) for b in bound):
                continue
            if columns.get(name) == role:
                continue
            if name in columns:
                issues.append(Issue(path, f"'{name}' is not a {role} column"))
                continue
            top = _field_of(path)
            why = ""
            if not processing.is_strict(path) and top not in never:
                candidates = [c for c, r in columns.items() if r == role]
                guess, why = guess_column(name, candidates)
                if guess is not None:
                    config = replace_at(config, path, guess)
                    issues.append(
                        Issue(
                            path,
                            f"'{name}' is not in the input: '{guess}' is used",
                            severity="guessed",
                            old=name,
                            suggestion=guess,
                        )
                    )
                    continue
            direct = re.fullmatch(rf"{top}\[[^\]]+\]", path) is not None
            skippable = processing.skip(top) != "none"
            if top in REMOVED_ENTRIES and direct and skippable:
                if not is_listed(name, processing.required.get(top, [])):
                    removed.setdefault(top, []).append(name)
                    message = f"'{name}' is not in the input: skipped"
                    issues.append(Issue(path, message, severity="skipped", old=name))
                    continue
                why = "required"
            reason = f" ({why})" if why else ""
            issues.append(Issue(path, f"Column '{name}' is not in the input{reason}"))
        for top, names in removed.items():
            value = getattr(config, top)
            if isinstance(value, dict):
                kept: Any = {k: v for k, v in value.items() if k not in names}
            else:
                kept = [v for v in value if v not in names]
            config = config.model_copy(update={top: kept})
            if processing.skip(top) == "some" and not kept:
                issues.append(Issue(top, f"No entry of {top} is in the input"))
        share = getattr(config, "_share_fields", None)
        if issues and share is not None:
            share()  # the guesses and removals into the steps' bound fields
        return config, issues


# --- workflow file steps: their `processing` applied before they run ---

@dataclass
class StepResolution:
    """A step's settings with its `processing` applied to its inputs.

    Attributes:
        config: The config the step runs with: guesses replaced, skipped entries
            removed.
        guessed: The replaced columns, e.g. `features[0]: 'FAD a1' -> 'FAD a1%'`.
        skipped: The removed entries, e.g. `features: 'FLIRR' (not in the input)`.
        errors: The problems that stop the step.
    """

    config: TaskConfig
    guessed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def resolve_step(
    tool: type["Tool"], config: TaskConfig, inputs: Sequence[Any], rules: Any
) -> StepResolution:
    """Apply a workflow file step's `processing` to its settings for its inputs.

    Per column that the settings name and the inputs lack: replaced by the closest
    column of the same role if the field isn't strict and the tool guesses it
    (`Tool.never_guessed`); else, in `grouping` or `features`, removed if the field
    is skippable and the entry isn't required; else an error. A missing column in a
    rule list the tool counts itself (e.g. Filter's `filters`) is left to the tool
    if the field is skippable. After removals, `grouping` and `features` keep at
    least the tool's minimum (`min_grouping`, `min_features`), and at least one
    entry if skippable is `some`. Nothing is validated if an input is unknown.

    Args:
        tool: The tool class.
        config: The step's config (not changed).
        inputs: The schemas of the step's inputs (a dict of them for an input with
            `many=True`); None for an unknown one.
        rules: The step's merged `processing` (`ProcessingRules`).

    Returns:
        The resolution.
    """
    from flim.core.tool import _flat_schemas, is_listed

    result = StepResolution(config)
    schemas = _flat_schemas(inputs)
    if not schemas or any(s is None or not s.complete for s in schemas):
        return result
    columns = {c.name: c.role for s in schemas for c in s.columns}
    roles = {path: role for path, _, role in column_references(config)}
    removed: dict[str, list[str]] = {}
    for issue in tool.validate(config, inputs):
        if issue.severity != "error":
            continue
        path = issue.field or ""
        top = _field_of(path)
        missing = _MISSING.match(issue.message)
        if missing is None:
            if not (top in REMOVED_ENTRIES and issue.message.startswith("Select at least")):
                result.errors.append(f"{path}: {issue.message}" if path else issue.message)
            continue  # minimums: validated after the removals
        name = missing.group(1)
        if not rules.is_strict(path) and top not in tool.never_guessed:
            candidates = [c for c, r in columns.items() if r == roles.get(path)]
            guess, _ = guess_column(name, candidates)
            if guess is not None:
                config = replace_at(config, path, guess)
                result.guessed.append(f"{path}: '{name}' -> '{guess}'")
                continue
        mode = rules.skip(top)
        direct = re.fullmatch(rf"{top}\[[^\]]+\]", path) is not None
        if top in REMOVED_ENTRIES and direct and mode != "none":
            if is_listed(name, rules.required.get(top, [])):
                result.errors.append(f"{path}: Column '{name}' is not in the input (required)")
            else:
                removed.setdefault(top, []).append(name)
            continue
        if top in tool.skippable_fields and top not in REMOVED_ENTRIES and mode != "none":
            continue  # the tool skips the entry (Tool.skip)
        result.errors.append(f"{path}: {issue.message}")
    for top, names in removed.items():
        value = getattr(config, top)
        if isinstance(value, dict):
            kept: Any = {k: v for k, v in value.items() if k not in names}
        else:
            kept = [v for v in value if v not in names]
        config = config.model_copy(update={top: kept})
        result.skipped += [f"{top}: '{n}' (not in the input)" for n in names]
    for top in REMOVED_ENTRIES:
        value = getattr(config, top, None)
        if value is None or value == "all":
            continue
        least = config.min_features if top == "features" else config.min_grouping
        if rules.skip(top) == "some":
            least = max(least, 1)
        if len(value) < least:
            present = ", ".join(map(str, value)) or "none"
            result.errors.append(
                f"{top}: {len(value)} entries apply ({present}); {tool.name} needs at"
                f" least {least}"
            )
    result.config = config
    return result
