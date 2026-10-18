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

    The result without its figures is pickled to ``<directory>/pickled/<name>``. If
    the result is a dict, each DataFrame is also written as ``<key>.txt``, each Figure
    as ``<key>.png`` and any other value pickled as ``<key>`` in ``directory``.

    Figures are only saved as PNG: pickling them is slow for figures with many
    points, and the pickles only work with the matplotlib version that wrote them.

    Args:
        results: plugin result, usually a dict of DataFrames and/or Figures.
        directory (str): target directory, created if it does not exist.
        name (str): name of the task that produced the results.
    """
    os.makedirs(directory, exist_ok=True)
    logging.debug(f"Saving results of {name} to {directory}")
    if isinstance(results, dict):
        to_pickle = {
            k: v for k, v in results.items() if not isinstance(v, matplotlib.figure.Figure)
        }
    else:
        to_pickle = None if isinstance(results, matplotlib.figure.Figure) else results
    if to_pickle is not None and not (isinstance(to_pickle, dict) and not to_pickle):
        pickledir = os.path.join(directory, "pickled")
        os.makedirs(pickledir, exist_ok=True)
        dump(to_pickle, os.path.join(pickledir, clean_path_component(name)))
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
