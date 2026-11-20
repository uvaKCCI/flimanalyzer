"""The run summary, `run_summary.txt` (flim.core.runner)."""

import datetime
import hashlib
import re

import pandas as pd
import pytest

import flim.tools  # noqa: F401
from flim.core.registry import tools
from flim.core.runner import elapsed


def test_elapsed_in_hours_minutes_and_seconds():
    start = datetime.datetime(2026, 11, 17, 10, 0, 0)
    assert elapsed(start, start + datetime.timedelta(seconds=125.4)) == "0:02:05"
    assert elapsed(start, start + datetime.timedelta(days=1, hours=3)) == "27:00:00"
    assert elapsed(start, start) == "0:00:00"


@pytest.mark.usefixtures("prefect_harness")
def test_summary_states_the_elapsed_time(tmp_path):
    from flim.core.runner import run_flow

    table = pd.DataFrame({"Treatment": ["a", "b"], "x": [1.0, 2.0]})
    Summarize = tools.get("Summarize")

    def build():
        Summarize()(table, config=Summarize.config_class(features=["x"], aggs=["mean"]))

    run = run_flow("elapsed test", build, autosave_dir=str(tmp_path))
    summary = next(tmp_path.rglob("run_summary.txt")).read_text()
    assert run.state == "completed"
    finished = summary.index("Finished:")
    assert re.search(r"^Elapsed:    \d+:\d\d:\d\d$", summary, re.M)
    assert summary.index("Elapsed:") > finished  # after Started and Finished


def _inputs(summary: str) -> list[list[str]]:
    """Return the rows of the run summary's `Inputs` table, split at two spaces."""
    lines = summary.splitlines()
    start = lines.index("Inputs:") + 2  # after the header
    rows = []
    for line in lines[start:]:
        if not line.strip():
            break
        rows.append(re.split(r"\s{2,}", line.strip()))
    return rows


@pytest.mark.usefixtures("prefect_harness")
def test_inputs_list_each_input_once_with_the_steps_it_enters(tmp_path):
    from flim.core.runner import InputOrigin, run_flow
    from flim.core.types import TableType

    a = pd.DataFrame({"Treatment": pd.Categorical(["a", "b"]), "x": [1.0, 2.0]})
    b = pd.DataFrame({"x": [3.0, None]})
    path = tmp_path / "a.txt"
    a.to_csv(path, sep="\t", index=False)
    Summarize = tools.get("Summarize")
    config = Summarize.config_class(features=["x"], aggs=["mean"])

    def build():
        first = Summarize()(a, config=config, step="01")["Table: Summary"]
        Summarize()(first, config=config, step="02")  # passed on: not an input
        Summarize()(a, config=config, step="03")  # the same table: one row
        Summarize()(b, config=config, step="03")

    run_flow("inputs", build, autosave_dir=str(tmp_path / "out"),
             input_origins=[(a, InputOrigin(file=path))])  # fmt: skip
    summary = next((tmp_path / "out").rglob("run_summary.txt")).read_text()
    assert summary.index("Inputs:") < summary.index("Task ")  # above the task table
    (first, second) = _inputs(summary)
    assert first[:4] == ["1", "01, 03", "file", str(path.absolute())]
    assert first[6] == hashlib.sha256(path.read_bytes()).hexdigest()  # the file's, not the table's
    assert second[:6] == ["2", "03", "table", "pandas.DataFrame", "2 rows x 1 cols", "float64 (1)"]
    assert second[6] == TableType.content_hash(b)
    assert second[7] == "1 features; 1 missing"


@pytest.mark.usefixtures("prefect_harness")
def test_inputs_through_an_input_node_enter_the_steps_that_use_it(tmp_path):
    from flim.core.runner import run_flow
    from flim.core.workflow import workflow_input

    table = pd.DataFrame({"x": [1.0, 2.0]})
    Summarize = tools.get("Summarize")
    config = Summarize.config_class(features=["x"], aggs=["mean"])

    def build():
        given = workflow_input(table, step="00")
        Summarize()(given, config=config, step="01")
        Summarize()(given, config=config, step="02")

    run_flow("input node", build, autosave_dir=str(tmp_path))
    summary = next(tmp_path.rglob("run_summary.txt")).read_text()
    ((row),) = _inputs(summary)
    assert row[1] == "01, 02"  # not 00: the Input node passes it on


@pytest.mark.usefixtures("prefect_harness")
def test_a_tool_run_has_no_step(tmp_path):
    from flim.core.runner import run_flow

    table = pd.DataFrame({"x": [1.0, 2.0]})
    Summarize = tools.get("Summarize")

    def build():
        Summarize()(table, config=Summarize.config_class(features=["x"], aggs=["mean"]))

    run_flow("tool run", build, autosave_dir=str(tmp_path))
    ((row),) = _inputs(next(tmp_path.rglob("run_summary.txt")).read_text())
    assert row[1] == "-"
