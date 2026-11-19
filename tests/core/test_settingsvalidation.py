"""Checking a settings file before it is used (flim.core.settings.validate_settings_file)
and the app settings file of a session (flim.core.settingsmgr)."""

import json
from pathlib import Path

import pytest

import flim.tools  # noqa: F401  (registers the tools: tool settings are checked)
from flim.core.registry import tools
from flim.core.settings import (
    SETTINGS_VERSION,
    validate_settings_file,
    load_settings,
    save_sections,
)
from flim.core.settingsmgr import session_settings, start_folder_settings

DATA = Path(__file__).parent / "data"
MIXED = {
    "schema_version": 1,
    "working_dir": "res",  # renamed
    "display": {"x": 1},  # dropped in version 2
    "bogus_section": 3,
    "import": {"delimiter": ";", "bogus_key": 1},
    "execution": {"executor": "ray"},  # invalid
    "tools": {
        "Summarize": {"config": {"aggs": ["count"], "nope": 1}},  # invalid config
        "Other Plugin": {"config": {"x": 1}},  # not installed
    },
}


def write(tmp_path, content, name="settings.json"):
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


def test_validation_sorts_the_keys(tmp_path):
    validation = validate_settings_file(write(tmp_path, MIXED))
    assert validation.version == 1 and validation.error is None and validation.problems
    assert validation.converted == ["working_dir to results_dir"]
    assert validation.dropped[0] == "display (histogram ranges)"
    assert validation.dropped[1].startswith("import (filename parser defaultparser)")
    assert validation.unknown == ["bogus_section"]
    assert [i.split(":")[0] for i in validation.invalid] == ["execution", "tools.Summarize.config"]
    assert validation.not_validated == ["tools.Other Plugin"]
    # usable: without unknown keys and without the sections with invalid values
    assert set(validation.sections) == {"results_dir", "tools"}
    assert list(validation.sections["tools"]) == ["Other Plugin"]
    text = validation.summary()
    for line in ("schema version 1", "bogus_section", "working_dir to results_dir"):
        assert line in text
    assert "and 1 more" in validation.summary(limit=1)


@pytest.mark.parametrize(
    "content, message",
    [
        ("{not json", "Expecting property name"),
        ("[1, 2]", "not a settings file"),
        (json.dumps({"classname": "x"}), "not a settings file"),  # a config alone
        (json.dumps({"schema_version": SETTINGS_VERSION + 1}), "is not supported by the installed FLIMAnalyzer"),
    ],
)
def test_files_that_cannot_be_used(tmp_path, content, message):
    validation = validate_settings_file(write(tmp_path, content))
    assert validation.problems and message in validation.error and validation.sections == {}
    assert validation.summary().endswith(validation.error)


def test_missing_file(tmp_path):
    assert "No such file" in validate_settings_file(tmp_path / "gone.json").error


def test_the_file_is_only_read(tmp_path):
    path = write(tmp_path, MIXED)
    before = path.read_text()
    validate_settings_file(path)
    assert path.read_text() == before


@pytest.mark.parametrize("name", ["settings_v0.json", "settings_v1.json"])
def test_files_of_earlier_versions_have_no_problems(name):
    validation = validate_settings_file(DATA / name)
    assert not validation.problems and validation.converted
    assert session_settings(str(DATA / name)).settings == load_settings(DATA / name)


def test_updated_file_has_nothing_left_to_convert(tmp_path):
    path = write(tmp_path, MIXED)
    save_sections(validate_settings_file(path).sections, path)
    validation = validate_settings_file(path)
    assert validation.version == SETTINGS_VERSION and not validation.problems
    assert validation.converted == validation.dropped == []
    assert json.loads(path.read_text())["results_dir"] == "res"


def test_tool_problems(tmp_path):
    validation = validate_settings_file(write(tmp_path, MIXED))
    assert validation.tool_problems(tools.get("Summarize"))
    assert not validation.tool_problems(tools.get("K-Means"))  # problems elsewhere only


# --- the app settings file of a session ---


def test_session_refuses_a_file_with_invalid_values(tmp_path):
    with pytest.raises(ValueError, match="execution"):
        session_settings(str(write(tmp_path, MIXED)))


def test_session_unknown_keys_alone_are_logged(tmp_path, caplog):
    path = write(tmp_path, {"schema_version": 2, "bogus": 1, "results_dir": "r"})
    manager = session_settings(str(path))
    assert manager.settings.results_dir == Path("r") and manager.source == path
    assert "ignoring unknown keys bogus" in caplog.text


def test_session_refuses_files_with_problems(tmp_path):
    refused = []
    session_settings(str(DATA / "settings_v1.json"), refuse=refused.append)
    assert refused == []
    path = write(tmp_path, MIXED)
    manager = session_settings(str(path), refuse=refused.append)
    assert [c.path for c in refused] == [path]
    assert manager.source is None and manager.settings.results_dir is None


def test_a_refused_file_returns_to_the_start_dialog(tmp_path, monkeypatch):
    folder = tmp_path / "appsettings"
    folder.mkdir()
    bad = write(folder, MIXED, "bad.json")
    good = write(folder, {"schema_version": 2, "results_dir": "res"}, "good.json")
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(folder))
    answers = [bad, good]
    picked, refused = [], []

    def pick(files, default, warning, search_path):
        picked.append(files)
        return Pick(answers.pop(0), default)

    manager = session_settings(pick=pick, refuse=refused.append)
    assert [c.path for c in refused] == [bad] and len(picked) == 2
    assert manager.source == good
    # -s with a file with problems: the start dialog follows
    answers = [good]
    manager = session_settings(str(bad), pick=pick, refuse=refused.append)
    assert manager.source == good


def test_a_browsed_folder_is_added_to_the_search_path(tmp_path, monkeypatch):
    from flim.core.settingsmgr import UserSettingsFile

    monkeypatch.delenv("FLIM_APP_SETTINGS_PATH", raising=False)
    default = tmp_path / "default"
    default.mkdir()
    write(default, {"schema_version": 2}, "lab.json")
    monkeypatch.setattr("flim.core.settingsmgr.default_app_settings_dir", lambda: default)
    other = tmp_path / "other"
    other.mkdir()
    chosen = write(other, {"schema_version": 2}, "course.json")
    user = UserSettingsFile(tmp_path / "user.json")
    manager = session_settings(
        user_file=user, pick=lambda files, d, w, path: Pick(chosen, d, other)
    )
    assert manager.source == chosen
    assert [Path(p) for p in manager.settings.appsettings_path] == [default, other.resolve()]


def test_start_folder_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert start_folder_settings() == (None, None)
    write(tmp_path, {"schema_version": 1}, "defaults.json")
    path, note = start_folder_settings()
    assert path == (tmp_path / "defaults.json").resolve()
    assert "deprecated and is removed in 0.8.0" in note and "-s NAME" in note


@pytest.mark.parametrize(
    "content, listed",
    [
        ({"schema_version": 2, "bogus": 1}, "bogus"),
        ({"schema_version": 2, "tools": {"Other Plugin": {"config": {}}}}, "Other Plugin"),
    ],
)
def test_complete_refuses_unknown_keys_and_tools_not_installed(tmp_path, content, listed):
    path = write(tmp_path, content)
    session_settings(str(path))  # accepted otherwise
    with pytest.raises(ValueError, match=listed):
        session_settings(str(path), complete=True)


# --- the choice of app settings file at startup ---

from flim.core.settingsmgr import Pick, SettingsManager, UserSettingsFile  # noqa: E402


def test_pick_is_asked_only_with_files_and_without_a_file_given(tmp_path, monkeypatch):
    folder = tmp_path / "appsettings"
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(folder))
    offered = []

    def pick(files, default, warning, search_path):
        offered.append((files, default, warning))
        return Pick(files[0], default)

    session_settings(pick=pick)  # the folder does not exist
    folder.mkdir()
    session_settings(pick=pick)  # no files
    assert offered == []
    cells = write(folder, {"schema_version": 2, "results_dir": "r"}, "cells.json")
    write(folder, {"schema_version": 2}, "other.json")
    manager = session_settings(pick=pick)
    assert offered == [([cells, folder / "other.json"], None, None)]
    assert manager.source == cells and manager.settings.results_dir == Path("r")
    session_settings(str(folder / "other.json"), pick=pick)  # given with -s: no question
    assert len(offered) == 1


def test_pick_of_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(tmp_path))
    write(tmp_path, {"schema_version": 2, "results_dir": "r"}, "cells.json")
    manager = session_settings(pick=lambda files, default, warning, search_path: Pick(None, None))
    assert manager.source is None and manager.settings.results_dir is None


def test_picked_file_is_validated_like_s(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(tmp_path))
    path = write(tmp_path, MIXED, "cells.json")
    refused, answers = [], [path, None]  # then Skip App Settings
    manager = session_settings(
        pick=lambda files, default, warning, search_path: Pick(answers.pop(0), default),
        refuse=refused.append,
    )
    assert [c.path for c in refused] == [path] and manager.source is None


def _user(tmp_path, **sections):
    path = tmp_path / "user.json"
    path.write_text(json.dumps({"schema_version": 2, **sections}, default=str))
    return UserSettingsFile(path)


def test_default_is_offered_and_kept_or_changed(tmp_path, monkeypatch):
    folder = tmp_path / "appsettings"
    folder.mkdir()
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(folder))
    # a default outside the search path is offered too
    default = write(tmp_path, {"schema_version": 2, "results_dir": "d"}, "lab.json")
    other = write(folder, {"schema_version": 2}, "other.json")
    user = _user(tmp_path, default_app_settings=str(default))
    offered = []

    def pick(files, given, warning, search_path):
        offered.append((files, given))
        return Pick(given, given)  # Enter: the preselected default

    manager = session_settings(user_file=user, pick=pick)
    assert offered == [([other], default)] and manager.source == default
    # the user makes another file the default
    manager = session_settings(
        user_file=user, pick=lambda files, given, warning, search_path: Pick(other, other)
    )
    assert SettingsManager(user_file=user).settings.default_app_settings == other
    assert manager.record()[1] == f"Default app settings file: {other}"


@pytest.mark.parametrize("content", [None, "{not json"])  # missing, not readable
def test_default_that_cannot_be_used_is_cleared_with_a_warning(tmp_path, monkeypatch, content):
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(tmp_path / "none"))
    default = tmp_path / "lab.json"
    if content is not None:
        default.write_text(content)
    user = _user(tmp_path, default_app_settings=str(default))
    manager = session_settings(user_file=user, pick=lambda *a: pytest.fail("asked"))
    assert "cannot be used" in manager.notices[0] and str(default) in manager.notices[0]
    assert SettingsManager(user_file=user).settings.default_app_settings is None


def test_default_and_last_run_are_not_exported(tmp_path):
    user = _user(tmp_path, default_app_settings="x.json", last_run_url="http://h/runs/flow-run/a")
    manager = SettingsManager(user_file=user)
    assert manager.settings.last_run_url == "http://h/runs/flow-run/a"
    manager.export(tmp_path / "e.json")
    exported = json.loads((tmp_path / "e.json").read_text())
    assert "default_app_settings" not in exported and "last_run_url" not in exported


def test_session_offers_to_update_a_file_of_an_older_version(tmp_path):
    offered = []
    session_settings(str(DATA / "settings_v1.json"), update=offered.append)
    assert [v.path for v in offered] == [DATA / "settings_v1.json"]
    offered.clear()
    current = write(tmp_path, {"schema_version": 2}, "current.json")
    session_settings(str(current), update=offered.append)
    assert offered == []
