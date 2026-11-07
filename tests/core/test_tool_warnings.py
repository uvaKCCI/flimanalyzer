"""Tools report warnings (Tool.warn): the task stays completed, its results go on, and
the warning is the task's message (run summary, Prefect UI). First use: Concatenate side
by side warns when the tables' rows don't match by their categories (0.6.2)."""

import pandas as pd
import pytest

import flim.tools  # noqa: F401
from flim.configs.data import ConcatConfig
from flim.core.registry import tools

SIDE_BY_SIDE = ConcatConfig(mode="horizontal", numbers_only=True)


def _table(order=("Ctrl", "Drug", "Ctrl", "Drug"), x=(1.0, 2.0, 3.0, 4.0)):
    return pd.DataFrame({"Treatment": pd.Categorical(list(order)), "x": list(x)})


def _warnings(tables, config=SIDE_BY_SIDE):
    tool = tools.get("Concatenate")()
    tool(tables, config=config)
    return tool.context.warnings


def test_reordered_table_warns():
    a = _table()
    b = a.sort_values("Treatment", ascending=False, kind="stable", ignore_index=True)
    (warning,) = _warnings({"Table: A": a, "Table: B": b})
    assert "'Table: B' don't match 'Table: A'" in warning
    assert "row 1, Treatment: Ctrl and Drug" in warning and "Merge" in warning


def test_same_order_does_not_warn():
    assert _warnings({"Table: A": _table(), "Table: B": _table(x=(5, 6, 7, 8))}) == []


def test_different_row_counts_warn():
    (warning,) = _warnings({"Table: A": _table(), "Table: B": _table().head(3)})
    assert "4 and 3 rows" in warning


def test_no_shared_categories_do_not_warn():
    b = pd.DataFrame({"y": [1.0, 2.0, 3.0, 4.0]})
    assert _warnings({"Table: A": _table(), "Table: B": b}) == []


def test_rows_below_each_other_do_not_warn():
    b = _table(order=("Drug", "Drug", "Ctrl", "Ctrl"))
    assert _warnings({"Table: A": _table(), "Table: B": b}, ConcatConfig()) == []


@pytest.mark.usefixtures("prefect_harness")
def test_warning_in_the_flow_run_and_its_summary(tmp_path):
    # the task stays completed, its results reach the next task, and the warning is
    # its message in FlowRun.warnings and run_summary.txt
    from flim.core.runner import run_flow

    a = _table()
    b = a.sort_values("Treatment", ascending=False, kind="stable", ignore_index=True)
    Concat, Summarize = tools.get("Concatenate"), tools.get("Summarize")

    def build():
        joined = Concat()({"Table: A": a, "Table: B": b}, config=SIDE_BY_SIDE)
        Summarize()(
            joined["Table: Concatenated"],
            config=Summarize.config_class(features=["x", "x (Table: B)"], aggs=["mean"]),
        )

    run = run_flow("warning test", build, autosave_dir=str(tmp_path))
    assert run.state == "completed" and not run.failed
    ((label, message),) = run.warnings
    assert label == "Concatenate" and "use Merge" in message
    summary = next(tmp_path.rglob("run_summary.txt")).read_text()
    assert "use Merge" in summary
    assert any("Summary" in name for result in run.results() for name in result)


def test_numeric_only_side_by_side_renames_taken_names():
    # both tables have x: the second becomes "x (Table: B)", not a second "x"
    out = tools.get("Concatenate")()(
        {"Table: A": _table(), "Table: B": _table(x=(5, 6, 7, 8))}, config=SIDE_BY_SIDE
    )
    columns = list(next(iter(out.values())).columns)
    assert columns == ["Treatment", "x", "x (Table: B)"]
