"""Calculating new columns from others: by expressions or by registered functions.

A calculation of kind `expression` is evaluated with `pandas.eval` (engine `pandas`):
arithmetic, comparisons, boolean logic and the math functions in `MATH_FUNCTIONS`;
column names with spaces or other characters in backticks, e.g.::

    `NAD(P)H a1[%]` * `NAD(P)H t1` / 100

Before it is evaluated, an expression is
parsed and validated (`expression_columns`): only these elements are allowed, no
attribute access, no other calls, no assignments, so a settings or workflow file
cannot run other code.

A calculation of kind `function` calls a registered function (`FUNCTIONS`) row by row
with the values of its argument columns and its keyword parameters, as Import did up
to FLIMAnalyzer 0.6. Plugins can add functions with `register_function`.

Infinite results (e.g. a division by 0) are stored as missing values.
"""

import ast
import inspect
import logging
import re
from dataclasses import dataclass, field
from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Callable, Optional

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from flim.configs.data import Calculation

logger = logging.getLogger(__name__)

# the math functions of pandas.eval (pandas user guide, "Enhancing performance",
# supported syntax)
MATH_FUNCTIONS = (
    "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2",
    "sinh", "cosh", "tanh", "arcsinh", "arccosh", "arctanh",
    "abs", "exp", "expm1", "log", "log1p", "log10", "sqrt",
)  # fmt: skip

FUNCTIONS: dict[str, Callable] = {}

_BACKTICKED = re.compile(r"`([^`]*)`")
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Name,
    ast.Constant, ast.Load, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub, ast.Not, ast.Invert, ast.And, ast.Or, ast.BitAnd, ast.BitOr,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)  # fmt: skip


def register_function(
    func: Optional[Callable] = None, *, name: Optional[str] = None
) -> Callable:
    """Register a function for calculations of kind `function`; usable as a decorator.

    The function takes one value per argument column (positional) and the
    calculation's parameters (keywords), and returns one value; it is called row by row.
    A function registered under an existing name replaces it.

    Args:
        func: The function; None when used as `@register_function(name=...)`.
        name: The name calculations refer to; defaults to the function's name.

    Returns:
        The function itself if `func` is given, otherwise a decorator that registers
        and returns the function it decorates.
    """

    def register(f: Callable) -> Callable:
        FUNCTIONS[name or f.__name__] = f
        return f

    return register(func) if func is not None else register


def _register_builtins() -> None:
    """Register the functions of `flim.core.preprocessor`, unless already registered."""
    from flim.core import preprocessor as p

    for f in (
        p.nadph_perc, p.nadh_perc, p.tm, p.ratio,
        p.trp_Eperc_1, p.trp_Eperc_2, p.trp_Eperc_3, p.trp_r,
    ):  # fmt: skip
        FUNCTIONS.setdefault(f.__name__, f)


def expression_columns(expression: str) -> list[str]:
    """Return the columns an expression uses, in order of first use.

    Args:
        expression: The expression, column names with other characters than letters,
            digits and `_` in backticks.

    Returns:
        The column names.

    Raises:
        ValueError: If the expression is empty, can't be parsed, or uses something
            other than arithmetic, comparisons, boolean logic, numbers, column names
            and the math functions.
    """
    if not expression or not expression.strip():
        raise ValueError("the expression is empty")
    quoted: list[str] = []

    def placeholder(match: re.Match) -> str:
        quoted.append(match.group(1))
        return f" _c{len(quoted) - 1}_ "

    text = _BACKTICKED.sub(placeholder, expression)
    if "`" in text:
        raise ValueError("a backtick (`) is not closed")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError:
        raise ValueError(f"'{expression}' is not a valid expression") from None
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            what = type(node).__name__
            raise ValueError(f"'{expression}': {what} is not allowed in an expression")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError(f"'{expression}': only numbers are allowed as values")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                raise ValueError(
                    f"'{expression}': methods (.{func.attr}) are not allowed in an"
                    " expression"
                )
            if not isinstance(func, ast.Name) or func.id not in MATH_FUNCTIONS:
                called = func.id if isinstance(func, ast.Name) else "this"
                raise ValueError(
                    f"'{expression}': {called}(...) is not a math function of"
                    f" expressions ({', '.join(MATH_FUNCTIONS)})"
                )
            if node.keywords:
                raise ValueError(f"'{expression}': keyword arguments are not allowed")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and not _is_called(tree, node):
            match = re.fullmatch(r"_c(\d+)_", node.id)
            names.append(quoted[int(match.group(1))] if match else node.id)
    # ast.walk is breadth first: order by position in the text instead
    positions = {n: expression.find(n) for n in names}
    return sorted(dict.fromkeys(names), key=lambda n: positions[n])


def _is_called(tree: ast.AST, name_node: ast.Name) -> bool:
    """Return whether a name node is the function of a call in the tree."""
    return any(isinstance(n, ast.Call) and n.func is name_node for n in ast.walk(tree))


def function_problem(
    name: str, args: Sequence[Any], params: Mapping[str, Any]
) -> Optional[str]:
    """Return why a function calculation can't be called, or None.

    Registers the built-in functions first. The arguments and parameters are bound
    to the function's signature; they are not called.

    Args:
        name: The registered function's name.
        args: The argument columns.
        params: The keyword parameters.

    Returns:
        The problem: the function is not registered, or the arguments don't fit its
        signature; None if it can be called.
    """
    _register_builtins()
    func = FUNCTIONS.get(name)
    if func is None:
        known = ", ".join(sorted(FUNCTIONS))
        return f"'{name}' is not a registered function ({known})"
    try:
        inspect.signature(func).bind(*args, **params)
    except TypeError as err:
        return f"{name}{inspect.signature(func)}: {err}"
    return None


def quote_columns(expression: str, columns: Iterable[Any] = ()) -> str:
    """Return an expression with the table's column names in backticks.

    A column name that appears in the expression as a whole name (not as part of a
    longer name, and not already in backticks) is put in backticks, so that names
    such as `NAD(P)H tm` can be typed as they are. Longer names are matched first.

    Args:
        expression: The expression.
        columns: The table's column names.

    Returns:
        The expression; unchanged if no column name is found.
    """
    names = sorted({str(c) for c in columns if str(c)}, key=len, reverse=True)
    if not names or not expression:
        return expression
    parts = re.split(r"(`[^`]*`)", expression)  # odd parts: already in backticks
    found: list[str] = []
    for i in range(0, len(parts), 2):
        text = parts[i]
        for name in names:
            pattern = rf"(?<![\w.]){re.escape(name)}(?![\w])"
            if re.search(pattern, text):
                found.append(name)
                # a placeholder of private-use characters, which no name contains
                mark = "\ue000" + chr(0xE100 + len(found) - 1) + "\ue001"
                text = re.sub(pattern, lambda m, mark=mark: mark, text)
        parts[i] = text
    joined = "".join(parts)
    return re.sub(
        "\ue000(.)\ue001", lambda m: f"`{found[ord(m.group(1)) - 0xE100]}`", joined
    )


def needed_columns(
    calculation: "Calculation", columns: Iterable[Any] = ()
) -> list[str]:
    """Return the columns a calculation uses.

    Args:
        calculation: The calculation.
        columns: The table's column names (they may be typed without backticks).

    Returns:
        The column names: those of the expression in order of first use, or the
        function's argument columns.

    Raises:
        ValueError: If an expression is not valid.
    """
    if calculation.kind == "expression":
        return expression_columns(quote_columns(calculation.expression, columns))
    return [a for a in calculation.args if isinstance(a, str)]


@dataclass
class Outcome:
    """The result of `calculate`.

    Attributes:
        data: The table with the new columns.
        calculated: The names of the calculated columns, in order.
        skipped: Why a calculation was skipped, by its name (e.g. missing columns).
        replaced: Input columns that a calculation replaced.
    """

    data: pd.DataFrame
    calculated: list = field(default_factory=list)
    skipped: dict = field(default_factory=dict)
    replaced: list = field(default_factory=list)


def evaluate(data: pd.DataFrame, expression: str) -> pd.Series:
    """Evaluate an expression on a table, after validating it (`expression_columns`).

    Args:
        data: The table.
        expression: The expression.

    Returns:
        A value per row.

    Raises:
        ValueError: If the expression is not allowed.
    """
    expression = quote_columns(expression, data.columns)
    expression_columns(expression)  # validated before pandas sees it
    result = data.eval(expression, engine="python", local_dict={}, global_dict={})
    if not isinstance(result, pd.Series):  # e.g. a number
        result = pd.Series(result, index=data.index)
    return result


def _evaluate(data: pd.DataFrame, calculation: "Calculation") -> pd.Series:
    """Return a calculation's values, one per row of the table."""
    if calculation.kind == "expression":
        return evaluate(data, calculation.expression)
    problem = function_problem(calculation.function, calculation.args, calculation.params)
    if problem:
        raise ValueError(problem)
    func = np.vectorize(FUNCTIONS[calculation.function], otypes=[float])
    columns = [data[a].to_numpy() if isinstance(a, str) else a for a in calculation.args]
    return pd.Series(func(*columns, **calculation.params), index=data.index)


def calculate(
    data: pd.DataFrame, calculations: Iterable["Calculation"], missing: str = "skip"
) -> Outcome:
    """Calculate new columns, in order: a calculation can use earlier ones' columns.

    A calculation that is not `enabled` is left out. A column named like an input
    column replaces it. Columns of calculations with `keep` False are removed at the
    end (helper columns), unless they replaced an input column. Numeric results are
    features, with infinite values as missing values; true/false and text results
    are category columns.

    Args:
        data: The table (not changed).
        calculations: The calculations (ExpressionCalculation, FunctionCalculation).
        missing: What to do if a calculation uses a column that is not in the table:
            `skip` it, or `raise` a ValueError. Defaults to `skip`.

    Returns:
        The table with the new columns, and what was calculated, skipped or replaced.

    Raises:
        ValueError: If a calculation is not valid (e.g. an expression that is not
            allowed), fails (e.g. text columns in arithmetic), or uses a missing
            column with `missing="raise"`.
    """
    outcome = Outcome(data=data.copy())
    table = outcome.data
    helpers = []
    for calculation in calculations:
        if not calculation.enabled:
            continue
        name = calculation.name
        try:
            used = needed_columns(calculation, table.columns)
            absent = [c for c in used if c not in table.columns]
        except ValueError as err:
            raise ValueError(f"{name}: {err}") from None
        if absent:
            reason = f"no column {', '.join(repr(c) for c in absent)}"
            if missing == "raise":
                raise ValueError(f"{name}: {reason}")
            outcome.skipped[name] = reason
            continue
        try:
            values = _evaluate(table, calculation)
        except ValueError as err:
            raise ValueError(f"{name}: {err}") from None
        except Exception as err:  # e.g. text columns in arithmetic
            raise ValueError(f"{name}: {type(err).__name__}: {err}") from None
        # numbers: a feature; true/false or text: a category column (e.g. a condition)
        if pd.api.types.is_bool_dtype(values) or not pd.api.types.is_numeric_dtype(values):
            values = values.astype("category")
        else:
            values = values.replace([np.inf, -np.inf], np.nan)
        if name in data.columns and name not in outcome.replaced:
            outcome.replaced.append(name)
        table[name] = values
        outcome.calculated.append(name)
        if not calculation.keep:
            helpers.append(name)
    for name in helpers:
        if name not in data.columns and name in table.columns:
            table.drop(columns=name, inplace=True)
    return outcome


def _closest(name: str, columns: Iterable[Any]) -> str:
    """Return a missing column's name, with the closest of the table's columns."""
    import difflib

    close = difflib.get_close_matches(name, [str(c) for c in columns], n=1, cutoff=0.6)
    return f"'{name}' (did you mean '{close[0]}'?)" if close else f"'{name}'"


def _hint(message: str, expression: str, columns: Optional[Iterable[Any]]) -> str:
    """Return an expression's error, with a hint on backticks.

    The hint is added if the columns are known and the expression has no backticks.
    """
    if columns is None or "`" in expression:
        return message
    return (
        f"{message}. Type column names as in the table; a name that is not in the"
        " table yet (e.g. calculated in a row above) goes in backticks: `FAD tm`"
    )


def validate_calculations(
    calculations: Iterable["Calculation"], columns: Optional[Collection[Any]] = None
) -> list[tuple[int, str, str, str]]:
    """Validate calculations before running them.

    Calculations that are not `enabled` are not validated.

    Args:
        calculations: The calculations.
        columns: The input table's column names; None if unknown (the columns used
            are then not validated).

    Returns:
        (index, field, severity, message) per problem: `error` for calculations that
        can't run (no name, a name used twice, an expression that is not valid, an
        unknown function or wrong parameters), `warning` for ones that are skipped
        (a column neither in the table nor calculated before) and for names that
        replace an input column.
    """
    problems = []
    available = set(columns) if columns is not None else None
    seen = set()
    for i, calculation in enumerate(calculations):
        if not calculation.enabled:
            continue
        name = (calculation.name or "").strip()
        if not name:
            problems.append((i, "name", "error", "give the new column a name"))
        elif name in seen:
            problems.append((i, "name", "error", f"'{name}' is calculated twice"))
        seen.add(name)
        if calculation.kind == "function":
            problem = function_problem(
                calculation.function, calculation.args, calculation.params
            )
            if problem:
                problems.append((i, "function", "error", problem))
                continue
            used, where = [a for a in calculation.args if isinstance(a, str)], "args"
        else:
            try:
                expression = quote_columns(calculation.expression, available or ())
                used, where = expression_columns(expression), "expression"
            except ValueError as err:
                problems.append((i, "expression", "error", _hint(str(err), calculation.expression, available)))
                continue
        if available is None:
            continue
        absent = [c for c in used if c not in available]
        if absent:
            missing = ", ".join(_closest(c, available) for c in absent)
            problems.append(
                (i, where, "warning", f"skipped: {missing} not in the table or calculated before")
            )
            continue
        if name in columns:
            problems.append((i, "name", "warning", f"replaces the column '{name}'"))
        available.add(name)
    return problems


def applicable(
    presets: Sequence["Calculation"], columns: Iterable[Any]
) -> list["Calculation"]:
    """Return the presets (calculations) that apply to a table, in their order.

    A preset applies if the columns it uses are in the table, or are calculated by
    other presets that apply, and if the table doesn't have its column yet.

    Args:
        presets: The calculations.
        columns: The table's column names.

    Returns:
        The presets that apply.
    """
    columns = {str(c) for c in columns}
    pool, offered, changed = set(columns), {}, True
    while changed:
        changed = False
        for preset in presets:
            if preset.name in offered or preset.name in columns:
                continue
            try:
                used = needed_columns(preset, pool)
            except ValueError:
                continue
            if all(c in pool for c in used):
                offered[preset.name] = preset
                pool.add(preset.name)
                changed = True
    return [p for p in presets if p.name in offered]


def with_prerequisites(
    chosen: Iterable["Calculation"],
    offered: Iterable["Calculation"],
    columns: Collection[Any],
) -> list["Calculation"]:
    """Return chosen presets with the presets they need first, in calculation order.

    Args:
        chosen: The presets chosen.
        offered: The presets that apply (see `applicable`).
        columns: The table's column names.

    Returns:
        The presets to add, each once.
    """
    by_name = {p.name: p for p in offered}
    result, names = [], set()

    def add(preset: "Calculation") -> None:
        if preset.name in names:
            return
        pool = {str(c) for c in columns} | names
        for column in needed_columns(preset, pool | set(by_name)):
            if column not in columns and column in by_name:
                add(by_name[column])
        names.add(preset.name)
        result.append(preset)

    for preset in chosen:
        add(preset)
    return result
