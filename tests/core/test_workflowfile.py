"""Workflow files: format and checks (flim.core.workflowfile)."""

import json
from pathlib import Path

import pytest

import flim.tools  # noqa: F401  (registers the tools)
from flim.core.workflowfile import (
    WORKFLOW_SCHEMA_VERSION,
    validate_workflow_file,
    find_workflow_file,
    parse_reference,
    validate_steps,
    workflow_path,
)
from flim.core.schema import TableSchema


def write(tmp_path, data, name="wf.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return path


GOOD = {
    "schema_version": 1,
    "name": "calc and aggregate",
    "steps": [
        {"id": 1, "tool": "Calculate", "processing": {"skippable": {"calculations": "some"}}},
        {"id": "2", "tool": "Summarize", "inputs": ["1.1"], "config": {"aggs": ["mean"]}, "output": {"save": True}},
        {"id": "3", "tool": "Sort", "output": {"save": ["3.1"]}},  # no inputs: step 2's output 1
    ],
}


def test_a_valid_file(tmp_path):
    validation = validate_workflow_file(write(tmp_path, GOOD))
    assert validation.errors == []
    definition = validation.definition
    assert definition.name == "calc and aggregate"
    assert [s.id for s in definition.steps] == ["1", "2", "3"]  # numbers as text
    assert definition.rules(definition.steps[0]).skip("calculations") == "some"
    assert definition.rules(definition.steps[1]).skip("features") == "none"  # the default
    assert definition.rules(definition.steps[1]).is_strict("features[0]")  # the default


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
        (lambda d: d["steps"][0].update(processing={"skippable": {"calculations": "most"}}), "processing"),
        (lambda d: d["steps"][1].update(processing={"skippable": {"aggs": "some"}}), "Summarize can't skip entries of 'aggs'"),
        (lambda d: d["steps"][1].update(processing={"strict": {"colour": False}}), "Summarize has no field 'colour'"),
        (lambda d: d["steps"][1].update(config={"features": ["a"]}, processing={"skippable": {"features": "some"}, "required": {"features": ["b"]}}), "processing.required.features: 'b' is not an entry of features"),
        (lambda d: d.update(processing={"skippable": {"drop": "all"}}), "processing.skippable: no step's tool can skip entries of 'drop'"),
        (lambda d: d["steps"][0].update(colour="red"), "colour"),
        (lambda d: d.update(steps=[]), "steps"),
        (lambda d: d.pop("name"), "name"),
    ],
)
def test_errors(tmp_path, change, message):
    data = json.loads(json.dumps(GOOD))
    change(data)
    validation = validate_workflow_file(write(tmp_path, data))
    assert validation.definition is None
    assert any(message in e for e in validation.errors), validation.errors


def test_unreadable_and_newer_files(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    assert "can't be read" in validate_workflow_file(bad).errors[0]
    newer = write(tmp_path, {**GOOD, "schema_version": WORKFLOW_SCHEMA_VERSION + 1})
    error = validate_workflow_file(newer).errors[0]
    newest = WORKFLOW_SCHEMA_VERSION
    assert (f"workflow file schema version {newest + 1} is not supported by the installed"
            " FLIMAnalyzer") in error  # fmt: skip
    assert error.endswith(f"(up to schema version {newest}). Upgrade FLIMAnalyzer.")


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
    validation = validate_workflow_file(write(tmp_path, data))
    assert len(validation.errors) == 1
    assert "step 02" in validation.errors[0].lower() and "is not the class of 'Sort'" in validation.errors[0]


def test_a_tool_file_is_not_a_workflow_file_unless_asked(tmp_path):
    path = write(tmp_path, {"schema_version": 2, "tool": "Sort", "config": {}}, "sort.json")
    validation = validate_workflow_file(path)
    assert validation.errors == ["sort.json: a tool file (the settings of Sort), not a workflow file"]
    validation = validate_workflow_file(path, tool_files=True)
    assert validation.errors == [] and validation.definition.name == "Sort"
    (step,) = validation.definition.steps
    assert (step.id, step.tool, step.output.save) == ("1", "Sort", True)


@pytest.mark.parametrize("bad", ["a", "0", "-1", "1.5", True])
def test_step_ids_are_whole_numbers_from_1(tmp_path, bad):
    data = {"name": "ids", "steps": [{"id": bad, "tool": "Sort"}]}
    assert "is not a whole number from 1" in " ".join(validate_workflow_file(write(tmp_path, data)).errors)


def test_a_step_description_and_no_output_names(tmp_path):
    data = {"name": "notes", "steps": [{"id": "1", "tool": "Sort", "description": "by FOV"}]}
    assert validate_workflow_file(write(tmp_path, data)).definition.steps[0].description == "by FOV"
    data["steps"][0]["output"] = {"items": {"1": "sorted"}}  # names of outputs: not a field
    assert validate_workflow_file(write(tmp_path, data)).errors


def _calculate_status(processing, calcs):
    """Run Calculate as a one-step workflow file; return its tasks' statuses."""
    definition = {
        "name": "processing",
        "steps": [{"id": "1", "tool": "Calculate", "processing": processing, "config": {"calculations": calcs}}],
    }
    run = _run(definition, {"a.txt": _tables()["a.txt"]})
    return {a["status"] for _, a in run.graph.nodes(data=True) if "tool" in a and a["label"].startswith("Calculate")}


def test_processing_skippable(prefect_harness):
    missing = {"kind": "expression", "name": "x", "expression": "gone * 2"}
    for skippable, calcs, state in (
        (None, [CALC, missing], "failed"),  # none, the default
        ("some", [CALC, missing], "completed"),
        ("some", [missing], "failed"),  # some needs at least one applied
        ("all", [missing], "completed"),
    ):
        processing = {"skippable": {"calculations": skippable}} if skippable else {}
        assert _calculate_status(processing, calcs) == {state}, (skippable, calcs)


def test_processing_required_entries_are_never_skipped(prefect_harness):
    missing = {"kind": "expression", "name": "x", "expression": "gone * 2"}
    processing = {"skippable": {"calculations": "all"}, "required": {"calculations": [missing]}}
    assert _calculate_status(processing, [CALC, missing]) == {"failed"}


def test_processing_required_names_a_rule_by_some_of_its_fields(tmp_path):
    step = {"id": "1", "tool": "Calculate", "config": {"calculations": [CALC]},
            "processing": {"skippable": {"calculations": "all"}, "required": {"calculations": [{"name": CALC["name"]}]}}}  # fmt: skip
    assert not validate_workflow_file(write(tmp_path, {"name": "w", "steps": [step]})).errors
    step["processing"]["required"] = {"calculations": [{"name": "other"}]}
    errors = validate_workflow_file(write(tmp_path, {"name": "w", "steps": [step]})).errors
    assert any("{'name': 'other'} is not an entry of calculations" in e for e in errors)


def test_processing_merges_per_key_step_over_workflow():
    definition = WorkflowDefinition.model_validate({
        "name": "merged",
        "processing": {"strict": False, "skippable": {"calculations": "all", "features": "some"}},
        "steps": [{"id": "1", "tool": "Calculate", "processing": {"strict": {"features": True}, "skippable": {"calculations": "none"}}}],
    })  # fmt: skip
    rules = definition.rules(definition.steps[0])
    assert rules.skip("calculations") == "none" and rules.skip("features") == "some"
    assert rules.is_strict("features[1]") and not rules.is_strict("grouping[0]")


def test_processing_strict_false_for_a_field_never_guessed_is_a_warning(tmp_path):
    data = {"name": "w", "steps": [{"id": "1", "tool": "Drop Columns", "processing": {"strict": {"drop": False}}}]}
    validation = validate_workflow_file(write(tmp_path, data))
    assert not validation.errors
    assert "step 01 (Drop Columns): processing.strict.drop: Drop Columns never guesses drop; it stays strict" in validation.warnings


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
    validation = validate_workflow_file(path)
    assert validation.errors == []
    run = workflow_class(validation.definition)().run_flow(read_tables([raw_dir]).tables)
    assert run.state == "completed", run.failed
    (new,) = [v for r in run.results() if isinstance(r, dict) for k, v in r.items() if k == "Table: Calculated"]
    assert_as_in_0_6(new, f"{parser}.txt")


def test_old_import_settings_become_an_equivalent_workflow(prefect_harness, raw_dir, tmp_path):
    from flim.core.reader import read_tables
    from flim.core.settings import validate_settings_file

    v1 = json.loads((Path(__file__).parent / "data" / "settings_v1.json").read_text())
    v1["import"]["filename_parser"] = {"parser": "fov_treatment_cell_parser", "patterns": []}
    v1["import"]["category_combinations"] = [["FOV", "Treatment"]]
    settings_file = write(tmp_path, v1, "old.json")
    validation = validate_settings_file(settings_file)
    assert validation.import_workflow["name"] == "Import (old)"
    assert validation.import_workflow["category"] == ["File", "Import"] and "read" not in validation.import_workflow
    assert validation.import_read == {}  # the default delimiter, no files left out
    path = write(tmp_path, validation.import_workflow, "old-import.json")
    result = validate_workflow_file(path)
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


def test_category_places_a_workflow_file():
    from flim.core.registry import category_path
    from flim.core.workflowfile import BUILT_IN, IMPORT_CATEGORY, import_workflows

    steps = [{"id": "1", "tool": "Sort"}]
    plain = workflow_class(WorkflowDefinition(name="plain", steps=steps))
    assert category_path(plain) == ["Workflow"]  # no category: the Workflow menu
    nested = workflow_class(
        WorkflowDefinition(name="nested", category=["Workflow", "Summaries"], steps=steps)
    )
    assert category_path(nested) == ["Workflow", "Summaries"]
    hidden = workflow_class(WorkflowDefinition(name="hidden", category=[], steps=steps))
    assert category_path(hidden) == []
    for path in BUILT_IN.glob("*.json"):  # all built-in files: offered by Import Tables
        assert validate_workflow_file(path).definition.category == IMPORT_CATEGORY, path.name
    register_workflow_files()
    assert [t.name for t in import_workflows()] == ["Import"]


# --- mappable output: a step's output as a list of parts ---


def _two_feature_tables():
    return {
        "a.txt": pd.DataFrame({"FOV": pd.Categorical(["1", "2"]), "t1": [1.0, 3.0], "t2": [2.0, 4.0]}),
        "b.txt": pd.DataFrame({"FOV": pd.Categorical(["1", "2"]), "t1": [5.0, 7.0], "t2": [6.0, 8.0]}),
    }


SUMMARY_PARTS = {"grouping": ["FOV"], "features": ["t1", "t2"], "aggs": ["mean"],
                 "single_table": False}  # fmt: skip


def _saved_files(run):
    return sorted(
        str(p.relative_to(run.autosave_dir)) for p in run.autosave_dir.rglob("*.txt")
        if p.is_file() and p.name != "run_summary.txt"
    )


def test_a_mappable_step_saves_each_part(prefect_harness, tmp_path):
    definition = {"name": "parts", "steps": [
        {"id": "1", "tool": "Summarize", "config": SUMMARY_PARTS, "output": {"save": True}},
    ]}  # fmt: skip
    run = _run(definition, _two_feature_tables(), autosave_dir=tmp_path)
    assert run.state == "completed", run.failed
    assert _saved_files(run) == [
        "01-Summarize/a.txt/t1/Table_Summary_t1.txt", "01-Summarize/a.txt/t2/Table_Summary_t2.txt",
        "01-Summarize/b.txt/t1/Table_Summary_t1.txt", "01-Summarize/b.txt/t2/Table_Summary_t2.txt",
    ]  # fmt: skip


def test_one_feature_is_still_a_part(prefect_harness, tmp_path):
    config = {**SUMMARY_PARTS, "features": ["t1"]}
    definition = {"name": "one part", "steps": [
        {"id": "1", "tool": "Summarize", "config": config, "output": {"save": True}},
    ]}  # fmt: skip
    run = _run(definition, {"a.txt": _two_feature_tables()["a.txt"]}, autosave_dir=tmp_path)
    assert _saved_files(run) == ["01-Summarize/a.txt/t1/Table_Summary_t1.txt"]


def test_a_later_step_maps_over_the_parts(prefect_harness, tmp_path):
    definition = {"name": "map", "steps": [
        {"id": "1", "tool": "Summarize", "config": SUMMARY_PARTS},
        {"id": "2", "tool": "Sort", "inputs": ["1.1"], "output": {"save": True}},
    ]}  # fmt: skip
    workflow = workflow_class(WorkflowDefinition.model_validate(definition))()
    run = workflow.run_flow(_two_feature_tables(), autosave_dir=tmp_path)
    assert run.state == "completed", run.failed
    assert _saved_files(run) == [
        "02-Sort/a.txt/t1/Table_Sorted.txt", "02-Sort/a.txt/t2/Table_Sorted.txt",
        "02-Sort/b.txt/t1/Table_Sorted.txt", "02-Sort/b.txt/t2/Table_Sorted.txt",
    ]  # fmt: skip
    # the GUI gets the leaves by label
    assert sorted(workflow.leaves["2"]) == ["a.txt / t1", "a.txt / t2", "b.txt / t1", "b.txt / t2"]


def test_a_join_keeps_the_parts(prefect_harness, tmp_path):
    definition = {"name": "join", "steps": [
        {"id": "1", "tool": "Summarize", "config": SUMMARY_PARTS},
        {"id": "2", "tool": "Concatenate", "config": {"add_input": False}, "output": {"save": True}},
    ]}  # fmt: skip
    run = _run(definition, _two_feature_tables(), autosave_dir=tmp_path)
    assert run.state == "completed", run.failed
    assert _saved_files(run) == [
        "02-Concatenate/t1/Table_Concatenated.txt", "02-Concatenate/t2/Table_Concatenated.txt"
    ]


def test_features_all_gives_a_part_per_feature_of_the_input(prefect_harness, tmp_path):
    config = {**SUMMARY_PARTS, "features": "all"}
    definition = {"name": "all", "steps": [
        {"id": "1", "tool": "Summarize", "config": config, "output": {"save": True}},
    ]}  # fmt: skip
    run = _run(definition, {"a.txt": _two_feature_tables()["a.txt"]}, autosave_dir=tmp_path)
    assert run.state == "completed", run.failed
    assert _saved_files(run) == [
        "01-Summarize/a.txt/t1/Table_Summary_t1.txt", "01-Summarize/a.txt/t2/Table_Summary_t2.txt"
    ]


def test_parts_of_two_steps_cant_be_combined(tmp_path):
    data = {"name": "two", "steps": [
        {"id": "1", "tool": "Summarize", "config": SUMMARY_PARTS},
        {"id": "2", "tool": "KS-Statistics", "inputs": ["input"], "config": {"features": ["t1"]}},
        {"id": "3", "tool": "Merge", "inputs": ["1.1", "2.1"]},
    ]}  # fmt: skip
    workflow = workflow_class(WorkflowDefinition.model_validate(data))
    assert any("combines the parts of different steps" in i.message for i in workflow.structure_issues())


def test_window_counts_count_the_parts():
    from flim.core.schema import TableSchema
    from flim.core.workflowfile import window_counts

    definition = WorkflowDefinition.model_validate({"name": "w", "steps": [
        {"id": "1", "tool": "Summarize", "config": SUMMARY_PARTS},
        {"id": "2", "tool": "Sort", "inputs": ["1.1"]},
    ]})  # fmt: skip
    schemas = {n: TableSchema.from_frame(t) for n, t in _two_feature_tables().items()}
    assert window_counts(definition, schemas) == {"table": 4}  # 2 inputs x 2 parts, 1 table each


def test_step_folders_sort_by_id():
    from flim.core.workflowfile import id_width, step_folder

    definition = WorkflowDefinition.model_validate({"name": "w", "steps": [
        {"id": str(i), "tool": "Sort"} for i in range(1, 12)
    ] + [{"id": "123", "tool": "Order Category Values"}]})  # fmt: skip
    width = id_width(definition)
    assert width == 3
    assert step_folder(definition.steps[0], width) == "001-Sort"
    assert step_folder(definition.steps[-1], width) == "123-Order Category Values"
    small = WorkflowDefinition.model_validate({"name": "w", "steps": [{"id": "1", "tool": "Sort"}]})
    assert step_folder(small.steps[0], id_width(small)) == "01-Sort"



def test_formats_of_kinds_the_tools_dont_make_are_errors(tmp_path):
    import json

    from flim.core.workflowfile import validate_workflow_file, step_kinds

    path = tmp_path / "w.json"
    path.write_text(json.dumps({
        "name": "w",
        "output": {"formats": [{"kind": "table", "format": "csv"}, {"kind": "plot", "format": "png"}]},
        "steps": [
            {"id": "1", "tool": "Summarize", "output": {"save": True,
             "formats": [{"kind": "plot", "format": "svg"}]}},
            {"id": "2", "tool": "Sort", "output": {"save": True}},
        ],
    }))  # fmt: skip
    validation = validate_workflow_file(path)
    assert validation.definition is None
    assert ("step 01 (Summarize): output.formats: a format of kind 'plot', which Summarize"
            " doesn't make (it makes: table)") in validation.errors  # fmt: skip
    assert ("output.formats: a format of kind 'plot', which no step makes (the steps"
            " make: table)") in validation.errors  # fmt: skip
    assert len(validation.errors) == 2  # the workflow-level table format is fine


# --- processing applied to grouping and features ---


def _summarize(features, processing=None, grouping=("FOV",)):
    """A workflow file of one Summarize step."""
    step = {"id": "1", "tool": "Summarize", "config": {"grouping": list(grouping), "features": features, "aggs": ["mean"]}}
    if processing:
        step["processing"] = processing
    return WorkflowDefinition.model_validate({"name": "summary", "steps": [step]})


def _errors(definition):
    schemas = {n: TableSchema.from_frame(t) for n, t in _tables().items()}
    return validate_steps(definition, schemas)


def test_a_missing_feature_is_an_error_by_default():
    assert _errors(_summarize(["t1", "gone"])) == ["step 1 (Summarize): features[1]: Column 'gone' is not in the input"]


def test_skippable_some_removes_missing_features_and_needs_one():
    assert _errors(_summarize(["t1", "gone"], {"skippable": {"features": "some"}})) == []
    errors = _errors(_summarize(["gone"], {"skippable": {"features": "some"}}))
    assert errors == ["step 1 (Summarize): features: 0 entries apply (none); Summarize needs at least 1"]


def test_a_required_feature_is_never_removed():
    processing = {"skippable": {"features": "all"}, "required": {"features": ["gone"]}}
    errors = _errors(_summarize(["t1", "gone"], processing))
    assert errors == ["step 1 (Summarize): features[1]: Column 'gone' is not in the input (required)"]


def test_the_minimum_of_the_tool_applies_after_skipping():
    # Scatter Plot needs two features
    definition = WorkflowDefinition.model_validate({"name": "s", "steps": [{
        "id": "1", "tool": "Scatter Plot", "config": {"features": ["t1", "gone"]},
        "processing": {"skippable": {"features": "all"}},
    }]})  # fmt: skip
    assert any("features: 1 entries apply (t1); Scatter Plot needs at least 2" in e for e in _errors(definition))


def test_strict_false_guesses_a_missing_column():
    assert _errors(_summarize(["T1"])) != []
    assert _errors(_summarize(["T1"], {"strict": False})) == []
    assert _errors(_summarize(["T1"], {"strict": {"grouping": False}})) != []  # features strict


def test_a_run_skips_missing_features_and_reports_them(prefect_harness):
    definition = _summarize(["t1", "gone"], {"skippable": {"features": "some"}}).model_dump()
    run = _run(definition, {"a.txt": _tables()["a.txt"]})
    assert run.state == "completed"
    messages = " ".join(str(a.get("message") or "") for _, a in run.graph.nodes(data=True))
    assert "skipped features: 'gone' (not in the input)" in messages


# --- plans and resolved files ---


def test_step_formats_per_kind_step_over_workflow_over_default():
    from flim.core.workflowfile import step_formats

    definition = WorkflowDefinition.model_validate({
        "name": "formats",
        "output": {"formats": [{"kind": "table", "format": "csv"}, {"kind": "plot", "format": "pdf"}]},
        "steps": [
            {"id": "1", "tool": "Heatmap", "output": {"formats": [{"kind": "plot", "format": "svg"}]}},
            {"id": "2", "tool": "Summarize"},
        ],
    })  # fmt: skip
    first, second = definition.steps
    assert {(f.kind, f.format) for f in step_formats(definition, first)} == {("plot", "svg"), ("table", "csv")}
    assert [(f.kind, f.format) for f in step_formats(definition, second)] == [("table", "csv")]  # no plots: Summarize makes none
    bare = WorkflowDefinition.model_validate({"name": "bare", "steps": [{"id": "1", "tool": "Summarize"}]})
    assert [(f.kind, f.format) for f in step_formats(bare, bare.steps[0])] == [("table", "tsv")]  # the default


def test_resolving_states_every_setting_and_is_stable():
    from flim.core.workflowfile import resolve_definition, resolved_data

    definition = _summarize(["t1", "gone"], {"skippable": {"features": "some"}})
    resolved = resolve_definition(definition)
    (step,) = resolved_data(resolved)["steps"]
    assert step["inputs"] == ["input"] and step["config"]["aggs"] == ["mean"]
    assert "single_table" in step["config"]  # a default, stated
    assert step["output"]["formats"] == [{"kind": "table", "format": "tsv"}]
    assert step["processing"] == {"strict": True, "skippable": {"grouping": "none", "features": "some"}}
    assert resolved_data(resolve_definition(resolved)) == resolved_data(resolved)


def test_resolving_with_the_tables_pins_what_depends_on_the_data():
    from flim.core.workflowfile import resolve_definition

    schemas = {n: TableSchema.from_frame(t) for n, t in _tables().items()}
    skipped = resolve_definition(_summarize(["t1", "gone"], {"skippable": {"features": "some"}}), schemas=schemas)
    assert skipped.steps[0].config["features"] == ["t1"]
    guessed = resolve_definition(_summarize(["T1"], {"strict": False}), schemas=schemas)
    assert guessed.steps[0].config["features"] == ["t1"]
    everything = resolve_definition(_summarize("all"), schemas=schemas)
    assert everything.steps[0].config["features"] == ["t1"]  # the input's feature columns


def test_parse_overrides():
    from flim.core.workflowfile import parse_overrides

    overrides = parse_overrides([
        "output.save=true", "output.formats=table:csv", "output.formats=[{\"kind\": \"plot\", \"format\": \"png\", \"dpi\": 600}]",
        "processing.strict=false", "processing.strict.grouping=true",
        "processing.skippable.features=some", "processing.required.features=FLIRR,t1",
    ])  # fmt: skip
    assert overrides.save is True
    assert [(f.kind, f.format, getattr(f, "dpi", None)) for f in overrides.formats] == [("table", "csv", None), ("plot", "png", 600)]
    from flim.core.config import ProcessingRules

    rules = ProcessingRules.of(overrides.processing)
    assert not rules.is_strict("features[0]") and rules.is_strict("grouping[0]")  # false, but grouping true
    assert rules.skip("features") == "some" and rules.required == {"features": ["FLIRR", "t1"]}
    assert overrides.formats_over([*parse_overrides(["output.formats=table:tsv,plot:svg"]).formats])[1].format == "png"
