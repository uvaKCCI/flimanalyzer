#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from analysis.absanalyzer import AbstractAnalyzer


class PCAnalysis(AbstractAnalyzer):
    
    def __init__(self, data, categories, features, keeporig=False, keepstd=True, explainedhisto=False, **kwargs):
        AbstractAnalyzer.__init__(self, data, categories, features, keeporig=keeporig, keepstd=keepstd, explainedhisto=explainedhisto, **kwargs)
        self.name = "Principal Component Analysis"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any', 'any']
    
    def run_configuration_dialog(self, parent):
        n = ''
        dlg = wx.TextEntryDialog(parent, 'Specifiy PCA components to retain:'\
                                 '\n\tleave empty:   retain all PCA components.'\
                                 '\n\t0.0 < n < 1.0 (float):   retain PCA components that explain specified fraction of observed variance.'\
                                 '\n\t1 <= n <= %d (integer):   retain first n PCA components.' % len(self.features),'PCA Configuration')
        dlg.SetValue(n)
        while True:
            if dlg.ShowModal() != wx.ID_OK:
                return
            entry = dlg.GetValue()
            if entry == '':
                n = None
            else:    
                try:
                    n = float(entry)
                    n = int(entry)
                except:
                    pass
            if n is None or (n > 0 and ((isinstance(n, float) and n <1.0) or (isinstance(n, int) and n >= 1 and n <= len(self.features)))):
                seed = np.random.randint(10000000)
                parameters = {
                    'random_state': seed,
                    'n_components': n}
                self.configure(**parameters)
                return parameters
        return  # explicit None
    
    
    #def pca(self, data, columns, keeporig=False, keepstd=True, explainedhisto=False, **kwargs):

    def execute(self):
        data = self.data.dropna(how='any', axis=0).reset_index()
        if len(self.features) == 1:
            # reshape 1d array
            data_no_class = data[self.features].values.reshape((-1,1))
        else:
            data_no_class = data[self.features].values
        scaler = StandardScaler()
        scaler.fit(data_no_class)
        standard_data = scaler.transform(data_no_class)
        standard_data
        
        pca_params = {k: self.params[k] for k in self.params if k not in ['keeporig', 'keepstd', 'explainedhisto']}
        pca = PCA(**pca_params)
        principalComponents = pca.fit_transform(standard_data)
        
        pca_df = pd.DataFrame(
            data = principalComponents,
            columns = ['Principal component %d' % x for x in range(1,principalComponents.shape[1]+1)])
        if self.params['keeporig'] and self.params['keepstd']:
            standard_df = pd.DataFrame(
                data = standard_data,
                columns = ["%s\nstandardized" % c for c in self.features])
            pca_df = pd.concat([data.select_dtypes(include='category'), data[self.features], standard_df, pca_df] , axis=1) #.reset_index(drop=True)
        elif self.params['keeporig']:    
            pca_df = pd.concat([data.select_dtypes(include='category'), data[self.features], pca_df] , axis=1) #.reset_index(drop=True)
        elif self.params['keepstd']:
            standard_df = pd.DataFrame(
                data = standard_data,
                columns = ["%s\nstandardized" % f for f in self.features])
            pca_df = pd.concat([data.select_dtypes(include='category'), standard_df, pca_df] , axis=1) #.reset_index(drop=True)
        else:
            pca_df = pd.concat([data.select_dtypes(include='category'), pca_df] , axis=1) #.reset_index(drop=True)                        
        pca_comp_label = 'PCA component'
        explained_label = 'explained var ratio'
        pca_explained_df = pd.DataFrame(data={
                pca_comp_label: range(1,len(pca.explained_variance_ratio_)+1), 
                explained_label: pca.explained_variance_ratio_})

        results = {
            'PCA': pca_df,
            'PCA explained': pca_explained_df}
        if self.params['explainedhisto']:
            results['PCA Plot'] = pca_explained_df.set_index(pca_comp_label).plot.bar()
        return results
            
