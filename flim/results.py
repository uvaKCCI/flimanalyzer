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
    """def __init__(self, dir: str = None, validate_dir: bool = True, **kwargs):
    if dir is not None:
        cleaned_dir = (
            repr(dir)
            .replace("%", "pcent")
            .replace("\r", "")
            .replace("\n", " ")
            .replace("|", "_")
        )
    else:
        cleaned_dir = dir
    super().__init__(cleaned_dir, validate_dir, **kwargs)"""

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
                    drive = dirpath[1:3]
                    savepath = (
                        dirpath[3:-1]
                        .replace("%", "pcent")
                        .replace("\r", "")
                        .replace("\\n", " ")
                        .replace("|", "_")
                    )
                    savepath = re.sub(":\s?", "_", savepath)
                    v.to_csv(drive + savepath)
                elif isinstance(v, matplotlib.figure.Figure):
                    # v.tight_layout()
                    dirpath = repr(os.path.join(cleardir, f"{k}.png"))
                    drive = dirpath[1:3]
                    savepath = (
                        dirpath[3:-1]
                        .replace("%", "pcent")
                        .replace("\\r", "")
                        .replace("\\n", " ")
                        .replace("|", "_")
                    )
                    savepath = re.sub(":\s?", "_", savepath)
                    v.savefig(drive + savepath)
                else:
                    dirpath = repr(os.path.join(cleardir, f"{k}"))
                    drive = dirpath[1:3]
                    savepath = (
                        dirpath[3:-1]
                        .replace("%", "pcent")
                        .replace("\\r", "")
                        .replace("\\n", " ")
                        .replace("|", "_")
                    )
                    savepath = re.sub(":\s?", "_", savepath)
                    dump(v, drive + savepath)
        return new
