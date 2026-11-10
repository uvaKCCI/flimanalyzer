"""Renaming and dropping columns by parts of their names, as Import and the Rename
Columns and Drop Columns tools do."""

from typing import Iterable

MATCHES = ("contains", "starts with", "ends with", "is")


def renamed_columns(names: Iterable[str], replacements) -> list[str]:
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
    """Return whether a column name matches a drop rule's text."""
    if match == "contains":
        return text in name
    if match == "starts with":
        return name.startswith(text)
    if match == "ends with":
        return name.endswith(text)
    if match == "is":
        return name == text
    raise ValueError(f"unknown match {match!r}: use {', '.join(MATCHES)}")


def columns_to_drop(names: Iterable[str], rules, drop_empty: bool = True) -> list[str]:
    """Return the columns that drop rules select.

    Args:
        names: The column names.
        rules: (text, match) pairs; a plain text means `contains`, as Import's drop
            list did. Rules with an empty text select nothing.
        drop_empty: Also select a column with an empty header (" " or "").

    Returns:
        The selected names, in table order.
    """
    rules = [(r, "contains") if isinstance(r, str) else tuple(r) for r in rules or []]
    selected = []
    for name in (str(n) for n in names):
        if (drop_empty and name.strip() == "") or any(
            text and matches(name, text, match) for text, match in rules
        ):
            selected.append(name)
    return selected
