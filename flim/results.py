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
from joblib import dump
from pathlib import Path
from prefect.engine.results.local_result import LocalResult

from flim import utils


class LocalResultClear(LocalResult):
    def write(self, value, **kwargs):
        # for k,v in kwargs.items():
        #    print (k,v)
        new = super().write(value, **kwargs)
        assert new.location is not None

        full_path = os.path.join(self.dir, new.location)
        pickledir = os.path.dirname(full_path)
        cleardir = Path(pickledir).parent
        logging.debug(f"Saving pickled data to {full_path}, raw data to {cleardir}")
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, pd.DataFrame):
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
