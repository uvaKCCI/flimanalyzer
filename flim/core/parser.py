#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File name parsers: regular expressions that take category values from file paths.

Deprecated: importing this module issues a `DeprecationWarning`. It is removed in
0.8.0. Separate Categories (`flim.core.categories.separate_by_patterns`, with the
built-in presets of `flim.core.categories.separate_presets`) replaces it.
"""

import logging
import os
import re
import importlib
import pkgutil
import warnings
from typing import Any, Optional

logger = logging.getLogger(__name__)

warnings.warn(
    "flim.core.parser is deprecated and is removed in 0.8.0; use Separate Categories"
    " (flim.core.categories.separate_by_patterns and separate_presets) instead",
    DeprecationWarning,
    stacklevel=2,
)


def get_available_parsers(
    pkdir: str = "core.parser",
) -> dict[str, type["defaultparser"]]:
    """Return the parser classes: the direct subclasses of `defaultparser`.

    The modules in the directory `pkdir` are imported first, relative to this
    module's package, so that parsers they define are found too.

    Args:
        pkdir: The directory whose modules are imported. Defaults to `core.parser`.

    Returns:
        Class name -> parser class.
    """
    for module_loader, name, ispkg in pkgutil.iter_modules([pkdir]):
        importlib.import_module("." + name, __package__)
    parser_classes = {cls.__name__: cls for cls in defaultparser.__subclasses__()}
    return parser_classes


def instantiate_parser(fullname: str) -> Optional["defaultparser"]:
    """Create a parser from its full class name, e.g. `flim.core.parser.no_parser`.

    Args:
        fullname: The module and the class name, joined by a dot.

    Returns:
        The parser; None if the module or the class cannot be imported or the class
        cannot be instantiated (the error is logged).
    """
    namesplit = fullname.rpartition(".")
    if len(namesplit) != 3:
        return None
    modulename = fullname.rpartition(".")[0]
    classname = fullname.rpartition(".")[2]
    logger.debug(f"Parser modulename={modulename}, classname={classname}")
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        parserinstance = class_()
    except Exception:
        logger.error(f"Error instantiating {fullname} parser.")
        logger.error(Exception)
        parserinstance = None
    return parserinstance


# keys of a pattern: {PATTERN_USE: bool, PATTERN_CATEGORY: column, PATTERN_REGEX: regex}
PATTERN_USE = "Use"
PATTERN_CATEGORY = "Category"
PATTERN_REGEX = "Regex"


class defaultparser(object):
    """A parser without patterns; the base of all parsers.

    A pattern is a dict with the keys `PATTERN_USE` (whether it is applied),
    `PATTERN_CATEGORY` (the name of the category column it fills) and `PATTERN_REGEX`
    (a regular expression whose first group is the value).
    """

    def __init__(self) -> None:
        """Set the parser's patterns and compile them."""
        self.init_patterns()
        self.compile_patterns()

    def is_readonly(self) -> bool:
        """Return True: the parser's patterns are predefined."""
        return True

    def get_name(self) -> str:
        """Return the parser's display name."""
        return "Default Parser"

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns; none for this parser."""
        self.regexpatterns = []

    def compile_patterns(self) -> None:
        """Compile the regular expressions of the patterns in use, by category.

        Raises:
            re.error: If a regular expression is not valid.
        """
        if self.regexpatterns is not None and len(self.regexpatterns) > 0:
            self.compiledpatterns = {
                rp[PATTERN_CATEGORY]: re.compile(rp[PATTERN_REGEX])
                for rp in self.regexpatterns
                if rp[PATTERN_USE]
            }
        else:
            self.compiledpatterns = {}

    def get_regexpatterns(self) -> list[dict[str, Any]]:
        """Return the parser's patterns (see the class docstring)."""
        return self.regexpatterns

    def set_regexpatterns(self, patterns: list[dict[str, Any]]) -> None:
        """Replace the parser's patterns and compile them.

        Args:
            patterns: The patterns (see the class docstring).

        Raises:
            re.error: If a regular expression is not valid.
        """
        self.regexpatterns = patterns
        self.compile_patterns()

    def parsefilename(self, fname: str) -> dict[str, str]:
        """Return the category values that the patterns take from a file's path.

        Each pattern in use gives the first group of its regular expression's first
        match (see `flim.core.categories.separate_by_patterns`): `?` for a group that
        matches nothing; backslashes in the path are matched as `/`. A pattern that
        does not match the path gives no value.

        Args:
            fname: The path of the file.

        Returns:
            Category -> value: `Directory` (the path's directory), `File` (the file
            name) and the value of each pattern that matched.

        Raises:
            ValueError: If a regular expression is not valid or has no group.
        """
        components = {
            "Directory": os.path.dirname(fname),
            "File": os.path.basename(fname),
        }
        # the patterns of Separate Categories' engine: the first group, "?" for an
        # empty match, "/" for "\\"; a category without a match is left out
        import pandas as pd

        from flim.core.categories import separate_by_patterns

        patterns = [
            (entry[PATTERN_CATEGORY], entry[PATTERN_REGEX])
            for entry in self.regexpatterns
            if entry[PATTERN_USE]
        ]
        if patterns:
            result = separate_by_patterns(pd.DataFrame({"path": [fname]}), "path", patterns)
            for name, values in result.columns.items():
                if not pd.isna(values[0]):
                    components[name] = str(values[0])
        return components


class no_parser(defaultparser):
    """A parser that takes no values, not even the directory and the file name."""

    def set_regexpatterns(self, patterns: list[dict[str, Any]]) -> None:
        """Ignore the patterns: this parser has none."""
        pass

    def parsefilename(self, fname: str) -> dict[str, str]:
        """Return no values."""
        return {}


class celltype_compartment_fov_treatment_cell_parser(defaultparser):
    """Cell line and compartment from the directories.

    FOV, treatment and cell from the file name.
    """

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell line",
                PATTERN_REGEX: r".*/(.*?)/.*/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Compartment",
                PATTERN_REGEX: r".*/(.*?)/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class compartment_fov_treatment_cell_parser(defaultparser):
    """Compartment from the directory; FOV, treatment and cell from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Compartment",
                PATTERN_REGEX: r".*/(.*?)/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class compartment_treatment_fov_cell_parser(defaultparser):
    """Compartment from the directory; treatment, FOV and cell from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Compartment",
                PATTERN_REGEX: r".*/(.*?)/",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class fov_treatment_cell_parser(defaultparser):
    """FOV, treatment and cell from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class treatment_fov_cell_parser(defaultparser):
    """Treatment, FOV and cell from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Cell",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class treatment_fov_time_parser(defaultparser):
    """Treatment, FOV and time from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Time",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](\d*?)\.",
            },
        ]


class treatment_time_parser(defaultparser):
    """Treatment and time from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Treatment",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Time",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](\d*?)\.",
            },
        ]


class fov_time_well_parser(defaultparser):
    """FOV, time and well from the file name."""

    def init_patterns(self) -> None:
        """Set the parser's predefined patterns."""
        self.regexpatterns = [
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "FOV",
                PATTERN_REGEX: r".*/.*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Time",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-](.*?)[_-]",
            },
            {
                PATTERN_USE: True,
                PATTERN_CATEGORY: "Well",
                PATTERN_REGEX: r".*/.*?[_-].*?[_-].*?[_-](.*?)\.",
            },
        ]

