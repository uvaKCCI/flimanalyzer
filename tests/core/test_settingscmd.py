"""flimsettings (flim.settingscmd): lists, shows and checks settings without the GUI."""

import json

import pytest

import flim.tools  # noqa: F401  (registers the tools)
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.core.registry import tools
from flim.core.settings import AppSettings, save_settings
from flim.settingscmd import ENV_VARIABLES, main

TOOL_FILE = {
    "schema_version": 2,
    "tool": "Summarize",
    "config": {"features": ["FLIRR"]},
    "output": {"save": False},
}
WORKFLOW = {
    "name": "per treatment",
    "steps": [
        {"id": "1", "tool": "Concatenate", "config": {"add_input": False}},
        {"id": "2", "tool": "Summarize", "output": {"save": True},
         "config": {"grouping": [], "features": ["FLIRR"], "aggs": ["mean"]}},
    ],
}  # fmt: skip


@pytest.fixture(autouse=True)
def restore_registry():
    """The workflow files are registered in the shared registry; other tests expect
    only the tools and the workflows defined in code."""
    saved = dict(tools._tools)
    yield
    tools._tools.clear()
    tools._tools.update(saved)


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """A workflow folder with a tool file and a workflow file; no other search path."""
    import flim.core.workflowfile as workflowfile

    folder = tmp_path / "workflows"
    folder.mkdir()
    (folder / "summarize.json").write_text(json.dumps(TOOL_FILE))
    (folder / "per-treatment.json").write_text(json.dumps(WORKFLOW))
    monkeypatch.delenv("FLIM_WORKFLOW_PATH", raising=False)
    monkeypatch.setattr(workflowfile, "default_workflow_dir", lambda: tmp_path / "none")
    return folder


@pytest.fixture
def clean_env(monkeypatch):
    """No FLIM_* variables, whatever the environment of the test run."""
    import os

    for name in [n for n in os.environ if n.startswith("FLIM_")]:
        monkeypatch.delenv(name)


def run(capsys, *argv):
    """Run flimsettings; return the exit code, standard output and standard error."""
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


# --- tool and workflow ---


def test_tool_list_shows_tools_by_menu_hidden_tools_and_tool_files(folder, capsys):
    code, out, _ = run(capsys, "tool", "--list", "-w", str(folder))
    assert code == 0
    assert "  Analysis: " in out and "Summarize" in out
    assert "Not in the menus (by name or as a workflow step):\n  Autoencoder Train Model" in out
    assert f"  summarize.json  ({folder})" in out
    assert "Autoencoder Train  (" not in out  # a workflow, listed by workflow --list
    assert f"Workflow search path:\n  {folder}" in out


def test_workflow_list_shows_workflows_in_code_and_workflow_files(folder, capsys):
    code, out, _ = run(capsys, "workflow", "--list", "-w", str(folder))
    assert code == 0
    assert "  Autoencoder Train  (built-in, Analysis)" in out
    assert "  Import  (built-in)" in out
    assert f"  per treatment  ({folder / 'per-treatment.json'})" in out
    assert "summarize.json" not in out  # a tool file


def test_show_prints_a_file_as_it_is_by_path_or_name(folder, capsys):
    text = (folder / "summarize.json").read_text()
    assert run(capsys, "tool", "--show", str(folder / "summarize.json"))[1].strip() == text
    code, out, _ = run(capsys, "tool", "--show", "summarize", "-w", str(folder))
    assert code == 0 and out.strip() == text
    code, out, _ = run(capsys, "workflow", "--show", "import")  # built in
    assert code == 0 and '"name": "Import"' in out


def test_show_refuses_a_file_of_another_kind_and_names_the_command(folder, tmp_path, capsys):
    path = folder / "per-treatment.json"
    code, out, err = run(capsys, "tool", "--show", str(path))
    assert code == 1 and not out
    assert (
        f"{path}: a workflow file, not a tool file (flimsettings workflow --show {path})" in err
    )
    app = tmp_path / "lab.json"
    save_settings(AppSettings.default(), app)
    code, _, err = run(capsys, "workflow", "--show", str(app))
    assert f"{app}: an app settings file, not a workflow file (flimsettings app --show -s {app})" in err
    columns = tmp_path / "columns.json"
    columns.write_text(json.dumps({"FLIRR": 1}))
    code, _, err = run(capsys, "tool", "--validate", str(columns))
    assert code == 1 and f"{columns}: not a tool file\n" in err


def test_a_missing_file_names_the_kind_and_where_it_was_searched(folder, capsys):
    code, _, err = run(capsys, "tool", "--show", "nothere", "-w", str(folder))
    assert code == 1
    assert "No tool file 'nothere' at this path, in the workflow search path or built in" in err


def test_show_prints_the_default_settings_of_a_tool_or_a_workflow_defined_in_code(
    folder, capsys
):
    code, out, _ = run(capsys, "workflow", "--show", "Basic FLIRR Analysis")
    data = json.loads(out)
    assert code == 0 and data["tool"] == "Basic FLIRR Analysis" and "config" in data
    assert "results_dir" not in data["output"]
    code, out, _ = run(capsys, "tool", "--show", "Summarize")
    assert code == 0 and json.loads(out)["tool"] == "Summarize"


def test_a_name_of_another_kind_or_with_validate_is_an_error(folder, capsys):
    code, out, err = run(capsys, "workflow", "--show", "Summarize")
    assert code == 1 and not out
    assert (
        "'Summarize' is a tool, not a workflow file; flimsettings tool --show 'Summarize'"
        " prints its default settings" in err
    )
    code, _, err = run(capsys, "tool", "--validate", "Summarize")
    assert code == 1 and "'Summarize' is a tool, not a tool file; --validate takes a file" in err


def test_tool_validate(folder, capsys):
    code, out, err = run(capsys, "tool", "--validate", str(folder / "summarize.json"))
    assert code == 0 and "a valid tool file of Summarize" in out
    assert "output.save=false applies in the GUI only" in err
    bad = folder / "bad.json"
    bad.write_text(json.dumps({**TOOL_FILE, "config": {"aggs": ["nonsense"]}}))
    code, out, err = run(capsys, "tool", "--validate", str(bad))
    assert code == 1 and not out and "aggs" in err


def test_workflow_validate_includes_the_save_rules(folder, capsys):
    code, out, _ = run(capsys, "workflow", "--validate", str(folder / "per-treatment.json"))
    assert code == 0 and "a valid workflow file (per treatment)" in out
    unsaved = folder / "unsaved.json"
    steps = [{**s, "output": {"save": False}} for s in WORKFLOW["steps"]]
    unsaved.write_text(json.dumps({**WORKFLOW, "steps": steps}))
    code, out, err = run(capsys, "workflow", "--validate", str(unsaved))
    assert code == 1 and not out and "no step saves its outputs" in err


# --- app and user settings ---


def test_app_list_shows_the_files_in_the_search_path(tmp_path, monkeypatch, capsys):
    (tmp_path / "lab.json").write_text('{"schema_version": 2}')
    (tmp_path / "summary.json").write_text(json.dumps(TOOL_FILE))  # not listed
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(tmp_path))
    code, out, _ = run(capsys, "app", "--list")
    assert code == 0 and f"  lab  ({tmp_path})" in out and "summary" not in out.split("Other")[0]
    assert "Other JSON files in these folders, not listed: 1" in out
    assert f"App settings search path:\n  {tmp_path}" in out


def test_app_show_shows_both_commands_and_where_each_value_comes_from(
    clean_env, tmp_path, monkeypatch, capsys
):
    user = tmp_path / "usersettings.json"
    monkeypatch.setenv("FLIM_USER_SETTINGS", str(user))
    monkeypatch.setenv("FLIM_SERVER_TIMEOUT", "5")
    code, out, _ = run(capsys, "app", "--show")
    assert code == 0
    # the same value and origin in both commands: one line
    assert "  Server timeout:\n      5 s  (from environment (FLIM_SERVER_TIMEOUT))\n" in out
    assert "      flimbatch:    not used: flimbatch saves under -o" in out
    # the user settings file sets a value for the GUI only
    user.write_text(json.dumps({"schema_version": 2, "log": {"dir": "logs"}}))
    code, out, _ = run(capsys, "app", "--show")
    assert "      flimanalyzer: logs; logs kept 30 days  (from user settings file)" in out


def test_app_show_uses_the_default_app_settings_file_for_the_gui(
    clean_env, tmp_path, monkeypatch, capsys
):
    app = tmp_path / "lab.json"
    app.write_text(json.dumps({"schema_version": 2, "server_timeout": 9}))
    user = tmp_path / "usersettings.json"
    user.write_text(json.dumps({"schema_version": 2, "default_app_settings": str(app)}))
    monkeypatch.setenv("FLIM_USER_SETTINGS", str(user))
    code, out, _ = run(capsys, "app", "--show")
    assert f"App settings file of flimanalyzer: {app} (the default app settings file)" in out
    assert "App settings file of flimbatch: none, set at runtime with -s <FILE>" in out
    assert "      flimanalyzer: 9 s  (from default app settings file)" in out


def test_app_show_leaves_an_unreadable_user_settings_file_as_it_is(
    clean_env, tmp_path, monkeypatch, capsys
):
    user = tmp_path / "usersettings.json"
    user.write_text("not json")
    monkeypatch.setenv("FLIM_USER_SETTINGS", str(user))
    code, _, err = run(capsys, "app", "--show")
    assert code == 0 and "cannot be read" in err
    assert user.read_text() == "not json" and not list(tmp_path.glob("*.unreadable*"))


def test_app_validate(tmp_path, capsys):
    good = tmp_path / "good.json"
    save_settings(AppSettings.default(), good)
    code, out, _ = run(capsys, "app", "--validate", str(good))
    assert code == 0 and "schema version" in out
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps({"schema_version": 2, "colour": "red"}))
    code, out, err = run(capsys, "app", "--validate", str(unknown))
    assert code == 1 and "colour" in out and "the GUI and flimbatch refuse it" in err


def test_user_show_reads_the_file_only(tmp_path, monkeypatch, capsys):
    path = tmp_path / "usersettings.json"
    monkeypatch.setenv("FLIM_USER_SETTINGS", str(path))
    assert run(capsys, "user", "--show")[1] == f"No user settings file: {path}\n"
    path.write_text('{"schema_version": 2}')
    code, out, _ = run(capsys, "user", "--show")
    assert code == 0 and out.startswith(f"User settings file: {path}\n{{")
    path.write_text("not json")
    code, out, err = run(capsys, "user", "--show")
    assert code == 0 and "not json" in out and "not valid JSON" in err
    assert path.read_text() == "not json"  # not set aside, as the GUI would


# --- the environment ---


def test_env_list_shows_every_variable_and_the_order_of_precedence(capsys):
    code, out, _ = run(capsys, "env", "--list")
    assert code == 0
    assert "A command-line option takes precedence over its environment variable" in out
    names = [line.strip() for line in out.splitlines() if line.startswith("  FLIM_")]
    assert names == sorted(ENV_VARIABLES)  # every variable, in alphabetical order
    assert "FLIM_DRY_RUN\n      true: a dry run (--dry-run); read by flimbatch\n" in out


def test_env_show_reports_unknown_names_and_invalid_values(clean_env, monkeypatch, capsys):
    code, out, err = run(capsys, "env", "--show")
    assert code == 0 and "  none" in out and not err
    monkeypatch.setenv("FLIM_SERVER_TIMEOUT", "5")
    monkeypatch.setenv("FLIM_EXECUTION__EXECUTOR", "dask-local")
    monkeypatch.setenv("FLIM_EXECUTION__WORKERS", "2")
    assert run(capsys, "env", "--show")[0] == 0
    monkeypatch.setenv("FLIM_DRYRUN", "1")
    monkeypatch.setenv("FLIM_LOG_LEVEL", "loud")
    code, out, err = run(capsys, "env", "--show")
    assert code == 1 and "  FLIM_DRYRUN=1" in out
    assert "FLIM_DRYRUN: FLIMAnalyzer does not read this variable; check the name" in err
    assert "FLIM_LOG_LEVEL=loud" in err


# --- arguments ---


@pytest.mark.parametrize(
    "argv",
    [
        ["tool"],  # no action
        ["tool", "--list", "--validate", "x.json"],  # two actions
        ["tool", "--show", "x.json", "-s", "lab.json"],  # -s belongs to app --show
        ["user", "--list"],
        ["nothing", "--list"],
    ],
)
def test_invalid_arguments(argv, capsys):
    with pytest.raises(SystemExit) as exit_:
        main(argv)
    assert exit_.value.code == 2


def test_resolve_prints_every_setting(folder, capsys):
    code, out, _ = run(capsys, "tool", "--resolve", str(folder / "summarize.json"))
    data = json.loads(out)
    assert code == 0 and data["tool"] == "Summarize" and data["output"]["save"] is True
    assert data["config"]["features"] == ["FLIRR"] and "aggs" in data["config"]  # defaults stated
    code, out, _ = run(capsys, "workflow", "--resolve", str(folder / "per-treatment.json"))
    steps = json.loads(out)["steps"]
    assert code == 0 and [s["inputs"] for s in steps] == [["input"], ["1"]]


def test_resolve_shows_the_effect_of_overrides(folder, capsys):
    code, out, _ = run(capsys, "workflow", "--resolve", str(folder / "per-treatment.json"),
                       "--override", "output.save=true", "--override", "output.formats=table:csv")  # fmt: skip
    steps = json.loads(out)["steps"]
    assert code == 0 and all(s["output"]["save"] for s in steps)
    assert steps[1]["output"]["formats"] == [{"kind": "table", "format": "csv"}]


def test_app_update(tmp_path, capsys):
    import shutil
    from pathlib import Path

    path = tmp_path / "lab.json"
    shutil.copy(Path(__file__).parent / "data" / "settings_v1.json", path)
    code, out, _ = run(capsys, "app", "--update", str(path))
    assert code == 0 and f"the original is kept as {tmp_path / 'lab.v1.json'}" in out
    code, _, err = run(capsys, "app", "--update", str(path))
    assert code == 1 and "already in the current format" in err


def test_app_show_validates_tool_settings_with_the_tools_loaded(tmp_path):
    """A file with tool settings: flimbatch accepts it, so app --show must say so.

    In a process of its own: here, the test module has loaded the tools already.
    """
    import os
    import subprocess
    import sys

    lab = tmp_path / "lab.json"
    lab.write_text(json.dumps({"schema_version": 2, "tools": {"Summarize": {"config": {"aggs": ["mean"]}}}}))
    env = {k: v for k, v in os.environ.items() if not k.startswith("FLIM_")}
    env["FLIM_USER_SETTINGS"] = str(tmp_path / "usersettings.json")
    code = "import sys; from flim.settingscmd import main; sys.exit(main(sys.argv[1:]))"
    result = subprocess.run(
        [sys.executable, "-c", code, "app", "--show", "-s", str(lab)],
        capture_output=True, text=True, env=env,
    )  # fmt: skip
    assert result.returncode == 0 and "not installed" not in result.stderr
    assert f"App settings file of flimbatch: {lab}" in result.stdout


def test_a_workflow_file_that_is_not_loaded_is_reported_once(tmp_path, capsys):
    folder = tmp_path / "workflows"
    folder.mkdir()
    (folder / "dup.json").write_text(json.dumps({"name": "Import", "steps": [{"id": "1", "tool": "Sort"}]}))
    code, _, err = run(capsys, "workflow", "--list", "-w", str(folder))
    assert err.count("dup.json: not loaded") == 1


def test_a_workflow_file_is_found_by_its_name_too(folder, capsys):
    code, out, _ = run(capsys, "workflow", "--show", "per treatment", "-w", str(folder))
    assert code == 0 and '"name": "per treatment"' in out
