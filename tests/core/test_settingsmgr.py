"""The SettingsManager and the user settings file."""

import json
import os
from pathlib import Path

import pytest

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
    path = tmp_path / "settings.json"
    manager = SettingsManager(user_file=UserSettingsFile(path))
    settings = manager.set_tool(KMEANS, KMeansConfig(n_clusters=4), True, "/results")
    assert settings.tools.config(KMEANS).n_clusters == 4
    assert manager.version == 1
    data = written(path)
    assert data["schema_version"] == SETTINGS_VERSION
    assert set(data) == {"schema_version", "tools"}
    assert set(data["tools"]) == {"K-Means"}
    assert data["tools"]["K-Means"]["autosave"] is True
    assert data["tools"]["K-Means"]["results_dir"] == "/results"


def test_changes_are_applied_at_the_next_start(tmp_path):
    path = tmp_path / "settings.json"
    SettingsManager(user_file=UserSettingsFile(path)).set_tool(KMEANS, KMeansConfig(n_clusters=6))
    again = SettingsManager(user_file=UserSettingsFile(path))
    assert again.settings.tools.config(KMEANS).n_clusters == 6


def test_two_instances_keep_each_others_sections(tmp_path):
    path = tmp_path / "settings.json"
    a = SettingsManager(user_file=UserSettingsFile(path))
    b = SettingsManager(user_file=UserSettingsFile(path))
    a.set_tool(KMEANS, KMeansConfig(n_clusters=3))
    b.set_tool(SUMMARIZE, SummaryConfig(aggs=["max"]))
    assert set(written(path)["tools"]) == {"K-Means", "Summarize"}


def test_same_section_the_instance_that_saves_last_takes_precedence(tmp_path):
    path = tmp_path / "settings.json"
    a = SettingsManager(user_file=UserSettingsFile(path))
    b = SettingsManager(user_file=UserSettingsFile(path))
    a.set_tool(KMEANS, KMeansConfig(n_clusters=3))
    b.set_tool(KMEANS, KMeansConfig(n_clusters=8))
    assert written(path)["tools"]["K-Means"]["config"]["n_clusters"] == 8


def test_the_file_is_replaced_without_leftovers(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(user_file=UserSettingsFile(path))
    manager.set_tool(KMEANS, KMeansConfig(n_clusters=3))
    manager.set_tool(KMEANS, KMeansConfig(n_clusters=5))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".settings-")]
    assert leftovers == []
    assert written(path)["tools"]["K-Means"]["config"]["n_clusters"] == 5


def test_missing_user_file_gives_the_base_settings(tmp_path):
    manager = SettingsManager(user_file=UserSettingsFile(tmp_path / "none.json"))
    assert manager.settings == AppSettings.default()


def test_unreadable_user_file_gives_the_base_settings_and_a_warning(tmp_path, caplog):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    manager = SettingsManager(user_file=UserSettingsFile(path))
    assert manager.settings == AppSettings.default()
    assert "not used" in caplog.text


def test_failed_write_keeps_the_change_and_warns(tmp_path, caplog, monkeypatch):
    user_file = UserSettingsFile(tmp_path / "settings.json")

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
    path = tmp_path / "settings.json"
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
    assert {"import", "filters", "tools"} <= set(data)


def test_older_user_file_is_migrated(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"root": {"filters": {"Use": True}}}))  # version 0
    assert SettingsManager(user_file=UserSettingsFile(path)).settings.filters.use is True


def test_user_settings_path_from_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("FLIM_USER_SETTINGS", str(tmp_path / "mine.json"))
    assert user_settings_path() == tmp_path / "mine.json"


def test_user_settings_path_in_the_platform_folder(monkeypatch):
    monkeypatch.delenv("FLIM_USER_SETTINGS", raising=False)
    path = user_settings_path()
    assert path.name == "settings.json" and path.parent.name == "FLIMAnalyzer"
    assert os.path.isabs(path)
