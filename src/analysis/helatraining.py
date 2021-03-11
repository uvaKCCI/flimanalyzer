#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/17/20 10:44 AM
# @Author: Jiaxin_Zhang

from analysis.absanalyzer import AbstractAnalyzer

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.optim as optim
import torch.utils.data
from sklearn import preprocessing
from sklearn.impute import SimpleImputer
from MLfeatureanalyzer.autoencoder2 import AE
from MLfeatureanalyzer.dataset import datasets
import logging
from gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl

class HelatrainingConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', epoches=20, batch_size=200, learning_rate=1e-4, weight_decay=1e-7, timeseries='', modelfile=''):
        self.timeseries_opts = data.select_dtypes(include=['category']).columns.values
        self.timeseries = timeseries
        self.epoches = epoches
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.modelfile = modelfile
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', optgridrows=0, optgridcols=2)
		    
    def get_option_panels(self):
        epoches_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.epoches_spinner = wx.SpinCtrl(self,wx.ID_ANY,min=1,max=500,initial=self.epoches)
        epoches_sizer.Add(wx.StaticText(self, label="Epoches"))
        epoches_sizer.Add(self.epoches_spinner, 0, wx.ALL|wx.EXPAND, 5)
        
        batch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.batchsize_spinner = wx.SpinCtrl(self,wx.ID_ANY,min=1,max=500,initial=self.batch_size)
        batch_sizer.Add(wx.StaticText(self, label="Batch Size"))
        batch_sizer.Add(self.batchsize_spinner, 0, wx.ALL|wx.EXPAND, 5)

        spinner_sizer = wx.BoxSizer(wx.HORIZONTAL)
        spinner_sizer.Add(epoches_sizer)
        spinner_sizer.Add(batch_sizer)

        learning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.learning_input = NumCtrl(self,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        learning_sizer.Add(wx.StaticText(self, label="Learning Rate"))
        learning_sizer.Add(self.learning_input, 0, wx.ALL|wx.EXPAND, 5)

        weight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.weight_input = NumCtrl(self,wx.ID_ANY, min=0.0, max=1.0, value=self.weight_decay, fractionWidth=10)
        weight_sizer.Add(wx.StaticText(self, label="Weight Decay"))
        weight_sizer.Add(self.weight_input, 0, wx.ALL|wx.EXPAND, 5)

        float_sizer = wx.BoxSizer(wx.HORIZONTAL)
        float_sizer.Add(learning_sizer)
        float_sizer.Add(weight_sizer)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sel_timeseries = self.timeseries
        if sel_timeseries not in self.timeseries_opts:
            sel_timeseries = self.timeseries_opts[0]
        self.timeseries_combobox = wx.ComboBox(self, wx.ID_ANY, value=sel_timeseries, choices=self.timeseries_opts)
        timeseries_sizer.Add(wx.StaticText(self, label="Time Series"))
        timeseries_sizer.Add(self.timeseries_combobox)

        model_sizer = wx.BoxSizer(wx.HORIZONTAL)
        model_sizer.Add(wx.StaticText(self, label="Save Model to File"))
        self.modelfiletxt = wx.StaticText(self, label=self.modelfile)
        browsebutton = wx.Button(self, wx.ID_ANY, 'Choose...')
        browsebutton.Bind(wx.EVT_BUTTON, self.OnBrowse)
        model_sizer.Add(self.modelfiletxt)
        model_sizer.Add(browsebutton)

        return [spinner_sizer, float_sizer, timeseries_sizer, model_sizer]
        
    def OnBrowse(self, event):
        fname = self.modelfiletxt.GetLabel()
        with wx.FileDialog(self, 'Model File', style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as fileDialog:    
            fileDialog.SetFilename(fname)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.modelfiletxt.SetLabel(fname)                

    def _get_selected(self):
        params = super()._get_selected()
        params['epoches'] = self.epoches_spinner.GetValue()
        params['batch_size'] = self.batchsize_spinner.GetValue()
        params['learning_rate'] = self.learning_input.GetValue()
        params['weight_decay'] = self.weight_input.GetValue()
        params['timeseries'] = self.timeseries_combobox.GetValue()
        params['modelfile'] = self.modelfiletxt.GetLabel()
        return params
        
        
class Helatraining(AbstractAnalyzer):

    def __init__(self, data, categories, features, **kwargs):
        AbstractAnalyzer.__init__(self, data, grouping=categories, features=features, **kwargs)
        self.name = "Hela Training"
        self.variables = self.params['features']
        self.epoches = self.params['epoches']
        self.timeseries = self.params['timeseries']
        self.modelfile = self.params['modelfile']
        self.lr = self.params['learning_rate']
        self.wd = self.params['weight_decay']
        self.bs = self.params['batch_size']

    def __repr__(self):
        return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_required_categories(self):
        return ["any"]

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
	    return {
	        'epoches': 20, 
	        'learning_rate': 1e-4, 
	        'weight_decay': 1e-7, 
	        'batch_size': 200,
	        'timeseries': '',
	        'modelfile': '',
	    }
	 
    def run_configuration_dialog(self, parent):
        dlg = HelatrainingConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            epoches=self.params['epoches'], 
            batch_size=self.params['batch_size'],
            weight_decay=self.params['weight_decay'],
            learning_rate=self.params['learning_rate'],
            timeseries=self.params['timeseries'],
            modelfile=self.params['modelfile'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        parameters = dlg.get_selected()  
        self.configure(**parameters)
        return parameters
   
    def _create_datasets(self):
        # self.data.rename(columns={'FLIRR':'FLIRR (NAD(P)H a2[%]/FAD a1[%])'}, inplace=True)

        ind = list(self.data.columns)
        ind_cell = ind.index('Cell')
        ind_fov = ind.index('FOV')
        ind_tre = ind.index('Treatment')
        self.len_info = ind_tre+1

        g = self.data.loc[:,self.variables]
        info = self.data.iloc[:, 0:self.len_info]
        data_set = pd.concat([info, g],axis=1)
        self.data_copy = data_set.copy()

        FOV = self.data_copy.loc[:,'FOV']
        FOV_u = np.unique(FOV)
        timepoint = self.data_copy.loc[:,'Treatment']
        tp_u = np.unique(timepoint)

        f = self.data.loc[:,'FLIRR']
        self.data_set_f = pd.concat([data_set,f],axis=1)
        data_set = np.array(data_set)
        data_set_f_np = np.array(self.data_set_f)

        # Split data into training and test sets
        training_set = np.zeros([1, data_set.shape[1]])
        val_set = np.zeros([1, data_set.shape[1]])

        for t in range(len(tp_u)):
            mask_time = (timepoint == tp_u[t])
            data_t = data_set_f_np[mask_time]

            for i in range(len(FOV_u)):
                data_len = data_t[data_t[:, ind_fov] == FOV_u[i]]
                cell = data_len[:, ind_cell]
                cell = np.array(list(map(int, cell)))
                print(cell)
                n_c = np.unique(cell)
                k = int(np.around(0.7 * len(n_c)))

                mask_train = (cell <= k)
                mask_val = (cell > k)
                data_t_mask = data_len[mask_train][:, :-1]
                data_v_mask = data_len[mask_val][:, :-1]
                training_set = np.append(training_set, data_t_mask, axis=0)
                val_set = np.append(val_set, data_v_mask, axis=0)
                # print('training', training_set.shape)
                # print('val', val_set.shape)

        training_set = training_set[1:, self.len_info:]
        val_set = val_set[1:, self.len_info:]

        my_imputer = SimpleImputer(strategy="constant", fill_value=0)
        min_max_scaler = preprocessing.MinMaxScaler()

        training_set_1 = training_set.astype(float)
        training_set_1 = min_max_scaler.fit_transform(training_set_1)  # Normalization
        training_set = my_imputer.fit_transform(training_set_1)
        self.training_set = torch.FloatTensor(training_set)
        self.param = self.training_set.size(1)
        print('Training set shape:', self.training_set.size())
        logging.basicConfig(filename='my.log', level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
        logging.info("Training set contains %d rows, %d columns" % (self.training_set.size(0), (self.training_set.size(1))))


        val_set_1 = val_set.astype(float)
        val_set_1 = min_max_scaler.fit_transform(val_set_1)  # Normalization
        val_set = my_imputer.fit_transform(val_set_1)
        self.val_set = torch.FloatTensor(val_set)
        print('Val set shape:', self.val_set.size())
        logging.info("Test set contains %d rows, %d columns" % (self.val_set.size(0), (self.val_set.size(1))))


    def _load_data(self):
        col = self.data_copy.columns.values[self.len_info:]
        t_set = np.array(self.training_set)
        v_set = np.array(self.val_set)
        training_frame = pd.DataFrame(t_set, index=None, columns=col)
        val_frame = pd.DataFrame(v_set, index=None, columns=col)

        train_dataset = datasets(training_frame)
        val_dataset = datasets(val_frame)
        self.train_loader = torch.utils.data.DataLoader(dataset=train_dataset,
                                                        batch_size=self.bs,
                                                        shuffle=True)
        self.val_loader = torch.utils.data.DataLoader(dataset=val_dataset,
                                                    batch_size=self.bs,
                                                    shuffle=True)
        return self.train_loader

    def execute(self):
        self._create_datasets()
        self._load_data()
        ae = AE(self.param)
        ae = ae.cuda()
        criterion = nn.MSELoss().cuda()
        optimizer = optim.RMSprop(ae.parameters(), self.lr, self.wd)

        loss_train = []
        loss_val = []

        logging.basicConfig(filename='AEloss.log', level=logging.DEBUG,
                            format="%(asctime)s - %(levelname)s - %(message)s", filemode='w')

        # Train the autoencoder
        for epoch in range(1, self.epoches + 1):
            cum_loss = 0

            for (i, inputs) in enumerate(self.train_loader):
                inputs = inputs.cuda()
                encoder_out, decoder_out = ae(inputs)

                loss = criterion(decoder_out, inputs)
                cum_loss += loss.data.item()

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                if (i + 1) % 100 == 0:
                    print('Train-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))
                    logging.info('Train-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))

            loss_train.append(cum_loss / (i + 1))
            cum_loss = 0

            for (i, inputs) in enumerate(self.val_loader):
                inputs = inputs.cuda()
                encoder_out, decoder_out = ae(inputs)

                loss = criterion(decoder_out, inputs)
                cum_loss += loss.data.item()

            print('Validation-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))
            logging.info('Validation-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))

            loss_val.append(cum_loss / (i + 1))

        print("\n")
        print("loss_TrainingSet:",loss_train[-1])
        print("loss_TestSet:",loss_val[-1])
        print("\nTraining complete!\n")
        torch.save(ae, self.data + '_autoencoder.pkl')

        fig, ax = plt.subplots()
        # plt.figure(figsize=(10, 4))
        ax.plot(loss_train, 'b-', label='train-loss')
        ax.plot(loss_val, 'r-', label='val-loss')
        ax.grid('on')
        ax.ylabel('loss')
        ax.xlabel('epoch')
        ax.legend(['training', 'testing'], loc='upper right')
        return {'loss': (fig, ax)}
