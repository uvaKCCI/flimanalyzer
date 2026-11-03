import threading
import time

import pytest

wx = pytest.importorskip("wx")

from flim.core.runner import run_flow  # noqa: E402
from tests.fake_tools import Counter, Waiter  # noqa: E402


pytestmark = pytest.mark.usefixtures("prefect_harness")


def _tasks(n, release=None):
    """Tasks T0, T1, ...: with ``release``, they run until it is set (or cancelled)."""
    if release is None:
        return [Counter(f"T{i}") for i in range(n)]
    return [Waiter(f"T{i}", release=release) for i in range(n)]


def _starter(tools, autosave_dir=None):
    def build():
        for tool in tools:
            tool()

    def start_run(cancel_token, on_progress, on_start):
        return run_flow(
            "test run",
            build,
            autosave_dir=autosave_dir,
            on_progress=on_progress,
            cancel_token=cancel_token,
            on_start=on_start,
        )

    return start_run


def _click(button):
    event = wx.CommandEvent(wx.wxEVT_BUTTON, button.GetId())
    event.SetEventObject(button)
    button.GetEventHandler().ProcessEvent(event)


def _tool_button(frame, name):
    return next(
        c
        for box in frame.toolpanel.GetChildren()
        for c in box.GetChildren()
        if isinstance(c, wx.BitmapButton) and c.GetName() == name
    )


def _open(frame, data, title="Data", **kwargs):
    """Opens ``data`` in a data window, as the application does."""
    from flim.gui.events import EVT_DATA_TYPE, DataWindowEvent

    event = DataWindowEvent(EVT_DATA_TYPE, frame.GetId())
    event.SetEventInfo(data, title, "createnew", **kwargs)
    frame.GetEventHandler().ProcessEvent(event)
    return frame.windowframes[title]


def _statuses(dlg):
    return {
        dlg.task_list.GetItemText(row, 0): dlg.task_list.GetItemText(row, 1)
        for row in range(dlg.task_list.GetItemCount())
    }


def _when(condition, action, *args, tries=100):
    """Calls ``action(*args)`` once ``condition()`` holds, checking every 0.1 s (at most
    ``tries`` times): busy test machines need more than a fixed delay."""
    if condition() or not tries:
        action(*args)
    else:
        wx.CallLater(100, _when, condition, action, *args, tries=tries - 1)


def test_progress_dialog_closes_when_the_run_completes(wxapp):
    from flim.gui.progressdlg import RunProgressDialog

    dlg = RunProgressDialog(None, "Test", _starter(_tasks(3)))
    try:
        assert dlg.ShowModal() == wx.ID_OK
        assert dlg.error is None and dlg.run.state == "completed"
        wx.Yield()  # pending progress updates
        assert dlg.count_text.GetLabel() == "3 of 3 tasks completed"
        assert dlg.gauge.GetValue() == dlg.gauge.GetRange() == 3
    finally:
        dlg.Destroy()


def test_progress_dialog_shows_prefect_link_and_task_statuses(wxapp):
    from flim.gui.progressdlg import RunProgressDialog

    seen = {}
    release = threading.Event()

    def snapshot(dlg):
        # while the first task runs
        seen["link"] = dlg.link.GetURL() if dlg.link.IsShown() else None
        seen["statuses"] = [
            dlg.task_list.GetItemText(row, 1) for row in range(dlg.task_list.GetItemCount())
        ]
        release.set()

    dlg = RunProgressDialog(None, "Test", _starter(_tasks(2, release)))
    _when(lambda: "running" in _statuses(dlg).values(), snapshot, dlg)
    try:
        assert dlg.ShowModal() == wx.ID_OK
        assert seen["link"] and seen["link"] == dlg.run.ui_url
        assert "running" in seen["statuses"]
        final = [
            (dlg.task_list.GetItemText(row, 0), dlg.task_list.GetItemText(row, 1))
            for row in range(dlg.task_list.GetItemCount())
        ]
        assert final == [("T0", "completed"), ("T1", "completed")]
    finally:
        dlg.Destroy()


def test_cancel_button_cancels_the_run(wxapp):
    from flim.gui.progressdlg import RunProgressDialog

    # the tasks run until cancelled
    dlg = RunProgressDialog(None, "Test", _starter(_tasks(2, threading.Event())))
    _when(lambda: "running" in _statuses(dlg).values(), _click, dlg.cancel_button)
    start = time.monotonic()
    try:
        assert dlg.ShowModal() == wx.ID_CANCEL
        assert time.monotonic() - start < 6
        assert dlg.run.state == "cancelled"
        assert not dlg.cancel_button.IsEnabled()
        assert dlg.task_text.GetLabel().startswith("Cancelling")
    finally:
        dlg.Destroy()


def test_error_in_the_workflow_script_is_kept(wxapp):
    from flim.gui.progressdlg import RunProgressDialog

    def start_run(cancel_token, on_progress, on_start):
        raise ValueError("bad workflow")

    dlg = RunProgressDialog(None, "Test", start_run)
    try:
        dlg.ShowModal()
        assert isinstance(dlg.error, ValueError) and dlg.run is None
    finally:
        dlg.Destroy()


@pytest.fixture
def frame(wxapp):
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    frame = AppFrame(FLIMAnalyzer())
    yield frame
    frame.Destroy()


def _first_task_then_waiting(n=3):
    """T0 completes at once, the others run until cancelled."""
    return [Counter("T0"), *_tasks(n, threading.Event())[1:]]


def _cancel_after_first_task(start_run):
    """Cancels the run once a task has completed."""

    def start(cancel_token, on_progress, on_start):
        def progress(done, total, label, complete):
            on_progress(done, total, label, complete)
            if done >= 1:
                cancel_token.set()

        return start_run(cancel_token, progress, on_start)

    return start


def _capture_cancelled_dialog(monkeypatch):
    from flim.gui.progressdlg import RunSummaryDialog

    shown = {}

    def show(dlg):
        texts = [c.GetLabel() for c in dlg.GetChildren() if isinstance(c, wx.StaticText)]
        paths = [dlg.folder.path] if dlg.folder else []
        shown.update(texts=texts, paths=paths, link=dlg.link.GetURL() if dlg.link else None)
        return wx.ID_OK

    monkeypatch.setattr(RunSummaryDialog, "ShowModal", show)
    return shown


def test_cancelled_run_shows_results_folder_and_prefect_link(frame, monkeypatch, tmp_path):
    shown = _capture_cancelled_dialog(monkeypatch)
    start = _cancel_after_first_task(
        _starter(_first_task_then_waiting(), autosave_dir=str(tmp_path))
    )
    assert frame.run_with_progress("My Tool", start) is None
    (run_dir,) = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert shown["paths"] == [str(run_dir)]
    assert shown["texts"][0].startswith("My Tool was cancelled after ")
    assert "Results of the completed tasks are in:" in shown["texts"]
    assert shown["link"] and "/runs/flow-run/" in shown["link"]
    assert (run_dir / "run_summary.txt").exists()
    assert frame.IsEnabled()  # back to interactive work


def test_cancelled_run_without_autosave(frame, monkeypatch):
    shown = _capture_cancelled_dialog(monkeypatch)
    start = _cancel_after_first_task(_starter(_first_task_then_waiting()))
    assert frame.run_with_progress("My Tool", start) is None
    assert shown["paths"] == []
    assert "No results were saved because Autosave is off." in shown["texts"]


def test_completed_run_is_returned(frame):
    run = frame.run_with_progress("My Tool", _starter(_tasks(2)))
    assert run.state == "completed" and len(run.results()) == 2


def test_error_is_reported(frame, monkeypatch):
    messages = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: messages.append(message))

    def start_run(cancel_token, on_progress, on_start):
        raise ValueError("bad workflow")

    assert frame.run_with_progress("My Tool", start_run) is None
    assert "bad workflow" in messages[0]


def test_toolbar_click_runs_the_tool_behind_the_progress_dialog(frame, monkeypatch, flim_data):
    import pandas as pd

    from flim.gui import configdialog, progressdlg
    from flim.gui.datapanel import PandasFrame

    _open(frame, flim_data)  # an open data table to analyze

    # stands in for the user's choices in the tool's configuration dialog
    def configure(dialog):
        dialog.fields.editors["grouping"].set(["Treatment"])
        dialog.fields.editors["features"].set(["NAD(P)H t1"])
        dialog.validate()
        return wx.ID_OK

    monkeypatch.setattr(configdialog.ConfigDialog, "ShowModal", configure)
    # never wait for a click: any other prompt is answered with No
    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)
    messages = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: messages.append(message))
    outcomes = []
    original = progressdlg.RunProgressDialog.ShowModal
    monkeypatch.setattr(
        progressdlg.RunProgressDialog,
        "ShowModal",
        lambda dlg: outcomes.append(original(dlg)) or outcomes[-1],
    )

    before = set(frame.windowframes)
    _click(_tool_button(frame, "Summarize"))

    assert messages == []
    assert outcomes == [wx.ID_OK]
    new = {t: w for t, w in frame.windowframes.items() if t not in before}
    assert new and all(isinstance(w, PandasFrame) for w in new.values())
    assert all(isinstance(w.GetViewData(), pd.DataFrame) for w in new.values())
    # close the data windows without the "save the modified data?" prompt
    for window in frame.windowframes.values():
        if isinstance(window, PandasFrame):
            window.modified = False
    frame.OnCloseAll(None)


def test_status_line_matches_the_task_list(wxapp):
    from flim.core.runner import default_task_runner
    from flim.gui.progressdlg import RunProgressDialog

    release = threading.Event()

    def build():
        Counter("Short")()
        Waiter("Long", release=release)()

    def start_run(cancel_token, on_progress, on_start):
        return run_flow(
            "status",
            build,
            default_task_runner(1),  # one task at a time
            on_progress=on_progress,
            cancel_token=cancel_token,
            on_start=on_start,
        )

    seen = {}

    def snapshot(dlg):
        seen["line"] = dlg.task_text.GetLabel()
        seen["list"] = _statuses(dlg)
        seen["count"] = dlg.count_text.GetLabel()
        release.set()

    dlg = RunProgressDialog(None, "Test", start_run)
    # when Short has finished and Long is running
    _when(lambda: _statuses(dlg) == {"Short": "completed", "Long": "running"}, snapshot, dlg)
    try:
        assert dlg.ShowModal() == wx.ID_OK
        assert seen["list"] == {"Short": "completed", "Long": "running"}
        assert seen["line"] == "Running: Long"
        assert seen["count"] == "1 of 2 tasks completed"
    finally:
        dlg.Destroy()


def test_results_folder_link_opens_the_file_browser(wxapp, monkeypatch, tmp_path):
    from flim.gui import progressdlg
    from flim.gui.progressdlg import RunProgressDialog

    opened = []
    monkeypatch.setattr(progressdlg, "open_in_file_browser", opened.append)
    seen = {}
    release = threading.Event()

    def snapshot(dlg):
        seen["shown"] = dlg.folder.IsShown()
        seen["label"] = dlg.folder.GetLabel()
        click = wx.adv.HyperlinkEvent(dlg.folder, dlg.folder.GetId(), "")
        dlg.folder.GetEventHandler().ProcessEvent(click)
        release.set()

    start = _starter(_tasks(2, release), autosave_dir=str(tmp_path))
    dlg = RunProgressDialog(None, "Test", start)
    _when(dlg.folder.IsShown, snapshot, dlg)
    try:
        assert dlg.ShowModal() == wx.ID_OK
        run_dir = dlg.run.autosave_dir
        assert run_dir.startswith(str(tmp_path))
        # long paths are shortened in the label, the click opens the whole path
        from flim.core.paths import shorten_path

        assert seen == {"shown": True, "label": shorten_path(run_dir)}
        assert dlg.folder.path == run_dir and run_dir in dlg.folder.GetToolTipText()
        assert opened == [run_dir]
    finally:
        dlg.Destroy()


def test_open_in_file_browser_creates_the_folder(monkeypatch, tmp_path):
    import subprocess
    import sys

    from flim.gui import progressdlg

    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, *a, **k: calls.append(args))
    monkeypatch.setattr(progressdlg.os, "startfile", lambda p: calls.append(["startfile", p]), raising=False)
    folder = tmp_path / "not yet created"
    progressdlg.open_in_file_browser(str(folder))
    assert folder.is_dir()
    expected = {"darwin": "open", "win32": "startfile"}.get(sys.platform, "xdg-open")
    assert calls == [[expected, str(folder)]]


def test_open_data_files_opens_a_data_window(frame, tmp_path, flim_data):
    from flim.gui.datapanel import PandasFrame

    csv = tmp_path / "cells.csv"
    flim_data.to_csv(csv, index=False)
    assert frame.open_data_files([str(csv)]) == "cells.csv"
    window = frame.windowframes["cells.csv"]
    assert isinstance(window, PandasFrame)
    assert len(window.GetViewData()) == len(flim_data)
    assert not window.is_modified()  # just read from the file: closing asks nothing
    frame.OnCloseAll(None)
    assert "cells.csv" not in frame.windowframes


def test_result_tables_are_marked_modified(frame, flim_data):
    window = _open(frame, flim_data, "Result")
    assert window.is_modified()  # unsaved: closing asks to save
    window.modified = False
    frame.OnCloseAll(None)


def test_files_given_with_input_are_opened_at_startup(frame, monkeypatch, tmp_path, flim_data):
    from flim.gui.app import FLIMAnalyzerApp

    csv = tmp_path / "cells.csv"
    flim_data.to_csv(csv, index=False)
    messages = []
    monkeypatch.setattr(wx, "MessageBox", lambda message, *a, **k: messages.append(message))

    class App:  # stands in for the running FLIMAnalyzerApp
        pass

    app = App()
    app.frame = frame
    FLIMAnalyzerApp.open_files(app, [str(csv), str(tmp_path / "missing.csv")])
    assert "cells.csv" in frame.windowframes
    assert len(messages) == 1 and "missing.csv" in messages[0]
    frame.windowframes["cells.csv"].modified = False
    frame.OnCloseAll(None)


def test_input_option_is_passed_to_the_app(monkeypatch):
    import sys

    import flim.analyzerapp as analyzerapp

    started = {}
    monkeypatch.setattr(sys, "argv", ["flimanalyzer", "-i", "a.csv", "b.txt", "--no-prefect-server"])
    monkeypatch.setattr(analyzerapp, "init_logger", lambda level: None)
    monkeypatch.setattr(
        analyzerapp,
        "interactive_run",
        lambda fa, files=None, settings=None: started.update(files=files),
    )
    analyzerapp.main()
    assert started["files"] == ["a.csv", "b.txt"]



class Failing(Counter):
    def run(self, *inputs, config):
        raise RuntimeError("boom")


def _summary_texts(run, title="My Workflow"):
    from flim.gui.progressdlg import RunSummaryDialog

    dlg = RunSummaryDialog(None, title, run)
    try:
        texts = [c.GetLabel() for c in dlg.GetChildren() if isinstance(c, wx.StaticText)]
        return texts, dlg.folder.path if dlg.folder else None, dlg.link.GetURL() if dlg.link else None
    finally:
        dlg.Destroy()


def test_summary_of_a_completed_run(wxapp, tmp_path):
    run = _starter(_tasks(2), autosave_dir=str(tmp_path))(None, None, None)
    texts, folder, link = _summary_texts(run)
    assert texts[0] == "My Workflow completed all 2 tasks."
    assert "Results are in:" in texts and folder == run.autosave_dir
    assert link == run.ui_url


def test_summary_of_a_run_with_failed_tasks(wxapp, tmp_path):
    def build():
        Counter(name="Good")()
        Failing(name="Bad")()

    run = run_flow("partly failing", build, autosave_dir=str(tmp_path))
    texts, folder, _ = _summary_texts(run)
    assert texts[0] == "My Workflow finished: 1 of 2 tasks completed, 1 failed: Bad"
    assert "See the log for details." in texts
    assert folder == run.autosave_dir


def test_workflow_always_shows_the_summary(frame, monkeypatch, flirr_data, tmp_path):
    from flim.gui import configdialog, progressdlg

    _open(frame, flirr_data, modified=False)

    locked = []

    def configure(dialog):
        dialog.fields.editors["grouping"].set(["Treatment", "FOV"])
        # the fewest features its steps take (pair plots of FAD and of NAD features)
        dialog.fields.editors["features"].set(["FAD a1[%]", "NAD(P)H a2[%]"])
        dialog.folder.SetPath(str(tmp_path))
        locked.append(not dialog.autosave.IsEnabled() and dialog.autosave.GetValue())
        dialog.validate()
        return wx.ID_OK

    monkeypatch.setattr(configdialog.ConfigDialog, "ShowModal", configure)
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: pytest.fail(f"unexpected message {a}"))
    summaries = []

    def show(dlg):
        texts = [c.GetLabel() for c in dlg.GetChildren() if isinstance(c, wx.StaticText)]
        summaries.append((texts[0], dlg.folder.path if dlg.folder else None, dlg.link is not None))
        return wx.ID_OK

    monkeypatch.setattr(progressdlg.RunSummaryDialog, "ShowModal", show)
    _click(_tool_button(frame, "Basic FLIRR Analysis"))

    assert locked == [True]  # workflows always save their results
    ((first_line, folder, has_link),) = summaries
    assert first_line.startswith("Basic FLIRR Analysis completed all ")
    assert folder and folder.startswith(str(tmp_path)) and has_link
    assert any("Graph" in title for title in frame.windowframes)  # graph window opened too
    frame.OnCloseAll(None)


def test_garbage_collection_stays_on_the_main_thread_during_a_run(wxapp):
    import gc

    from flim.gui.progressdlg import RunProgressDialog

    seen = []

    class Probe(Counter):
        def run(self, *inputs, config):
            seen.append(gc.isenabled())  # in a worker thread
            return {}

    def start_run(cancel_token, on_progress, on_start):
        return run_flow("gc", lambda: Probe()(), on_progress=on_progress,
                        cancel_token=cancel_token, on_start=on_start)

    assert gc.isenabled()
    dlg = RunProgressDialog(None, "Test", start_run)
    try:
        assert dlg.ShowModal() == wx.ID_OK
    finally:
        dlg.Destroy()
    assert seen == [False]  # no automatic collection while the flow ran
    assert gc.isenabled()  # restored afterwards
