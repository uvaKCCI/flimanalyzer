"""The app settings as rows for the Settings viewer (flim.core.settingsview), and the
layer each setting comes from (SettingsManager.origins)."""

import json
from pathlib import Path

from flim.core.cli import command_line_changes
from flim.core.settingsmgr import SettingsManager, UserSettingsFile, session_settings
from flim.core.settingsview import VIEWED, overview


def rows(manager):
    return {row.name: row for row in overview(manager)}


def test_defaults():
    shown = rows(SettingsManager())
    assert list(shown) == list(VIEWED)
    assert shown["results_dir"].title == "Results folder"
    assert shown["results_dir"].value.startswith("start folder (")
    assert shown["execution"].value == "local, workers: automatic"
    assert shown["prefect_server"].value.startswith("yes")
    assert all(row.origin == "built-in default" for row in shown.values())
    assert shown["execution"].change.startswith("-e, FLIM_EXECUTION")
    assert shown["prefect_server"].change == "--prefect-server, --no-prefect-server, FLIM_PREFECT_SERVER"


def test_each_setting_names_its_layer(tmp_path, monkeypatch):
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"schema_version": 2, "log": {"dir": "logs"}}))
    app = tmp_path / "cells.json"
    app.write_text(json.dumps({"schema_version": 2, "strict": True,
                               "execution": {"executor": "dask-local", "workers": 8}}))
    monkeypatch.setenv("FLIM_PREFECT_SERVER", "false")

    import argparse

    from flim.core.cli import add_settings_options

    parser = argparse.ArgumentParser()
    add_settings_options(parser)
    changes, _ = command_line_changes(parser.parse_args(["-o", "out"]))
    manager = session_settings(str(app), changes, user_file=UserSettingsFile(user))
    shown = rows(manager)
    assert shown["results_dir"].origin == "command line (-o)"
    assert shown["results_dir"].value == str(Path("out"))
    assert shown["prefect_server"].origin == "environment (FLIM_PREFECT_SERVER)"
    assert shown["prefect_server"].value == "no: a temporary server for each run"
    assert shown["execution"].origin == "app settings file"
    assert shown["execution"].value == "dask-local, 8 workers, scheduler: threads"
    assert shown["strict"].origin == "app settings file"
    assert shown["strict"].value == "errors"
    assert shown["log"].origin == "user settings file"
    assert shown["log"].value == "logs; logs kept 30 days"


def test_a_change_in_the_gui_comes_from_the_user_settings_file(tmp_path):
    manager = SettingsManager(user_file=UserSettingsFile(tmp_path / "user.json"))
    manager.update({"results_dir": "r"})
    assert rows(manager)["results_dir"].origin == "user settings file"
