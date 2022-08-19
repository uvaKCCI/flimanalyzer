#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 12:45:21 2022

@author: khs3z
"""
import os

import matplotlib
import pandas as pd
from prefect.engine.results.local_result import LocalResult


class LocalResultClear(LocalResult):
    def write(self, value, **kwargs):
        new = self.format(**kwargs)
        new.value = value
        assert new.location is not None

        full_path = os.path.join(self.dir, new.location)
        # for k,v in kwargs.items():
        #    print (f'{k}: {v}')
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, pd.DataFrame):
                    v.to_csv(f"{full_path}-){k}.csv")
                elif isinstance(v, matplotlib.figure.Figure):
                    v.savefig(f"{full_path}-){k}.png")
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return super().write(value, **kwargs)
