"""Workflow validation: dry runs, guessed columns, strict mode (flim.core.validation)."""

import numpy as np
import pandas as pd
import pytest

import flim.workflow  # noqa: F401  (registers the workflows)
from flim.configs import PivotConfig, SummaryConfig
from flim.configs.workflow import AETuneConfig, BasicFLIRRConfig, WorkflowConfig
from flim.core.config import CategoryColumn, FeatureColumn
from flim.core.schema import TableSchema
from flim.core.validation import guess_column, replace_at
from flim.core.workflow import Workflow, WorkflowValidationError, workflow_input
from flim.tools.data import Pivot
from flim.tools.statistics import Summarize
from flim.workflow.aetune import AETune
from flim.workflow.basicflow import BasicFLIRR


@pytest.fixture
def data():
    """FLIM-like data whose percentage columns are named "FAD a1[%]"."""
    rng = np.random.default_rng(0)
    n = 60
    df = pd.DataFrame(
        {
            "Treatment": pd.Categorical(rng.choice(["ctrl", "Dox15", "Dox30"], n)),
            "FOV": pd.Categorical(rng.choice(["a", "b"], n)),
            "Cell": pd.Categorical(rng.choice(["1", "2", "3"], n)),
        }
    )
    for name in ("FAD a1", "FAD a1[%]", "NAD(P)H a2", "NAD(P)H a2[%]", "FLIRR"):
        df[name] = rng.uniform(1, 100, n)
    return df


FEATURES = ["FLIRR", "FAD a1%", "NAD(P)H a2%"]  # as in older settings


def test_guess_column():
    columns = ["FAD a1", "FAD a1[%]", "FAD t1", "NAD(P)H a2[%]"]
    assert guess_column("FAD a1%", columns) == ("FAD a1[%]", "")
    assert guess_column("fad T1", columns) == ("FAD t1", "")
    assert guess_column("NADPH a2[%]", columns) == ("NAD(P)H a2[%]", "")
    assert guess_column("Volume", columns)[0] is None
    guess, why = guess_column("FAD a1", ["FAD a1 ", "fad_a1"])  # both the same
    assert guess is None and "several" in why


def test_replace_at():
    config = BasicFLIRRConfig(features=["FLIRR", "FAD a1%"])
    changed = replace_at(config, "features[1]", "FAD a1[%]")
    assert changed.features == ["FLIRR", "FAD a1[%]"]
    assert config.features == ["FLIRR", "FAD a1%"]  # a copy
    from flim.configs import HistogramConfig

    hist = HistogramConfig(features={"t1": {"bins": 5}, "t2": {}})
    changed = replace_at(hist, "features['t1']", "t1 new")
    assert list(changed.features) == ["t1 new", "t2"]  # the key, in its place
    assert changed.features["t1 new"].bins == 5


def test_missing_columns_are_guessed(data):
    config = BasicFLIRRConfig(grouping=["Treatment", "FOV"], features=FEATURES)
    report = BasicFLIRR().resolve(config, [data], strict=False)
    assert report.errors == []
    assert [(i.field, i.old, i.suggestion) for i in report.guesses] == [
        ("features[1]", "FAD a1%", "FAD a1[%]"),
        ("features[2]", "NAD(P)H a2%", "NAD(P)H a2[%]"),
    ]
    assert report.config.features == ["FLIRR", "FAD a1[%]", "NAD(P)H a2[%]"]
    assert config.features == FEATURES  # the user's settings are unchanged
    # every step was checked, with the guessed columns
    assert len(report.steps) > 10
    assert all(None not in step.inputs for step in report.steps)


def test_strict_reports_errors(data):
    config = BasicFLIRRConfig(grouping=["Treatment", "FOV"], features=FEATURES, strict=True)
    report = BasicFLIRR().resolve(config, [data], strict=False)  # the config's wins
    assert [i.field for i in report.errors] == ["features[1]", "features[2]"]
    assert report.guesses == []
    # the steps do not repeat the workflow's missing columns
    assert all(i.step is None for i in report.issues)


def test_guesses_reach_the_steps_bound_fields(data):
    config = AETuneConfig(grouping=["Treatment", "FOV"], features=FEATURES)
    report = AETune().resolve(config, [data], strict=False)
    assert report.errors == []
    assert report.config.training.features == report.config.features
    assert "FAD a1[%]" in report.config.augment.features


class StepsConfig(WorkflowConfig):
    grouping: list[CategoryColumn] = ["Treatment"]
    features: list[FeatureColumn] = ["FLIRR"]
    pivot_by: list[CategoryColumn] = ["FOV"]


class SummaryPivot(Workflow[StepsConfig]):
    """Summarizes, then pivots the summary (not registered: a test's)."""

    name = "Test: Summary Pivot"

    def build(self, data, *, config):
        summary = Summarize()(
            workflow_input(data),
            config=SummaryConfig(
                grouping=config.grouping, features=config.features, aggs=["mean"]
            ),
        )["Table: Summary"]
        Pivot()(summary, config=PivotConfig(grouping=config.pivot_by))


def test_steps_are_checked_against_earlier_outputs(data):
    # FOV is in the input, but not in the summary (grouped by Treatment only)
    report = SummaryPivot().resolve(StepsConfig(), [data])
    (error,) = report.errors
    assert (error.step, error.field) == ("Pivot", "grouping[0]")
    assert "'FOV' is not in the input" in error.message
    report = SummaryPivot().resolve(StepsConfig(grouping=["Treatment", "FOV"]), [data])
    assert report.issues == []
    pivot = report.steps[-1]
    assert pivot.inputs[0].names == ["Treatment", "FOV", "FLIRR\nmean"]
    # the dialogs' check (not strict)
    issues = SummaryPivot.validate(StepsConfig(), [TableSchema.from_frame(data)])
    assert [i.step for i in issues] == ["Pivot"]


def test_unknown_inputs_are_not_checked():
    report = SummaryPivot().resolve(StepsConfig(), [None])
    assert report.issues == [] and report.steps == []


def step_config(report, tool_name):
    return next(s.config for s in report.steps if s.name.startswith(tool_name))


def test_basic_flirr_settings_taken_from_the_data(data):
    config = BasicFLIRRConfig(grouping=["Treatment", "FOV"], features=["FLIRR"])
    report = BasicFLIRR().resolve(config, [data])
    # empty: the first value of the first grouping column; the columns by name
    first = list(data["Treatment"].cat.categories)[0]  # in category order
    assert step_config(report, "Relative Change").reference_value == first
    scatter = step_config(report, "Scatter Plot")
    assert (scatter.features, scatter.x_axis) == (["FAD a1[%]", "NAD(P)H a2[%]"], "FAD a1[%]")
    # set: used
    config = config.model_copy(
        update={"reference_value": "Dox30", "fad_a1": "NAD(P)H a2", "nadph_a2": "FAD a1"}
    )
    report = BasicFLIRR().resolve(config, [data])
    assert step_config(report, "Relative Change").reference_value == "Dox30"
    scatter = step_config(report, "Scatter Plot")
    assert (scatter.features, scatter.x_axis) == (["NAD(P)H a2", "FAD a1"], "NAD(P)H a2")


def test_time_points_in_category_order():
    from flim.tools.common import ordered_values as series_values

    column = pd.Series(
        pd.Categorical(["Dox30", "ctrl", "Dox15"], categories=["ctrl", "Dox15", "Dox30", "Dox60"])
    )
    # all values (none skipped for containing "15"), unused categories left out
    assert series_values(column) == ["ctrl", "Dox15", "Dox30"]
    assert series_values(pd.Series(["b", "a", "b"])) == ["b", "a"]


class TestRuns:
    @pytest.fixture(scope="class", autouse=True)
    def prefect_harness(self):
        from prefect.testing.utilities import prefect_test_harness

        with prefect_test_harness():
            yield

    def test_strict_runs_stop_before_they_start(self, data):
        config = BasicFLIRRConfig(grouping=["Treatment", "FOV"], features=FEATURES)
        with pytest.raises(WorkflowValidationError, match="'FAD a1%' is not in the"):
            BasicFLIRR().run_flow(data, config=config)  # strict by default

    def test_runs_use_and_report_the_guesses(self, data, tmp_path):
        config = SummaryPivot.config_class(
            grouping=["Treatment", "FOV"], features=["flirr"]
        )
        run = SummaryPivot().run_flow(
            data, config=config, autosave_dir=str(tmp_path), strict=False
        )
        assert run.failed == []
        (summary,) = tmp_path.rglob("run_summary.txt")
        text = summary.read_text()
        assert "features[0]: 'flirr' -> 'FLIRR' (guessed)" in text
        # the resources each task was granted
        assert "Resources" in text and "cpu, 1 thread" in text
        assert [label for label, _ in run.resources()] == ["Summarize", "Pivot"]
