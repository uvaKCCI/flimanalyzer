"""Fusing category columns into one, and separating one into several.

Fuse joins the values of category columns with a delimiter (default `:`), e.g. `FOV`
= `1` and `Cell` = `1` become `FOV:Cell` = `1:1`; Separate reverses it with the same
delimiter, or takes parts of the values by patterns (regular expressions, the first
group), as the filename parser does. Both report, as warnings, values that would not
survive the round trip, e.g. a delimiter inside a value.
"""

import os
import re
from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import Any, Optional

import pandas as pd

DELIMITER = ":"  # not ".": a decimal point; not "|": regex alternation; not "-": in names
PARTS = ("value", "file name", "file name without extension")
EMPTY_MATCH = "?"  # a pattern whose group matched nothing, as the filename parser
SHOWN = 5  # values named in a warning


@dataclass
class Result:
    """New columns and the warnings that came with them.

    Attributes:
        columns: The new columns by name, in order.
        warnings: Messages for the user, e.g. values that could not be separated.
    """

    columns: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def _listed(values: Iterable[Any]) -> str:
    """Return the first `SHOWN` values as text, and how many more there are."""
    values = list(values)
    shown = ", ".join(repr(v) for v in values[:SHOWN])
    return shown + (f" and {len(values) - SHOWN} more" if len(values) > SHOWN else "")


def fuse(
    data: pd.DataFrame,
    columns: Iterable[str],
    delimiter: str = DELIMITER,
    name: Optional[str] = None,
) -> Result:
    """Join category columns into one category column.

    A row with a missing value in one of the columns gets a missing value. The new
    column's categories are the combinations that occur, ordered by the source
    columns' category orders.

    Args:
        data: The table.
        columns: The category columns, in order.
        delimiter: Joins the column names and the values. Defaults to `:`.
        name: The new column's name; None or empty for the column names joined by
            the delimiter.

    Returns:
        The new column, and warnings where the delimiter occurs in a column name or a
        value (separating back would be ambiguous).
    """
    columns = list(columns)
    name = name or delimiter.join(columns)
    result = Result()
    in_names = [c for c in columns if delimiter in str(c)]
    if in_names:
        result.warnings.append(
            f"{delimiter!r} occurs in the column names {_listed(in_names)}: separating"
            " the fused column back would be ambiguous"
        )
    parts = data[columns]
    texts = parts.astype("string")
    with_delimiter = set()
    for column in columns:
        hits = texts[column].dropna()
        hits = hits[hits.str.contains(delimiter, regex=False)]
        with_delimiter.update(hits.unique())
    if with_delimiter:
        result.warnings.append(
            f"{delimiter!r} occurs in the values {_listed(sorted(with_delimiter))}:"
            " separating the fused column back would be ambiguous"
        )
    missing = parts.isna().any(axis=1)
    joined = texts[columns[0]].str.cat(
        [texts[c] for c in columns[1:]], sep=delimiter
    ).where(~missing)
    # categories: the observed combinations, in the order of the source categories
    keys = []
    for column in columns:
        values = parts[column]
        if isinstance(values.dtype, pd.CategoricalDtype):
            keys.append(values.cat.codes)
        else:
            keys.append(values.astype("string").rank(method="dense"))
    order = (
        pd.DataFrame({"value": joined, **{str(i): k for i, k in enumerate(keys)}})
        .dropna(subset=["value"])
        .drop_duplicates("value")
        .sort_values([str(i) for i in range(len(keys))])["value"]
    )
    result.columns[name] = pd.Categorical(joined, categories=list(order))
    return result


def _decoded(value: str) -> str:
    """Return a `file://` URI (e.g. a Source value) as its path, other values as is.

    Escapes such as `%20` in the URI are decoded.
    """
    if not value.startswith("file:"):
        return value
    from urllib.parse import unquote, urlparse

    url = urlparse(value)
    path = unquote(url.path)
    if len(path) > 2 and path[0] == "/" and path[2] == ":":  # file:///D:/...
        path = path[1:]
    return f"//{url.netloc}{path}" if url.netloc else path


def _part(values: pd.Series, part: str) -> pd.Series:
    """Return the part of each value to separate.

    The part is the value, its file name, or its file name without the extension;
    `file://` URIs are taken as their paths.

    Raises:
        ValueError: If `part` is not one of `PARTS`.
    """
    if part not in PARTS:
        raise ValueError(f"unknown part {part!r}: use {', '.join(PARTS)}")
    texts = values.astype("string").map(lambda v: v if pd.isna(v) else _decoded(v))
    if part == "value":
        return texts
    names = texts.map(lambda v: v if pd.isna(v) else os.path.basename(v.replace("\\", "/")))
    if part == "file name":
        return names
    return names.map(lambda v: v if pd.isna(v) else os.path.splitext(v)[0])


def separate(
    data: pd.DataFrame,
    column: str,
    delimiters: Iterable[str] = (DELIMITER,),
    names: Iterable[str] = (),
    part: str = "value",
) -> Result:
    """Separate a category column into several, at delimiters.

    Any of the delimiters separates; empty delimiters are ignored. A value with more
    or fewer parts than names is not separated (missing values in its row) and is
    named in a warning, so no part lands in the wrong column.

    Args:
        data: The table.
        column: The category column.
        delimiters: The delimiters, e.g. `[":"]` (the reverse of Fuse) or `["-", "_"]`.
        names: The new columns' names by position; an empty name skips that part.
            Empty: the column name separated the same way (e.g. `FOV:Cell`).
        part: Which part of the values: `value`, `file name` or `file name without
            extension`. Defaults to `value`.

    Returns:
        The new columns, and warnings.

    Raises:
        ValueError: If no delimiter is given, or `part` is not known.
    """
    delimiters = [d for d in delimiters if d]
    if not delimiters:
        raise ValueError("give at least one delimiter")
    splitter = re.compile("|".join(re.escape(d) for d in delimiters))
    names = list(names) or splitter.split(str(column))
    result = Result()
    texts = _part(data[column], part)
    pieces = texts.map(lambda v: v if pd.isna(v) else splitter.split(v))
    wrong = pieces.dropna()[pieces.dropna().map(len) != len(names)]
    if len(wrong):
        result.warnings.append(
            f"{column}: {len(wrong)} value(s) have not {len(names)} parts and are not"
            f" separated: {_listed(texts[wrong.index].unique())}"
        )
    for i, name in enumerate(names):
        if not name:
            continue  # this part is skipped
        values = pieces.map(lambda p: None if not isinstance(p, list) or len(p) != len(names) else p[i])
        result.columns[name] = pd.Categorical(values)
    return result


def separate_by_patterns(
    data: pd.DataFrame,
    column: str,
    patterns: Iterable[tuple[str, str]],
    part: str = "value",
) -> Result:
    """Take parts of a category column's values by patterns, as the filename parser.

    Per pattern, the part is the first group of its regular expression's first match.

    A group that matches nothing gives `?`; a value the pattern does not match gives a
    missing value. Backslashes in the values are matched as `/`, so path patterns work
    for Windows paths too.

    Args:
        data: The table.
        column: The category column.
        patterns: (new column name, regular expression) pairs, in order.
        part: Which part of the values (see `separate`). Defaults to `value`.

    Returns:
        The new columns, and a warning per pattern that matched no value.

    Raises:
        ValueError: If a pattern is not a valid regular expression, or has no group,
            or `part` is not known.
    """
    result = Result()
    texts = _part(data[column], part).map(lambda v: v if pd.isna(v) else v.replace("\\", "/"))
    for name, regex in patterns:
        try:
            compiled = re.compile(regex)
        except re.error as err:
            raise ValueError(f"{name}: '{regex}' is not a valid pattern ({err})") from None
        if compiled.groups < 1:
            raise ValueError(f"{name}: '{regex}' has no group (...) to take")

        def take(value: Any) -> Optional[str]:
            if pd.isna(value):
                return None
            match = compiled.search(value)
            if match is None:
                return None
            return match.group(1) or EMPTY_MATCH

        values = texts.map(take)
        if values.isna().all() and texts.notna().any():
            result.warnings.append(f"{name}: the pattern '{regex}' matched no value")
        result.columns[name] = pd.Categorical(values)
    return result


def template_regex(template: str) -> tuple[re.Pattern, list[str]]:
    """Return the regular expression of a template, and the names of its parts.

    In a template, `{Name}` is a part that becomes the column `Name`, `{}` a part that
    is not kept, and the text between the braces must be there as it is, e.g.
    `Results-{FOV}-{Treatment}_{Cell}`.

    Args:
        template: The template.

    Returns:
        The regular expression, which matches the whole value (a group per part
        with a name), and the names in order.

    Raises:
        ValueError: If the template has no named part, a name twice, or a brace
            that is not closed.
    """
    regex, names = "", []
    for piece in re.split(r"(\{[^{}]*\})", template):
        if piece.startswith("{") and piece.endswith("}"):
            name = piece[1:-1].strip()
            if name in names:
                raise ValueError(f"the template names '{name}' twice")
            if name:
                names.append(name)
                regex += "(.+?)"
            else:
                regex += ".*?"  # a part that is not kept
        elif "{" in piece or "}" in piece:
            raise ValueError(f"the template has a brace that is not closed: '{piece}'")
        else:
            regex += re.escape(piece)
    if not names:
        raise ValueError("the template has no part with a name, e.g. {Treatment}")
    return re.compile(f"^{regex}$"), names


def separate_by_template(
    data: pd.DataFrame, column: str, template: str, part: str = "value"
) -> Result:
    """Separate a category column into several by a template of its values.

    The template is turned into a regular expression by `template_regex`.

    A value that doesn't fit the template is not separated (missing values in its
    row) and is named in a warning.

    Args:
        data: The table.
        column: The category column.
        template: The layout of the values, e.g. `Results-{FOV}-{Treatment}_{Cell}`.
        part: Which part of the values (see `separate`). Defaults to `value`.

    Returns:
        The new columns, and warnings.

    Raises:
        ValueError: If the template is not valid (see `template_regex`), or `part`
            is not known.
    """
    regex, names = template_regex(template)
    result = Result()
    texts = _part(data[column], part)
    matches = texts.map(lambda v: None if pd.isna(v) else regex.match(v))
    unmatched = texts[matches.isna() & texts.notna()]
    if len(unmatched):
        result.warnings.append(
            f"{column}: {len(unmatched)} value(s) don't fit the template '{template}' and"
            f" are not separated: {_listed(unmatched.unique())}"
        )
    for i, name in enumerate(names, 1):
        result.columns[name] = pd.Categorical(matches.map(lambda m: None if m is None else m.group(i)))
    return result


# the column, mode, part, delimiters, names, patterns and template of Separate Categories that a
# preset sets (see `separate_presets`)
PRESET_FIELDS = ("column", "mode", "part", "delimiters", "names", "patterns", "template")


def separate_presets() -> list[dict]:
    """Return the built-in presets of Separate Categories.

    The presets are the filename parsers of FLIMAnalyzer 0.6, as patterns on the
    whole value of the `Source` column.

    Returns:
        One dict per preset: its `name` and its `settings` (fields of
        `PRESET_FIELDS`).
    """
    return [
        {"name": name, "settings": {"column": "Source", "mode": "pattern", "part": "value", "patterns": patterns}}
        for name, patterns in _PARSER_PATTERNS
    ]


# (preset name, patterns) of the filename parsers of FLIMAnalyzer 0.6
_PARSER_PATTERNS = [
    (
        "Cell line, Compartment, FOV, Treatment, Cell",
        [
            {"name": "Cell line", "regex": r".*/(.*?)/.*/"},
            {"name": "Compartment", "regex": r".*/(.*?)/"},
            {"name": "FOV", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "Treatment", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Cell", "regex": r".*/.*?[_-].*?[_-].*?[_-](\d*?)\."},
        ],
    ),
    (
        "Compartment, FOV, Treatment, Cell",
        [
            {"name": "Compartment", "regex": r".*/(.*?)/"},
            {"name": "FOV", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "Treatment", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Cell", "regex": r".*/.*?[_-].*?[_-].*?[_-](\d*?)\."},
        ],
    ),
    (
        "Compartment, Treatment, FOV, Cell",
        [
            {"name": "Compartment", "regex": r".*/(.*?)/"},
            {"name": "Treatment", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "FOV", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Cell", "regex": r".*/.*?[_-].*?[_-].*?[_-](\d*?)\."},
        ],
    ),
    (
        "FOV, Time, Well",
        [
            {"name": "FOV", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "Time", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Well", "regex": r".*/.*?[_-].*?[_-].*?[_-](.*?)\."},
        ],
    ),
    (
        "FOV, Treatment, Cell",
        [
            {"name": "FOV", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "Treatment", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Cell", "regex": r".*/.*?[_-].*?[_-].*?[_-](\d*?)\."},
        ],
    ),
    (
        "Treatment, FOV, Cell",
        [
            {"name": "Treatment", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "FOV", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Cell", "regex": r".*/.*?[_-].*?[_-].*?[_-](\d*?)\."},
        ],
    ),
    (
        "Treatment, FOV, Time",
        [
            {"name": "Treatment", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "FOV", "regex": r".*/.*?[_-].*?[_-](.*?)[_-]"},
            {"name": "Time", "regex": r".*/.*?[_-].*?[_-].*?[_-](\d*?)\."},
        ],
    ),
    (
        "Treatment, Time",
        [
            {"name": "Treatment", "regex": r".*/.*?[_-](.*?)[_-]"},
            {"name": "Time", "regex": r".*/.*?[_-].*?[_-](\d*?)\."},
        ],
    ),
]
