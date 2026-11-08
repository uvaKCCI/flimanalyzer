"""The choice the GUI offers when some settings of a settings file cannot be used
(flim.gui.settingscheck), in File > Load Settings... and in tool dialogs."""

import json
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

import flim.tools  # noqa: E402, F401  (registers the tools: tool settings are checked)
from flim.core.settings import check_settings_file  # noqa: E402
from flim.gui import settingscheck  # noqa: E402

MIXED = {
    "schema_version": 1,
    "working_dir": "res",
    "bogus_section": 3,
    "execution": {"executor": "ray"},
    "tools": {"Summarize": {"config": {"aggs": ["count"], "nope": 1}}},
}
CLEAN = {"schema_version": 2, "results_dir": "other"}


@pytest.fixture
def table():
    import pandas as pd

    return pd.DataFrame({"Treatment": pd.Categorical(["Ctrl", "Drug"]), "x": [1.0, 2.0]})


def write(tmp_path, content, name="settings.json"):
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


@pytest.fixture
def answers(monkeypatch, wxapp):
    """Answers the dialogs in order: an option of the choice (or None for Cancel),
    True/False for the confirmation, a path (or None) for the file dialog. Records the
    choices offered."""
    queue, offered = [], []

    class Choice:
        def __init__(self, parent, message, caption, choices):
            offered.append((message, list(choices)))
            self.choices = list(choices)
            self.answer = queue.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ShowModal(self):
            return wx.ID_CANCEL if self.answer is None else wx.ID_OK

        def GetSelection(self):
            return self.choices.index(self.answer)

    monkeypatch.setattr(settingscheck.wx, "SingleChoiceDialog", Choice)
    monkeypatch.setattr(settingscheck, "_confirm_update", lambda check, parent: queue.pop(0))
    monkeypatch.setattr(settingscheck, "_other_file", lambda parent: queue.pop(0))
    return queue, offered


def test_use_what_can_be_used(tmp_path, answers):
    queue, offered = answers
    queue.append(settingscheck.USE)
    check = check_settings_file(write(tmp_path, MIXED))
    assert settingscheck.choose_settings(check) is check
    message, options = offered[0]
    assert "bogus_section" in message and "working_dir to results_dir" in message
    assert options == [settingscheck.USE, settingscheck.IGNORE, settingscheck.UPDATE,
                       settingscheck.OTHER]


@pytest.mark.parametrize("answer", [settingscheck.IGNORE, None])  # None: Cancel
def test_dont_use_the_file(tmp_path, answers, answer):
    queue, _ = answers
    queue.append(answer)
    assert settingscheck.choose_settings(check_settings_file(write(tmp_path, MIXED))) is None


def test_update_the_file_after_confirmation(tmp_path, answers):
    queue, offered = answers
    path = write(tmp_path, MIXED)
    queue += [settingscheck.UPDATE, False, settingscheck.UPDATE, True]
    check = settingscheck.choose_settings(check_settings_file(path))
    assert len(offered) == 2  # not confirmed: asked again
    data = json.loads(path.read_text())
    assert data == {"schema_version": 2, "results_dir": "res", "tools": {}}
    assert check.path == path and not check.problems and check.converted == []


def test_another_file_is_checked_the_same_way(tmp_path, answers):
    queue, offered = answers
    broken = write(tmp_path, "{not json", "broken.json")
    clean = write(tmp_path, CLEAN, "clean.json")
    queue += [settingscheck.OTHER, str(broken), settingscheck.OTHER, None,
              settingscheck.OTHER, str(clean)]
    check = settingscheck.choose_settings(check_settings_file(write(tmp_path, MIXED)))
    assert check.path == clean
    # the broken file offers no settings to use or keep
    assert offered[1][1] == [settingscheck.IGNORE, settingscheck.OTHER]
    assert len(offered) == 3  # file dialog cancelled: asked again


# --- where the GUI reads settings files ---


@pytest.fixture
def frame(wxapp, monkeypatch, tmp_path):
    from flim.core.settingsmgr import SettingsManager, UserSettingsFile
    from flim.core.tools import FLIMAnalyzer
    from flim.gui.app import AppFrame

    monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda dlg: wx.ID_NO)
    frame = AppFrame(
        FLIMAnalyzer(), SettingsManager(user_file=UserSettingsFile(tmp_path / "user.json"))
    )
    yield frame
    frame.Destroy()


def test_load_settings_asks_for_a_file_with_problems(frame, tmp_path, answers):
    queue, offered = answers
    queue.append(settingscheck.USE)
    path = write(tmp_path, MIXED)
    frame.load_settings(path)
    assert len(offered) == 1
    assert frame.settings.results_dir == Path("res")
    assert frame.settings_manager.source == path


def test_load_settings_without_problems_does_not_ask(frame, tmp_path, answers):
    _, offered = answers
    frame.load_settings(write(tmp_path, CLEAN))
    assert offered == [] and frame.settings.results_dir == Path("other")


def test_load_settings_not_used(frame, tmp_path, answers):
    queue, _ = answers
    queue.append(settingscheck.IGNORE)
    frame.load_settings(write(tmp_path, MIXED))
    assert frame.settings.results_dir is None and frame.settings_manager.source is None


def test_tool_dialog_asks_only_for_its_own_problems(dialog, tmp_path, answers):
    queue, offered = answers
    path = write(tmp_path, MIXED)
    # K-Means has no settings in the file: the problems of other sections don't matter
    assert not dialog("K-Means").load_settings(str(path))
    assert offered == []
    queue.append(settingscheck.IGNORE)
    d = dialog("Summarize")
    assert not d.load_settings(str(path))
    assert len(offered) == 1


def test_tool_dialog_uses_another_file(dialog, tmp_path, answers):
    from flim.core.settings import save_sections

    queue, _ = answers
    other = tmp_path / "other.json"
    save_sections(
        {"tools": {"Summarize": {"config": {"aggs": ["count"]}, "autosave": False}}}, other
    )
    queue += [settingscheck.OTHER, str(other)]
    d = dialog("Summarize")
    assert d.load_settings(str(write(tmp_path, MIXED)))
    assert d.result().config.aggs == ["count"]
    assert "other.json" in d.settings_message.GetLabel()
