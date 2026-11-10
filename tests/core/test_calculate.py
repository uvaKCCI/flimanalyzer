"""Calculations by expressions and registered functions (flim.core.calculate) and the
Calculate tool."""

import numpy as np
import pandas as pd
import pytest

from flim.configs import CalculateConfig
from flim.configs.data import ExpressionCalculation as Expr
from flim.configs.data import FunctionCalculation as Func
from flim.core.calculate import calculate, check, expression_columns, register_function
from flim.tools.data import Calculate


@pytest.fixture
def data():
    return pd.DataFrame(
        {
            "NAD(P)H tm": [1000.0, 1200.0, 0.0],
            "FAD tm": [2000.0, 0.0, 1000.0],
            "FOV": pd.Categorical(["1", "1", "2"]),
        }
    )


def test_expression_columns_in_order_and_backticks():
    assert expression_columns("log(`FAD tm`) / `NAD(P)H tm` + FLIRR * 2") == [
        "FAD tm", "NAD(P)H tm", "FLIRR"
    ]
    assert expression_columns("`a` > 1 & ~(`b` < 2)") == ["a", "b"]


@pytest.mark.parametrize(
    "expression, message",
    [
        ("", "empty"),
        ("1 +", "not a valid expression"),
        ("`FAD tm`.to_csv(1)", "not allowed"),
        ("`FAD tm`.sum()", "not allowed"),
        ("__import__(1)", "not a math function"),
        ("where(`a` > 1, 1, 0)", "not a math function"),
        ("x = 1", "not a valid expression"),
        ("`a` + 'text'", "only numbers"),
        ("`a` + 1`", "not closed"),
        ("@local + 1", "not a valid expression"),
        ("`a`[0]", "not allowed"),
        ("log(`a`, base=2)", "keyword"),
    ],
)
def test_expressions_that_are_refused(expression, message):
    with pytest.raises(ValueError, match=message):
        expression_columns(expression)


def test_expressions_functions_and_order(data):
    calculations = [
        Expr(name="ratio", expression="`FAD tm` / `NAD(P)H tm`"),
        Expr(name="double", expression="ratio * 2"),  # uses the one before
        Func(name="tm", function="tm", args=["NAD(P)H tm", "FAD tm", "NAD(P)H tm", "FAD tm"]),
        Func(name="E%", function="trp_Eperc_1", args=["NAD(P)H tm"], params={"const": 2000}),
    ]
    outcome = calculate(data, calculations)
    table = outcome.data
    assert outcome.calculated == ["ratio", "double", "tm", "E%"]
    assert list(table["ratio"])[:2] == [2.0, 0.0]
    assert np.isnan(table["ratio"].iloc[2])  # 1000 / 0: missing, not infinite
    assert list(table["double"])[:2] == [4.0, 0.0]
    assert table["tm"].iloc[0] == (1000 * 2000 + 2000 * 1000) / 100
    assert list(table["E%"]) == [50.0, 40.0, 100.0]
    assert "ratio" not in data.columns  # the input is not changed


def test_disabled_helpers_types_and_replaced(data):
    calculations = [
        Expr(name="helper", expression="`FAD tm` + 1", keep=False),
        Expr(name="sum", expression="helper + 1"),
        Expr(name="off", expression="1 +", enabled=False),  # not checked either
        Expr(name="high", expression="`FAD tm` > 500", column_type="category"),
        Expr(name="FAD tm", expression="`FAD tm` / 1000"),
    ]
    outcome = calculate(data, calculations)
    table = outcome.data
    assert "helper" not in table.columns and list(table["sum"]) == [2002.0, 2.0, 1002.0]
    assert "off" not in table.columns
    assert isinstance(table["high"].dtype, pd.CategoricalDtype)
    assert list(table["FAD tm"]) == [2.0, 0.0, 1.0] and outcome.replaced == ["FAD tm"]


def test_missing_columns_skip_or_raise(data):
    calculations = [Expr(name="x", expression="`trp t1` * 2"), Expr(name="y", expression="x + 1")]
    outcome = calculate(data, calculations)
    assert outcome.calculated == [] and set(outcome.skipped) == {"x", "y"}
    assert "'trp t1'" in outcome.skipped["x"]
    with pytest.raises(ValueError, match="x: no column 'trp t1'"):
        calculate(data, calculations, missing="raise")


def test_text_columns_in_arithmetic_are_an_error(data):
    with pytest.raises(ValueError, match="bad:"):
        calculate(data, [Expr(name="bad", expression="FOV * `FAD tm`")])


def test_registered_functions():
    @register_function(name="twice")
    def _twice(value, factor=2):
        return value * factor

    table = calculate(
        pd.DataFrame({"a": [1.0, 2.0]}),
        [Func(name="b", function="twice", args=["a"], params={"factor": 3})],
    ).data
    assert list(table["b"]) == [3.0, 6.0]


def test_check(data):
    calculations = [
        Expr(name="", expression="1"),
        Expr(name="a", expression="1 +"),
        Func(name="b", function="nope"),
        Func(name="c", function="ratio", args=["FAD tm"]),  # one argument missing
        Func(name="d", function="ratio", args=["FAD tm", "x"]),
        Expr(name="FAD tm", expression="`FAD tm` * 2"),
        Expr(name="e", expression="`FAD tm` * 2"),
        Expr(name="e", expression="`FAD tm` * 3"),
    ]
    problems = {(i, field, severity) for i, field, severity, _ in check(calculations, data.columns)}
    assert problems == {
        (0, "name", "error"),
        (1, "expression", "error"),
        (2, "function", "error"),
        (3, "function", "error"),
        (4, "args", "warning"),  # skipped
        (5, "name", "warning"),  # replaces the column
        (7, "name", "error"),  # twice
    }
    # without the table's columns: only what doesn't depend on them
    assert {p[0] for p in check(calculations)} == {0, 1, 2, 3, 7}


def test_default_calculations_are_imports():
    from flim.core.preprocessor import DEFAULT_CALCULATIONS

    calculations = CalculateConfig().calculations
    assert [(c.name, c.function, c.args) for c in calculations] == [
        (n, f, list(a)) for n, f, a in DEFAULT_CALCULATIONS
    ]
    assert check(calculations) == []


def test_calculate_tool(data):
    config = CalculateConfig(
        calculations=[
            Expr(name="ratio", expression="`FAD tm` / `NAD(P)H tm`"),
            Expr(name="trp", expression="`trp t1` * 2"),
        ]
    )
    (table,) = Calculate()(data, config=config).values()
    assert "ratio" in table.columns and "trp" not in table.columns
    assert Calculate.example(config, [data]) == "ratio = 2"
    (issue,) = Calculate.validate_data(config, [data])
    assert (issue.field, issue.severity) == ("calculations[1].expression", "warning")
    bad = CalculateConfig(calculations=[Expr(name="x", expression="1 +")])
    (issue,) = Calculate.validate(bad, [])
    assert issue.field == "calculations[0].expression" and issue.severity == "error"


def test_calculate_tool_warns_in_the_run_summary(prefect_harness, data):
    from flim.core.runner import run_flow

    config = CalculateConfig(calculations=[Expr(name="trp", expression="`trp t1` * 2")])
    run = run_flow("calculate", lambda: Calculate()(data, config=config))
    messages = [a.get("message") for _, a in run.graph.nodes(data=True) if "tool" in a]
    assert any("trp skipped" in (m or "") for m in messages)


def test_calculations_from_json():
    config = CalculateConfig.model_validate(
        {
            "calculations": [
                {"kind": "expression", "name": "a", "expression": "1"},
                {"kind": "function", "name": "b", "function": "ratio", "args": ["x", "y"]},
            ]
        }
    )
    assert [type(c).__name__ for c in config.calculations] == [
        "ExpressionCalculation", "FunctionCalculation"
    ]
