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
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl


class PCAnalysisConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, 
            selectedgrouping=['None'], 
            selectedfeatures='All', 
            keeporig=False, 
            keepstd=True,
            explainedhisto=False,
            n_components=None):

        self.allfeatures = data.select_dtypes(include=['number'], exclude=['category']).columns.values
        self.keeporig = keeporig
        self.keepstd = keepstd
        self.explainedhisto = explainedhisto
        self.n_components = n_components
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=2, optgridcols=1)
		    
    def get_option_panels(self):
        helptxt = f'Specifiy PCA components to retain:'\
                                 '\n\tleave empty:   retain all PCA components.'\
                                 '\n\t0.0 < n < 1.0 (float):   retain PCA components that explain specified fraction of observed variance.'\
                                 '\n\t1 <= n <= {len(self.allfeatures)} (integer):   retain first n PCA components.'
        
        helpsizer = wx.BoxSizer(wx.HORIZONTAL)
        helpsizer.Add(wx.StaticText(self, label=helptxt), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.n_components_input = NumCtrl(self,wx.ID_ANY, min=0.0, max=float(len(self.allfeatures)), value=self.n_components, fractionWidth=3)
        sizer.Add(wx.StaticText(self, label="N-components"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.n_components_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.keeporig_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Include original data")
        self.keeporig_cb.SetValue(self.keeporig)
        sizer.Add(self.keeporig_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.keepstd_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Include standardized data")
        self.keepstd_cb.SetValue(self.keepstd)
        sizer.Add(self.keepstd_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.explainedhisto_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Explained histogram")
        self.explainedhisto_cb.SetValue(self.explainedhisto)
        sizer.Add(self.explainedhisto_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [helpsizer, sizer]
        
    def _get_selected(self):
        n_comps = self.n_components_input.GetValue()
        if n_comps >= 1.0:
           # convert float to int
           n_comps = int(n_comps)
        params = super()._get_selected()
        params['keeporig'] = self.keeporig_cb.GetValue()
        params['keepstd'] = self.keepstd_cb.GetValue()
        params['n_components'] = n_comps
        params['explainedhisto'] = self.explainedhisto_cb.GetValue()

        return params


class PCAnalysis(AbstractAnalyzer):
    
    def __init__(self, data, keeporig=False, keepstd=True, explainedhisto=False, **kwargs):
        AbstractAnalyzer.__init__(self, data, keeporig=keeporig, keepstd=keepstd, explainedhisto=explainedhisto, **kwargs)
        self.name = "Principal Component Analysis"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_required_categories(self):
        return []
    
    def get_icon(self):
        return wx.Bitmap("resources/pca.png")
        
    def get_required_features(self):
        return ['any', 'any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'keeporig':False, 
            'keepstd':True,
            'explainedhisto': False,
            'n_components': 0.999,
            })
        return params
            
    def run_configuration_dialog(self, parent):
        dlg = PCAnalysisConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            keeporig=self.params['keeporig'], 
            keepstd=self.params['keepstd'],
            explainedhisto=self.params['explainedhisto'],
            n_components=self.params['n_components'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params    
    
        n = ''
        dlg = wx.TextEntryDialog(parent, 'Specifiy PCA components to retain:'\
                                 '\n\tleave empty:   retain all PCA components.'\
                                 '\n\t0.0 < n < 1.0 (float):   retain PCA components that explain specified fraction of observed variance.'\
                                 '\n\t1 <= n <= %d (integer):   retain first n PCA components.' % len(self.params['features']),'PCA Configuration')
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
            if n is None or (n > 0 and ((isinstance(n, float) and n <1.0) or (isinstance(n, int) and n >= 1 and n <= len(self.params['features'])))):
                seed = np.random.randint(10000000)
                parameters = {
                    'random_state': seed,
                    'n_components': n}
                self.configure(**parameters)
                return parameters
        return  # explicit None
    
    
    def execute(self):
        data = self.data.dropna(how='any', axis=0).reset_index()
        features = self.params['features']
        if len(features) == 1:
            # reshape 1d array
            data_no_class = data[features].values.reshape((-1,1))
        else:
            data_no_class = data[features].values
        scaler = StandardScaler()
        scaler.fit(data_no_class)
        standard_data = scaler.transform(data_no_class)
        standard_data
        
        pca_params = {k: self.params[k] for k in self.params if k not in ['keeporig', 'keepstd', 'explainedhisto', 'features', 'grouping']}
        pca = PCA(**pca_params)
        principalComponents = pca.fit_transform(standard_data)
        
        pca_df = pd.DataFrame(
            data = principalComponents,
            columns = ['Principal component %d' % x for x in range(1,principalComponents.shape[1]+1)])
        if self.params['keeporig'] and self.params['keepstd']:
            standard_df = pd.DataFrame(
                data = standard_data,
                columns = ["%s\nstandardized" % c for c in features])
            pca_df = pd.concat([data.select_dtypes(include='category'), data[features], standard_df, pca_df] , axis=1) #.reset_index(drop=True)
        elif self.params['keeporig']:    
            pca_df = pd.concat([data.select_dtypes(include='category'), data[features], pca_df] , axis=1) #.reset_index(drop=True)
        elif self.params['keepstd']:
            standard_df = pd.DataFrame(
                data = standard_data,
                columns = ["%s\nstandardized" % f for f in features])
            pca_df = pd.concat([data.select_dtypes(include='category'), standard_df, pca_df] , axis=1) #.reset_index(drop=True)
        else:
            pca_df = pd.concat([data.select_dtypes(include='category'), pca_df] , axis=1) #.reset_index(drop=True)                        
        pca_comp_label = 'PCA component'
        explained_label = 'explained var ratio'
        pca_explained_df = pd.DataFrame(data={
                pca_comp_label: range(1,len(pca.explained_variance_ratio_)+1), 
                explained_label: pca.explained_variance_ratio_})
        pca_explained_df[pca_comp_label] = pca_explained_df[pca_comp_label].astype('category')

        
        results = {
            'PCA': pca_df,
            'PCA explained': pca_explained_df}
        if self.params['explainedhisto']:
            plot = pca_explained_df.set_index(pca_comp_label).plot.bar()
            results['PCA Plot'] = plot.get_figure()
        return results
            
