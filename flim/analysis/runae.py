#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 03/30/21 10:44 AM
# @Author: Jiaxin_Zhang

import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.autograd import Variable
import matplotlib.pyplot as plt
from sklearn.impute import SimpleImputer
from sklearn import preprocessing
from flim.gui.dialogs import BasicAnalysisConfigDlg
import flim.analysis.ml.autoencoder as autoencoder
import wx
from wx.lib.masked import NumCtrl

from flim.analysis.absanalyzer import AbstractAnalyzer
import flim.resources
from importlib_resources import files, as_file


class AERunningConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', modelfile=''):
        self.modelfile = modelfile
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping,
                                        selectedfeatures=selectedfeatures, optgridrows=0, optgridcols=1)

    def get_option_panels(self):
        self.modelfiletxt = wx.StaticText(self, label=self.modelfile)
        browsebutton = wx.Button(self, wx.ID_ANY, 'Choose...')
        browsebutton.Bind(wx.EVT_BUTTON, self.OnBrowse)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        timeseries_sizer.Add(wx.StaticText(self, label="Load Model from File"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(browsebutton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        return [timeseries_sizer]

    def OnBrowse(self, event):
        fname = self.modelfiletxt.GetLabel()
        with wx.FileDialog(self, 'Model File', style=wx.FD_OPEN) as fileDialog:
            fileDialog.SetFilename(fname)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.modelfiletxt.SetLabel(fname)

    def _get_selected(self):
        params = super()._get_selected()
        params['modelfile'] = self.modelfiletxt.GetLabel()
        return params


class RunAE(AbstractAnalyzer):

    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Autoencoder: Run"
        self.variables = self.params['features']
        self.modelfile = self.params['modelfile']

    def __repr__(self):
        return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_icon(self):
        source = files(flim.resources).joinpath('aerun.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'modelfile': ''
        })
        return params

    def run_configuration_dialog(self, parent):
        dlg = AERunningConfigDlg(parent, f'Configuration: {self.name}', self.data,
                                  selectedgrouping=self.params['grouping'],
                                  selectedfeatures=self.params['features'],
                                  modelfile=self.params['modelfile'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params

    def execute(self):
        data_feat = self.data[self.params['features']]

        # load an AE model
        ae = torch.load(self.params['modelfile'], map_location = 'cpu')

        data_feat = data_feat.astype(float)
        print('ROI shape:',data_feat.shape)
        my_imputer = SimpleImputer(strategy="constant",fill_value=0)
        min_max_scaler = preprocessing.MinMaxScaler()
        data_feat = min_max_scaler.fit_transform(data_feat) # Normalization
        data_feat = my_imputer.fit_transform(data_feat)

        data_feat = torch.FloatTensor(data_feat)
        print('original:\n',data_feat)

        data_input = Variable(data_feat)
        features, reconstructed = ae(data_input)
        print('Reconstructed:\n',reconstructed.data)
        print('Reconstructed shape:', reconstructed.shape)

        features=torch.squeeze(features)
        print('Features shape:',features.shape)
        print('Features:\n',features.data)
        print('\n')

        criterion = nn.MSELoss()
        loss = criterion(reconstructed, data_feat)
        print(loss.data)
