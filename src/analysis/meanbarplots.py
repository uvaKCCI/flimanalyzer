#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

from analysis.absanalyzer import AbstractAnalyzer

class MeanBarPlots(AbstractAnalyzer):
    
    def __init__(self, data, categories, features, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories, features, **kwargs)
        self.name = "Mean Bar Plots"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def configure(self,params):
        pass

    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return []
    
    def get_configuration_dialog(self):
        pass
    
    def execute(self):
        pass