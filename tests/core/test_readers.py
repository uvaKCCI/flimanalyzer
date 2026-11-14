"""Open Tables (TableReader) and Import Tables (flim.tools.readers)."""

import pandas as pd
import pytest

from flim.configs import ImportTablesConfig, TableReaderConfig
from flim.tools.readers import READ_STEP, ImportTables, TableReader, data_files


@pytest.fixture
def files(tmp_path):
    paths = []
    for name, values in (("a.txt", [1.0, 3.0]), ("b.txt", [5.0, 7.0])):
        path = tmp_path / "data" / name
        path.parent.mkdir(exist_ok=True)
        pd.DataFrame({"FOV": ["1", "2"], "t1": values}).to_csv(path, sep="\t", index=False)
        paths.append(path)
    (tmp_path / "data" / "notes.md").write_text("not data")
    return paths


def _completed(run):
    return [a["label"] for _, a in run.graph.nodes(data=True) if "tool" in a and a["status"] == "completed"]


def test_table_reader_reads_one_file(files):
    (table,) = TableReader()(files[0], config=TableReaderConfig()).values()
    assert list(table.columns) == ["Source", "Directory", "File", "FOV", "t1"]
    assert table["Source"].iloc[0].startswith("file:///")


def test_data_files_by_name(files, tmp_path):
    found, skipped = data_files([tmp_path / "data"], TableReaderConfig())
    assert list(found) == ["a.txt", "b.txt"] and not skipped  # .md is not a data file
    found, _ = data_files([tmp_path / "data"], TableReaderConfig(exclude=["b.txt"]))
    assert list(found) == ["a.txt"]


def test_import_tables_without_a_workflow(prefect_harness, files):
    workflow = ImportTables()
    run = workflow.run_flow(files, config=ImportTablesConfig())
    assert run.state == "completed", run.failed
    assert sum(label.startswith("Open Tables") for label in _completed(run)) == 2  # one task per file
    tables = {name: next(iter(out.value().values())) for name, out in workflow.leaves[READ_STEP].items()}
    assert list(tables) == ["a.txt", "b.txt"] and list(tables["b.txt"]["t1"]) == [5.0, 7.0]


def test_import_tables_runs_a_workflow_on_the_tables(prefect_harness, files, tmp_path):
    import json

    path = tmp_path / "join.json"
    path.write_text(json.dumps({
        "name": "join", "category": ["File", "Import"],
        "steps": [{"id": "1", "tool": "Concatenate", "config": {"add_input": False}}],
    }))  # fmt: skip
    workflow = ImportTables()
    run = workflow.run_flow(files, config=ImportTablesConfig(workflow=str(path)))
    assert run.state == "completed", run.failed
    ((step, output),) = workflow.leaves.items()
    (table,) = output.value().values()
    assert step == "1" and len(table) == 4 and workflow.definition.name == "join"


def test_import_tables_checks_the_workflow():
    (issue,) = ImportTables.validate(ImportTablesConfig(workflow="no such workflow"), [])
    assert issue.field == "workflow" and "No workflow named" in issue.message
    assert ImportTables.validate(ImportTablesConfig(), []) == []


def test_import_joins_files_without_flim_channels(prefect_harness, tmp_path, monkeypatch):
    """The built-in Import on files without the channels' columns (e.g. one channel,
    `_t1`): nothing to rename, drop or calculate; the tables are joined as they are."""
    paths = []
    for name in ("Results-1-KO.txt", "Results-2-WT.txt"):
        path = tmp_path / name
        pd.DataFrame({"_t1": [1.0, 2.0], "_a1[%]": [60.0, 70.0]}).to_csv(path, sep="\t", index=False)
        paths.append(path)
    from flim.core.registry import tools
    from flim.core.workflowfile import register_workflow_files

    monkeypatch.setattr(tools, "_tools", dict(tools._tools))  # restored afterwards
    register_workflow_files()
    workflow = ImportTables()
    run = workflow.run_flow(paths, config=ImportTablesConfig(workflow="Import"))
    assert run.state == "completed", run.failed
    ((_, output),) = workflow.leaves.items()
    (table,) = output.value().values()
    assert len(table) == 4 and "_t1" in table.columns


def test_an_empty_header_in_a_file_is_dropped(tmp_path):
    """pandas names a column whose header is empty `Unnamed: 0`; Drop Columns' empty
    header rule now selects it (it matched only blank names)."""
    from flim.configs import DropColumnsConfig
    from flim.tools.data import DropColumns

    path = tmp_path / "a.txt"
    path.write_text("x\t\tt1\n1\t5\t2.0\n")  # the second header is empty
    (table,) = TableReader()(path, config=TableReaderConfig()).values()
    assert "Unnamed: 1" in table.columns
    (dropped,) = DropColumns()(table, config=DropColumnsConfig(drop=[])).values()
    assert "Unnamed: 1" not in dropped.columns and {"x", "t1"} <= set(dropped.columns)
