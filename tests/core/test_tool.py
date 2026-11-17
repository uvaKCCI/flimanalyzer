import matplotlib.figure
import pandas as pd
import pytest

from flim.configs import SortConfig
from flim.core.config import Issue, TaskConfig
from flim.core.registry import tools
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


@pytest.mark.parametrize(
    "cuda, mps, preferred, expected",
    [
        (True, True, "auto", ("cuda", None)),
        (False, True, "auto", ("mps", None)),
        (False, False, "auto", ("cpu", None)),
        (True, False, "cuda", ("cuda", None)),
        (False, True, "cuda", ("cpu", "preferred cuda, ran on cpu: no cuda device here")),
        (True, False, "mps", ("cpu", "preferred mps, ran on cpu: no mps device here")),
    ],
)
def test_resolve_device(monkeypatch, cuda, mps, preferred, expected):
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: cuda)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: mps)
    assert resolve_device(preferred) == expected


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
    # a filter on a column the input doesn't have keeps all rows: a warning
    assert [(i.field, i.severity) for i in issues] == [
        ("filters[0].column", "warning"),
        ("filters[1].keep", "warning"),
    ]


# --- tools in a flow ---


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
    # the graph links the steps through the table they pass on; the plot is apart
    label = {n: a["label"] for n, a in run.graph.nodes(data=True)}
    edges = sorted((label[u], label[v]) for u, v in run.graph.edges)
    assert edges == [("Double", "Table: Doubled"), ("Table: Doubled", "Sort")]



# --- output kinds ---


def _ours():
    import flim.tools  # noqa: F401
    import flim.workflow  # noqa: F401
    from flim.core.registry import tools

    every = [c for g in tools.by_category().values() for c in g] + tools.hidden()
    return [c for c in every if getattr(c, "definition", None) is None]


def test_every_tool_and_workflow_declares_its_output_kinds():
    import warnings

    for tool in _ours():
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            kinds = tool.output_kinds()
        assert kinds, tool.name
        declared = {o.type.kind for o in tool.outputs}
        typed = {t.kind for t in tool.output_types}
        assert not (declared and typed) or declared <= typed, tool.name  # they agree


def test_output_schema_makes_only_the_declared_kinds():
    """With two features and a category column, each tool's outputs have its kinds."""
    import numpy as np
    import pandas as pd

    from flim.core.schema import TableSchema
    from flim.core.workflow import Workflow

    df = pd.DataFrame({
        "Treatment": pd.Categorical(["a", "b"] * 10),
        "FLIRR": np.random.rand(20), "NADH tm": np.random.rand(20),
    })  # fmt: skip
    schema = TableSchema.from_frame(df)
    for tool in _ours():
        if issubclass(tool, Workflow):
            continue
        fields = tool.config_class.model_fields
        settings = {}
        if "features" in fields:
            dict_type = "dict" in str(fields["features"].annotation)
            settings["features"] = {"FLIRR": {}, "NADH tm": {}} if dict_type else ["FLIRR", "NADH tm"]
        if "grouping" in fields:
            settings["grouping"] = ["Treatment"]
        try:
            config = tool.config_class.model_validate(settings)
        except Exception:
            config = tool.config_class()
        specs = tool().output_schema(config, [schema] * max(1, len(tool.inputs)))
        made = {s.type.kind for s in specs.values()}
        assert made <= set(tool.output_kinds()), (tool.name, made)


def test_a_tool_without_output_types_makes_any_kind_with_a_deprecation_warning():
    import pytest

    from flim.core.config import TaskConfig
    from flim.core.tool import Tool

    class Old(Tool[TaskConfig]):
        name = "Old plugin tool"

    with pytest.warns(DeprecationWarning, match="declares no output types"):
        kinds = Old.output_kinds()
    assert kinds[0] == "table" and "plot" in kinds
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert Old.output_kinds() == kinds  # warned once


def test_the_0_6_name_check_requirements_is_deprecated():
    import flim.core.tool as tool_module

    with pytest.warns(DeprecationWarning, match="removed in 0.8.0; use flim.core.tool.validate_requirements"):
        assert tool_module.check_requirements is tool_module.validate_requirements
