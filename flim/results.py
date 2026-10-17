#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 12:45:21 2022

@author: khs3z
"""
import os
import logging
import matplotlib.figure
import pandas as pd
import re
from joblib import dump


def clean_path_component(name: str) -> str:
    """Makes a result/tag name usable as a file or directory name."""
    name = (
        str(name)
        .replace("%", "pcent")
        .replace("\r", "")
        .replace("\n", " ")
        .replace("|", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )
    return re.sub(r":\s?", "_", name)


def save_results(results, directory: str, name: str) -> None:
    """Saves a plugin's results below ``directory``.

    The complete result is pickled to ``<directory>/pickled/<name>``. If the result is a
    dict, each DataFrame is also written as ``<key>.txt``, each Figure as ``<key>.png``
    and any other value pickled as ``<key>`` in ``directory``.

    Args:
        results: plugin result, usually a dict of DataFrames and/or Figures.
        directory (str): target directory, created if it does not exist.
        name (str): name of the task that produced the results.
    """
    pickledir = os.path.join(directory, "pickled")
    os.makedirs(pickledir, exist_ok=True)
    dump(results, os.path.join(pickledir, clean_path_component(name)))
    logging.debug(f"Saving results of {name} to {directory}")
    if not isinstance(results, dict):
        return
    for k, v in results.items():
        basename = os.path.join(directory, clean_path_component(k))
        if isinstance(v, pd.DataFrame):
            v = v.copy()
            # if index was flattened in analyzer.summarize_data, multiindex col values
            # were joined with '\n'--> revert here
            v.columns = [str(c).replace("\n", " ") for c in v.columns.values]
            v.to_csv(f"{basename}.txt")
        elif isinstance(v, matplotlib.figure.Figure):
            v.savefig(f"{basename}.png")
        else:
            dump(v, basename)
