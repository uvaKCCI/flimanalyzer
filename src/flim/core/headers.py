"""Column headers with levels, one level per line.

The header with the lines `FLIRR`, `mean` and `Dox15` is the feature FLIRR, the
statistic mean and the Treatment Dox15.

Tools that make such headers (Pivot, Summarize) record the names of the levels in the
table's `attrs` (`HEADER_LEVELS`), e.g. `["Feature", "Statistic", "Treatment"]`.
The names are lost when a table is saved as text and read back; levels are then named
by their position ("Level 2").
"""

from collections.abc import Iterable
from typing import Any, Optional

import pandas as pd

HEADER_LEVELS = "header_levels"  # key in DataFrame.attrs
FEATURE_LEVEL = "Feature"  # the name of the first level


def split(name: Any) -> list[str]:
    """Return the lines (levels) of a column header."""
    return str(name).split("\n")


def join(parts: Iterable[str]) -> str:
    """Return a column header of the lines (levels), joined by line breaks."""
    return "\n".join(parts)


def level_names(data: pd.DataFrame) -> list[str]:
    """Return the names a tool recorded for the levels of the table's headers.

    Args:
        data: The table.

    Returns:
        The names; empty if none are recorded.
    """
    return list(data.attrs.get(HEADER_LEVELS) or [])


def set_level_names(data: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """Record the names of the levels of a table's headers in its `attrs`.

    With fewer than two names the headers have no levels, and a recorded list is
    removed.

    Args:
        data: The table, changed in place.
        names: The names of the levels, from the first line.

    Returns:
        The same table.
    """
    if len(names) > 1:
        data.attrs[HEADER_LEVELS] = list(names)
    else:
        data.attrs.pop(HEADER_LEVELS, None)  # one line: no levels
    return data


def default_name(index: int) -> str:
    """Return the name of a level by position: `Feature`, `Level 2`, `Level 3`, ..."""
    return FEATURE_LEVEL if index == 0 else f"Level {index + 1}"


def names_for(depth: int, recorded: list[str]) -> list[str]:
    """Return the names of `depth` levels.

    Args:
        depth: The number of levels.
        recorded: The names a tool recorded (see `level_names`).

    Returns:
        The recorded names if there are `depth` of them, else the names by position
        (`Feature`, `Level 2`, ...).
    """
    if len(recorded) == depth:
        return list(recorded)
    return [default_name(i) for i in range(depth)]


def depth(columns: Iterable[Any]) -> int:
    """Return the largest number of levels of the column headers; 0 for no columns."""
    return max((len(split(c)) for c in columns), default=0)


def level_index(level: Optional[str], names: list[str]) -> int:
    """Return the index of `level` in `names`.

    Args:
        level: A name in `names`, a position from 1 (`Level 2` or `2`, also accepted
            where the levels have names), or None or empty for the last level.
        names: The names of the levels.

    Returns:
        The index, from 0.

    Raises:
        ValueError: If `level` matches no level.
    """
    if not level:
        return len(names) - 1
    if level in names:
        return names.index(level)
    number = level.removeprefix("Level").strip()
    if number.isdigit() and 1 <= int(number) <= len(names):
        return int(number) - 1
    raise ValueError(f"No header level '{level}'; the levels are {', '.join(names)}")


def level_values(columns: Iterable[Any], index: int) -> list[str]:
    """Return the values of level `index` in the column headers.

    Headers with fewer levels are left out.

    Args:
        columns: The column headers.
        index: The level's index, from 0.

    Returns:
        The distinct values, in order of first occurrence.
    """
    values = [split(c)[index] for c in columns if len(split(c)) > index]
    return list(dict.fromkeys(values))
