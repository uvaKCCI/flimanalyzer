"""Folders for results: one canonical form, a validation before a run, and file names.

Every file and folder name FLIMAnalyzer makes (results, step and input folders) is
made with one rule, `path_name`: the character replacements of the task's `output`
section (`char_replacements`, added to the defaults), then only
ASCII letters, digits, `-`, `_` and `.`. Paths the user gives are not changed.

A folder chosen by the user is stored as an absolute path with links resolved
(`canonical_folder`). A tool's folder is stored relative to the default results
folder (`stored_folder`): no folder if it is the default folder, a relative path if
it is inside it, so that it moves with the default folder; `resolved_folder` turns it
back into a path. On Windows a mapped network drive (`Z:\\results`) becomes
its UNC path (`\\\\server\\share\\results`): that also works for programs that do not
see the user's drive mappings (e.g. started as administrator), and on computers that
map the share to another letter.
"""

import os
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Any, Optional

from pydantic import BeforeValidator

# the default character replacements of file and folder names (`output` >
# `char_replacements` of a tool or a workflow adds to them or overrides single ones)
DEFAULT_CHAR_REPLACEMENTS = {"%": "pcent", "τ": "tau", "µ": "u", "μ": "u"}
# the characters a name keeps; any other becomes `_`
NAME_CHARS = "A-Za-z0-9._-"
_OTHER = re.compile(f"[^{NAME_CHARS}]")
_REPEATED = re.compile(r"_{2,}")


def with_default_replacements(value: Any) -> Any:
    """Return character replacements added to the defaults; refuse invalid ones.

    The validator of `CharReplacements`: a replacement may hold only the characters
    a name keeps, so that it can't make a folder (`/`) or another invalid name.

    Args:
        value: Text -> replacement; other values are returned as they are, for the
            type check.

    Returns:
        The defaults updated with `value`.

    Raises:
        ValueError: If a text is empty or a replacement has other characters.
    """
    if not isinstance(value, Mapping):
        return value
    for old, new in value.items():
        if not old:
            raise ValueError("char_replacements: an empty text can't be replaced")
        if not isinstance(new, str) or re.search(f"[^{NAME_CHARS}]", new):
            raise ValueError(
                f"char_replacements: {old!r} -> {new!r}: a replacement may contain"
                " only ASCII letters, digits, -, _ and ."
            )
    return {**DEFAULT_CHAR_REPLACEMENTS, **value}


# the `char_replacements` of an `output` section: text -> replacement, in order,
# added to the defaults
CharReplacements = Annotated[dict[str, str], BeforeValidator(with_default_replacements)]


def without_unset_replacements(data: Any) -> Any:
    """Drop `char_replacements` from a serialized `output` section if it is not set.

    Files written before the setting existed stay as they were, and a file states it
    only where it was set.

    Args:
        data: The serialized section.

    Returns:
        The section, without `char_replacements` if its value is None.
    """
    if isinstance(data, dict) and data.get("char_replacements", ...) is None:
        data = {k: v for k, v in data.items() if k != "char_replacements"}
    return data


def path_name(name: object, replacements: Optional[Mapping[str, str]] = None) -> str:
    """Return a name as FLIMAnalyzer writes it into a file or folder name.

    1. The replacements, in order (e.g. `%` -> `pcent`).
    2. Letters with accents lose them (`é` -> `e`).
    3. Every character other than ASCII letters, digits, `-`, `_` and `.` becomes
       `_`; repeated `_` become one; `_`, `.` and spaces at both ends are removed.

    Args:
        name: The name, e.g. a result or a tool's name; other values are converted
            with `str`.
        replacements: The replacements, e.g. an `output` section's
            `char_replacements`; None for the defaults (`DEFAULT_CHAR_REPLACEMENTS`).

    Returns:
        The name, or `_` if nothing is left. For example
        `Summary_NAD_P_H_a2_pcent` for `Summary: NAD(P)H a2[%]`.
    """
    text = str(name)
    for old, new in (DEFAULT_CHAR_REPLACEMENTS if replacements is None else replacements).items():
        text = text.replace(old, new)
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    text = _REPEATED.sub("_", _OTHER.sub("_", text)).strip("_. ")
    return text or "_"


def same_names(
    names: Iterable[object], replacements: Optional[Mapping[str, str]] = None
) -> list[tuple[str, str]]:
    """Return the pairs of names that `path_name` makes equal, ignoring case.

    Case is ignored as macOS and Windows do.

    Args:
        names: The names, e.g. a task's results or the inputs of a run.
        replacements: As for `path_name`; None for the defaults.

    Returns:
        (first, second) for each name that becomes the file name of an earlier one.
    """
    seen: dict[str, str] = {}
    pairs = []
    for name in names:
        key = path_name(name, replacements).lower()
        if key in seen:
            pairs.append((seen[key], str(name)))
        else:
            seen[key] = str(name)
    return pairs


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



def _key(path: str) -> str:
    """Return a path in the form used to compare folders.

    On Windows and macOS file names are case-insensitive by default, so the path is
    compared case-folded there.
    """
    path = os.path.normcase(path)
    return path.casefold() if sys.platform == "darwin" else path


def stored_folder(
    folder: Optional[str | os.PathLike], default: str | os.PathLike
) -> Optional[Path]:
    """Return a tool's results folder in the form it is stored in its settings.

    Args:
        folder: The folder chosen, e.g. with `Browse`; empty or None for none.
        default: The default results folder.

    Returns:
        None if `folder` is empty or is the default folder; the path relative to the
        default folder if `folder` is inside it (e.g. `kmeans/run1`); otherwise the
        canonical absolute path (`canonical_folder`).
    """
    if not folder:
        return None
    path, base = Path(canonical_folder(folder)), Path(canonical_folder(default))
    parts, base_parts = path.parts, base.parts
    same = [_key(a) for a in parts[: len(base_parts)]] == [_key(b) for b in base_parts]
    if not same:
        return path
    inner = parts[len(base_parts):]
    return Path(*inner) if inner else None


def resolved_folder(
    folder: Optional[str | os.PathLike], default: str | os.PathLike
) -> Path:
    """Return the folder a tool saves in, from its stored folder (`stored_folder`).

    Args:
        folder: The stored folder: None, a path relative to the default folder, or
            an absolute path (`~` is expanded).
        default: The default results folder.

    Returns:
        `default` for None; `default / folder` for a relative path; otherwise the
        path itself.
    """
    if not folder:
        return Path(default)
    path = Path(folder).expanduser()
    return path if path.is_absolute() else Path(default) / path

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


def with_extension(path: str | os.PathLike, extension: str) -> str:
    """Return a path with a file extension, added if the path doesn't have it.

    The comparison ignores case, so `data.JSON` is kept.

    Args:
        path: The path, for example from a save dialog.
        extension: The extension with its dot, for example `.json`.

    Returns:
        The path as a string.
    """
    path = os.fspath(path)
    return path if path.lower().endswith(extension.lower()) else path + extension
