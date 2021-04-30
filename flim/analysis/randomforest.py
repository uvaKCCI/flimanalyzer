#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import wx
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn import metrics
from flim.analysis.absanalyzer import AbstractAnalyzer
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources

class RandomForestConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', classifier='', importancehisto=True, n_estimators=100, test_size=0.3):
        self.classifieropts = data.select_dtypes(['category']).columns.values
        if classifier in self.classifieropts:
            self.classifier = classifier
        else:
            self.classifier = self.classifieropts[0]
        self.importancehisto = importancehisto
        self.n_estimators = n_estimators
        self.test_size = test_size
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=1, optgridcols=1)
		    
    def get_option_panels(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.classifier_selector = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.classifier, choices=self.classifieropts)
        sizer.Add(wx.StaticText(self, id=wx.ID_ANY, label="Classifier"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.classifier_selector, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.n_estimators_spinner = wx.SpinCtrl(self,wx.ID_ANY,min=1,max=500,initial=self.n_estimators)
        sizer.Add(wx.StaticText(self, label="N-estimator"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.n_estimators_spinner, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.test_size_input = NumCtrl(self,wx.ID_ANY, min=0.0, max=1.0, value=self.test_size, fractionWidth=10)
        sizer.Add(wx.StaticText(self, label="Test size"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        sizer.Add(self.test_size_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        self.importancehisto_cb = wx.CheckBox(self, id=wx.ID_ANY, label="Importance histogram")
        self.importancehisto_cb.SetValue(self.importancehisto)
        sizer.Add(self.importancehisto_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [sizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['classifier'] = self.classifier_selector.GetValue()
        params['importancehisto'] = self.importancehisto_cb.GetValue()
        params['n_estimators'] = self.n_estimators_spinner.GetValue()
        params['test_size'] = self.test_size_input.GetValue()
        return params
        
        
class RandomForest(AbstractAnalyzer):
    
    def __init__(self, data, classifier=None, importancehisto=True, n_estimators=100, test_size=0.3, **kwargs):
        AbstractAnalyzer.__init__(self, data, classifier=classifier, importancehisto=importancehisto, n_estimators=n_estimators, test_size=test_size, **kwargs)
        self.name = "Random Forest"
    
    def __repr__(self):
        return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('randomforest.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return ['any']
    
    def get_required_features(self):
        return ['any']
    
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'classifier': '',
            'n_estimators': 100, 
            'test_size': 0.3,
            'importancehisto': True})
        return params    
        
    def run_configuration_dialog(self, parent):
        dlg = RandomForestConfigDlg(parent, f'Configuration: {self.name}', self.data, 
           selectedgrouping=self.params['grouping'], 
           selectedfeatures=self.params['features'], 
           classifier=self.params['classifier'],
           n_estimators=self.params['n_estimators'],
           test_size=self.params['test_size'],
           importancehisto=self.params['importancehisto'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        parameters = dlg.get_selected()  
        self.configure(**parameters)
        return parameters

        category_cols = self.data.select_dtypes(['category']).columns.values
        dlg = wx.SingleChoiceDialog(parent, 'Choose feature to be used as classifier', 'Random Forest Classifier', category_cols)
        if dlg.ShowModal() == wx.ID_OK:
            parameters = {'classifier': dlg.GetStringSelection()}
            self.configure(**parameters)
            return parameters
        return  # explicit None
    
    def execute(self):
        results = {}
        data = self.data.dropna(how='any', axis=0)
        data_features = [f for f in self.params['features'] if f not in self.params['grouping']]
        X = data[data_features]  # Features
        y = data[self.params['classifier']]  # one of the categorical columns
        # Split dataset into training set and test set
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=self.params['test_size'])
        #Create a Gaussian Classifier
        clf = RandomForestClassifier(n_estimators=self.params['n_estimators'])
        #Train the model using the training sets y_pred=clf.predict(X_test)
        clf.fit(X_train,y_train)

        y_pred=clf.predict(X_test)
        
        accuracy = metrics.accuracy_score(y_test, y_pred)
        featurecol = 'Feature'
        importance_df = pd.DataFrame({featurecol: self.params['features'], 'Importance Score':clf.feature_importances_})
        importance_df[featurecol] = importance_df[featurecol].astype('category')
        importance_df.sort_values(by='Importance Score', ascending=False, inplace=True)
        if self.params['importancehisto']:
            importance_plot = importance_df.set_index('Feature').plot.bar()
            fig = importance_plot.get_figure()
            ax = fig.get_axes()[0]
            ax.text(0.95, 0.80, f'accuracy={accuracy:.3f}', 
                        horizontalalignment='right',
                        verticalalignment='center',
                        transform = ax.transAxes)
            results['Importance Score Plot'] = fig
        # results['Accuracy'] = accuracy
        results['Importance Score Data'] = importance_df
        return results
            
