"""The run summary, `run_summary.txt` (flim.core.runner)."""

import datetime
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
