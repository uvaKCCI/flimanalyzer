"""Log files: one per session, never overwritten, with a size limit and an age limit.

A session's log file is named after the program, its start time and its process ID,
e.g. `flimbatch_2026-11-09T14-23-43_12345.log` (`-` instead of `:`, which Windows
does not allow in file names). Records logged before the file is known (e.g. while
the settings are read) are kept in memory and written to it when it is opened.
"""

import datetime
import logging
import logging.handlers
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

APP_NAME = "FLIMAnalyzer"
MAX_BYTES = 10 * 1024 * 1024  # size of a log file before it is rotated
BACKUP_COUNT = 3  # older parts of a session's log kept: <name>.log.1, ... .3
MAX_AGE_DAYS = 30  # GUI logs older than this are removed at startup
FORMAT = "%(levelname)s \t %(asctime)-15s - %(name)s: %(message)s"
# the terminal: the format of Prefect's console handler, which the GUI's terminal shows
CONSOLE_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(name)s - %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S"
_NAME = re.compile(r"^(flimanalyzer|flimbatch)_\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d_\d+\.log(\.\d+)?$")


def default_log_dir() -> Path:
    """Return the platform's log folder of FLIMAnalyzer.

    Returns:
        E.g. `~/Library/Logs/FLIMAnalyzer` on macOS (platformdirs `user_log_dir`).
    """
    from platformdirs import user_log_dir

    return Path(user_log_dir(APP_NAME, appauthor=False))


def log_file_name(program: str, start: datetime.datetime, pid: int) -> str:
    """Return the name of a session's log file.

    Args:
        program: `flimanalyzer` or `flimbatch`.
        start: The session's start time.
        pid: The process ID.

    Returns:
        E.g. `flimbatch_2026-11-09T14-23-43_12345.log`.
    """
    return f"{program}_{start:%Y-%m-%dT%H-%M-%S}_{pid}.log"


def begin(level: str) -> logging.handlers.MemoryHandler:
    """Configure the root logger and keep records in memory until the log file opens.

    The root logger's existing handlers are removed and closed. The level is set on
    the root logger and on the `flim` logger.

    Args:
        level: The log level, e.g. `INFO`.

    Returns:
        The handler that keeps the records; `open_log_file` writes them to the file.
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)
    # also on FLIMAnalyzer's own logger: Prefect sets the root logger's level when it
    # configures its logging (WARNING by default), which would drop these records
    logging.getLogger("flim").setLevel(level)
    memory = logging.handlers.MemoryHandler(capacity=100_000, flushLevel=logging.CRITICAL + 1)
    root.addHandler(memory)
    return memory


def open_log_file(
    program: str,
    folder: str | os.PathLike,
    memory: Optional[logging.handlers.MemoryHandler] = None,
    *,
    start: Optional[datetime.datetime] = None,
    name: Optional[str] = None,
) -> tuple[Path, Optional[str]]:
    """Open the session's log file and write the records kept in memory to it.

    If the folder cannot be created or written to, the log file is opened in the
    system's temporary folder instead.

    Args:
        program: `flimanalyzer` or `flimbatch`.
        folder: The log folder.
        memory: The handler returned by `begin`; it is removed after its records are
            written.
        start: The session's start time. Defaults to now.
        name: The file's name; None for one with the program, the start time and
            the process ID (`log_file_name`), e.g. in a shared log folder.

    Returns:
        The log file, and a message for the user if the temporary folder is used
        (else None).

    Raises:
        OSError: If the log file cannot be opened in the temporary folder either.
    """
    name = name or log_file_name(program, start or datetime.datetime.now(), os.getpid())
    notice = None
    try:
        handler = _file_handler(Path(folder), name)
    except OSError as err:
        fallback = Path(tempfile.gettempdir()) / APP_NAME
        handler = _file_handler(fallback, name)
        notice = (
            f"The log folder {folder} cannot be used ({err}); the log is written to"
            f" {fallback} instead."
        )
    root = logging.getLogger()
    root.addHandler(handler)
    if memory is not None:
        memory.setTarget(handler)
        memory.flush()
        root.removeHandler(memory)
        memory.close()
    if notice:
        logger.warning(notice)
    return Path(handler.baseFilename), notice


def _file_handler(folder: Path, name: str) -> logging.handlers.RotatingFileHandler:
    """Create the folder if needed and return a rotating handler of a file in it."""
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        folder / name, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(FORMAT))
    return handler


def remove_old_logs(
    folder: str | os.PathLike, max_age_days: int = MAX_AGE_DAYS
) -> list[Path]:
    """Remove FLIMAnalyzer's log files older than an age from a folder.

    Only files named like a session's log file (and their rotated parts) are removed.
    Files that cannot be removed are logged as warnings and skipped.

    Args:
        folder: The log folder.
        max_age_days: The age in days, by the time the file was last written.
            Defaults to 30.

    Returns:
        The removed files.
    """
    cutoff = time.time() - max_age_days * 86400
    removed = []
    for path in session_logs(folder):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path)
        except OSError as err:
            logger.warning(f"Could not remove the old log file {path}: {err}")
    return removed


def session_logs(folder: str | os.PathLike) -> list[Path]:
    """Return FLIMAnalyzer's log files in a folder, sorted by name.

    Args:
        folder: The log folder.

    Returns:
        The files named like a session's log file, and their rotated parts, sorted by
        name: by program, then by start time (oldest first). An empty list if the
        folder does not exist.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and _NAME.match(p.name))


def console_handler(level: str) -> logging.Handler:
    """Return a handler that writes records to standard error, as the GUI's terminal.

    The format is that of Prefect's console handler (`CONSOLE_FORMAT`), e.g.
    `08:29:03.614 | INFO    | flim.batch - Read 8 file(s)`.

    Args:
        level: The log level, e.g. `INFO`.

    Returns:
        The handler.
    """
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, CONSOLE_DATE_FORMAT))
    return handler
