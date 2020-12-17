#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 23:01:55 2020

@author: khs3z
"""

import os
import pkgutil
import importlib
import analysis.absanalyzer
from analysis.absanalyzer import AbstractAnalyzer

pkdir = os.path.dirname(__file__)
for (module_loader, name, ispkg) in pkgutil.iter_modules([pkdir]):
    importlib.import_module('.' + name, __package__)
available_tools = {str(analysis.absanalyzer.create_instance(cls, None, None, None)): cls for cls in AbstractAnalyzer.__subclasses__()}
