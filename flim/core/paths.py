"""Folders for results: one canonical form, and a check before a run.

A folder chosen by the user is stored as an absolute path with links resolved
(`canonical_folder`). On Windows a mapped network drive (`Z:\\results`) becomes
its UNC path (`\\\\server\\share\\results`): that also works for programs that do not
see the user's drive mappings (e.g. started as administrator), and on computers that
map the share to another letter.
"""

import os
from pathlib import Path
from typing import Optional


def canonical_folder(
    path: Optional[str | os.PathLike],
) -> Optional[str | os.PathLike]:
    """Return `path` as an absolute path with `~` expanded and links resolved.

    On Windows a mapped network drive becomes its UNC path.

    Args:
        path: The folder.

    Returns:
        The canonical path as a string; the absolute but unresolved path if it
        cannot be resolved (e.g. the drive is not available). An empty value (None,
        "") is returned as it is.
    """
    if not path:
        return path
    path = os.path.abspath(os.path.expanduser(str(path)))
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return path


def folder_problem(path: str | os.PathLike) -> Optional[str]:
    """Return why results cannot be saved in `path`, or None if they can.

    A folder that does not exist yet is accepted if it can be created: its nearest
    existing parent is a writable folder.

    Args:
        path: The folder; `~` is expanded and a relative path is taken as relative
            to the current folder.

    Returns:
        A message for the user (the folder cannot be reached, is not a folder, or
        cannot be written to), or None.
    """
    path = os.path.abspath(os.path.expanduser(str(path)))
    existing = path
    while not os.path.exists(existing):
        parent = os.path.dirname(existing)
        if parent == existing:  # not even the drive or share is there
            return f"{path} can't be reached (is the drive or network share available?)"
        existing = parent
    if not os.path.isdir(existing):
        return f"{existing} is not a folder"
    if not os.access(existing, os.W_OK):
        return f"{existing} can't be written to"
    return None


def shorten_path(path: str, max_length: int = 50) -> str:
    """Return `path` shortened to about `max_length` characters, for display.

    The result is the start (e.g. `/Users/mst3k`, `C:\\Users\\mst3k`,
    `\\\\server\\share`), `...` and as many of the last folders as fit, e.g.
    `/Users/mst3k/.../folder/subfolder`. The last folder is always kept, so the
    result can be longer than `max_length`.

    Args:
        path: The path.
        max_length: The length above which the path is shortened. Defaults to 50.

    Returns:
        The path, shortened, or unchanged if it is not longer than `max_length` or
        has too few parts to shorten.
    """
    path = str(path)
    if len(path) <= max_length:
        return path
    sep = "\\" if "\\" in path else "/"
    parts = path.split(sep)
    leading = len(path) - len(path.lstrip(sep))  # "/" or "\\" (network path)
    drive = 1 if parts[0].endswith(":") else 0  # C:
    head = parts[: leading + drive + 2]
    rest = parts[leading + drive + 2 :]
    if len(rest) < 2:
        return path
    tail = [rest[-1]]
    for part in reversed(rest[1:-1]):
        if len(sep.join(head + ["..."] + [part] + tail)) > max_length:
            break
        tail.insert(0, part)
    return sep.join(head + ["..."] + tail)


def unique_run_folder(parent: str | os.PathLike, name: str) -> Path:
    """Create a run's results folder that no other run uses.

    The folder is created exclusively, so two runs started in the same second (e.g.
    parallel flimbatch jobs with the same output folder) get different folders:
    `name`, else `name-2`, `name-3`, ...

    Args:
        parent: The folder to create it in; created if it does not exist.
        name: The folder's name, e.g. the run's start time.

    Returns:
        The created folder.

    Raises:
        OSError: If the folder cannot be created.
    """
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        folder = parent / (name if number == 1 else f"{name}-{number}")
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            number += 1


def path_uri(directory: str, name: str) -> str:
    """Return the `file://` URI of a file given by its folder and name.

    The folder can be a path as recorded on any system: a Windows path (with a drive
    letter or a server share) or a POSIX path.

    Args:
        directory: The folder, absolute (else the result is a relative reference).
        name: The file name.

    Returns:
        The URI, with special characters percent-encoded (a space as `%20`), e.g.
        `file:///D:/KCCI/Results-a.txt`. For a relative folder, the percent-encoded
        relative reference without `file://`.
    """
    import re
    from pathlib import PurePosixPath, PureWindowsPath
    from urllib.parse import quote

    folder = directory.replace("\\", "/").rstrip("/")
    text = f"{folder}/{name}" if folder else name
    if re.match(r"^[A-Za-z]:/", text) or text.startswith("//"):
        return PureWindowsPath(text).as_uri()
    if text.startswith("/"):
        return PurePosixPath(text).as_uri()
    return quote(text)
