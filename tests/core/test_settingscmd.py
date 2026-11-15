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
    assert "  Autoencoder Train  (Analysis)" in out
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
    code, _, err = run(capsys, "tool", "--check", str(columns))
    assert code == 1 and f"{columns}: not a tool file\n" in err


def test_a_missing_file_names_the_kind_and_where_it_was_searched(folder, capsys):
    code, _, err = run(capsys, "tool", "--show", "nothere", "-w", str(folder))
    assert code == 1
    assert "No tool file 'nothere' at this path, in the workflow search path or built in" in err


def test_tool_check(folder, capsys):
    code, out, err = run(capsys, "tool", "--check", str(folder / "summarize.json"))
    assert code == 0 and "a valid tool file of Summarize" in out
    assert "output.save=false applies in the GUI only" in err
    bad = folder / "bad.json"
    bad.write_text(json.dumps({**TOOL_FILE, "config": {"aggs": ["nonsense"]}}))
    code, out, err = run(capsys, "tool", "--check", str(bad))
    assert code == 1 and not out and "aggs" in err


def test_workflow_check_includes_the_save_rules(folder, capsys):
    code, out, _ = run(capsys, "workflow", "--check", str(folder / "per-treatment.json"))
    assert code == 0 and "a valid workflow file (per treatment)" in out
    unsaved = folder / "unsaved.json"
    steps = [{**s, "output": {"save": False}} for s in WORKFLOW["steps"]]
    unsaved.write_text(json.dumps({**WORKFLOW, "steps": steps}))
    code, out, err = run(capsys, "workflow", "--check", str(unsaved))
    assert code == 1 and not out and "no step saves its outputs" in err


# --- app and user settings ---


def test_app_list_shows_the_files_in_the_search_path(tmp_path, monkeypatch, capsys):
    (tmp_path / "lab.json").write_text("{}")
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(tmp_path))
    code, out, _ = run(capsys, "app", "--list")
    assert code == 0 and f"  lab  ({tmp_path})" in out
    assert f"App settings search path:\n  {tmp_path}" in out


def test_app_show_names_where_each_value_comes_from(clean_env, monkeypatch, capsys):
    monkeypatch.setenv("FLIM_SERVER_TIMEOUT", "5")
    code, out, _ = run(capsys, "app", "--show")
    assert code == 0
    assert "  Server timeout: 5 s\n      from environment (FLIM_SERVER_TIMEOUT)" in out
    assert "  Executor: local" in out


def test_app_check(tmp_path, capsys):
    good = tmp_path / "good.json"
    save_settings(AppSettings.default(), good)
    code, out, _ = run(capsys, "app", "--check", str(good))
    assert code == 0 and "schema version" in out
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps({"schema_version": 2, "colour": "red"}))
    code, out, err = run(capsys, "app", "--check", str(unknown))
    assert code == 1 and "colour" in out and "flimbatch refuses it" in err


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
    for name in ENV_VARIABLES:
        assert f"\n  {name}\n" in out
    assert "FLIM_DRY_RUN\n      true: a dry run (--dry-run); read by flimbatch\n" in out


def test_env_show_reports_unknown_names_and_invalid_values(clean_env, monkeypatch, capsys):
    code, out, err = run(capsys, "env", "--show")
    assert code == 0 and "  none" in out and not err
    monkeypatch.setenv("FLIM_SERVER_TIMEOUT", "5")
    monkeypatch.setenv("FLIM_EXECUTION__EXECUTOR", "dask-local")
    monkeypatch.setenv("FLIM_EXECUTION__WORKERS", "2")
    assert run(capsys, "env", "--show")[0] == 0
    monkeypatch.setenv("FLIM_DRYRUN", "1")
    monkeypatch.setenv("FLIM_SAVE_ALL", "maybe")
    monkeypatch.setenv("FLIM_LOG_LEVEL", "loud")
    code, out, err = run(capsys, "env", "--show")
    assert code == 1 and "  FLIM_DRYRUN=1" in out
    assert "FLIM_DRYRUN: FLIMAnalyzer does not read this variable; check the name" in err
    assert "FLIM_SAVE_ALL=maybe" in err and "FLIM_LOG_LEVEL=loud" in err


# --- arguments ---


@pytest.mark.parametrize(
    "argv",
    [
        ["tool"],  # no action
        ["tool", "--list", "--check", "x.json"],  # two actions
        ["tool", "--show", "x.json", "-s", "lab.json"],  # -s belongs to app --show
        ["user", "--list"],
        ["nothing", "--list"],
    ],
)
def test_invalid_arguments(argv, capsys):
    with pytest.raises(SystemExit) as exit_:
        main(argv)
    assert exit_.value.code == 2
