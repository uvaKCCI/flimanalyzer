#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 12:45:21 2022

@author: khs3z
"""
import os
import logging
import matplotlib
import pandas as pd
import re
from joblib import dump
from pathlib import Path
from prefect.engine.results.local_result import LocalResult

from flim import utils


class LocalResultClear(LocalResult):
    def write(self, value, **kwargs):
        # store relevant params for location templating
        keys = [k.split(":")[0] for k in re.findall("(?<=\{).*?(?=\})", self.location)]
        self.location_params = {}
        for k in keys:
            self.location_params[k] = kwargs.get(k, None)

        new = super().write(value, **kwargs)
        assert new.location is not None

        full_path = os.path.join(self.dir, new.location)
        pickledir = os.path.dirname(full_path)
        cleardir = Path(pickledir).parent
        logging.debug(f"Saving pickled data to {full_path}, raw data to {cleardir}")
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, pd.DataFrame):
                    v = v.copy()
                    v.reset_index()
                    # if indx was flattened in analyzer.summarize_data, multiindex col values were joined with '\n'--> revert here
                    v.columns = [c.replace("\n", " ") for c in v.columns.values]
                    dirpath = repr(os.path.join(cleardir, f"{k}.txt"))
                    start = re.match("^\W{0,2}\w", dirpath).end() - 1
                    end = re.search("\w\W{0,2}$", dirpath).start() + 1
                    drive = dirpath[1:3]
                    v.to_csv(
                        drive
                        + dirpath[3:-1]
                        .replace("%", "pcent")
                        .replace(":", "_")
                        .replace("\r", "")
                        .replace("\n", " "),
                        index=False,
                        sep="\t",
                    )
                elif isinstance(v, matplotlib.figure.Figure):
                    # v.tight_layout()
                    dirpath = repr(os.path.join(cleardir, f"{k}.png"))
                    start = re.match("^\W{0,2}\w", dirpath).end() - 1
                    end = re.search("\w\W{0,2}$", dirpath).start() + 1
                    drive = dirpath[1:3]
                    v.savefig(
                        drive
                        + dirpath[3:-1]
                        .replace("%", "pcent")
                        .replace(":", "_")
                        .replace("\r", "")
                        .replace("\n", " ")
                    )
                else:
                    dirpath = repr(os.path.join(cleardir, f"{k}"))
                    start = re.match("^\W{1,2}\w", dirpath).end() - 1
                    end = re.search("\w\W{1,2}$", dirpath).start() + 1
                    drive = dirpath[1:3]
                    dump(
                        v,
                        drive
                        + dirpath[3:-1]
                        .replace("%", "pcent")
                        .replace(":", "_")
                        .replace("\r", "")
                        .replace("\n", " "),
                    )
        return new
