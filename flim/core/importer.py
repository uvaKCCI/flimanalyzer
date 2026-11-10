#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reads data files into one table, with category columns taken from the file
names."""

import itertools
import logging
import os
import glob
from pathlib import Path
import pandas as pd

from flim.core.categories import DELIMITER, fuse
from flim.core.columns import CLASH_TEMPLATE, PROTECTED, make_room
from flim.core.parser import PATTERN_CATEGORY, defaultparser
import flim.core.preprocessor as pp

logger = logging.getLogger(__name__)

DEFAULT_EXT = [".txt", ".csv"]
SOURCE = "Source"  # the column with each row's origin, a URI


def source_uri(path) -> str:
    """The URI of a data file, e.g. `file:///data/9SR/Results-a-Dox15_01.txt`."""
    return Path(path).resolve().as_uri()


class dataimporter:
    def __init__(self):
        self.files = []
        self.delimiter = "\t,"
        self.data = pd.DataFrame()
        self.excluded_files = []
        self.parser = defaultparser()
        self.preprocessor = None
        self.combolist = None

    def set_parser(self, parser):
        if parser is not None:
            self.parser = parser

    def get_parser(self):
        return self.parser

    def set_preprocessor(self, preprocessor):
        self.preprocessor = preprocessor

    def get_preprocessor(self):
        return self.preprocessor

    def set_delimiter(self, delimiter):
        if delimiter is not None:
            self.delimiter = delimiter

    def get_delimiter(self):
        return self.delimiter

    def set_column_combos(self, combolist):
        self.combolist = combolist

    def set_files(self, files, extensions=DEFAULT_EXT, exclude=None, sort=True):
        if exclude is None:
            exclude = self.excluded_files
        self.files = []
        self.add_files(files, extensions, exclude, sort)

    def set_excluded_files(self, exclude):
        if exclude is None:
            exclude = []
        self.excluded_files = exclude

    def get_excluded_files(self):
        return self.excluded_files

    def add_files(self, files, extensions=DEFAULT_EXT, exclude=None, sort=True):
        if files is None:
            return None, 0
        if exclude is None:
            exclude = self.excluded_files
        added_files = 0
        skipped_files = 0
        files = [os.path.abspath(f) for f in set(files)]
        ext = tuple(extensions)
        for f in files:
            if os.path.isdir(f):
                filesindir = glob.glob(os.path.join(f, "*"))
                added, skipped = self.add_files(
                    filesindir, extensions=extensions, exclude=exclude
                )
                added_files += added
                skipped_files += skipped
            else:
                if (
                    os.path.isfile(f)
                    and f.endswith(ext)
                    and not f in self.files
                    and not os.path.basename(f) in exclude
                ):
                    self.files.append(f)
                    added_files += 1
                else:
                    skipped_files += 1
        if sort:
            self.files = sorted(self.files)
        return (added_files, skipped_files)

    def remove_files(self, rfiles):
        logger.debug(f"removing {rfiles}")
        if rfiles is not None:
            self.files = [f for f in self.files if f not in rfiles]

    def remove_allfiles(self):
        self.files = []

    def get_files(self):
        return self.files

    def get_reserved_categorycols(self, parser=None):
        if parser is None:
            parser = self.parser
        rcatnames = [
            "Cell line",
            "Category",
            "Cat",
            "Cluster",
            "FOV",
            "Well",
            "Cell",
            "Treatment",
            "Treatment 1",
            "Treatment 2",
            "Treatment 1 & 2",
            "Time",
            "Compartment",
            "New Cat",
            "Origin",
            "AE Label",
            "Time",
            "Combined",
            "Cell line-Compartment",
            "Cell line-FOV",
            "Cell line-Treatment",
            "Cell line-Cell",
            "Compartment-Cell",
            "Compartment-FOV",
            "Compartment-Treatment",
            "FOV-Time",
            "FOV-Well",
            "Time-Well",
            "Treatment-Time",
            "Treatment-FOV",
            "FOV-Cell",
            "FOV-Treatment",
            "Treatment-Cell",
        ]
        rcatnames.extend(
            [
                entry[PATTERN_CATEGORY]
                for entry in parser.get_regexpatterns()
                for key in entry
            ]
        )
        return sorted(set(rcatnames))

    def import_data(
        self,
        delimiter=None,
        parser=None,
        preprocessor=None,
        nrows=None,
        keep_existing=False,
        clash_name=CLASH_TEMPLATE,
        clash_renames=None,
        tool="Import",
    ):
        """Read the files into one table.

        Each file's rows get the columns of its file name: `Directory`, `File`, the
        filename parser's categories, and `Source` (the file as a URI). A file that
        already has a column of such a name: with `keep_existing` (File > Open: the
        table as it is, e.g. one saved by FLIMAnalyzer) the column is kept and not
        added; else a column of a protected name (`Source`, `Directory`, `File`) is
        renamed (`clash_name`, `clash_renames`) and a category of the parser
        replaces the file's column. What was renamed or replaced is in `renamed` and
        `replaced`; `tool` is the template's `{tool}`.

        Returns:
            The table (None if no file could be read), the files read, and the names
            of the columns taken from the file names.
        """
        self.renamed: dict = {}  # file -> {old: new}
        self.replaced: dict = {}  # file -> columns replaced by the parser's
        if delimiter is None:
            delimiter = self.delimiter
        delimiter = "|".join(delimiter)
        if parser is None:
            parser = self.parser
        if preprocessor is None:
            preprocessor = self.preprocessor
        dflist = []
        filenames = []
        fheaders = []
        comboheaders = []
        for f in self.files:
            if not os.path.isfile(f):
                continue
            # reserved category columns (including the parser's) are read as text;
            # they are converted to categories after all files are read
            category_dtypes = {
                col: "object" for col in self.get_reserved_categorycols(parser)
            }
            df = pd.read_table(
                f,
                delimiter=delimiter,
                engine="python",
                dtype=category_dtypes,
                nrows=nrows,
            )
            headers = parser.parsefilename(f)
            headers[SOURCE] = source_uri(f)  # provenance: a text column, a URI
            if keep_existing:
                headers = {k: v for k, v in headers.items() if k not in df.columns}
            else:
                protected = [k for k in headers if k in PROTECTED]
                renames = make_room(
                    df.columns, protected, clash_name, clash_renames, tool=tool
                )
                if renames:
                    df = df.rename(columns=renames)
                    self.renamed[f] = renames
                replaced = [k for k in headers if k in df.columns]
                if replaced:
                    self.replaced[f] = replaced
            for key, value in headers.items():
                df[key] = value
            if preprocessor is not None:
                df, ch = preprocessor.rename_headers(df)
                df, dl = preprocessor.drop_columns(df)
            dflist.append(df)
            fheaders.extend(list(headers.keys()))
            filenames.append(f)

            if self.combolist is not None and len(self.combolist) == 0:
                # all pairs of the text category columns of the first file
                categories = [
                    cat
                    for cat in category_dtypes
                    if cat in df.select_dtypes(["object"]).columns
                ]
                self.combolist = [
                    combo for combo in itertools.combinations(categories, 2)
                ]

        if len(dflist) == 0:
            return None, filenames, set()
        else:
            df = pd.concat(dflist).reset_index(drop=True)
            # combined category columns: Fuse Categories' engine, joined with ":"
            for combo in self.combolist or []:
                result = fuse(df, list(combo), DELIMITER)
                for message in result.warnings:
                    logger.warning(f"Column Combos: {message}")
                for name, values in result.columns.items():
                    df[name] = values
                    comboheaders.append(name)
            fheaders = set(fheaders + comboheaders)
            allheaders = list(df.columns.values)
            logger.debug(self.get_reserved_categorycols(parser))
            categories = [
                key
                for key in self.get_reserved_categorycols(parser)
                if key in allheaders
            ] + comboheaders

            for ckey in categories:
                df[ckey] = df[ckey].astype("category")
            if preprocessor is None:
                dp = pp.defaultpreprocessor()
                df = dp.reorder_columns(df)
            else:
                df = preprocessor.reorder_columns(df)
                df, _, _ = preprocessor.calculate(df)
            return df, filenames, fheaders
