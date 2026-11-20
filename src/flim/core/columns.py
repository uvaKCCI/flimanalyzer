"""Column names: renaming and dropping columns by parts of their names, and new names.

The Rename Columns and Drop Columns tools rename and drop columns
(`renamed_columns`, `columns_to_drop`). The reader and the tools that add columns
choose names that do not clash with the table's (`unique_name`, `make_room`,
`free_names`); `validate_template` checks rename templates.
"""

import re
from typing import Any, Collection, Container, Iterable, Mapping, Optional, Sequence

MATCHES = ("contains", "starts with", "ends with", "is")


def renamed_columns(
    names: Iterable[str], replacements: Iterable[tuple[str, str]]
) -> list[str]:
    """Return column names with parts replaced, in order.

    Each replacement applies to the names the earlier ones produced. An empty part is
    skipped: it would insert the new text between all characters.

    Args:
        names: The column names.
        replacements: (part, new text) pairs, in order.

    Returns:
        The new names, in the same order.
    """
    names = [str(n) for n in names]
    for part, new in replacements:
        if not part:
            continue
        names = [n.replace(part, new) for n in names]
    return names


def matches(name: str, text: str, match: str) -> bool:
    """Return whether a column name matches a drop rule's text.

    Args:
        name: The column name.
        text: The rule's text.
        match: How the text is compared: one of `MATCHES` (`contains`,
            `starts with`, `ends with`, `is`).

    Returns:
        Whether the name matches.

    Raises:
        ValueError: If `match` is not one of `MATCHES`.
    """
    if match == "contains":
        return text in name
    if match == "starts with":
        return name.startswith(text)
    if match == "ends with":
        return name.endswith(text)
    if match == "is":
        return name == text
    raise ValueError(f"unknown match {match!r}: use {', '.join(MATCHES)}")


# the name pandas gives a column whose header is empty in the file, e.g. `Unnamed: 0`
_UNNAMED = re.compile(r"Unnamed: \d+")


def is_empty_header(name: str) -> bool:
    """Return whether a column name stands for an empty header in the file."""
    return name.strip() == "" or _UNNAMED.fullmatch(name) is not None


def columns_to_drop(
    names: Iterable[str],
    rules: Optional[Iterable[str | Sequence[str]]],
    drop_empty: bool = True,
) -> list[str]:
    """Return the columns that drop rules select.

    Args:
        names: The column names.
        rules: (text, match) pairs, `match` as in `matches`; a plain text means
            `contains`, as in Import's drop list. Rules with an empty text select
            nothing. None for no rules.
        drop_empty: Whether to also select a column with an empty header: a name of
            only white space, "", or `Unnamed: <n>`, the name pandas gives a column
            whose header is empty in the file. Defaults to True.

    Returns:
        The selected names, in table order.

    Raises:
        ValueError: If a rule's match is unknown (see `matches`).
    """
    rules = [(r, "contains") if isinstance(r, str) else tuple(r) for r in rules or []]
    selected = []
    for name in (str(n) for n in names):
        if (drop_empty and is_empty_header(name)) or any(
            text and matches(name, text, match) for text, match in rules
        ):
            selected.append(name)
    return selected


# columns FLIMAnalyzer writes with a fixed meaning: Source (each row's origin, a
# URI), Input (Concatenate: the table a row came from), Directory and File (the
# reader, with Source; deprecated, removed in 0.8.0)
PROTECTED = ("Source", "Input", "Directory", "File")
CLASH_TEMPLATE = "{name} (before {tool})"  # an existing column of a protected name
TEMPLATE_FIELDS = ("name", "tool", "table")


def unique_name(name: str, default: str, existing: Container[str]) -> str:
    """Return `name` (or `default` if empty), numbered if it is already taken.

    Args:
        name: The wanted name.
        default: The name if `name` is empty.
        existing: The names taken.

    Returns:
        The name, or the name with `_1`, `_2`, ... appended.
    """
    name = name or default
    base, i = name, 1
    while name in existing:
        name = f"{base}_{i}"
        i += 1
    return name


def validate_template(template: str) -> str:
    """Return a rename template if it uses only `{name}`, `{tool}` and `{table}`.

    Args:
        template: The template, a Python format string.

    Returns:
        The template, unchanged.

    Raises:
        ValueError: If the template has another field or no `{name}`, or is not a
            valid format string.
    """
    import string

    try:
        fields = [f for _, f, _, _ in string.Formatter().parse(template) if f is not None]
    except ValueError as err:
        raise ValueError(f"'{template}' is not a valid template ({err})") from None
    unknown = [f for f in fields if f not in TEMPLATE_FIELDS]
    if unknown:
        known = ", ".join(f"{{{f}}}" for f in TEMPLATE_FIELDS)
        raise ValueError(f"'{template}': {{{unknown[0]}}} is not one of {known}")
    if "name" not in fields:
        raise ValueError(f"'{template}' needs {{name}}, the column's name")
    return template


def make_room(
    columns: Iterable[Any],
    names: Collection[str],
    template: str,
    renames: Optional[Mapping[str, str]] = None,
    **fields: Any,
) -> dict[str, str]:
    """Return how to rename existing columns that have names a tool will write.

    Args:
        columns: The table's column names.
        names: The names the tool writes (e.g. `["Source"]`).
        template: The new name of such a column, e.g. `{name} (before {tool})`.
        renames: Per column, a new name that overrides the template; an empty name
            means the template.
        **fields: The template's other fields, e.g. `tool="Import"`; fields not
            given are empty.

    Returns:
        Old name -> new name, for the columns in the way; a new name that is taken
        (or written by the tool) gets a number.
    """
    columns = [str(c) for c in columns]
    renames = dict(renames or {})
    taken = set(columns) | set(names)
    result = {}
    for name in names:
        if name not in columns:
            continue
        new = renames.get(name) or template.format(name=name, **{"tool": "", "table": "", **fields})
        new = unique_name(new, new, taken)
        taken.add(new)
        result[name] = new
    return result


def free_names(names: Iterable[str], taken: Iterable[Any]) -> list[str]:
    """Return the names a tool gives new columns, numbered where a name is taken.

    A name is numbered if a column of the table (or an earlier new one) already has
    it, so no column of the table is overwritten or duplicated.

    Args:
        names: The wanted names, e.g. `["PC 1", "PC 2"]`.
        taken: The table's column names.

    Returns:
        The names, e.g. `["PC 1_1", "PC 2"]` if the table has a column `PC 1`.
    """
    used = {str(t) for t in taken}
    result = []
    for name in names:
        free = unique_name(name, name, used)
        used.add(free)
        result.append(free)
    return result
