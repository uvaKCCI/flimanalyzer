"""Calculating new columns from others: by expressions or by registered functions.

A calculation of kind `expression` is evaluated with `pandas.eval` (engine `pandas`):
arithmetic, comparisons, boolean logic and the math functions in `MATH_FUNCTIONS`;
column names with spaces or other characters in backticks, e.g.::

    `NAD(P)H a1[%]` * `NAD(P)H t1` / 100

Before it is evaluated, an expression is
parsed and checked (`expression_columns`): only these elements are allowed, no
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
from typing import Callable, Optional

import numpy as np
import pandas as pd

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


def register_function(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """Register a function for calculations of kind `function`; usable as a decorator.

    The function takes one value per argument column (positional) and the
    calculation's parameters (keywords), and returns one value; it is called row by row.

    Args:
        func: The function.
        name: The name calculations refer to; default: the function's name.
    """

    def register(f):
        FUNCTIONS[name or f.__name__] = f
        return f

    return register(func) if func is not None else register


def _register_builtins() -> None:
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

    def placeholder(match):
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


def _is_called(tree, name_node) -> bool:
    return any(isinstance(n, ast.Call) and n.func is name_node for n in ast.walk(tree))


def function_problem(name: str, args, params) -> Optional[str]:
    """Return why a function calculation can't be called, or None.

    Args:
        name: The registered function's name.
        args: The argument columns.
        params: The keyword parameters.
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


def needed_columns(calculation) -> list[str]:
    """Return the columns a calculation uses (an expression's raise ValueError if it
    is not valid)."""
    if calculation.kind == "expression":
        return expression_columns(calculation.expression)
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
    """Evaluate an expression on a table, after checking it (`expression_columns`).

    Args:
        data: The table.
        expression: The expression.

    Returns:
        A value per row.

    Raises:
        ValueError: If the expression is not allowed.
    """
    expression_columns(expression)  # checked before pandas sees it
    result = data.eval(expression, engine="python", local_dict={}, global_dict={})
    if not isinstance(result, pd.Series):  # e.g. a number
        result = pd.Series(result, index=data.index)
    return result


def _evaluate(data: pd.DataFrame, calculation):
    if calculation.kind == "expression":
        return evaluate(data, calculation.expression)
    problem = function_problem(calculation.function, calculation.args, calculation.params)
    if problem:
        raise ValueError(problem)
    func = np.vectorize(FUNCTIONS[calculation.function], otypes=[float])
    columns = [data[a].to_numpy() if isinstance(a, str) else a for a in calculation.args]
    return pd.Series(func(*columns, **calculation.params), index=data.index)


def calculate(data: pd.DataFrame, calculations, missing: str = "skip") -> Outcome:
    """Calculate new columns, in order: a calculation can use earlier ones' columns.

    A calculation that is not `enabled` is left out. A column named like an input
    column replaces it. Columns of calculations with `keep` False are removed at the
    end (helper columns).

    Args:
        data: The table (not changed).
        calculations: The calculations (ExpressionCalculation, FunctionCalculation).
        missing: What to do if a calculation uses a column that is not in the table:
            `skip` it, or `raise` a ValueError.

    Returns:
        The table with the new columns, and what was calculated, skipped or replaced.

    Raises:
        ValueError: If a calculation is not valid (e.g. an expression that is not
            allowed), or uses a missing column with `missing="raise"`.
    """
    outcome = Outcome(data=data.copy())
    table = outcome.data
    helpers = []
    for calculation in calculations:
        if not calculation.enabled:
            continue
        name = calculation.name
        try:
            absent = [c for c in needed_columns(calculation) if c not in table.columns]
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
        if calculation.column_type == "category":
            values = values.astype("category")
        elif pd.api.types.is_numeric_dtype(values) and not pd.api.types.is_bool_dtype(values):
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


def check(calculations, columns=None) -> list[tuple[int, str, str, str]]:
    """Check calculations before running them.

    Args:
        calculations: The calculations.
        columns: The input table's column names; None: unknown (the columns used are
            not checked).

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
                used, where = expression_columns(calculation.expression), "expression"
            except ValueError as err:
                problems.append((i, "expression", "error", str(err)))
                continue
        if available is None:
            continue
        absent = [c for c in used if c not in available]
        if absent:
            missing = ", ".join(repr(c) for c in absent)
            problems.append(
                (i, where, "warning", f"skipped: {missing} not in the table or calculated before")
            )
            continue
        if name in columns:
            problems.append((i, "name", "warning", f"replaces the column '{name}'"))
        available.add(name)
    return problems
