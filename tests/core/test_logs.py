"""Log files (flim.core.logs): one per session, kept from the start, rotated, removed
after an age."""

import datetime
import logging
import os
import time

import pytest

from flim.core import logs


@pytest.fixture
def clean_logging():
    """The root logger's handlers and level restored afterwards."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def test_file_name():
    start = datetime.datetime(2026, 11, 9, 14, 23, 43)
    assert logs.log_file_name("flimbatch", start, 12345) == (
        "flimbatch_2026-11-09T14-23-43_12345.log"
    )


def test_records_before_the_file_opens_are_kept(tmp_path, clean_logging):
    memory = logs.begin("INFO")
    logging.getLogger("flim.test").info("before")
    logging.getLogger("flim.test").debug("not at this level")
    path, notice = logs.open_log_file("flimanalyzer", tmp_path / "logs", memory)
    logging.getLogger("flim.test").warning("after")
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = path.read_text()
    assert notice is None and path.parent == tmp_path / "logs"
    assert path.name.startswith("flimanalyzer_") and path.name.endswith(f"_{os.getpid()}.log")
    assert "flim.test: before" in text and "flim.test: after" in text
    assert "not at this level" not in text
    assert memory not in logging.getLogger().handlers


def test_a_second_session_gets_its_own_file(tmp_path, clean_logging):
    first, _ = logs.open_log_file(
        "flimbatch", tmp_path, start=datetime.datetime(2026, 1, 1, 9, 0, 0)
    )
    second, _ = logs.open_log_file(
        "flimbatch", tmp_path, start=datetime.datetime(2026, 1, 1, 9, 0, 1)
    )
    assert first != second and first.exists() and second.exists()


def test_unwritable_folder_falls_back_to_the_temporary_folder(tmp_path, clean_logging):
    blocked = tmp_path / "file"
    blocked.write_text("not a folder")
    path, notice = logs.open_log_file("flimanalyzer", blocked / "logs")
    assert path.parent.name == logs.APP_NAME and path.exists()
    assert "cannot be used" in notice and str(path.parent) in notice
    path.unlink()


def test_rotation_limits(tmp_path, clean_logging):
    path, _ = logs.open_log_file("flimanalyzer", tmp_path)
    (handler,) = [
        h for h in logging.getLogger().handlers if getattr(h, "baseFilename", "") == str(path)
    ]
    assert handler.maxBytes == 10 * 1024 * 1024 and handler.backupCount == 3


def test_old_logs_are_removed(tmp_path):
    old = tmp_path / "flimanalyzer_2026-01-01T09-00-00_1.log"
    old_part = tmp_path / "flimanalyzer_2026-01-01T09-00-00_1.log.1"
    new = tmp_path / "flimbatch_2026-11-09T09-00-00_2.log"
    other = tmp_path / "notes.log"  # not FLIMAnalyzer's: never removed
    for path in (old, old_part, new, other):
        path.write_text("x")
    month_ago = time.time() - 31 * 86400
    for path in (old, old_part, other):
        os.utime(path, (month_ago, month_ago))
    assert logs.session_logs(tmp_path) == [old, old_part, new]
    assert sorted(logs.remove_old_logs(tmp_path)) == [old, old_part]
    assert new.exists() and other.exists()
    assert logs.session_logs(tmp_path / "missing") == []


def test_the_chosen_level_survives_prefects_logging_setup(tmp_path):
    """Prefect sets the root logger to WARNING when it loads (after the GUI started its
    log); FLIMAnalyzer's own records keep the chosen level. A fresh process: in pytest,
    Prefect is loaded before the log starts."""
    import subprocess
    import sys

    script = f"""
import logging
from pathlib import Path
from flim.core import logs
memory = logs.begin("DEBUG")
from prefect import flow  # noqa: F401  (configures Prefect's logging)
path, _ = logs.open_log_file("probe", Path({str(tmp_path)!r}), memory)
logging.getLogger("flim.gui.app").debug("a debug record")
for handler in logging.getLogger().handlers:
    handler.flush()
print("debug record written:", "a debug record" in path.read_text())
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert "debug record written: True" in result.stdout, result.stderr[-2000:]
