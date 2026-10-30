"""Batch mode (flim.batch): import and run tools or workflows without the GUI."""

import numpy as np
import pandas as pd
import pytest

import flim.tools  # noqa: F401  (registers the tools)
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.batch import BatchError, filtered, import_table, main
from flim.configs import SummaryConfig
from flim.configs.workflow import BasicFLIRRConfig
from flim.core.registry import tools
from flim.core.settings import AppSettings, save_settings


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        yield


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
    settings = AppSettings.default()
    settings.import_.filename_parser.parser = "fov_treatment_cell_parser"
    settings.import_.filename_parser.patterns = []  # the parser's own
    return settings


def test_import_with_the_settings(data_dir, settings):
    data = import_table([data_dir], settings)
    assert len(data) == 40
    assert set(data["Treatment"]) == {"WT", "KO"}
    assert {"FOV", "Cell", "FLIRR"} <= set(data.columns)
    with pytest.raises(BatchError, match="No data files"):
        import_table([data_dir / "missing"], settings)


def test_range_filters():
    data = pd.DataFrame({"x": [1.0, 5.0, 10.0], "y": [0.0, 0.0, 0.0]})
    keep = filtered(data, [{"name": "x", "rangelow": 0, "rangehigh": 6, "selected": True}])
    assert list(keep["x"]) == [1.0, 5.0]
    unused = filtered(data, [{"name": "x", "rangelow": 0, "rangehigh": 6, "selected": False}])
    assert len(unused) == 3


def test_run_a_tool_with_its_settings(data_dir, settings, tmp_path):
    settings.tool_settings.set(
        tools.get("Summarize"),
        SummaryConfig(grouping=["Treatment"], features=["FLIRR"], aggs=["mean"]),
    )
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    out = tmp_path / "out"
    code = main(
        ["-i", str(data_dir), "-o", str(out), "-c", str(path), "--run", "Summarize",
         "--no-prefect-server"]
    )
    assert code == 0
    imported = pd.read_csv(out / "Imported.txt", sep="\t")
    assert len(imported) == 40
    (summary,) = (out / "Summarize").rglob("*Summary*")
    table = pd.read_csv(summary, index_col=0)
    assert list(table.columns) == ["Treatment", "FLIRR mean"]
    assert set(table["Treatment"]) == {"WT", "KO"}
    assert any((out / "Summarize").rglob("run_summary.txt"))


def test_workflows_are_strict_unless_guesses_are_allowed(data_dir, settings, tmp_path):
    settings.tool_settings.set(
        tools.get("Basic FLIRR Analysis"),
        BasicFLIRRConfig(
            grouping=["Treatment", "FOV"], features=["FLIRR", "FAD a1%", "NAD(P)H a2%"]
        ),
    )
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    args = ["-i", str(data_dir), "-c", str(path), "--run", "Basic FLIRR Analysis",
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
    assert main(["-i", str(tmp_path / "gone"), "-o", str(tmp_path / "o")]) == 1


def test_the_application_command_hands_batch_runs_to_flimbatch(data_dir, tmp_path):
    import subprocess
    import sys

    out = tmp_path / "out"
    script = (
        "import sys\n"
        "sys.modules['wx'] = None  # batch runs must not import wx\n"
        "from flim import analyzerapp\n"
        f"sys.argv = ['flimanalyzer', '--batch', '-i', {str(data_dir)!r},"
        f" '-o', {str(out)!r}, '--no-prefect-server']\n"
        "analyzerapp.main()\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert (out / "Imported.txt").exists()
