"""The SettingsManager and the user settings file."""

import json
import os
from pathlib import Path

import pytest

from flim.core.saving import AutosaveConfig

from flim.configs import KMeansConfig, SummaryConfig
from flim.core.registry import tools
from flim.core.settings import SETTINGS_VERSION, AppSettings, save_settings
from flim.core.settingsmgr import SettingsManager, UserSettingsFile, user_settings_path
import flim.tools  # noqa: F401  (registers the tools)

KMEANS = tools.get("K-Means")
SUMMARIZE = tools.get("Summarize")


def written(path) -> dict:
    return json.loads(Path(path).read_text())


def test_readers_get_copies():
    manager = SettingsManager()
    copy = manager.settings
    copy.filters.use = not copy.filters.use
    assert manager.settings.filters.use != copy.filters.use


def test_set_tool_writes_only_that_tool(tmp_path):
    path = tmp_path / "usersettings.json"
    manager = SettingsManager(user_file=UserSettingsFile(path))
    settings = manager.set_tool(
        KMEANS, KMeansConfig(n_clusters=4), AutosaveConfig(enabled=True, results_dir="/results")
    )
    assert settings.tools.config(KMEANS).n_clusters == 4
    assert manager.version == 1
    data = written(path)
    assert data["schema_version"] == SETTINGS_VERSION
    assert set(data) == {"schema_version", "tools"}
    assert set(data["tools"]) == {"K-Means"}
    assert data["tools"]["K-Means"]["output"] == {
        "save": True, "results_dir": "/results", "formats": []
    }


def test_changes_are_applied_at_the_next_start(tmp_path):
    path = tmp_path / "usersettings.json"
    SettingsManager(user_file=UserSettingsFile(path)).set_tool(KMEANS, KMeansConfig(n_clusters=6))
    again = SettingsManager(user_file=UserSettingsFile(path))
    assert again.settings.tools.config(KMEANS).n_clusters == 6


def test_two_instances_keep_each_others_sections(tmp_path):
    path = tmp_path / "usersettings.json"
    a = SettingsManager(user_file=UserSettingsFile(path))
    b = SettingsManager(user_file=UserSettingsFile(path))
    a.set_tool(KMEANS, KMeansConfig(n_clusters=3))
    b.set_tool(SUMMARIZE, SummaryConfig(aggs=["max"]))
    assert set(written(path)["tools"]) == {"K-Means", "Summarize"}


def test_same_section_the_instance_that_saves_last_takes_precedence(tmp_path):
    path = tmp_path / "usersettings.json"
    a = SettingsManager(user_file=UserSettingsFile(path))
    b = SettingsManager(user_file=UserSettingsFile(path))
    a.set_tool(KMEANS, KMeansConfig(n_clusters=3))
    b.set_tool(KMEANS, KMeansConfig(n_clusters=8))
    assert written(path)["tools"]["K-Means"]["config"]["n_clusters"] == 8


def test_the_file_is_replaced_without_leftovers(tmp_path):
    path = tmp_path / "usersettings.json"
    manager = SettingsManager(user_file=UserSettingsFile(path))
    manager.set_tool(KMEANS, KMeansConfig(n_clusters=3))
    manager.set_tool(KMEANS, KMeansConfig(n_clusters=5))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".settings-")]
    assert leftovers == []
    assert written(path)["tools"]["K-Means"]["config"]["n_clusters"] == 5


def test_missing_user_file_gives_the_base_settings(tmp_path):
    manager = SettingsManager(user_file=UserSettingsFile(tmp_path / "none.json"))
    assert manager.settings == AppSettings.default()


@pytest.mark.parametrize(
    "content", ["{not json", "[1]", json.dumps({"schema_version": SETTINGS_VERSION + 1})]
)
def test_unreadable_user_file_is_renamed_and_a_new_one_started(tmp_path, caplog, content):
    path = tmp_path / "usersettings.json"
    path.write_text(content)
    manager = SettingsManager(user_file=UserSettingsFile(path))
    assert manager.settings == AppSettings.default()
    kept = tmp_path / "usersettings.unreadable.json"
    assert kept.read_text() == content and not path.exists()
    assert "renamed to" in caplog.text and str(kept) in manager.notices[0]
    manager.update({"results_dir": "r"})  # a new file; the old one is kept
    assert json.loads(path.read_text())["results_dir"] == "r"
    assert kept.read_text() == content


def test_earlier_unreadable_files_are_kept(tmp_path):
    (tmp_path / "usersettings.unreadable.json").write_text("first")
    path = tmp_path / "usersettings.json"
    path.write_text("second")
    SettingsManager(user_file=UserSettingsFile(path))
    assert (tmp_path / "usersettings.unreadable.json").read_text() == "first"
    assert (tmp_path / "usersettings.unreadable-2.json").read_text() == "second"


def test_unreadable_user_file_that_cannot_be_renamed_is_not_written(
    tmp_path, monkeypatch, caplog
):
    import flim.core.settingsmgr as settingsmgr

    path = tmp_path / "usersettings.json"
    path.write_text("{not json")

    def no_rename(*args):
        raise PermissionError("denied")

    monkeypatch.setattr(settingsmgr.os, "rename", no_rename)
    manager = SettingsManager(user_file=UserSettingsFile(path))
    assert "not saved" in manager.notices[0]
    manager.update({"results_dir": "r"})  # kept in memory only
    assert manager.settings.results_dir == Path("r")
    assert path.read_text() == "{not json" and "Settings not saved" in caplog.text


def test_record_names_the_settings_files(tmp_path):
    from flim.core.settingsmgr import session_settings

    path = tmp_path / "cells.json"
    path.write_text(json.dumps({"schema_version": 1, "working_dir": "r", "bogus": 1}))
    manager = session_settings(str(path), user_file=UserSettingsFile(tmp_path / "u.json"))
    assert manager.record() == [
        f"User settings file: {tmp_path / 'u.json'}",
        f"App settings file: {path} (schema version 1)",
        "  converted: working_dir to results_dir",
        "  not used (unknown): bogus",
    ]
    assert session_settings().record() == [
        "User settings file: not read",
        "App settings file: none",
    ]


def test_failed_write_keeps_the_change_and_warns(tmp_path, caplog, monkeypatch):
    user_file = UserSettingsFile(tmp_path / "usersettings.json")

    def fail(changes):
        raise OSError("read-only file system")

    monkeypatch.setattr(user_file, "merge", fail)
    manager = SettingsManager(user_file=user_file)
    settings = manager.set_tool(KMEANS, KMeansConfig(n_clusters=7))
    assert settings.tools.config(KMEANS).n_clusters == 7
    assert "not saved" in caplog.text


def test_invalid_change_leaves_the_settings_unchanged():
    manager = SettingsManager()
    before = manager.settings
    with pytest.raises(Exception):
        manager.update({"filters": {"use": "not a boolean"}})
    assert manager.settings == before
    assert manager.version == 0


def test_load_applies_a_file_for_the_session_only(tmp_path):
    path = tmp_path / "usersettings.json"
    project = tmp_path / "project.json"
    settings = AppSettings.default()
    settings.tools.set(KMEANS, KMeansConfig(n_clusters=9))
    save_settings(settings, project)
    manager = SettingsManager(user_file=UserSettingsFile(path))
    assert manager.load(project).tools.config(KMEANS).n_clusters == 9
    assert not path.exists()


def test_load_migrates_older_files(tmp_path):
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"root": {"filters": {"Use": True}}}))  # version 0
    assert SettingsManager().load(old).filters.use is True


def test_export_writes_all_settings(tmp_path):
    manager = SettingsManager()
    manager.set_tool(KMEANS, KMeansConfig(n_clusters=2))
    out = tmp_path / "export.json"
    manager.export(out)
    data = written(out)
    assert data["schema_version"] == SETTINGS_VERSION
    assert {"filters", "tools"} <= set(data) and "import" not in data
    # every installed tool, its defaults if not set; read only from the user file
    names = [t.name for group in tools.by_category().values() for t in group]
    assert sorted(data["tools"]) == sorted(names)
    assert data["tools"][KMEANS.name]["config"]["n_clusters"] == 2
    assert data["tools"]["Summarize"]["config"]["classname"]
    assert "appsettings_path" not in data
    assert all("legacy" not in entry for entry in data["tools"].values())
    # the exported file gives the same settings, and none of them is reported
    from flim.core.settings import validate_settings_file

    validation = validate_settings_file(out)
    assert not validation.problems and validation.not_validated == []
    assert SettingsManager().apply(validation).tools.config(KMEANS).n_clusters == 2


def test_legacy_is_written_only_if_set(tmp_path):
    from flim.core.settings import ToolSettings

    assert "legacy" not in ToolSettings().model_dump(mode="json")
    assert ToolSettings(legacy={"a": 1}).model_dump(mode="json")["legacy"] == {"a": 1}


def test_older_user_file_is_migrated(tmp_path):
    path = tmp_path / "usersettings.json"
    path.write_text(json.dumps({"root": {"filters": {"Use": True}}}))  # version 0
    assert SettingsManager(user_file=UserSettingsFile(path)).settings.filters.use is True


def test_user_settings_path_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("FLIM_USER_SETTINGS", str(tmp_path / "mine.json"))
    assert user_settings_path() == tmp_path / "mine.json"


def test_user_settings_path_in_the_platform_folder(monkeypatch):
    monkeypatch.delenv("FLIM_USER_SETTINGS", raising=False)
    path = user_settings_path()
    assert path.name == "usersettings.json" and path.parent.name == "FLIMAnalyzer"
    assert os.path.isabs(path)


# --- app settings files, the environment and the session layers ---

from flim.core.settingsmgr import (  # noqa: E402
    app_settings_path,
    default_app_settings_dir,
    environment_changes,
    find_app_settings,
    list_app_settings,
    session_settings,
)


def test_search_path_variable_over_user_list_over_default(monkeypatch, tmp_path):
    monkeypatch.delenv("FLIM_APP_SETTINGS_PATH", raising=False)
    assert app_settings_path() == [default_app_settings_dir()]
    assert default_app_settings_dir().name == "appsettings"
    assert app_settings_path([tmp_path / "mine"]) == [tmp_path / "mine"]
    monkeypatch.setenv(
        "FLIM_APP_SETTINGS_PATH", os.pathsep.join([str(tmp_path / "lab"), "", "~/flim"])
    )
    assert app_settings_path([tmp_path / "mine"]) == [
        tmp_path / "lab",
        Path("~/flim").expanduser(),
    ]


def test_find_app_settings(monkeypatch, tmp_path):
    lab, mine = tmp_path / "lab", tmp_path / "mine"
    lab.mkdir()
    mine.mkdir()
    for path in (lab / "flirr.json", lab / "shared.json", mine / "shared.json"):
        path.write_text('{"schema_version": 2}')
    (mine / "summary.json").write_text('{"schema_version": 2, "tool": "Summarize"}')  # a tool file
    here = tmp_path / "here.json"
    here.write_text("{}")
    path = [lab, mine]
    assert find_app_settings(here, path) == here  # a path as given takes precedence
    assert find_app_settings("flirr", path) == lab / "flirr.json"  # .json added
    assert find_app_settings("flirr.json", path) == lab / "flirr.json"
    with pytest.raises(ValueError, match="ambiguous") as err:
        find_app_settings("shared", path)
    assert str(lab / "shared.json") in str(err.value) and str(mine) in str(err.value)
    with pytest.raises(FileNotFoundError, match=str(mine)):
        find_app_settings("missing", path)
    assert list_app_settings(path + [tmp_path / "none"]) == [
        lab / "flirr.json",
        lab / "shared.json",
        mine / "shared.json",
    ]  # not the tool file


def test_environment_changes(monkeypatch):
    for name in list(os.environ):
        if name.startswith("FLIM_") and name != "FLIM_USER_SETTINGS":
            monkeypatch.delenv(name)
    assert environment_changes() == {}
    monkeypatch.setenv("FLIM_RESULTS_DIR", "/data/out")
    monkeypatch.setenv("FLIM_CACHE_DIR", "/scratch/cache")
    monkeypatch.setenv("FLIM_PREFECT_SERVER", "false")
    monkeypatch.setenv("FLIM_EXECUTION__EXECUTOR", "dask-local")
    monkeypatch.setenv("FLIM_EXECUTION__WORKERS", "8")
    monkeypatch.setenv("FLIM_SERVER_TIMEOUT", "90")
    changes = environment_changes()
    assert changes["server_timeout"] == 90
    assert changes["results_dir"] == "/data/out" and changes["cache"] == {"dir": "/scratch/cache"}
    assert changes["prefect_server"] is False and "strict" not in changes
    assert changes["execution"]["executor"] == "dask-local"
    assert changes["execution"]["workers"] == 8
    monkeypatch.setenv("FLIM_EXECUTION__EXECUTOR", "dask")  # no address
    with pytest.raises(ValueError, match="FLIM_EXECUTION"):
        environment_changes()


def test_session_layers(monkeypatch, tmp_path):
    for name in list(os.environ):
        if name.startswith("FLIM_") and name != "FLIM_USER_SETTINGS":
            monkeypatch.delenv(name)
    user = UserSettingsFile(tmp_path / "usersettings.json")
    SettingsManager(user_file=user).set_tool(KMEANS, KMeansConfig(n_clusters=2))
    folder = tmp_path / "appsettings"
    folder.mkdir()
    project = AppSettings.default()
    project.results_dir = Path("/from/file")
    project.tools.set(KMEANS, KMeansConfig(n_clusters=5))
    save_settings(project, folder / "project.json")
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(folder))
    monkeypatch.setenv("FLIM_RESULTS_DIR", "/from/env")

    # user file < app settings file < environment < command line
    manager = session_settings("project", {"results_dir": "/from/cli"}, user_file=user)
    settings = manager.settings
    assert manager.source == folder / "project.json"
    assert settings.tools.config(KMEANS).n_clusters == 5
    assert settings.results_dir == Path("/from/cli")
    assert session_settings("project", user_file=user).settings.results_dir == Path("/from/env")
    # the layers are not written to the user settings file
    assert "results_dir" not in written(user.path)
    assert written(user.path)["tools"]["K-Means"]["config"]["n_clusters"] == 2


def test_session_without_user_file_ignores_it(monkeypatch, tmp_path):
    # flimbatch: settings changed in the GUI don't reach batch runs
    user = UserSettingsFile(tmp_path / "usersettings.json")
    SettingsManager(user_file=user).set_tool(KMEANS, KMeansConfig(n_clusters=7))
    assert session_settings().settings.tools.config(KMEANS).n_clusters == 2  # default


def test_partial_cache_section_keeps_the_other_cache_settings(monkeypatch):
    monkeypatch.delenv("FLIM_CACHE_DIR", raising=False)
    settings = session_settings(None, {"cache": {"dir": "/c"}}).settings
    assert settings.cache.dir == Path("/c") and settings.cache.max_age_days == 7


# --- adding a folder to the app settings search path ---


def test_adding_a_folder_keeps_the_default_folder(tmp_path, monkeypatch):
    from flim.core.settingsmgr import default_app_settings_dir

    monkeypatch.delenv("FLIM_APP_SETTINGS_PATH", raising=False)
    user = UserSettingsFile(tmp_path / "user.json")
    manager = SettingsManager(user_file=user)
    lab = tmp_path / "lab"
    assert manager.add_to_search_path(lab)
    expected = [str(default_app_settings_dir()), str(lab.resolve())]
    assert written(user.path)["appsettings_path"] == expected
    assert not manager.add_to_search_path(lab)  # already there
    other = tmp_path / "other"
    assert manager.add_to_search_path(other)
    assert written(user.path)["appsettings_path"] == expected + [str(other.resolve())]


def test_adding_has_no_effect_with_the_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(tmp_path / "env"))
    manager = SettingsManager(user_file=UserSettingsFile(tmp_path / "user.json"))
    assert manager.search_path_addition(tmp_path / "lab") is None
    assert not manager.add_to_search_path(tmp_path / "lab")


def test_favorites_of_the_user_settings_file_win(tmp_path, monkeypatch):
    """An app settings file presets the favorites; the user's own choice takes precedence."""
    folder = tmp_path / "appsettings"
    folder.mkdir()
    course = AppSettings.default()
    course.favorites = ["Calculate", "Box Plot"]
    save_settings(course, folder / "course.json")
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(folder))
    user = UserSettingsFile(tmp_path / "u.json")
    manager = session_settings("course", user_file=user)
    assert manager.settings.favorites == ["Calculate", "Box Plot"]  # none of the user's
    manager.update({"favorites": ["Sort"]})  # File > Favorites...
    manager = session_settings("course", user_file=user)
    assert manager.settings.favorites == ["Sort"]
    assert manager.origins["favorites"] == "user settings file"


def test_user_settings_file_of_an_older_version_is_kept_before_it_is_rewritten(tmp_path):
    path = tmp_path / "usersettings.json"
    path.write_text(json.dumps({"schema_version": 1, "working_dir": "res"}))
    user = UserSettingsFile(path)
    user.merge({"schema_version": 2, "server_timeout": 5})
    copy = tmp_path / "usersettings.v1.json"
    assert json.loads(copy.read_text()) == {"schema_version": 1, "working_dir": "res"}
    assert json.loads(path.read_text())["schema_version"] == 2
    user.merge({"schema_version": 2, "server_timeout": 6})  # current now: no new copy
    assert sorted(p.name for p in tmp_path.glob("*.json")) == ["usersettings.json", "usersettings.v1.json"]
