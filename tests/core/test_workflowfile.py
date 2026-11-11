"""Workflow files: format and checks (flim.core.workflowfile)."""

import json

import pytest

import flim.tools  # noqa: F401  (registers the tools)
from flim.core.workflowfile import (
    WORKFLOW_SCHEMA_VERSION,
    check_workflow_file,
    find_workflow_file,
    parse_reference,
    workflow_path,
)


def write(tmp_path, data, name="wf.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


GOOD = {
    "schema_version": 1,
    "name": "calc and aggregate",
    "read": {"delimiter": "\t,"},
    "steps": [
        {"id": 1, "tool": "Calculate", "processing": "allow_partial"},
        {"id": "2", "tool": "Summarize", "inputs": ["1.1"], "config": {"aggs": ["mean"]}, "save": True},
        {"id": "3", "tool": "Sort", "save": ["3.1"]},  # no inputs: step 2's output 1
    ],
}


def test_a_valid_file(tmp_path):
    check = check_workflow_file(write(tmp_path, GOOD))
    assert check.errors == []
    definition = check.definition
    assert definition.name == "calc and aggregate"
    assert [s.id for s in definition.steps] == ["1", "2", "3"]  # numbers as text
    assert definition.steps[0].processing == "allow_partial"
    assert definition.steps[1].processing == "require_all"  # the default


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda d: d["steps"][1].update(inputs=["3"]), "not an output of an earlier step"),
        (lambda d: d["steps"][1].update(inputs=["1.0"]), "1 or more"),
        (lambda d: d["steps"][2].update(id="1"), "used twice"),
        (lambda d: d["steps"][0].update(tool="Nope"), "no tool or workflow named 'Nope'"),
        (lambda d: d["steps"][1].update(config={"aggs": ["bogus"]}), "settings not valid"),
        (lambda d: d["steps"][2].update(save=["2.1"]), "is not this step's"),
        (lambda d: d["steps"][0].update(processing="lenient"), "processing"),
        (lambda d: d["steps"][0].update(colour="red"), "colour"),
        (lambda d: d.update(steps=[]), "steps"),
        (lambda d: d.pop("name"), "name"),
    ],
)
def test_errors(tmp_path, change, message):
    data = json.loads(json.dumps(GOOD))
    change(data)
    check = check_workflow_file(write(tmp_path, data))
    assert check.definition is None
    assert any(message in e for e in check.errors), check.errors


def test_unreadable_and_newer_files(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    assert "can't be read" in check_workflow_file(bad).errors[0]
    newer = write(tmp_path, {**GOOD, "schema_version": WORKFLOW_SCHEMA_VERSION + 1})
    assert "update FLIMAnalyzer" in check_workflow_file(newer).errors[0]


def test_references():
    assert parse_reference("4.2") == ("4", 2)
    assert parse_reference("4") == ("4", 1)
    assert parse_reference("input") == ("input", 1)


def test_search_path(tmp_path, monkeypatch):
    folder = tmp_path / "workflows"
    folder.mkdir()
    path = write(folder, GOOD, "calc.json")
    monkeypatch.delenv("FLIM_WORKFLOW_PATH", raising=False)
    assert workflow_path([folder]) == [folder]
    assert find_workflow_file("calc", [folder]) == path  # a name in the search path
    assert find_workflow_file(str(path)) == path  # a path
    with pytest.raises(FileNotFoundError):
        find_workflow_file("gone", [folder])
    monkeypatch.setenv("FLIM_WORKFLOW_PATH", str(tmp_path))
    assert workflow_path([folder]) == [tmp_path]


# --- running workflow files ---

import pandas as pd  # noqa: E402

from flim.core.workflowfile import WorkflowDefinition, register_workflow_files, workflow_class  # noqa: E402


def _tables():
    return {
        "a.txt": pd.DataFrame({"FOV": pd.Categorical(["1", "2"]), "t1": [1.0, 3.0]}),
        "b.txt": pd.DataFrame({"FOV": pd.Categorical(["1", "2"]), "t1": [5.0, 7.0]}),
    }


def _run(definition, tables, **kwargs):
    workflow = workflow_class(WorkflowDefinition.model_validate(definition))
    return workflow().run_flow(tables, **kwargs)


def _completed(run):
    return {a["label"]: a for _, a in run.graph.nodes(data=True) if "tool" in a and a["status"] == "completed"}


CALC = {
    "kind": "expression", "name": "t2", "expression": "t1 * 2",
}  # fmt: skip


def test_steps_are_mapped_per_table_and_reduced(prefect_harness):
    definition = {
        "name": "map and reduce",
        "steps": [
            {"id": "1", "tool": "Calculate", "config": {"calculations": [CALC]}},
            {"id": "2", "tool": "Concatenate", "config": {"add_input": True}},
            {"id": "3", "tool": "Summarize", "config": {"aggs": ["mean"], "features": ["t2"]}},
        ],
    }
    run = _run(definition, _tables())
    assert run.state == "completed", run.failed
    results = [r for r in run.results() if isinstance(r, dict)]
    (summary,) = [v for r in results for k, v in r.items() if k.startswith("Table: Summary")]
    assert summary.iloc[0, -1] == pytest.approx((2 + 6 + 10 + 14) / 4)
    labels = list(_completed(run))
    assert sum(label.startswith("Calculate") for label in labels) == 2  # once per table
    assert sum(label.startswith("Concatenate") for label in labels) == 1


def test_without_a_reducing_step_each_table_runs_to_the_end(prefect_harness):
    definition = {
        "name": "per file",
        "steps": [{"id": "1", "tool": "Summarize", "config": {"aggs": ["max"], "features": ["t1"]}}],
    }
    run = _run(definition, _tables())
    assert sum(label.startswith("Summarize") for label in _completed(run)) == 2


def test_save_decides_what_is_written(prefect_harness, tmp_path):
    definition = {
        "name": "saving",
        "steps": [
            {"id": "1", "tool": "Calculate", "config": {"calculations": [CALC]}},
            {"id": "2", "tool": "Concatenate", "save": True},
        ],
    }
    run = _run(definition, _tables(), autosave_dir=tmp_path)
    assert run.state == "completed", run.failed
    saved = [p.name for p in run.autosave_dir.rglob("*.txt") if p.name != "run_summary.txt"]
    assert saved == ["Table_Concatenated.txt"], saved  # not the inputs, not step 1


def test_processing(prefect_harness):
    missing = {"kind": "expression", "name": "x", "expression": "gone * 2"}
    for processing, state in (("require_all", "failed"), ("allow_partial", "completed"), ("allow_none", "completed")):
        calcs = [missing] if processing == "allow_none" else [CALC, missing]
        definition = {
            "name": f"processing {processing}",
            "steps": [{"id": "1", "tool": "Calculate", "processing": processing, "config": {"calculations": calcs}}],
        }
        run = _run(definition, {"a.txt": _tables()["a.txt"]})
        statuses = {a["status"] for _, a in run.graph.nodes(data=True) if "tool" in a and a["label"].startswith("Calculate")}
        assert statuses == {state}, (processing, statuses)
    # allow_partial needs at least one part applied
    definition = {
        "name": "nothing applies",
        "steps": [{"id": "1", "tool": "Calculate", "processing": "allow_partial", "config": {"calculations": [missing]}}],
    }
    run = _run(definition, {"a.txt": _tables()["a.txt"]})
    assert "failed" in {a["status"] for _, a in run.graph.nodes(data=True) if "tool" in a}


def test_mixing_per_table_and_single_is_an_error():
    definition = WorkflowDefinition.model_validate({
        "name": "mixed",
        "steps": [
            {"id": "1", "tool": "Concatenate"},
            {"id": "2", "tool": "Merge", "inputs": ["1", "input"]},
        ],
    })
    issues = workflow_class(definition).validate(None, [])
    assert any("combines tables per file with a single table" in i.message for i in issues)


def test_registration_by_name(tmp_path):
    from flim.core.registry import tools

    write(tmp_path, {**GOOD, "name": "Calc And Aggregate Test"}, "calc.json")
    write(tmp_path, {**GOOD, "name": "summarize"}, "clash.json")  # a tool's name
    write(tmp_path, {"name": "broken", "steps": []}, "broken.json")
    try:
        messages = register_workflow_files([tmp_path])
        assert "Calc And Aggregate Test" in tools
        assert tools.get("Calc And Aggregate Test").definition.steps[1].tool == "Summarize"
        assert any("clash.json" in m and "conflict" in m for m in messages)
        assert any("broken.json" in m for m in messages)
    finally:
        tools.unregister("Calc And Aggregate Test")


# --- the built-in import workflow files ---


@pytest.fixture
def raw_dir(tmp_path):
    """Raw result files with the channels' column names, named <x>_<FOV>_<Treatment>_<Cell>."""
    import numpy as np

    rng = np.random.default_rng(3)
    folder = tmp_path / "data"
    folder.mkdir()
    for treatment in ("WT", "KO"):
        for cell in ("1", "2"):
            a1 = rng.uniform(60, 80, 3)
            pd.DataFrame(
                {
                    "Exc1_-Ch2-_a1[%]": a1,
                    "Exc1_-Ch2-_a2[%]": 100 - a1,
                    "Exc1_-Ch2-_t1": rng.normal(400, 20, 3),
                    "Exc1_-Ch2-_t2": rng.normal(2500, 100, 3),
                    "Exc2_-Ch3-_a1[%]": rng.uniform(20, 40, 3),
                    "Exc3_-Ch4-_x": rng.normal(0, 1, 3),
                }
            ).to_csv(folder / f"Results_FOV1_{treatment}_{cell}.txt", sep="\t", index=False)
    return folder


@pytest.mark.parametrize(
    "file, parser",
    [("import.json", "defaultparser"), ("import-fov-treatment-cell.json", "fov_treatment_cell_parser")],
)
def test_built_in_import_files_match_the_import_of_0_6(prefect_harness, raw_dir, file, parser):
    from flim.core.reader import read_tables
    from flim.core.settings import AppSettings
    from flim.configs import ImportConfig
    from flim.core.workflowfile import BUILT_IN
    from flim.tools.data import Import, import_steps

    check = check_workflow_file(BUILT_IN / file)
    assert check.errors == []
    run = workflow_class(check.definition)().run_flow(read_tables([raw_dir]).tables)
    assert run.state == "completed", run.failed
    (new,) = [v for r in run.results() if isinstance(r, dict) for k, v in r.items() if k == "Table: Calculated"]
    settings = AppSettings.default()
    settings.tools.set(Import, ImportConfig(parser=parser))
    old = import_steps([raw_dir], settings)  # 0.6's import path (Import tool and steps)
    assert set(new.columns) == set(old.columns)
    columns = sorted(old.columns)
    pd.testing.assert_frame_equal(
        new.sort_values("Source").reset_index(drop=True)[columns],
        old.sort_values("Source").reset_index(drop=True)[columns],
        check_categorical=False,
    )


def test_every_built_in_file_is_valid():
    from flim.core.workflowfile import BUILT_IN

    files = sorted(BUILT_IN.glob("*.json"))
    assert len(files) == 9
    for path in files:
        assert check_workflow_file(path).errors == [], path
