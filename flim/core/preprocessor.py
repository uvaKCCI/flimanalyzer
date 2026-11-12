#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preprocessing of imported tables.

Renaming and dropping columns, and calculating further features.
"""

import logging
from collections.abc import Callable
from typing import Any, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRP_RZERO = 2.1
ONE_SIXTH = 1.0 / 6


def percentile(n: float) -> Callable[[np.ndarray], float]:
    """Return a function that computes the n-th percentile, ignoring missing values.

    The function is named `<n> percentile`.

    Args:
        n: The percentile, from 0 to 100.

    Returns:
        A function of an array of values.
    """

    def percentile_(x: np.ndarray) -> float:
        return np.nanpercentile(x, n)

    percentile_.__name__ = f"{n} percentile"
    return percentile_


def nadph_perc(nadph_t2: float) -> float:
    """Return the fraction of NADPH in percent, from the NAD(P)H lifetime t2.

    The lifetime is mapped linearly from 1500 (0 %) to 4400 (100 %); values outside
    that range give percentages below 0 or above 100.

    Args:
        nadph_t2: The lifetime of the second NAD(P)H component, in ps.

    Returns:
        The percentage of NADPH.
    """
    return ((nadph_t2 - 1500) / (4400 - 1500)) * 100


def nadh_perc(nadph_perc: float) -> float:
    """Return the fraction of NADH in percent: 100 minus the NADPH percentage."""
    return 100.0 - nadph_perc


def tm(a1perc: float, t1: float, a2perc: float, t2: float) -> float:
    """Return the mean lifetime of two components, weighted by their amplitudes.

    Args:
        a1perc: The amplitude of the first component, in percent.
        t1: The lifetime of the first component.
        a2perc: The amplitude of the second component, in percent.
        t2: The lifetime of the second component.

    Returns:
        `(a1perc * t1 + a2perc * t2) / 100`, in the unit of the lifetimes.
    """
    return ((a1perc * t1) + (a2perc * t2)) / 100


def trp_Eperc_1(trp_tm: float, const: float = 3100) -> float:
    """Return the FRET efficiency in percent, from the mean tryptophan lifetime.

    Args:
        trp_tm: The mean tryptophan lifetime.
        const: The unquenched tryptophan lifetime, in the unit of `trp_tm`.
            Defaults to 3100.

    Returns:
        `(1 - trp_tm / const) * 100`; NaN if `const` is 0.
    """
    if const != 0:
        return (1.0 - (trp_tm / const)) * 100
    else:
        return np.nan


def trp_Eperc_2(trp_t1: float, trp_t2: float) -> float:
    """Return the FRET efficiency in percent, from the two tryptophan lifetimes.

    Args:
        trp_t1: The lifetime of the first component.
        trp_t2: The lifetime of the second component, taken as the unquenched
            lifetime.

    Returns:
        `(1 - trp_t1 / trp_t2) * 100`; NaN if `trp_t2` is 0.
    """
    if trp_t2 != 0:
        return (1.0 - (trp_t1 / trp_t2)) * 100
    else:
        return np.nan


def trp_Eperc_3(trp_t1: float, const: float = 3100) -> float:
    """Return the FRET efficiency in percent, from the first tryptophan lifetime.

    Args:
        trp_t1: The lifetime of the first component.
        const: The unquenched tryptophan lifetime, in the unit of `trp_t1`.
            Defaults to 3100.

    Returns:
        `(1 - trp_t1 / const) * 100`; NaN if `const` is 0.
    """
    if const != 0:
        return (1.0 - (trp_t1 / const)) * 100
    else:
        return np.nan


def trp_r(trp_Eperc: float) -> float:
    """Return the donor-acceptor distance from a FRET efficiency.

    Args:
        trp_Eperc: The FRET efficiency, in percent.

    Returns:
        `TRP_RZERO * (100 / trp_Eperc - 1) ** (1/6)`, in the unit of `TRP_RZERO`
        (the Förster distance); NaN unless 0 < `trp_Eperc` <= 100.
    """
    # defined for 0 < Eperc <= 100, NaN otherwise
    if trp_Eperc != 0:
        t = 100.0 / trp_Eperc - 1
        if t >= 0:
            return TRP_RZERO * t**ONE_SIXTH
    return np.nan


def ratio(v1: float, v2: float) -> float:
    """Return `v1 / v2`; NaN if `v2` is 0."""
    if v2 != 0:
        return float(v1) / v2
    else:
        return np.nan


# the column name parts Import replaces and drops by default (the Rename Columns and
# Drop Columns tools' defaults): the channels of the FLIM exports
DEFAULT_RENAME = {
    "Exc1_-Ch1-_": "trp ",
    "Exc1_-Ch2-_": "NAD(P)H ",
    "Exc2_-Ch3-_": "FAD ",
}
DEFAULT_DROP = ("Exc1_", "Exc2_", "Exc3_")


# the calculations Import makes by default (the Calculate tool's defaults), in order:
# a calculation can use the columns of earlier ones
DEFAULT_CALCULATIONS = (
    ('NAD(P)H tm', 'tm', ['NAD(P)H a1[%]', 'NAD(P)H t1', 'NAD(P)H a2[%]', 'NAD(P)H t2']),
    ('NAD(P)H a2[%]/a1[%]', 'ratio', ['NAD(P)H a2[%]', 'NAD(P)H a1[%]']),
    ('NADPH %', 'nadph_perc', ['NAD(P)H t2']),
    ('NADH %', 'nadh_perc', ['NADPH %']),
    ('NADPH/NADH', 'ratio', ['NADPH %', 'NADH %']),  # after NADH % (0.6: before)
    ('trp tm', 'tm', ['trp a1[%]', 'trp t1', 'trp a2[%]', 'trp t2']),
    ('trp E%1', 'trp_Eperc_1', ['trp tm']),
    ('trp E%2', 'trp_Eperc_2', ['trp t1', 'trp t2']),
    ('trp E%3', 'trp_Eperc_3', ['trp t1']),
    ('trp r1', 'trp_r', ['trp E%1']),
    ('trp r2', 'trp_r', ['trp E%2']),
    ('trp r3', 'trp_r', ['trp E%3']),
    ('trp a1[%]/a2[%]', 'ratio', ['trp a1[%]', 'trp a2[%]']),
    ('FAD tm', 'tm', ['FAD a1[%]', 'FAD t1', 'FAD a2[%]', 'FAD t2']),
    ('FAD a1[%]/a2[%]', 'ratio', ['FAD a1[%]', 'FAD a2[%]']),
    ('FAD photons/NAD(P)H photons', 'ratio', ['FAD photons', 'NAD(P)H photons']),
    ('NAD(P)H tm/FAD tm', 'ratio', ['NAD(P)H tm', 'FAD tm']),
    ('FLIRR', 'ratio', ['NAD(P)H a2[%]', 'FAD a1[%]']),
    ('NADPH a2/FAD a1', 'ratio', ['NAD(P)H a2', 'FAD a1']),
)


class defaultpreprocessor:
    """Renames and drops the columns of imported tables and calculates new columns.

    By default the parts of `DEFAULT_RENAME` are replaced, the columns that contain
    a part of `DEFAULT_DROP` are dropped, and the calculations are those of the
    Calculate tool's default config.
    """

    def __init__(self) -> None:
        """Create a preprocessor with the default renames, drops and calculations."""
        self.newheaders = dict(DEFAULT_RENAME)
        self.dropcolumns = list(DEFAULT_DROP)
        self.calculations = None  # None: the Calculate tool's defaults

    def set_replacementheaders(self, headers: dict[str, str]) -> None:
        """Set the replacements of column name parts: part -> new text, in order."""
        self.newheaders = headers

    def get_replacementheaders(self) -> dict[str, str]:
        """Return the replacements of column name parts: part -> new text."""
        return self.newheaders

    def set_dropcolumns(self, cols: list[Union[str, tuple[str, str]]]) -> None:
        """Set the drop rules: texts, or (text, match) pairs (see `drop_columns`)."""
        self.dropcolumns = cols

    def rename_headers(
        self,
        data: Optional[pd.DataFrame],
        newheaders: Optional[dict[str, str]] = None,
        preview: bool = False,
    ) -> Optional[tuple[pd.DataFrame, dict[str, str]]]:
        """Replace parts of the column names, in order.

        Each replacement applies to the names the earlier ones produced; an empty
        part is skipped.

        Args:
            data: The table; its columns are renamed in place unless `preview`.
            newheaders: Part -> new text. Defaults to the preprocessor's.
            preview: Only return the new names, leaving the table unchanged.

        Returns:
            The table, and old name -> new name for the changed columns; None if
            `data` is None.
        """
        if data is None:
            return None
        if newheaders is None:
            newheaders = self.newheaders
        from flim.core.columns import renamed_columns

        oldheaders = list(data.columns.values)
        # in order; an empty part is skipped (it would insert text between all
        # characters)
        currentheaders = renamed_columns(oldheaders, list(dict(newheaders).items()))
        changedheaders = {
            oldheaders[i]: currentheaders[i]
            for i in range(len(oldheaders))
            if oldheaders[i] != currentheaders[i]
        }
        if not preview:
            data.columns = currentheaders
        return data, changedheaders

    def set_calculations(self, calculations: Optional[list[Any]]) -> None:
        """Set the calculations (the Calculate tool's `calculations`).

        Args:
            calculations: The calculations; None: the Calculate tool's defaults.
        """
        self.calculations = calculations

    def calculate(
        self, data: pd.DataFrame, inplace: bool = True
    ) -> tuple[pd.DataFrame, list[str], list[str]]:
        """Calculate the new columns (see `flim.core.calculate.calculate`).

        A calculation that uses a column the table doesn't have is skipped.

        Args:
            data: The table.
            inplace: Add the new columns to `data` and replace the columns of the
                same names; else `data` is not changed and a new table is returned.

        Returns:
            The table, the calculated columns' names, and the skipped calculations'
            names.

        Raises:
            ValueError: If a calculation is not valid or fails.
        """
        from flim.core.calculate import calculate

        calculations = self.calculations
        if calculations is None:
            from flim.configs.data import CalculateConfig

            calculations = CalculateConfig().calculations
        outcome = calculate(data, calculations)
        for name, reason in outcome.skipped.items():
            logger.debug(f"Calculate: {name} skipped: {reason}")
        if inplace:
            for name in outcome.data.columns.difference(data.columns, sort=False):
                data[name] = outcome.data[name]
            for name in outcome.replaced:
                data[name] = outcome.data[name]
            outcome.data = data
        return outcome.data, outcome.calculated, list(outcome.skipped)

    def reorder_columns(
        self, data: pd.DataFrame, first: Optional[list[str]] = []
    ) -> pd.DataFrame:
        """Return the table with the columns `first` first, then the others, sorted.

        Without `first`, the text columns come first, sorted, then the category
        columns, sorted. If `first` names a column the table does not have, the
        table is returned unchanged. A given `first` list is extended in place.

        Args:
            data: The table.
            first: The columns to put first, in order; None or empty: the text and
                category columns.

        Returns:
            The reordered table.
        """
        if first is None or len(first) == 0:
            first = sorted(data.select_dtypes(["object"]).columns.values)
            first.extend(sorted(data.select_dtypes(["category"]).columns.values))
        newheaders = first
        newheaders.extend(sorted(set(data.columns.values) - set(first)))
        if len(newheaders) == len(data.columns):
            data = data.reindex(newheaders, axis=1)
        logger.debug(f"Reordered headers: {data.columns.values}")
        return data

    def drop_columns(
        self,
        data: Optional[pd.DataFrame],
        drops: Optional[list[Union[str, tuple[str, str]]]] = None,
        func: str = "contains",
        dropemptyheader: bool = True,
        inplace: bool = True,
        preview: bool = False,
    ) -> Optional[tuple[pd.DataFrame, list[str]]]:
        """Drop the columns that drop rules select (see `columns_to_drop`).

        Args:
            data: The table.
            drops: Texts, matched as `func`, or (text, match) pairs. Defaults to the
                preprocessor's drop rules.
            func: How a plain text matches: `startswith`, `endswith`, or one of
                `flim.core.columns.MATCHES`. Defaults to `contains`.
            dropemptyheader: Also drop columns with an empty header.
            inplace: Drop the columns from `data`; else a new table is returned.
            preview: Only return the selected columns, leaving the table unchanged.

        Returns:
            The table, and the names of the selected columns; None if `data` is
            None.

        Raises:
            ValueError: If a rule's match is not one of `MATCHES`.
        """
        if data is None:
            return None
        if drops is None:
            drops = self.dropcolumns
        from flim.core.columns import columns_to_drop

        # a plain text matches as `func`; (text, match) rules as their match
        names = {"startswith": "starts with", "endswith": "ends with"}
        rules = [
            (d, names.get(func, func)) if isinstance(d, str) else d for d in drops or []
        ]
        droplist = columns_to_drop(data.columns, rules, drop_empty=dropemptyheader)
        if not preview:
            if inplace:
                data.drop(droplist, axis=1, inplace=inplace)
            else:
                data = data.drop(droplist, axis=1, inplace=inplace)
        return data, droplist

