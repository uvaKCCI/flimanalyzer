"""The flimanalyzer command (flim/analyzerapp.py), in-process: the GUI start, the log
file, --batch, -c and startup errors. No window opens: the GUI app is replaced."""

import logging
import sys

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
    settings.working_dir = str(clean_logging / "results")
    save_settings(settings, str(path))
    started = {}
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "-c", str(path), "-i", "a.txt"])
    monkeypatch.setattr(
        analyzerapp,
        "interactive_run",
        lambda fa, files=None, settings=None: started.update(files=files, settings=settings),
    )
    _no_server(monkeypatch)
    analyzerapp.main()
    assert started["files"] == ["a.txt"]
    assert started["settings"].working_dir == str(clean_logging / "results")


def test_unavailable_executor_stops_the_start(monkeypatch):
    def unavailable(executor):
        raise RuntimeError("needs the optional Dask support")

    monkeypatch.setattr(analyzerapp, "check_executor_available", unavailable)
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "-e", "DaskExecutor"])
    with pytest.raises(SystemExit, match="Dask support"):
        analyzerapp.main()


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
        def __init__(self, fa, config=None, files=None):
            created.update(fa=fa, config=config, files=files)

        def MainLoop(self):
            created["loop"] = True

    monkeypatch.setattr(flim.gui.app, "FLIMAnalyzerApp", FakeApp)
    fa, settings = object(), object()
    analyzerapp.interactive_run(fa, files=["a.txt"], settings=settings)
    assert created == {"fa": fa, "config": settings, "files": ["a.txt"], "loop": True}


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
