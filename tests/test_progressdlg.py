import time

import pytest
from prefect.testing.utilities import prefect_test_harness

wx = pytest.importorskip("wx")

from flim.core.runner import run_flow  # noqa: E402
from flim.plugin import AbstractPlugin  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def prefect_harness():
    # temporary Prefect server and database, nothing is reported to a real server
    with prefect_test_harness():
        yield


@pytest.fixture(scope="module")
def wxapp():
    try:
        app = wx.App()
    except SystemExit:  # raised by wx when no display is available
        pytest.skip("no display available")
    import flim.gui  # noqa: F401

    yield app
    for window in wx.GetTopLevelWindows():
        window.Destroy()


class Task(AbstractPlugin):
    def __init__(self, name="Task", seconds=0.0, **kwargs):
        super().__init__(name=name, **kwargs)
        self.seconds = seconds

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return []

    def execute(self):
        end = time.monotonic() + self.seconds
        while time.monotonic() < end:
            self.check_cancelled()
            time.sleep(0.02)
        return {f"{self.name} done": True}


def _starter(n=3, seconds=0.0, autosave_dir=None):
    def build():
        for i in range(n):
            Task(name=f"T{i}", seconds=seconds)(input={})

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


def test_progress_dialog_closes_when_the_run_completes(wxapp):
    from flim.gui.progressdlg import RunProgressDialog

    dlg = RunProgressDialog(None, "Test", _starter(3))
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

    def snapshot(dlg):
        # while the first task runs
        seen["link"] = dlg.link.GetURL() if dlg.link.IsShown() else None
        seen["statuses"] = [
            dlg.task_list.GetItemText(row, 1) for row in range(dlg.task_list.GetItemCount())
        ]

    dlg = RunProgressDialog(None, "Test", _starter(2, seconds=1.5))
    wx.CallLater(1000, snapshot, dlg)
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

    dlg = RunProgressDialog(None, "Test", _starter(2, seconds=10))
    wx.CallLater(700, _click, dlg.cancel_button)
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
    from flim.gui.progressdlg import RunCancelledDialog

    shown = {}

    def show(dlg):
        texts = [c.GetLabel() for c in dlg.GetChildren() if isinstance(c, wx.StaticText)]
        paths = [c.GetValue() for c in dlg.GetChildren() if isinstance(c, wx.TextCtrl)]
        shown.update(texts=texts, paths=paths, link=dlg.link.GetURL() if dlg.link else None)
        return wx.ID_OK

    monkeypatch.setattr(RunCancelledDialog, "ShowModal", show)
    return shown


def test_cancelled_run_shows_results_folder_and_prefect_link(frame, monkeypatch, tmp_path):
    shown = _capture_cancelled_dialog(monkeypatch)
    start = _cancel_after_first_task(_starter(3, seconds=0.5, autosave_dir=str(tmp_path)))
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
    start = _cancel_after_first_task(_starter(3, seconds=0.5))
    assert frame.run_with_progress("My Tool", start) is None
    assert shown["paths"] == []
    assert "No results were saved because Autosave is off." in shown["texts"]


def test_completed_run_is_returned(frame):
    run = frame.run_with_progress("My Tool", _starter(2))
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

    from flim.gui import progressdlg
    from flim.gui.datapanel import PandasFrame
    from flim.analysis.summarystats import SummaryStats
    from flim.gui.events import EVT_DATA_TYPE, DataWindowEvent

    # an open data table to analyze
    event = DataWindowEvent(EVT_DATA_TYPE, frame.GetId())
    event.SetEventInfo(flim_data, "Data", "createnew")
    frame.GetEventHandler().ProcessEvent(event)

    # stands in for the user's choices in the tool's configuration dialog
    def configure(tool, parent, data_choices={}):
        tool.params.update(grouping=["Treatment"], features=["NAD(P)H t1"])
        return tool.params

    monkeypatch.setattr(SummaryStats, "run_configuration_dialog", configure)
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

    button = next(
        c
        for box in frame.toolpanel.GetChildren()
        for c in box.GetChildren()
        if isinstance(c, wx.BitmapButton) and c.GetName() == "Summarize"
    )
    click = wx.CommandEvent(wx.wxEVT_BUTTON, button.GetId())
    click.SetEventObject(button)
    before = set(frame.windowframes)
    frame.on_run_plugin(click)

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
