#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 03/30/21 10:44 AM
# @Author: Jiaxin_Zhang

import logging
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

from flim.plugin import AbstractPlugin
import flim.resources
from importlib_resources import files, as_file
from flim.plugin import plugin


class AERunningConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', modelfile='', device='cpu'):
        self.modelfile = modelfile
        self.device = device
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping,
                                        selectedfeatures=selectedfeatures, optgridrows=0, optgridcols=1)

    def get_option_panels(self):
        self.modelfiletxt = wx.StaticText(self.panel, label=self.modelfile)
        browsebutton = wx.Button(self.panel, wx.ID_ANY, 'Choose...')
        browsebutton.Bind(wx.EVT_BUTTON, self.OnBrowse)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        timeseries_sizer.Add(wx.StaticText(self.panel, label="Load Model"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(browsebutton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)

        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=self.device, choices=['cpu', 'cuda'])
        device_sizer.Add(wx.StaticText(self.panel, label="Device"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        device_sizer.Add(self.device_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        return [timeseries_sizer, device_sizer]

    def OnBrowse(self, event):
        fpath = self.modelfiletxt.GetLabel()
        _,fname = os.path.split(fpath)
        with wx.FileDialog(self, 'Model File', style=wx.FD_OPEN) as fileDialog:
            fileDialog.SetPath(fpath)
            fileDialog.SetFilename(fname)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.modelfiletxt.SetLabel(fname)

    def _get_selected(self):
        params = super()._get_selected()
        params['modelfile'] = self.modelfiletxt.GetLabel()
        params['device'] = self.device_combobox.GetValue()
        return params


@plugin(plugintype='Analysis')
class RunAE(AbstractPlugin):

    def __init__(self, data, **kwargs):
        AbstractPlugin.__init__(self, data, **kwargs)
        self.name = "Autoencoder: Run"
        self.variables = self.params['features']
        self.modelfile = self.params['modelfile']
        self.device = self.params['device']

    #def __repr__(self):
    #    return f"{'name': {self.name}}"

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
            'modelfile': '',
            'device': 'cpu',
        })
        return params

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AERunningConfigDlg(parent, f'Configuration: {self.name}', self.data,
                                  selectedgrouping=self.params['grouping'],
                                  selectedfeatures=self.params['features'],
                                  modelfile=self.params['modelfile'],
                                  device=self.params['device'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params

    def execute(self):
        data_feat = self.data[self.params['features']]

        # load an AE model
        device = self.params['device']
        if self.params['device'] == 'cuda' and not torch.cuda.is_available():
            device = 'cpu'
            logging.info("CUDA selected, but no CUDA device available. Switching to CPU.")
        ae = torch.load(self.params['modelfile'], map_location = device)

        data_feat = data_feat.astype(float)
        my_imputer = SimpleImputer(strategy="constant",fill_value=0)
        min_max_scaler = preprocessing.MinMaxScaler()
        data_feat = min_max_scaler.fit_transform(data_feat) # Normalization
        data_feat = my_imputer.fit_transform(data_feat)

        data_feat = torch.FloatTensor(data_feat)
        logging.debug(f'original shape: {data_feat.shape}')

        data_input = Variable(data_feat)
        features, reconstructed = ae(data_input)
        logging.debug(f'Reconstructed shape: {reconstructed.shape}')

        features=torch.squeeze(features)
        logging.debug(f'Features shape: {features.shape}')

        criterion = nn.MSELoss()
        loss = criterion(reconstructed, data_feat)
        logging.debug(f'Loss: {loss.data}')
        
        recon_data = reconstructed.detach().numpy()
        features_data = features.detach().numpy()
        len_features = 1 if len(features_data.shape) == 1 else features_data.shape[1]
        recon_df = pd.DataFrame(recon_data,columns=[f'Recon Feature {i}' for i in range(1,recon_data.shape[1]+1)])
        features_df = pd.DataFrame(features_data,columns=[f'Feature {i}' for i in range(1,len_features+1)])
        return {'Reconstructed': recon_df, 'Features': features_df}
