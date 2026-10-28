import threading

import matplotlib.figure
import pandas as pd
import pytest
from prefect.testing.utilities import prefect_test_harness

from flim.configs import SortConfig
from flim.core.config import Issue, TaskConfig
from flim.core.registry import ToolRegistry, tools
from flim.core.runner import CancelToken, run_flow
from flim.core.schema import TableSchema
from flim.core.tool import (
    RunContext,
    TaskCancelled,
    Tool,
    resolve_device,
    resolve_threads,
)
from flim.core.types import OutputSpec, PlotType, TableType
from flim.tools.data import Filter, Sort


class DoubleConfig(TaskConfig):
    factor: float = 2.0


class Double(Tool[DoubleConfig]):
    name = "Double"
    category = "Data"
    outputs = (OutputSpec("Doubled", TableType),)

    def run(self, data, *, config):
        features = data.select_dtypes("number").columns
        out = data.copy()
        out[features] = out[features] * config.factor
        return {"Doubled": out}


class Plot(Tool[TaskConfig]):
    name = "Demo Plot"
    category = "Plot"
    draws_figures = True
    outputs = (OutputSpec("Plot", PlotType),)

    def run(self, data, *, config):
        return {"Plot": matplotlib.figure.Figure()}


@pytest.fixture
def table():
    return pd.DataFrame({"T": pd.Categorical(["a", "b", "a"]), "x": [3.0, 1.0, 2.0]})


def test_config_class_from_generic_parameter():
    assert Double.config_class is DoubleConfig
    assert Sort.config_class is SortConfig


def test_tool_can_be_registered():
    registry = ToolRegistry()
    registry.register(Double)
    assert registry.for_config(DoubleConfig()) is Double


def test_builtin_tools_are_registered():
    assert tools.get("Sort") is Sort
    assert SortConfig().classname == "flim.tools.data.Sort"


def test_call_outside_flow(table):
    results = Double()(table, config=DoubleConfig(factor=3))
    assert list(results) == ["Table: Doubled"]
    assert results["Table: Doubled"]["x"].tolist() == [9.0, 3.0, 6.0]


def test_default_config_and_prefix(table):
    assert Double()(table)["Table: Doubled"]["x"].tolist() == [6.0, 2.0, 4.0]
    results = Double()(table, config=DoubleConfig(prefix="Run1-"))
    assert list(results) == ["Run1-Table: Doubled"]


def test_wrong_config_type(table):
    with pytest.raises(TypeError, match="DoubleConfig"):
        Double()(table, config=SortConfig())


def test_display_names_by_value_type():
    named = Tool.display_names(
        {"A": pd.DataFrame(), "B": matplotlib.figure.Figure(), "C": 1}
    )
    assert list(named) == ["Table: A", "Plot: B", "C"]


def test_cancel(table):
    class Stops(Double):
        name = "Stops"

        def run(self, data, *, config):
            self.check_cancelled()
            return super().run(data, config=config)

    tool = Stops()
    token = CancelToken()
    tool._cancel_token = token
    tool(table)  # not cancelled
    token.set()
    with pytest.raises(TaskCancelled):
        tool(table)


def test_resources():
    assert resolve_device("cpu") == ("cpu", None)
    assert resolve_threads(1) == 1
    assert resolve_threads(-1) >= 1
    assert resolve_threads(10_000) <= resolve_threads(-1)
    context = RunContext.for_config(SortConfig())
    assert (context.device, context.threads) == ("cpu", 1)


# --- schemas and validation ---


def test_output_schema_from_sample(table):
    schema = TableSchema.from_frame(table)
    outputs = Double.output_schema(DoubleConfig(), [schema])
    assert outputs["Doubled"].type is TableType
    assert outputs["Doubled"].schema.names == ["T", "x"]
    assert outputs["Doubled"].schema.column("x").derived_from == ["x"]
    assert outputs["Doubled"].display_name == "Table: Doubled"


def test_output_schema_unknown_input():
    outputs = Double.output_schema(DoubleConfig(), [None])
    assert not outputs["Doubled"].schema.complete


def test_output_schema_when_the_sample_fails(table):
    # Sort by a column the input does not have
    outputs = Sort.output_schema(
        SortConfig(features=["nope"]), [TableSchema.from_frame(table)]
    )
    assert not outputs["Sorted"].schema.complete


def test_output_schema_of_plots_does_not_draw(table):
    outputs = Plot.output_schema(TaskConfig(), [TableSchema.from_frame(table)])
    assert outputs["Plot"].type is PlotType and outputs["Plot"].schema is None


def test_validate_columns(table):
    schema = TableSchema.from_frame(table)
    assert Sort.validate(SortConfig(features=["x"]), [schema]) == []
    issues = Sort.validate(SortConfig(grouping=["x", "Q"], features="all"), [schema])
    assert issues == [
        Issue("grouping[0]", "'x' is not a category column"),
        Issue("grouping[1]", "Column 'Q' is not in the input"),
    ]
    # unknown or incomplete inputs are not checked
    assert Sort.validate(SortConfig(features=["Q"]), [None]) == []
    assert Sort.validate(SortConfig(features=["Q"]), [TableSchema.unknown()]) == []


def test_validate_nested_columns(table):
    from flim.configs import FilterConfig

    config = FilterConfig(range_filters={"y": {}}, category_filters={"T": ["a", "c"]})
    issues = Filter.validate(config, [TableSchema.from_frame(table)])
    assert [(i.field, i.severity) for i in issues] == [
        ("range_filters['y']", "error"),
        ("category_filters['T']", "warning"),
    ]


# --- tools in a flow ---


@pytest.fixture(scope="module")
def prefect_harness():
    with prefect_test_harness():
        yield


def test_tools_in_a_flow(prefect_harness, table):
    outputs = {}

    def build():
        doubled = Double()(table, config=DoubleConfig(), task_tags="Step 1")
        outputs["sorted"] = Sort()(
            doubled["Table: Doubled"], config=SortConfig(features=["x"])
        )
        outputs["plot"] = Plot()(table)

    run = run_flow("tools", build)
    assert run.failed == [] and run.state == "completed"
    assert outputs["sorted"].value()["Table: Sorted"]["x"].tolist() == [2.0, 4.0, 6.0]
    assert isinstance(outputs["plot"].value()["Plot: Plot"], matplotlib.figure.Figure)
    labels = [label for label, _ in run.tasks()]
    assert labels == ["Double", "Sort", "Demo Plot"]
    # the graph links the steps through the table they pass on
    assert run.graph.number_of_edges() >= 2


def test_cancelled_tool_in_a_flow(prefect_harness, table):
    started = threading.Event()

    class Waits(Double):
        name = "Waits"

        def run(self, data, *, config):
            started.set()
            while True:
                self.check_cancelled()

    token = CancelToken()

    def build():
        Waits()(table)
        started.wait(30)
        token.set()

    run = run_flow("cancel tools", build, cancel_token=token)
    assert run.cancelled == ["Waits"]
