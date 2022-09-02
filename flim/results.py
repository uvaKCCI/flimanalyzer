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
                    v.to_csv(os.path.join(cleardir, f"{k}.txt"), index=False, sep="\t")
                elif isinstance(v, matplotlib.figure.Figure):
                    # v.tight_layout()
                    v.savefig(os.path.join(cleardir, f"{k}.png"))
                else:
                    dump(v, os.path.join(cleardir, f"{k}"))
        return new
