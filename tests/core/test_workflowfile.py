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
