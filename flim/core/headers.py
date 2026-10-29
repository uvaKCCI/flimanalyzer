"""Column headers with levels: ``"FLIRR\\nmean\\nDox15"`` is the feature FLIRR, the
statistic mean and the Treatment Dox15, one level per line.

Tools that make such headers (Pivot, Summarize) record the names of the levels in the
table's ``attrs`` (``HEADER_LEVELS``), e.g. ``["Feature", "Statistic", "Treatment"]``.
The names are lost when a table is saved as text and read back; levels are then named
by their position ("Level 2").
"""

from typing import Optional

import pandas as pd

HEADER_LEVELS = "header_levels"  # key in DataFrame.attrs
FEATURE_LEVEL = "Feature"  # the name of the first level


def split(name) -> list[str]:
    return str(name).split("\n")


def join(parts) -> str:
    return "\n".join(parts)


def level_names(data: pd.DataFrame) -> list[str]:
    """The names a tool recorded for the levels of the table's headers."""
    return list(data.attrs.get(HEADER_LEVELS) or [])


def set_level_names(data: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    if len(names) > 1:
        data.attrs[HEADER_LEVELS] = list(names)
    else:
        data.attrs.pop(HEADER_LEVELS, None)  # one line: no levels
    return data


def default_name(index: int) -> str:
    return FEATURE_LEVEL if index == 0 else f"Level {index + 1}"


def names_for(depth: int, recorded: list[str]) -> list[str]:
    """The names of ``depth`` levels: the recorded ones if they match, else by
    position ("Feature", "Level 2", ...)."""
    if len(recorded) == depth:
        return list(recorded)
    return [default_name(i) for i in range(depth)]


def depth(columns) -> int:
    """The number of levels of the columns (0: none given)."""
    return max((len(split(c)) for c in columns), default=0)


def level_index(level: Optional[str], names: list[str]) -> int:
    """The position of ``level`` in ``names``: its name, its position ("Level 2" or
    "2", also where the levels have names), or empty for the last level."""
    if not level:
        return len(names) - 1
    if level in names:
        return names.index(level)
    number = level.removeprefix("Level").strip()
    if number.isdigit() and 1 <= int(number) <= len(names):
        return int(number) - 1
    raise ValueError(f"No header level '{level}'; the levels are {', '.join(names)}")


def level_values(columns, index: int) -> list[str]:
    """The values of level ``index`` in the headers of ``columns``, in order."""
    values = [split(c)[index] for c in columns if len(split(c)) > index]
    return list(dict.fromkeys(values))
