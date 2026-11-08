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


def test_log_file_in_the_start_folder(clean_logging):
    analyzerapp.init_logger("DEBUG")
    logging.debug("hello")
    assert logging.root.level == logging.DEBUG
    assert "hello" in (clean_logging / "flimanalyzer.log").read_text()


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
    assert settings.results_dir == Path("out") and settings.log_dir == Path("logs")
    assert settings.execution.workers == 3 and settings.prefect_server is False
    assert settings.cache.dir == Path("cache") and settings.strict is True
    assert settings.cache.max_size_mb == 2048  # only the cache folder changed
    assert started["fa"].execution.execution.workers == 3


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
