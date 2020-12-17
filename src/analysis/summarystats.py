#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 17 09:50:44 2020

@author: khs3z
"""

from analysis.absanalyzer import AbstractAnalyzer
import numpy as np
import pandas as pd

def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)
    percentile_.__name__ = '%s percentile' % n
    return percentile_    

class SummaryStats(AbstractAnalyzer):
    
    def __init__(self, data, categories, features, aggs=['count', 'min', 'max', 'mean', 'std', 'median', percentile(25), percentile(75)], singledf=True, flattenindex=True):
        AbstractAnalyzer.__init__(self, data, categories, features)
        self.name = "Summary Tables"
        self.aggs = aggs
        self.singledf = singledf
        self.flattenindex = flattenindex
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return []
    
    def get_configuration_dialog(self):
        pass
    
    def execute(self):
        summaries = {}
        allfunc_dict = self.analysis_functions['Summary Tables']['functions']
        agg_functions = [self.agg_functions[f] for f in self.aggs]
        if self.features is None or len(self.features) == 0:
            return summaries
        for header in self.features:
            #categories = [col for col in self.flimanalyzer.get_importer().get_parser().get_regexpatterns()]
            allcats = [x for x in self.categories]
            allcats.append(header)
            dftitle = ": ".join([titleprefix,header.replace('\n',' ')])
            if self.features is None or len(self.features) == 0:
                # create fake group by --> creates 'index' column that needs to removed from aggregate results
                summary = self.data[allcats].groupby(lambda _ : True, group_keys=False).agg(agg_functions)
            else:                
                #data = data.copy()
                #data.reset_index(inplace=True)
                grouped_data = self.data[allcats].groupby(self.categories, observed=True)
                summary = grouped_data.agg(agg_functions)
                #summary = summary.dropna()
            if self.flattenindex:
                summary.columns = ['\n'.join(col).strip() for col in summary.columns.values]    
            summaries[dftitle] = summary
        if self.singledf:
            concat_df = pd.concat([summaries[key] for key in summaries], axis=1)
            return {f"titleprefix - rows={len(self.data)}": concat_df}
        else:
            return summaries
