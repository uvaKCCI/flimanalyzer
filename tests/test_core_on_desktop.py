"""Core tests that need wxPython or macOS. They are in the GUI suite, which runs on
macOS and Windows with wxPython: the core job (Linux) has neither."""

import sys
from pathlib import Path

import pytest

import flim.analyzerapp as analyzerapp


def test_gui_starts_with_files_and_settings(monkeypatch):
    import flim.gui.app

    created = {}

    class FakeApp:
        def __init__(self, fa, settings_manager=None, files=None, **_):
            created.update(fa=fa, manager=settings_manager, files=files)

        def MainLoop(self):
            created["loop"] = True

    monkeypatch.setattr(flim.gui.app, "FLIMAnalyzerApp", FakeApp)
    fa, manager = object(), object()
    analyzerapp.interactive_run(fa, files=["a.txt"], settings_manager=manager)
    assert created == {"fa": fa, "manager": manager, "files": ["a.txt"], "loop": True}


def test_startup_error_shows_a_message_box(monkeypatch):
    import wx

    shown = []
    monkeypatch.setattr(wx, "App", lambda *a, **k: object())
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: shown.append(message))
    analyzerapp.show_startup_error("No Prefect server could be started")
    assert shown == ["No Prefect server could be started"]


@pytest.mark.skipif(sys.platform != "darwin", reason="case-insensitive file names by default")
def test_folders_compared_without_case_on_macos(tmp_path):
    from flim.core.paths import stored_folder

    default = tmp_path / "Results"
    assert stored_folder(tmp_path / "results" / "a", default) == Path("a")
