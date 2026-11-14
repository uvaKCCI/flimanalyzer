"""Workflow files: format and checks (flim.core.workflowfile)."""

import json
from pathlib import Path

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
    "steps": [
        {"id": 1, "tool": "Calculate", "processing": "allow_partial"},
        {"id": "2", "tool": "Summarize", "inputs": ["1.1"], "config": {"aggs": ["mean"]}, "output": {"save": True}},
        {"id": "3", "tool": "Sort", "output": {"save": ["3.1"]}},  # no inputs: step 2's output 1
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
        (lambda d: d["steps"][2].update(output={"save": ["2.1"]}), "is not this step's"),
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
    # the folders of -w come first, before the environment variable
    assert workflow_path([folder], [folder / "a", folder / "b"]) == [folder / "a", folder / "b"]


@pytest.mark.parametrize(
    "name, is_file",
    [("Summarize", False), ("Basic FLIRR Analysis", False), ("calc.json", True),
     ("calc.JSON", True), ("sub/calc", True), ("./calc", True)],
)
def test_a_run_argument_names_a_file_or_a_registered_name(name, is_file):
    from flim.core.workflowfile import is_workflow_file

    assert is_workflow_file(name) is is_file


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
            {"id": "2", "tool": "Concatenate", "output": {"save": True}},
        ],
    }
    run = _run(definition, _tables(), autosave_dir=tmp_path)
    assert run.state == "completed", run.failed
    saved = [p.name for p in run.autosave_dir.rglob("*.txt") if p.name != "run_summary.txt"]
    assert saved == ["Table_Concatenated.txt"], saved  # not the inputs, not step 1


def test_a_step_saves_in_its_own_formats(prefect_harness, tmp_path):
    definition = {
        "name": "formats",
        "output": {"formats": [{"kind": "table", "format": "csv"}]},
        "steps": [
            {"id": "1", "tool": "Calculate", "config": {"calculations": [CALC]},
             "output": {"save": True}},  # the workflow's formats: csv
            {"id": "2", "tool": "Concatenate",
             "output": {"save": True, "formats": [{"kind": "table", "format": "tsv"}]}},
        ],
    }  # fmt: skip
    # the caller passes the workflow's formats (the GUI's dialog may change them)
    formats = WorkflowDefinition.model_validate(definition).output.formats
    run = _run(definition, _tables(), autosave_dir=tmp_path, save_formats=formats)
    assert run.state == "completed", run.failed
    names = {p.name for p in run.autosave_dir.rglob("*") if p.suffix in (".csv", ".txt")}
    assert "Table_Concatenated.txt" in names  # step 2: its own tsv
    assert any(n.endswith(".csv") for n in names)  # step 1: the workflow's csv
    assert not any(n.endswith(".csv") and "Concatenated" in n for n in names)


def test_a_step_classname_must_be_its_tools(tmp_path):
    from flim.core.registry import tools

    summarize = tools.get("Summarize")
    own = f"{summarize.__module__}.{summarize.__qualname__}"
    data = {"name": "classnames", "steps": [
        {"id": "1", "tool": "Summarize", "config": {"classname": own}},
        {"id": "2", "tool": "Sort", "config": {"classname": own}},
    ]}  # fmt: skip
    check = check_workflow_file(write(tmp_path, data))
    assert len(check.errors) == 1
    assert "step 2" in check.errors[0].lower() and "is not the class of 'Sort'" in check.errors[0]


def test_a_tool_file_is_not_a_workflow_file_unless_asked(tmp_path):
    path = write(tmp_path, {"schema_version": 2, "tool": "Sort", "config": {}}, "sort.json")
    check = check_workflow_file(path)
    assert check.errors == ["sort.json: a tool file (the settings of Sort), not a workflow file"]
    check = check_workflow_file(path, tool_files=True)
    assert check.errors == [] and check.definition.name == "Sort"
    (step,) = check.definition.steps
    assert (step.id, step.tool, step.output.save) == ("1", "Sort", True)


def test_a_step_description_and_no_output_names(tmp_path):
    data = {"name": "notes", "steps": [{"id": "1", "tool": "Sort", "description": "by FOV"}]}
    assert check_workflow_file(write(tmp_path, data)).definition.steps[0].description == "by FOV"
    data["steps"][0]["output"] = {"items": {"1": "sorted"}}  # names of outputs: not a field
    assert check_workflow_file(write(tmp_path, data)).errors


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


# what FLIMAnalyzer 0.6's import gave for `raw_dir` (tests/core/data/import-0.6, written
# with the 0.6 importer before it was removed; without Source and Directory, which name
# the temporary folder)
IMPORT_0_6 = Path(__file__).parent / "data" / "import-0.6"


def assert_as_in_0_6(new: pd.DataFrame, reference: str) -> None:
    """Assert that a table equals a stored result of 0.6's import, row by row."""
    old = pd.read_csv(IMPORT_0_6 / reference, sep="\t")
    new = new.drop(columns=["Source", "Directory"]).sort_values("File", kind="stable")
    assert set(new.columns) == set(old.columns)
    columns = sorted(old.columns)
    # category and text columns are read back as numbers where they look like them
    text = {c: str for c in columns if not pd.api.types.is_numeric_dtype(new[c])}
    pd.testing.assert_frame_equal(
        new[columns].reset_index(drop=True).astype(text),
        old[columns].reset_index(drop=True).astype(text),
        check_dtype=False,
    )


@pytest.mark.parametrize(
    "preset, parser", [(None, "defaultparser"), ("FOV, Treatment, Cell", "fov_treatment_cell_parser")]
)
def test_built_in_import_and_presets_match_the_import_of_0_6(prefect_harness, raw_dir, tmp_path, preset, parser):
    """Import alone, and Import with the Separate Categories step of a preset, give
    what 0.6's import gave with the default parser or that filename parser."""
    from flim.core.reader import read_tables
    from flim.core.workflowfile import BUILT_IN

    from tests.workflows import import_with_preset, write_workflow

    path = BUILT_IN / "import.json" if preset is None else write_workflow(
        tmp_path / "preset.json", import_with_preset(preset)
    )
    check = check_workflow_file(path)
    assert check.errors == []
    run = workflow_class(check.definition)().run_flow(read_tables([raw_dir]).tables)
    assert run.state == "completed", run.failed
    (new,) = [v for r in run.results() if isinstance(r, dict) for k, v in r.items() if k == "Table: Calculated"]
    assert_as_in_0_6(new, f"{parser}.txt")


def test_old_import_settings_become_an_equivalent_workflow(prefect_harness, raw_dir, tmp_path):
    from flim.core.reader import read_tables
    from flim.core.settings import check_settings_file

    v1 = json.loads((Path(__file__).parent / "data" / "settings_v1.json").read_text())
    v1["import"]["filename_parser"] = {"parser": "fov_treatment_cell_parser", "patterns": []}
    v1["import"]["category_combinations"] = [["FOV", "Treatment"]]
    settings_file = write(tmp_path, v1, "old.json")
    check = check_settings_file(settings_file)
    assert check.import_workflow["name"] == "Import (old)"
    assert check.import_workflow["tags"] == ["import"] and "read" not in check.import_workflow
    assert check.import_read == {}  # the default delimiter, no files left out
    path = write(tmp_path, check.import_workflow, "old-import.json")
    result = check_workflow_file(path)
    assert result.errors == []
    tools_in_order = [s.tool for s in result.definition.steps]
    assert tools_in_order == [
        "Rename Columns", "Drop Columns", "Concatenate", "Separate Categories",
        "Fuse Categories", "Calculate",
    ]
    run = workflow_class(result.definition)().run_flow(read_tables([raw_dir]).tables)
    assert run.state == "completed", run.failed
    (new,) = [v for r in run.results() if isinstance(r, dict) for k, v in r.items() if k == "Table: Calculated"]
    assert_as_in_0_6(new, "settings_v1_fov_treatment_cell.txt")


def _steps(section):
    from flim.core.workflowfile import import_workflow_data

    return import_workflow_data(section, {}, "old")["steps"]


def test_old_import_with_own_patterns_skips_those_not_in_use():
    section = {
        "filename_parser": {
            "parser": "fov_treatment_cell_parser",  # own patterns replace the parser's
            "patterns": [
                {"Use": True, "Category": "A", "Regex": r"/(\w+)_"},
                {"Use": False, "Category": "B", "Regex": r"_(\w+)\."},
            ],
        }
    }
    (separate,) = [s for s in _steps(section) if s["tool"] == "Separate Categories"]
    assert separate["config"]["patterns"] == [{"name": "A", "regex": r"/(\w+)_"}]


@pytest.mark.parametrize("parser", ["defaultparser", "no_parser", "unknown_parser"])
def test_old_import_without_patterns_has_no_separate_step(parser):
    steps = _steps({"filename_parser": {"parser": parser}, "category_combinations": []})
    assert [s["tool"] for s in steps] == ["Rename Columns", "Drop Columns", "Concatenate", "Calculate"]


def test_old_import_with_no_combinations_listed_fuses_all_pairs():
    section = {"filename_parser": {"parser": "fov_treatment_cell_parser"}, "category_combinations": []}
    fused = [s["config"]["grouping"] for s in _steps(section) if s["tool"] == "Fuse Categories"]
    assert fused == [["FOV", "Treatment"], ["FOV", "Cell"], ["Treatment", "Cell"]]
    section["category_combinations"] = None  # none
    assert not [s for s in _steps(section) if s["tool"] == "Fuse Categories"]


def test_each_task_records_its_settings_in_prefect(prefect_harness):
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterFlowRunId

    definition = {
        "name": "settings artifact",
        "steps": [{"id": "1", "tool": "Summarize", "config": {"aggs": ["max"], "features": ["t1"]}}],
    }
    run = _run(definition, {"a.txt": _tables()["a.txt"]})
    assert run.state == "completed"
    with get_client(sync_client=True) as client:
        artifacts = client.read_artifacts(
            artifact_filter=ArtifactFilter(flow_run_id=ArtifactFilterFlowRunId(any_=[run.flow_run_id]))
        )
    settings = [a for a in artifacts if (a.description or "").startswith("Summarize")]
    assert len(settings) == 1 and '"aggs"' in settings[0].data and '"max"' in settings[0].data


def test_each_run_records_app_execution_and_inputs_and_sends_its_logs_to_prefect(prefect_harness, monkeypatch):
    import json
    import logging

    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterFlowRunId, LogFilter, LogFilterFlowRunId
    from prefect.logging.handlers import APILogHandler

    from flim.tools.statistics import Summarize as Summary

    original = Summary.run

    def logging_run(self, *args, **kwargs):
        logging.getLogger("flim.tools.statistics").info("summarizing for the test")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Summary, "run", logging_run)
    monkeypatch.setattr(logging.getLogger("flim"), "level", logging.INFO)
    table = _tables()["a.txt"].assign(Source=["file:///data/a.txt", "file:///data/a.txt"])
    definition = {
        "name": "run record",
        "steps": [{"id": "1", "tool": "Summarize", "config": {"aggs": ["max"], "features": ["t1"]}}],
    }
    run = _run(definition, {"a.txt": table})
    assert run.state == "completed"
    logging.getLogger("flim.core").info("outside any run: not sent")  # no warning either
    APILogHandler().flush()  # the records are sent by a background worker
    with get_client(sync_client=True) as client:
        artifacts = client.read_artifacts(
            artifact_filter=ArtifactFilter(flow_run_id=ArtifactFilterFlowRunId(any_=[run.flow_run_id]))
        )
        logs = client.read_logs(log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=[run.flow_run_id])))
    (record,) = [a for a in artifacts if "app version, execution and input files" in (a.description or "")]
    data = json.loads(record.data.split("```json\n", 1)[1].rsplit("```", 1)[0])
    assert data["app"]["FLIMAnalyzer"] and data["app"]["pandas"] and data["app"]["Python"]
    assert data["execution"]["task runner"] == "ThreadPoolTaskRunner"
    assert data["input files"] == ["file:///data/a.txt"]
    assert any("summarizing for the test" in log.message for log in logs)


def test_tags_and_menu_groups():
    from flim.core.workflowfile import (
        BUILT_IN, IMPORT_TAG, WorkflowDefinition, check_workflow_file, panel_group,
        workflow_group,
    )

    steps = [{"id": "1", "tool": "Sort"}]
    assert WorkflowDefinition(name="a", steps=steps).tags == []
    assert workflow_group(WorkflowDefinition(name="a", steps=steps)) == "Workflow Files"
    assert workflow_group(WorkflowDefinition(name="a", tags=["summaries", "x"], steps=steps)) == "Summaries"
    groups = ["File", "Data", "Plot", "Workflow"]
    tagged = WorkflowDefinition(name="a", tags=["file", "import"], steps=steps)
    assert workflow_group(tagged, groups) == "Import"  # group names are passed over
    assert panel_group(tagged, groups) == "File"
    assert panel_group(WorkflowDefinition(name="a", tags=["x"], steps=steps), groups) is None
    assert workflow_group(WorkflowDefinition(name="a", tags=["Plot"], steps=steps), groups) == "Workflow Files"
    for path in BUILT_IN.glob("*.json"):  # all built-in files: data workflows for import
        assert check_workflow_file(path).definition.tags == [IMPORT_TAG], path.name
