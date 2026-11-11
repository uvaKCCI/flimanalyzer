"""Batch mode (flim.batch): read files and run tools or workflows without the GUI."""

import logging

import numpy as np
import pandas as pd
import pytest

import flim.tools  # noqa: F401  (registers the tools)
import flim.workflow  # noqa: F401  (registers the workflows)
import json

from flim.batch import main
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


def _settings_file(settings, tmp_path):
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    return path


SEPARATE = {
    "column": "Source", "mode": "patterns",
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
    summaries = sorted((out / "Summarize").rglob("*Summary*"))
    assert len(summaries) == 8  # one per file
    table = pd.read_csv(summaries[0], sep="\t")  # tab-separated, no index column (#119)
    assert list(table.columns) == ["FLIRR mean"]
    (run_summary,) = (out / "Summarize").rglob("run_summary.txt")
    text = run_summary.read_text()
    assert "User settings file: not read" in text
    assert f"App settings file: {path} (schema version 2)" in text
    (log,) = out.glob("flimbatch_*.log")  # the log goes with the results
    assert "Read 8 file(s)" in log.read_text()


def test_a_workflow_file_joins_the_files(data_dir, settings, tmp_path):
    workflow = tmp_path / "per-treatment.json"
    workflow.write_text(json.dumps({
        "name": "per treatment",
        "steps": [
            {"id": "1", "tool": "Concatenate", "config": {"add_input": False}},
            {"id": "2", "tool": "Separate Categories", "config": SEPARATE},
            {"id": "3", "tool": "Summarize", "save": True,
             "config": {"grouping": ["Treatment"], "features": ["FLIRR"], "aggs": ["mean"]}},
        ],
    }))
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "--workflow", str(workflow),
                 "--no-prefect-server"])
    assert code == 0
    saved = [p for p in (out / "per treatment").rglob("*.txt") if p.name != "run_summary.txt"]
    (summary,) = saved  # only the step that saves
    table = pd.read_csv(summary, sep="\t")
    assert list(table.columns) == ["Treatment", "FLIRR mean"] and set(table["Treatment"]) == {"WT", "KO"}


def test_the_built_in_import_workflows_run_by_name(data_dir, tmp_path):
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "--run", "Import: FOV, Treatment, Cell",
                 "--no-prefect-server"])
    assert code == 0
    (calculated,) = (out / "Import: FOV, Treatment, Cell").rglob("*Calculated*")
    table = pd.read_csv(calculated, sep="\t")
    assert len(table) == 40 and set(table["Treatment"]) == {"WT", "KO"}


def test_import_tables_takes_reading_and_workflow_from_the_settings(data_dir, settings, tmp_path, capsys):
    from flim.configs import ImportTablesConfig
    from flim.tools.readers import ImportTables

    settings.tools.set(ImportTables, ImportTablesConfig(workflow="Import: FOV, Treatment, Cell"))
    path = _settings_file(settings, tmp_path)
    out = tmp_path / "out"
    code = main(["-i", str(data_dir), "-o", str(out), "-s", str(path), "--run", "Import Tables",
                 "--no-prefect-server"])  # fmt: skip
    assert code == 0
    (calculated,) = (out / "Import: FOV, Treatment, Cell").rglob("*Calculated*")
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
    assert main(["-i", str(data_dir), "--dry-run", "-s", str(path), "--run", "Import"]) == 0
    assert "Import: OK (7 file(s))" in capsys.readouterr().out  # one file left out


def test_a_run_is_required(data_dir, tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["-i", str(data_dir), "-o", str(tmp_path)])
    assert "--run NAME or --workflow FILE" in capsys.readouterr().err


def test_dry_run_checks_and_runs_nothing(data_dir, settings, tmp_path, capsys):
    settings.tools.set(tools.get("Summarize"), SummaryConfig(features=["gone"], aggs=["mean"]))
    path = _settings_file(settings, tmp_path)
    assert main(["-i", str(data_dir), "--dry-run", "--run", "Import"]) == 0
    assert "Import: OK (8 file(s))" in capsys.readouterr().out
    assert main(["-i", str(data_dir), "--dry-run", "-s", str(path), "--run", "Summarize"]) == 1
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
    assert list((out / "Import").rglob("*Calculated*"))


def test_old_import_settings_are_not_used_and_said_so(data_dir, tmp_path, capsys):
    from pathlib import Path

    v1 = Path(__file__).parent / "data" / "settings_v1.json"
    path = tmp_path / "old.json"
    path.write_text(v1.read_text())
    main(["-i", str(data_dir), "--dry-run", "-s", str(path), "--run", "Import"])
    assert "import settings (FLIMAnalyzer 0.6) are not used" in capsys.readouterr().err
