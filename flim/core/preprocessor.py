#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preprocessing of imported tables: renaming and dropping columns, and calculating
further features."""

import logging
import numpy as np

logger = logging.getLogger(__name__)

TRP_RZERO = 2.1
ONE_SIXTH = 1.0 / 6


def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)

    percentile_.__name__ = f"{n} percentile"
    return percentile_


def nadph_perc(nadph_t2):
    return ((nadph_t2 - 1500) / (4400 - 1500)) * 100


def nadh_perc(nadph_perc):
    return 100.0 - nadph_perc


def tm(a1perc, t1, a2perc, t2):
    return ((a1perc * t1) + (a2perc * t2)) / 100


def trp_Eperc_1(trp_tm, const=3100):
    if const != 0:
        return (1.0 - (trp_tm / const)) * 100
    else:
        return np.nan


def trp_Eperc_2(trp_t1, trp_t2):
    if trp_t2 != 0:
        return (1.0 - (trp_t1 / trp_t2)) * 100
    else:
        return np.nan


def trp_Eperc_3(trp_t1, const=3100):
    if const != 0:
        return (1.0 - (trp_t1 / const)) * 100
    else:
        return np.nan


def trp_r(trp_Eperc):
    # defined for 0 < Eperc <= 100, NaN otherwise
    if trp_Eperc != 0:
        t = 100.0 / trp_Eperc - 1
        if t >= 0:
            return TRP_RZERO * t**ONE_SIXTH
    return np.nan


def ratio(v1, v2):
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
    def __init__(self):
        self.newheaders = dict(DEFAULT_RENAME)
        self.dropcolumns = list(DEFAULT_DROP)
        self.calculations = None  # None: the Calculate tool's defaults

    def set_replacementheaders(self, headers):
        self.newheaders = headers

    def get_replacementheaders(self):
        return self.newheaders

    def set_dropcolumns(self, cols):
        self.dropcolumns = cols

    def rename_headers(self, data, newheaders=None, preview=False):
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

    def set_calculations(self, calculations):
        """Set the calculations (the Calculate tool's `calculations`); None: its
        defaults."""
        self.calculations = calculations

    def calculate(self, data, inplace=True):
        """Calculate the new columns; a calculation that uses a column the table
        doesn't have is skipped. Returns the table, the calculated and the skipped
        columns' names."""
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

    def reorder_columns(self, data, first=[]):
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
        data,
        drops=None,
        func="contains",
        dropemptyheader=True,
        inplace=True,
        preview=False,
    ):
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

