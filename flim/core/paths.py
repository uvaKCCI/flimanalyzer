"""Folders for results: one canonical form, and a check before a run.

A folder chosen by the user is stored as an absolute path with links resolved
(:func:`canonical_folder`). On Windows a mapped network drive (``Z:\\results``) becomes
its UNC path (``\\\\server\\share\\results``): that also works for programs that don't
see the user's drive mappings (e.g. started as administrator), and on computers that
map the share to another letter.
"""

import os
from typing import Optional


def canonical_folder(path):
    """``path`` as an absolute path with ``~`` expanded and links resolved; on Windows
    a mapped network drive becomes its UNC path. Kept absolute but unresolved when it
    can't be resolved (e.g. the drive is not available); empty values are returned
    as they are."""
    if not path:
        return path
    path = os.path.abspath(os.path.expanduser(str(path)))
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):
        return path


def folder_problem(path) -> Optional[str]:
    """Why results can't be saved in ``path``, or None. A folder that doesn't exist yet
    is fine if it can be created (its nearest existing parent is a writable folder)."""
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
    """``path`` shortened to about ``max_length`` characters for display: the start
    (e.g. ``/Users/mst3k``, ``C:\\Users\\mst3k``, ``\\\\server\\share``), ``...`` and as
    many of the last folders as fit, e.g. ``/Users/mst3k/.../folder/subfolder``. The
    last folder is always kept."""
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
