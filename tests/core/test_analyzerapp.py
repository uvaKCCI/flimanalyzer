"""The flimanalyzer command (flim/analyzerapp.py), in-process: the GUI start, the log
file, --batch, -c and startup errors. No window opens: the GUI app is replaced."""

import logging
import sys
from pathlib import Path

import pytest

import flim.analyzerapp as analyzerapp


@pytest.fixture
def clean_logging(tmp_path, monkeypatch):
    """A temporary start folder (the log file goes there) and the logging setup
    restored afterwards."""
    monkeypatch.chdir(tmp_path)
    handlers, level = logging.root.handlers[:], logging.root.level
    yield tmp_path
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()
    for handler in handlers:
        logging.root.addHandler(handler)
    logging.root.setLevel(level)


def _no_server(monkeypatch):
    import contextlib

    monkeypatch.setattr(
        analyzerapp, "use_prefect_server", lambda **kw: contextlib.nullcontext()
    )


# --- init_logger ---


def test_session_log_file_in_the_log_folder(monkeypatch, clean_logging, tmp_path):
    monkeypatch.setenv("FLIM_LOG_DIR", str(tmp_path / "logs"))
    _start(monkeypatch, [])
    for handler in logging.root.handlers:
        handler.flush()
    (path,) = (tmp_path / "logs").glob("flimanalyzer_*.log")
    assert "FLIMAnalyzer version" in path.read_text()  # logged before the file opened
    assert not (clean_logging / "flimanalyzer.log").exists()  # not in the start folder


def test_log_dir_option(monkeypatch, clean_logging, tmp_path):
    _start(monkeypatch, ["--log-dir", str(tmp_path / "mine")])
    assert list((tmp_path / "mine").glob("flimanalyzer_*.log"))


def test_log_replaces_earlier_handlers(clean_logging):
    logging.root.addHandler(logging.NullHandler())
    analyzerapp.init_logger("INFO")
    assert not any(isinstance(h, logging.NullHandler) for h in logging.root.handlers)


def test_invalid_log_level(clean_logging):
    with pytest.raises(ValueError, match="Invalid log level"):
        analyzerapp.init_logger("LOUD")


# --- main ---


def test_batch_hands_over_to_flimbatch(monkeypatch):
    import flim.batch

    seen = []
    monkeypatch.setattr(flim.batch, "main", lambda argv: seen.append(argv) or 3)
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "--batch", "-i", "x", "-o", "y"])
    with pytest.raises(SystemExit) as exit_:
        analyzerapp.main()
    assert exit_.value.code == 3
    assert seen == [["-i", "x", "-o", "y"]]


def test_settings_file_reaches_the_gui(monkeypatch, clean_logging):
    from flim.core.settings import AppSettings, save_settings

    path = clean_logging / "project.json"
    settings = AppSettings.default()
    settings.results_dir = clean_logging / "results"
    save_settings(settings, str(path))
    started = {}
    monkeypatch.setattr(
        analyzerapp,
        "interactive_run",
        lambda fa, files=None, settings_manager=None: started.update(
            files=files, manager=settings_manager
        ),
    )
    _no_server(monkeypatch)
    analyzerapp.main(["-s", str(path), "-i", "a.txt"])
    manager = started["manager"]
    assert started["files"] == ["a.txt"] and manager.source == path
    assert manager.settings.results_dir == clean_logging / "results"


def test_config_option_still_works_with_a_warning(monkeypatch, clean_logging, capsys):
    from flim.core.settings import AppSettings, save_settings

    path = clean_logging / "project.json"
    save_settings(AppSettings.default(), str(path))
    started = {}
    monkeypatch.setattr(
        analyzerapp,
        "interactive_run",
        lambda fa, files=None, settings_manager=None: started.update(manager=settings_manager),
    )
    _no_server(monkeypatch)
    analyzerapp.main(["-c", str(path)])
    assert started["manager"].source == path
    assert "-c/--config is deprecated; use -s/--settings" in capsys.readouterr().err


def test_command_line_options_set_the_session_settings(monkeypatch, clean_logging):
    started = {}
    monkeypatch.setattr(
        analyzerapp,
        "interactive_run",
        lambda fa, files=None, settings_manager=None: started.update(
            fa=fa, manager=settings_manager
        ),
    )
    _no_server(monkeypatch)
    analyzerapp.main(
        ["-o", "out", "-e", "local:workers=3", "--no-prefect-server", "--log-dir", "logs",
         "--cache-dir", "cache", "--strict"]
    )
    settings = started["manager"].settings
    assert settings.results_dir == Path("out") and settings.log.dir == Path("logs")
    assert settings.execution.workers == 3 and settings.prefect_server is False
    assert settings.cache.dir == Path("cache") and settings.strict is True
    assert settings.cache.max_size_mb == 2048  # only the cache folder changed
    assert started["fa"].execution.execution.workers == 3


def _start(monkeypatch, argv, choose=None):
    started = {}
    monkeypatch.setattr(
        analyzerapp,
        "interactive_run",
        lambda fa, files=None, settings_manager=None: started.update(manager=settings_manager),
    )
    if choose is not None:
        monkeypatch.setattr(analyzerapp, "choose_settings", choose)
    _no_server(monkeypatch)
    analyzerapp.main(argv)
    return started["manager"]


def test_defaults_json_is_used_as_the_app_settings_file(monkeypatch, clean_logging, capsys):
    import json

    path = clean_logging / "defaults.json"
    path.write_text(json.dumps({"schema_version": 1, "working_dir": "res"}))
    manager = _start(monkeypatch, [])
    assert manager.source == path.resolve() and manager.settings.results_dir == Path("res")
    assert "defaults.json from the start folder is deprecated" in capsys.readouterr().err
    assert json.loads(path.read_text()) == {"schema_version": 1, "working_dir": "res"}


def test_defaults_json_is_not_read_with_s(monkeypatch, clean_logging, capsys):
    import json

    (clean_logging / "defaults.json").write_text(json.dumps({"results_dir": "res"}))
    other = clean_logging / "cells.json"
    other.write_text(json.dumps({"schema_version": 2}))
    manager = _start(monkeypatch, ["-s", str(other)])
    assert manager.source == other and manager.settings.results_dir is None
    assert "defaults.json" not in capsys.readouterr().err


def test_file_with_problems_asks_before_the_gui_opens(monkeypatch, clean_logging):
    import json

    path = clean_logging / "cells.json"
    path.write_text(json.dumps({"schema_version": 2, "execution": {"executor": "ray"}}))
    asked = []
    manager = _start(monkeypatch, ["-s", str(path)], lambda check: asked.append(check))
    assert [c.path for c in asked] == [path] and manager.source is None


def test_unreadable_user_settings_file_is_reported(
    monkeypatch, clean_logging, capsys, user_settings_file
):
    user_settings_file.write_text("{not json")
    manager = _start(monkeypatch, [])
    assert "renamed to" in manager.notices[0]
    assert "renamed to" in capsys.readouterr().err


def test_startup_choice_of_app_settings_file(monkeypatch, clean_logging, tmp_path):
    import json

    folder = tmp_path / "appsettings"
    folder.mkdir()
    (folder / "cells.json").write_text(json.dumps({"schema_version": 2}))
    monkeypatch.setenv("FLIM_APP_SETTINGS_PATH", str(folder))
    offered = []
    from flim.core.settingsmgr import Pick

    monkeypatch.setattr(
        analyzerapp,
        "pick_app_settings",
        lambda files, default, warning: offered.append(files) or Pick(files[0], default),
    )
    manager = _start(monkeypatch, [])
    assert offered == [[folder / "cells.json"]] and manager.source == folder / "cells.json"
    offered.clear()
    _start(monkeypatch, ["-s", str(folder / "cells.json")])  # -s: no question
    assert offered == []


def test_unavailable_executor_stops_the_start(monkeypatch, capsys):
    from flim.core.execution import ExecutionOptions

    def unavailable(self):
        raise RuntimeError("needs the optional Dask support")

    monkeypatch.setattr(ExecutionOptions, "check_available", unavailable)
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "-e", "dask-local"])
    with pytest.raises(SystemExit) as stop:
        analyzerapp.main()
    assert stop.value.code == 2 and "Dask support" in capsys.readouterr().err


# --- interactive_run and show_startup_error ---


def test_gui_needs_wxpython(monkeypatch):
    monkeypatch.setitem(sys.modules, "wx", None)  # import wx raises ImportError
    with pytest.raises(SystemExit, match="needs wxPython"):
        analyzerapp.interactive_run(object())


def test_startup_error_without_wxpython_is_quiet(monkeypatch):
    monkeypatch.setitem(sys.modules, "wx", None)
    analyzerapp.show_startup_error("no server")  # no exception, nothing shown


def test_gui_starts_with_files_and_settings(monkeypatch):
    pytest.importorskip("wx")
    import flim.gui.app

    created = {}

    class FakeApp:
        def __init__(self, fa, settings_manager=None, files=None):
            created.update(fa=fa, manager=settings_manager, files=files)

        def MainLoop(self):
            created["loop"] = True

    monkeypatch.setattr(flim.gui.app, "FLIMAnalyzerApp", FakeApp)
    fa, manager = object(), object()
    analyzerapp.interactive_run(fa, files=["a.txt"], settings_manager=manager)
    assert created == {"fa": fa, "manager": manager, "files": ["a.txt"], "loop": True}


def test_startup_error_shows_a_message_box(monkeypatch):
    wx = pytest.importorskip("wx")
    shown = []
    monkeypatch.setattr(wx, "App", lambda *a, **k: object())
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: shown.append(message))
    analyzerapp.show_startup_error("No Prefect server could be started")
    assert shown == ["No Prefect server could be started"]


@pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")
def test_runs_as_a_module(monkeypatch):
    # python -m flim.analyzerapp runs main(), like the flimanalyzer command
    import runpy

    import flim.batch

    monkeypatch.setattr(flim.batch, "main", lambda argv: 0)
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "--batch"])
    with pytest.raises(SystemExit) as exit_:
        runpy.run_module("flim.analyzerapp", run_name="__main__")
    assert exit_.value.code == 0
