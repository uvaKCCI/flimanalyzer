"""flimbatch (flim.batchcmd): read files and run tools or workflows without the GUI."""

import logging
import tempfile

import numpy as np
import pandas as pd
import pytest

import flim.tools  # noqa: F401  (registers the tools)
import flim.workflow  # noqa: F401  (registers the workflows)
import json

from flim.batchcmd import main
from flim.configs import SummaryConfig
from flim.configs.workflow import BasicFLIRRConfig
from flim.core.registry import tools
from flim.core.settings import AppSettings, save_settings


pytestmark = pytest.mark.usefixtures("prefect_harness")


@pytest.fixture(autouse=True)
def restore_registry():
    """main() registers the workflow files in the shared registry; other tests expect
    only the tools and code-defined workflows."""
    saved = dict(tools._tools)
    yield
    tools._tools.clear()
    tools._tools.update(saved)


@pytest.fixture(autouse=True)
def restore_logging():
    """main() configures the root logger (basicConfig) with this test's captured
    stderr; later log records would be written to it after pytest closed it."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture
def data_dir(tmp_path):
    """Result files named <prefix>_<FOV>_<Treatment>_<Cell>.txt, 5 rows each."""
    rng = np.random.default_rng(0)
    folder = tmp_path / "data"
    folder.mkdir()
    for treatment in ("WT", "KO"):
        for fov in ("FOV1", "FOV2"):
            for cell in ("1", "2"):
                a1 = rng.uniform(60, 80, 5)
                pd.DataFrame(
                    {
                        "NAD(P)H t1": rng.normal(400, 20, 5),
                        "NAD(P)H a2[%]": 100 - a1,
                        "FAD a1[%]": rng.uniform(20, 40, 5),
                        "FLIRR": rng.uniform(0.5, 1.5, 5),
                    }
                ).to_csv(folder / f"Results_{fov}_{treatment}_{cell}.txt", sep="\t", index=False)
    return folder


@pytest.fixture
def settings():
    return AppSettings.default()


# a dry run needs -o too: it checks the folder and writes its log there
DRY_RUN = ["--dry-run", "-o", tempfile.mkdtemp(prefix="flimbatch-dry-run-")]


def run_dir(out, number=1):
    """Return the folder of a flimbatch call's run: `<out>/<date and time>/run-<n>`."""
    (call,) = [p for p in out.iterdir() if p.is_dir()]  # one folder per call
    return call / f"run-{number}"


def _settings_file(settings, tmp_path):
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    return path


SEPARATE = {
    "column": "Source", "mode": "pattern",
    "patterns": [
        {"name": "FOV", "regex": ".*/.*?[_-](.*?)[_-]"},
        {"name": "Treatment", "regex": ".*/.*?[_-].*?[_-](.*?)[_-]"},
    ],
}  # fmt: skip


def test_run_a_tool_on_each_file(data_dir, settings, tmp_path, monkeypatch):
    monkeypatch.delenv("FLIM_LOG_DIR", raising=False)  # default: the output folder
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["FLIRR"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "--run", "Summarize",
                 "--no-prefect-server"])
    assert code == 0
    assert not (out / "Imported.txt").exists()  # no fixed outputs: the run's only
    summaries = sorted(run_dir(out).rglob("*Summary*"))
    assert len(summaries) == 8  # one per file
    table = pd.read_csv(summaries[0], sep="\t")  # tab-separated, no index column (#119)
    assert list(table.columns) == ["FLIRR mean"]
    (run_summary,) = run_dir(out).rglob("run_summary.txt")
    text = run_summary.read_text()
    assert "User settings file: not read" in text
    assert f"App settings file: {path} (schema version 2)" in text
    log = run_dir(out).parent / "flimbatch.log"  # the call's log, with its results
    assert "Read 8 file(s)" in log.read_text()
    assert not list(out.glob("*.log"))  # not in -o itself


def test_a_workflow_file_joins_the_files(data_dir, settings, tmp_path):
    workflow = tmp_path / "per-treatment.json"
    workflow.write_text(json.dumps({
        "name": "per treatment",
        "steps": [
            {"id": "1", "tool": "Concatenate", "config": {"add_input": False}},
            {"id": "2", "tool": "Separate Categories", "config": SEPARATE},
            {"id": "3", "tool": "Summarize", "output": {"save": True},
             "config": {"grouping": ["Treatment"], "features": ["FLIRR"], "aggs": ["mean"]}},
        ],
    }))
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "--run", str(workflow),
                 "--no-prefect-server"])
    assert code == 0
    saved = [p for p in run_dir(out).rglob("*.txt") if p.name != "run_summary.txt"]
    (summary,) = saved  # only the step that saves
    table = pd.read_csv(summary, sep="\t")
    assert list(table.columns) == ["Treatment", "FLIRR mean"] and set(table["Treatment"]) == {"WT", "KO"}


def test_the_built_in_import_workflow_runs_by_name(data_dir, tmp_path):
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "--run", "Import", "--no-prefect-server"])
    assert code == 0
    (calculated,) = run_dir(out).rglob("*Calculated*")
    table = pd.read_csv(calculated, sep="\t")
    assert len(table) == 40 and "FLIRR" in table.columns


def test_import_with_a_preset_step_takes_the_categories(data_dir, tmp_path):
    from tests.workflows import import_with_preset, write_workflow

    path = write_workflow(tmp_path / "fov.json", import_with_preset("FOV, Treatment, Cell"))
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "--run", str(path), "--no-prefect-server"])
    assert code == 0
    (calculated,) = run_dir(out).rglob("*Calculated*")
    table = pd.read_csv(calculated, sep="\t")
    assert set(table["Treatment"]) == {"WT", "KO"} and set(table["FOV"]) == {"FOV1", "FOV2"}


def test_import_tables_takes_reading_and_workflow_from_the_settings(data_dir, settings, tmp_path, capsys):
    from flim.configs import ImportTablesConfig
    from flim.tools.readers import ImportTables

    settings.tools.set(ImportTables, ImportTablesConfig(workflow="Import"))
    path = _settings_file(settings, tmp_path)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "--run", "Import Tables",
                 "--no-prefect-server"])  # fmt: skip
    assert code == 0
    (calculated,) = run_dir(out).rglob("*Calculated*")
    assert len(pd.read_csv(calculated, sep="\t")) == 40
    # without a workflow in the settings: an error that says what to set
    settings.tools.set(ImportTables, ImportTablesConfig())
    path = _settings_file(settings, tmp_path)
    assert main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "--run", "Import Tables"]) == 1
    assert "set `workflow`" in capsys.readouterr().err


def test_files_are_read_with_open_tables_settings(data_dir, settings, tmp_path, capsys):
    from flim.configs import TableReaderConfig
    from flim.tools.readers import TableReader

    settings.tools.set(TableReader, TableReaderConfig(exclude=["Results_FOV1_WT_1.txt"]))
    path = _settings_file(settings, tmp_path)
    assert main(["-i", str(data_dir), *DRY_RUN, "-s", str(path), "--run", "Import"]) == 0
    assert "Import: OK (7 file(s))" in capsys.readouterr().out  # one file left out


def test_a_run_is_required(data_dir, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["-i", str(data_dir), "-o", str(tmp_path)])
    assert "give --run NAME" in capsys.readouterr().err


PER_TREATMENT = {
    "name": "per treatment",
    "steps": [
        {"id": "1", "tool": "Concatenate", "config": {"add_input": False}},
        {"id": "2", "tool": "Summarize", "output": {"save": True},
         "config": {"grouping": [], "features": ["FLIRR"], "aggs": ["mean"]}},
    ],
}


@pytest.fixture
def workflow_folder(tmp_path, monkeypatch):
    """A folder with the workflow file `per-treatment.json`; no other search path."""
    import flim.core.workflowfile as workflowfile

    folder = tmp_path / "workflows"
    folder.mkdir()
    (folder / "per-treatment.json").write_text(json.dumps(PER_TREATMENT))
    monkeypatch.delenv("FLIM_WORKFLOW_PATH", raising=False)
    empty = tmp_path / "default-workflows"
    monkeypatch.setattr(workflowfile, "default_workflow_dir", lambda: empty)
    return folder


def test_run_takes_a_workflow_file_by_path_or_by_file_name(data_dir, workflow_folder, capsys):
    path = workflow_folder / "per-treatment.json"
    assert main(["-i", str(data_dir), *DRY_RUN, "--run", str(path)]) == 0
    assert main(["-i", str(data_dir), *DRY_RUN, "-w", str(workflow_folder),
                 "--run", "per-treatment.json"]) == 0  # fmt: skip
    assert capsys.readouterr().out.count("per treatment: OK") == 2


def test_a_name_without_json_is_a_registered_name(data_dir, workflow_folder, capsys):
    code = main(["-i", str(data_dir), *DRY_RUN, "-w", str(workflow_folder),
                 "--run", "per-treatment"])  # fmt: skip
    assert code == 1
    assert "No tool or workflow named 'per-treatment'" in capsys.readouterr().err


def test_a_settings_file_doesnt_set_the_workflow_folders(
    data_dir, workflow_folder, settings, tmp_path, capsys
):
    settings.workflow_paths = [workflow_folder]
    path = _settings_file(settings, tmp_path)
    code = main(["-i", str(data_dir), *DRY_RUN, "-s", str(path),
                 "--run", "per-treatment.json"])  # fmt: skip
    err = capsys.readouterr().err
    assert code == 1 and "No workflow file 'per-treatment.json'" in err
    assert "not used, read only from the user settings file: workflow_paths" in err


def test_tool_settings_flimbatch_doesnt_use_are_warned(data_dir, settings, tmp_path, capsys):
    from flim.core.saving import AutosaveConfig

    summarize = tools.get("Summarize")
    settings.tools.set(
        summarize,
        SummaryConfig(features=["FLIRR"], aggs=["mean"]),
        AutosaveConfig(enabled=False, results_dir="summaries"),
    )
    path = _settings_file(settings, tmp_path)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "--run", "Summarize",
                 "--no-prefect-server"])  # fmt: skip
    err = capsys.readouterr().err
    assert code == 0, err
    from flim.core.paths import canonical_folder

    where = "flimbatch: warning: step 01, tool 'Summarize'"
    assert f"{where}: output.results_dir=summaries superseded by -o {canonical_folder(out)}" in err
    assert (f"{where}: output.save=false applies in the GUI only; flimbatch always saves"
            " the results of a tool run") in err  # fmt: skip
    assert list(out.rglob("Table_Summary*"))  # saved under -o all the same


def test_run_takes_a_tool_file_as_a_workflow_of_one_step(
    data_dir, workflow_folder, tmp_path, capsys
):
    tool_file = workflow_folder / "summarize.json"
    tool_file.write_text(json.dumps({
        "schema_version": 2, "tool": "Summarize",
        "config": {"grouping": [], "features": ["FLIRR"], "aggs": ["mean"]},
        "output": {"save": False},
    }))  # fmt: skip
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-w", str(workflow_folder),
                 "--run", "summarize.json", "--no-prefect-server"])  # fmt: skip
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert ("flimbatch: warning: step 01, tool 'Summarize': output.save=false applies in"
            " the GUI only; flimbatch always saves the results of a tool run") in captured.err  # fmt: skip
    assert list(run_dir(out).rglob("Table_Summary*"))  # saved anyway
    # in the workflow folder, the tool file is not a workflow: no message about it
    assert "summarize.json: not loaded" not in captured.err


def test_runs_run_in_the_order_given(data_dir, workflow_folder, capsys):
    code = main(["-i", str(data_dir), *DRY_RUN, "-w", str(workflow_folder),
                 "--run", "Import", "--run", "per-treatment.json"])  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0 and out.index("Import: OK") < out.index("per treatment: OK")


@pytest.mark.parametrize("value, source", [("true", "FLIM_DRY_RUN"), (None, "--dry-run")])
def test_a_dry_run_says_so_first_and_last(data_dir, monkeypatch, capsys, value, source):
    monkeypatch.delenv("FLIM_DRY_RUN", raising=False)
    argv = ["-i", str(data_dir), "--run", "Import", "-o", DRY_RUN[2]]
    if value is None:
        argv.append("--dry-run")
    else:
        monkeypatch.setenv("FLIM_DRY_RUN", value)
    assert main(argv) == 0
    captured = capsys.readouterr()
    lines = captured.err.strip().splitlines()
    assert lines[0] == f"flimbatch: dry run (set by {source}): nothing is run"
    assert lines[-1] == f"flimbatch: dry run (set by {source}): nothing was run"
    assert "Import: OK" in captured.out


def test_dry_run_variable_false_or_invalid(data_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLIM_DRY_RUN", "false")  # not a dry run: -o is needed
    with pytest.raises(SystemExit):
        main(["-i", str(data_dir), "--run", "Import"])
    assert "-o/--output" in capsys.readouterr().err
    monkeypatch.setenv("FLIM_DRY_RUN", "maybe")
    with pytest.raises(SystemExit) as exit_:
        main(["-i", str(data_dir), "--run", "Import"])
    assert exit_.value.code == 2
    assert "FLIM_DRY_RUN=maybe; use true or false" in capsys.readouterr().err


def test_server_timeout_reaches_the_prefect_server(data_dir, tmp_path, monkeypatch):
    import contextlib

    import flim.core.prefect_server as prefect_server

    used = {}
    monkeypatch.setattr(
        prefect_server,
        "use_prefect_server",
        lambda **kw: used.update(kw) or contextlib.nullcontext(),
    )
    code = main(["-i", str(data_dir), "-o", str(tmp_path / "out"), "--run", "Import",
                 "--server-timeout", "90"])  # fmt: skip
    assert code == 0 and used == {"start": True, "timeout": 90}


def test_inputs_with_the_same_folder_name_stop_the_run(tmp_path, capsys):
    folder = tmp_path / "data"
    folder.mkdir()
    table = pd.DataFrame({"FLIRR": [1.0, 2.0]})
    for name in ("a b.txt", "a_b.txt"):
        table.to_csv(folder / name, sep="\t", index=False)
    code = main(["-i", str(folder), *DRY_RUN, "--run", "Sort"])
    assert code == 1
    assert "the inputs 'a b.txt' and 'a_b.txt' get the same folder name" in capsys.readouterr().err


def test_input_is_required(capsys):
    with pytest.raises(SystemExit):
        main(["--run", "Import", "-o", "out"])
    assert "required: -i/--input" in capsys.readouterr().err


def test_one_folder_per_call_with_a_folder_per_run(data_dir, settings, tmp_path, workflow_folder):
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["FLIRR"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "-w", str(workflow_folder),
                 "--run", "Summarize", "--run", "per-treatment.json", "--no-prefect-server"])  # fmt: skip
    assert code == 0
    (call,) = [p for p in out.iterdir() if p.is_dir()]
    assert sorted(p.name for p in call.iterdir() if p.is_dir()) == ["run-1", "run-2"]
    first, second = call / "run-1", call / "run-2"
    assert (first / "run_summary.txt").is_file() and (second / "run_summary.txt").is_file()
    # --run Summarize: a workflow of one step, run per file
    inputs = sorted(p.name for p in (first / "01-Summarize").iterdir())
    assert len(inputs) == 8 and inputs[0].endswith(".txt")
    # the workflow file: Concatenate joins the files, Summarize saves
    assert sorted(p.name for p in second.iterdir() if p.is_dir()) == ["02-Summarize"]


UNSAVED = {
    "name": "unsaved",
    "steps": [
        {"id": "1", "tool": "Concatenate", "config": {"add_input": False}},
        {"id": "2", "tool": "Sort", "config": {"features": ["FLIRR"]}},
    ],
}


def test_a_workflow_that_saves_nothing_is_refused_and_a_leaf_warned(data_dir, tmp_path, capsys):
    path = tmp_path / "unsaved.json"
    path.write_text(json.dumps(UNSAVED))
    assert main(["-i", str(data_dir), *DRY_RUN, "--run", str(path)]) == 1
    captured = capsys.readouterr()
    assert ("flimbatch: warning: step 02, tool 'Sort': output.save not set (default: false)"
            " and no later step uses its outputs; its results are not saved") in captured.err  # fmt: skip
    assert "workflow 'unsaved': no step saves its outputs" in captured.err and "--save-all" in captured.err
    out = tmp_path / "out"
    assert main(["-i", str(data_dir), "-o", str(out), "--run", str(path), "--no-prefect-server"]) == 1
    assert not list(out.rglob("*.txt"))  # refused before it ran


@pytest.mark.parametrize("how", ["option", "variable"])
def test_save_all_saves_every_step(data_dir, tmp_path, monkeypatch, capsys, how):
    path = tmp_path / "unsaved.json"
    path.write_text(json.dumps(UNSAVED))
    out = tmp_path / "out"
    argv = ["-i", str(data_dir), "-o", str(out), "--run", str(path), "--no-prefect-server"]
    monkeypatch.delenv("FLIM_SAVE_ALL", raising=False)
    if how == "option":
        argv.append("--save-all")
    else:
        monkeypatch.setenv("FLIM_SAVE_ALL", "true")
    assert main(argv) == 0
    assert "warning" not in capsys.readouterr().err  # nothing goes unsaved
    run = run_dir(out)
    assert sorted(p.name for p in run.iterdir() if p.is_dir()) == ["01-Concatenate", "02-Sort"]
    source = "--save-all" if how == "option" else "FLIM_SAVE_ALL"
    assert f"every step saves all its outputs ({source})" in (run / "run_summary.txt").read_text()


def test_with_a_log_folder_the_log_is_named_after_the_call(data_dir, settings, tmp_path, monkeypatch):
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["FLIRR"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    logs = tmp_path / "logs"
    monkeypatch.setenv("FLIM_LOG_DIR", str(logs))
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "--run", "Summarize",
                 "--no-prefect-server"])  # fmt: skip
    assert code == 0
    (log,) = logs.glob("flimbatch_*.log")  # with the start time and the process ID
    assert run_dir(out).parent.name.replace("_", "T", 1) in log.name
    assert not (run_dir(out).parent / "flimbatch.log").exists()


def test_a_dry_run_needs_an_output_folder(data_dir, capsys):
    with pytest.raises(SystemExit):
        main(["-i", str(data_dir), "--dry-run", "--run", "Import"])
    assert "required: -o/--output" in capsys.readouterr().err


def test_a_dry_run_checks_the_environment_and_logs_into_the_output_folder(
    data_dir, tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("FLIM_LOG_DIR", raising=False)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "--dry-run", "-o", str(out), "--run", "Import",
                 "--no-prefect-server"])  # fmt: skip
    assert code == 0
    from flim.core.paths import canonical_folder

    report = capsys.readouterr().out
    assert f"Output folder {canonical_folder(out)}: OK" in report
    assert "Executor local: OK" in report
    # the test harness configures a server; --no-prefect-server only prevents starting one
    assert "Prefect server: the configured server at http" in report
    (log,) = out.glob("flimbatch_*.log")  # no call folder: the log in -o
    assert "Read 8 file(s)" in log.read_text()
    assert [p for p in out.iterdir() if p.is_dir()] == []  # nothing else written


def test_a_dry_run_reports_a_dask_cluster_that_doesnt_answer(data_dir, tmp_path, capsys):
    pytest.importorskip("distributed")
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "--dry-run", "-o", str(out), "--run", "Import",
                 "-e", "dask:address=tcp://127.0.0.1:9", "--server-timeout", "1",
                 "--no-prefect-server"])  # fmt: skip
    assert code == 1
    assert "Executor dask: the Dask cluster at tcp://127.0.0.1:9 doesn't answer" in capsys.readouterr().err


def test_input_and_exclude_can_be_repeated(data_dir, capsys):
    first, second, third = sorted(data_dir.glob("*.txt"))[:3]
    code = main(["-i", str(first), "-i", str(second), str(third),
                 "-x", first.name, "-x", second.name, *DRY_RUN, "--run", "Import"])  # fmt: skip
    assert code == 0 and "Import: OK (1 file(s))" in capsys.readouterr().out


def test_dry_run_checks_and_runs_nothing(data_dir, settings, tmp_path, capsys):
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["gone"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    assert main(["-i", str(data_dir), *DRY_RUN, "--run", "Import"]) == 0
    assert "Import: OK (8 file(s))" in capsys.readouterr().out
    assert main(["-i", str(data_dir), *DRY_RUN, "-s", str(path), "--run", "Summarize"]) == 1
    assert "'gone'" in capsys.readouterr().err
    assert not list(tmp_path.glob("Summarize*"))


@pytest.mark.parametrize(
    "extra, listed",
    [
        ({"bogus": 1}, "bogus"),  # unknown
        ({"tools": {"Other Plugin": {"config": {}}}}, "Other Plugin"),  # not installed
    ],
)
def test_settings_that_cannot_be_used_or_checked_stop_the_run(
    data_dir, settings, tmp_path, capsys, extra, listed
):
    path = _settings_file(settings, tmp_path)
    path.write_text(json.dumps({**json.loads(path.read_text()), **extra}))
    code = main(["-i", str(data_dir), "-o", str(tmp_path / "out"), "-s", str(path),
                 "--run", "Summarize", "--no-prefect-server"])
    assert code == 1
    err = capsys.readouterr().err
    assert listed in err and "can all be used" in err
    assert not (tmp_path / "out").exists()


def test_workflows_are_strict_unless_guesses_are_allowed(data_dir, settings, tmp_path):
    # one file with the category columns, as a table saved by FLIMAnalyzer
    rows = []
    for path in sorted(data_dir.iterdir()):
        _, fov, treatment, cell = path.stem.split("_")
        rows.append(pd.read_csv(path, sep="\t").assign(Treatment=treatment, FOV=fov, Cell=cell))
    table = tmp_path / "table.txt"
    pd.concat(rows).to_csv(table, sep="\t", index=False)
    settings.tools.set(
        tools.get("Basic FLIRR Analysis"),
        # the fewest features its steps take (pair plots of FAD and of NAD features)
        BasicFLIRRConfig(grouping=["Treatment", "FOV"], features=["FAD a1%", "NAD(P)H a2%"]),
    )
    path = _settings_file(settings, tmp_path)
    args = ["-i", str(table), "-s", str(path), "--run", "Basic FLIRR Analysis",
            "--no-prefect-server"]
    assert main(args + ["-o", str(tmp_path / "strict")]) == 1  # 'FAD a1%' is missing
    assert not (tmp_path / "strict" / "Basic FLIRR Analysis").exists()
    assert main(args + ["-o", str(tmp_path / "guessed"), "--allow-guesses"]) == 0
    (summary,) = (tmp_path / "guessed").rglob("run_summary.txt")
    assert "'FAD a1%' -> 'FAD a1[%]' (guessed)" in summary.read_text()


def test_unknown_tools_and_missing_files(data_dir, tmp_path, capsys):
    assert main(["-i", str(data_dir), "-o", str(tmp_path), "--run", "Nothing",
                 "--no-prefect-server"]) == 1
    assert "No tool or workflow named 'Nothing'" in capsys.readouterr().err
    assert main(["-i", str(tmp_path / "gone"), "-o", str(tmp_path / "o"), "--run", "Import"]) == 1
    assert "No data files could be read" in capsys.readouterr().err


def test_output_folder_that_cannot_be_used(data_dir, tmp_path, capsys):
    (tmp_path / "file").write_text("x")
    assert main(["-i", str(data_dir), "-o", str(tmp_path / "file" / "out"), "--run", "Import"]) == 1
    assert "--output:" in capsys.readouterr().err


def test_the_application_command_hands_batch_runs_to_flimbatch(data_dir, tmp_path):
    import subprocess
    import sys

    out = tmp_path / "out"
    script = (
        "import sys\n"
        "sys.modules['wx'] = None  # batch runs must not import wx\n"
        "from flim import analyzerapp\n"
        f"sys.argv = ['flimanalyzer', '--batch', '-i', {str(data_dir)!r},"
        f" '-o', {str(out)!r}, '--run', 'Import', '--no-prefect-server']\n"
        "analyzerapp.main()\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert list(run_dir(out).rglob("*Calculated*"))


def test_old_import_settings_are_not_used_and_said_so(data_dir, tmp_path, capsys):
    from pathlib import Path

    v1 = Path(__file__).parent / "data" / "settings_v1.json"
    path = tmp_path / "old.json"
    path.write_text(v1.read_text())
    main(["-i", str(data_dir), *DRY_RUN, "-s", str(path), "--run", "Import"])
    assert "import settings (FLIMAnalyzer 0.6) are not used" in capsys.readouterr().err


def test_dask_local_starts_one_cluster_for_all_runs(data_dir, settings, tmp_path, workflow_folder):
    pytest.importorskip("prefect_dask")
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["FLIRR"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "-w", str(workflow_folder),
                 "--run", "Summarize", "--run", "per-treatment.json", "-e", "dask-local:workers=1",
                 "--no-prefect-server"])  # fmt: skip
    assert code == 0
    notes = []
    for number in (1, 2):
        text = (run_dir(out, number) / "run_summary.txt").read_text()
        (line,) = [s for s in text.splitlines() if "executor dask-local" in s]
        notes.append(line)
    assert notes[0] == notes[1]  # the same cluster, at the same address


def test_the_old_module_still_works_with_a_deprecation_warning():
    import importlib
    import sys

    sys.modules.pop("flim.batch", None)
    with pytest.warns(DeprecationWarning, match="flim.batch is deprecated and is removed in 0.8.0"):
        old = importlib.import_module("flim.batch")
    from flim.batchcmd import main as new_main
    from flim.core.batchrun import resolve_run

    assert old.main is new_main and old.resolve_run is resolve_run


def test_a_tool_or_workflow_file_given_to_s_is_refused(data_dir, workflow_folder, tmp_path, capsys):
    tool_file = tmp_path / "boxplot.json"
    tool_file.write_text(json.dumps({"schema_version": 2, "tool": "Box Plot", "config": {}}))
    assert main(["-i", str(data_dir), *DRY_RUN, "-s", str(tool_file), "--run", "Summarize"]) == 1
    err = capsys.readouterr().err
    assert (f"{tool_file} cannot be used: a tool file (the settings of Box Plot), not an app"
            " settings file; flimbatch runs it with --run") in err  # fmt: skip
    workflow = workflow_folder / "per-treatment.json"
    assert main(["-i", str(data_dir), *DRY_RUN, "-s", str(workflow), "--run", "Summarize"]) == 1
    assert "a workflow file, not an app settings file" in capsys.readouterr().err


def test_run_by_name_with_settings_from_s(data_dir, settings, tmp_path, capsys):
    """Deprecated: the tool's section is used with a warning; without one, an error."""
    empty = _settings_file(settings, tmp_path)
    assert main(["-i", str(data_dir), *DRY_RUN, "-s", str(empty), "--run", "Summarize"]) == 1
    assert (f"--run Summarize: the app settings file {empty} has no settings of Summarize;"
            " give the tool's settings as a tool file") in capsys.readouterr().err  # fmt: skip
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["FLIRR"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    assert main(["-i", str(data_dir), *DRY_RUN, "-s", str(path), "--run", "Summarize"]) == 0
    assert (f"--run Summarize: taking the tool's settings from the app settings file {path}"
            " is deprecated and is removed in 0.8.0") in capsys.readouterr().err  # fmt: skip
