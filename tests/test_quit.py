"""Quitting asks before unsaved results are lost (flim.gui.saveall).

Quitting closes the main window, which destroys the table and plot windows without
their own save question; the quit dialog asks first: Cancel, Review..., Save All
Windows... or Discard All.
"""

import pandas as pd
import pytest

wx = pytest.importorskip("wx")

from flim.gui import saveall  # noqa: E402


@pytest.fixture
def app_frame(wxapp, monkeypatch):
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    frame = AppFrame(FLIMAnalyzer())
    frame.asked = []
    # messages (e.g. after Save All) are not shown
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.OK)

    def answer_with(choice, review=(), save_all=None):
        """The quit dialog answers `choice`; Review... answers `review` in order;
        Save All Windows... answers `save_all` (folder, formats) or None (Cancel)."""
        answers = list(review)

        def quit(parent, titles):
            frame.asked.append(list(titles))
            return choice

        monkeypatch.setattr(saveall, "ask_quit", quit)
        monkeypatch.setattr(saveall, "ask_review", lambda parent, title: answers.pop(0))
        monkeypatch.setattr(saveall, "ask_save_all", lambda parent, folder, kinds: save_all)

    frame.answer_with = answer_with
    yield frame
    if frame:
        frame.Destroy()


def _open_table(frame, title="Table: Summary"):
    from flim.gui.events import EVT_DATA_TYPE, DataWindowEvent

    event = DataWindowEvent(EVT_DATA_TYPE, frame.GetId())
    event.SetEventInfo(pd.DataFrame({"x": [1.0, 2.0]}), title, "createnew")
    frame.GetEventHandler().ProcessEvent(event)
    return frame.windows_by_title()[title]


def _open_plot(frame, title="Plot: Box", modified=True):
    import matplotlib.figure

    figure = matplotlib.figure.Figure(figsize=(2, 1))
    figure.add_subplot().plot([0, 1], [0, 1])
    return frame.open_plot(figure, title, modified=modified)


def test_cancel_keeps_everything_open(app_frame):
    table = _open_table(app_frame)
    assert table.modified
    app_frame.answer_with(saveall.CANCEL)
    assert not app_frame.Close()  # vetoed
    assert app_frame and table
    assert app_frame.asked == [["Table: Summary"]]


def test_discard_all_closes(app_frame):
    _open_table(app_frame)
    app_frame.answer_with(saveall.DISCARD)
    assert app_frame.Close()


def test_no_question_without_unsaved_windows(app_frame):
    table = _open_table(app_frame)
    table.modified = False  # e.g. saved
    _open_plot(app_frame, modified=False)  # e.g. saved by the run
    app_frame.answer_with(saveall.CANCEL)
    assert app_frame.Close()
    assert app_frame.asked == []


def test_unsaved_plots_are_listed_too(app_frame):
    _open_table(app_frame)
    _open_plot(app_frame)
    app_frame.answer_with(saveall.CANCEL)
    app_frame.Close()
    assert app_frame.asked == [["Table: Summary", "Plot: Box"]]


def test_exit_menu_asks_too(app_frame):
    _open_table(app_frame)
    app_frame.answer_with(saveall.CANCEL)
    app_frame.OnExit(None)  # File > Exit (Cmd-Q on macOS)
    assert app_frame and len(app_frame.asked) == 1


def test_review_window_by_window(app_frame, monkeypatch, tmp_path):
    table = _open_table(app_frame)
    plot = _open_plot(app_frame)
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda dlg: wx.ID_OK)
    monkeypatch.setattr(wx.FileDialog, "GetPath", lambda dlg: str(tmp_path / "summary"))
    monkeypatch.setattr(wx.FileDialog, "GetFilterIndex", lambda dlg: 0)
    app_frame.answer_with(saveall.REVIEW, review=["save", "skip"])
    assert app_frame.Close()
    assert (tmp_path / "summary.txt").exists() and not table.modified
    assert plot.modified  # not saved: discarded with the window


def test_review_cancel_keeps_everything_open(app_frame):
    _open_table(app_frame)
    _open_plot(app_frame)
    app_frame.answer_with(saveall.REVIEW, review=["skip", saveall.CANCEL])
    assert not app_frame.Close()


def test_save_all_windows_then_quit(app_frame, tmp_path):
    table = _open_table(app_frame)
    plot = _open_plot(app_frame)
    app_frame.answer_with(saveall.SAVE_ALL, save_all=(tmp_path, []))
    assert app_frame.Close()
    (folder,) = list(tmp_path.iterdir())  # a new subfolder
    assert sorted(p.name for p in folder.iterdir()) == ["Plot_Box.png", "Table_Summary.txt"]
    assert not table.modified and not plot.modified


def test_save_all_cancelled_keeps_everything_open(app_frame):
    _open_table(app_frame)
    app_frame.answer_with(saveall.SAVE_ALL, save_all=None)
    assert not app_frame.Close()


def test_end_of_session_asks_too(app_frame, monkeypatch):
    from flim.gui.app import FLIMAnalyzerApp

    _open_table(app_frame)
    app_frame.answer_with(saveall.CANCEL)

    class Event:
        vetoed = skipped = False

        def CanVeto(self):
            return True

        def Veto(self):
            self.vetoed = True

        def Skip(self):
            self.skipped = True

    class App:  # stands in for the running FLIMAnalyzerApp
        frame = app_frame

    event = Event()
    FLIMAnalyzerApp.OnQueryEndSession(App(), event)
    assert event.vetoed and not event.skipped


# --- the Save All Windows dialog ---


def test_save_all_dialog_needs_a_folder_and_formats(wxapp, tmp_path):
    dialog = saveall.SaveAllDialog(None, None, ["table", "plot"])
    try:
        ok = dialog.FindWindowById(wx.ID_OK)
        assert not ok.IsEnabled() and "Choose the folder" in dialog.message.GetLabel()
        dialog.folder.SetPath(str(tmp_path))
        assert dialog.validate() == [] and ok.IsEnabled()
        dialog.formats.editors["plot_formats"].set([])
        assert "at least one format" in dialog.validate()[0] and not ok.IsEnabled()
        dialog.formats.editors["plot_formats"].set(["svg"])
        dialog.validate()
        folder, formats = dialog.result()
        assert folder == tmp_path and [(f.kind, f.format) for f in formats] == [
            ("table", "tsv"), ("plot", "svg")
        ]
    finally:
        dialog.Destroy()


def test_save_all_opens_at_the_folder_last_used(app_frame, monkeypatch, tmp_path):
    _open_table(app_frame)
    folders = []

    def ask(parent, folder, kinds):
        folders.append((folder, kinds))
        return (tmp_path / "chosen", [])

    monkeypatch.setattr(saveall, "ask_save_all", ask)
    app_frame.save_all_windows()
    app_frame.save_all_windows()
    assert folders[0] == (app_frame.settings.resolved_results_dir(), ["table"])
    assert folders[1][0] == tmp_path / "chosen"  # the folder last used
    assert app_frame.settings.results_dir is None  # the results folder is unchanged
    assert len(list((tmp_path / "chosen").iterdir())) == 2  # two runs, two subfolders
