"""Quitting asks before unsaved results are lost (0.6.2).

Quitting closes the main window, which destroys the table windows without their own
save question; in 0.5 to 0.6.1 unsaved tables were lost without asking.
"""

import pandas as pd
import pytest

wx = pytest.importorskip("wx")


@pytest.fixture
def app_frame(wxapp, monkeypatch):
    from flim.core.settings import AppSettings
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    frame = AppFrame(FLIMAnalyzer(), AppSettings.default())
    frame.asked = []

    def answer_with(answer):
        def show(dialog):
            frame.asked.append(dialog.GetMessage())
            return answer

        monkeypatch.setattr(wx.MessageDialog, "ShowModal", show)

    frame.answer_with = answer_with
    yield frame
    if frame:
        frame.Destroy()


def _open_table(frame, title="Table: Summary"):
    from flim.gui.events import EVT_DATA_TYPE, DataWindowEvent

    event = DataWindowEvent(EVT_DATA_TYPE, frame.GetId())
    event.SetEventInfo(pd.DataFrame({"x": [1.0, 2.0]}), title, "createnew")
    frame.GetEventHandler().ProcessEvent(event)
    return frame.windowframes[title]


def test_cancel_keeps_everything_open(app_frame):
    table = _open_table(app_frame)
    assert table.modified
    app_frame.answer_with(wx.ID_NO)  # "Cancel"
    assert not app_frame.Close()  # vetoed
    assert app_frame and table
    assert len(app_frame.asked) == 1 and "Table: Summary" in app_frame.asked[0]


def test_quit_anyway_closes(app_frame):
    _open_table(app_frame)
    app_frame.answer_with(wx.ID_YES)  # "Quit"
    assert app_frame.Close()
    assert len(app_frame.asked) == 1


def test_no_question_without_unsaved_windows(app_frame):
    table = _open_table(app_frame)
    table.modified = False  # e.g. saved
    app_frame.answer_with(wx.ID_NO)
    assert app_frame.Close()
    assert app_frame.asked == []


def test_exit_menu_asks_too(app_frame):
    _open_table(app_frame)
    app_frame.answer_with(wx.ID_NO)
    app_frame.OnExit(None)  # File > Exit (Cmd-Q on macOS)
    assert app_frame and len(app_frame.asked) == 1
