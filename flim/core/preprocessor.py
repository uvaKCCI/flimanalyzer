#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The functions of the Calculate tool, and the default renames, drops and calculations.

The defaults are those of the Rename Columns, Drop Columns and Calculate tools.
"""

import logging
from collections.abc import Callable

import numpy as np

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
