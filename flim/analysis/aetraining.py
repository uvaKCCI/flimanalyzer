#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/17/20 10:44 AM
# @Author: Jiaxin_Zhang

from flim.analysis.absanalyzer import AbstractAnalyzer

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.optim as optim
import torch.utils.data
from torch.utils.data.dataset import Dataset
from sklearn import preprocessing
from sklearn.impute import SimpleImputer
import flim.analysis.ml.autoencoder as autoencoder
import logging
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from wx.lib.masked import NumCtrl
from importlib_resources import files
import flim.resources

class datasets(Dataset):
    def __init__(self, data):
        self.data_arr = np.asarray(data)
        self.data_len = len(self.data_arr)

    def __getitem__(self, index):
        single_data = self.data_arr[index]
        return single_data

    def __len__(self):
        return self.data_len
        
        
class AETrainingConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', epoches=20, batch_size=200, learning_rate=1e-4, weight_decay=1e-7, timeseries='', model='', modelfile=''):
        self.timeseries_opts = data.select_dtypes(include=['category']).columns.values
        self.timeseries = timeseries
        self.epoches = epoches
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.model = model
        self.model_opts = [a for a in autoencoder.get_autoencoder_classes()]
        self.modelfile = modelfile
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=0, optgridcols=1)
		    
    def get_option_panels(self):
        epoches_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.epoches_spinner = wx.SpinCtrl(self,wx.ID_ANY,min=1,max=500,initial=self.epoches)
        epoches_sizer.Add(wx.StaticText(self, label="Epoches"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        epoches_sizer.Add(self.epoches_spinner, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        batch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.batchsize_spinner = wx.SpinCtrl(self,wx.ID_ANY,min=1,max=500,initial=self.batch_size)
        batch_sizer.Add(wx.StaticText(self, label="Batch Size"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        batch_sizer.Add(self.batchsize_spinner, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        spinner_sizer = wx.BoxSizer(wx.HORIZONTAL)
        spinner_sizer.Add(epoches_sizer)
        spinner_sizer.Add(batch_sizer)

        learning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.learning_input = NumCtrl(self,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        learning_sizer.Add(wx.StaticText(self, label="Learning Rate"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        learning_sizer.Add(self.learning_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        weight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.weight_input = NumCtrl(self,wx.ID_ANY, min=0.0, max=1.0, value=self.weight_decay, fractionWidth=10)
        weight_sizer.Add(wx.StaticText(self, label="Weight Decay"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        weight_sizer.Add(self.weight_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        float_sizer = wx.BoxSizer(wx.HORIZONTAL)
        float_sizer.Add(learning_sizer)
        float_sizer.Add(weight_sizer)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sel_timeseries = self.timeseries
        if sel_timeseries not in self.timeseries_opts:
            sel_timeseries = self.timeseries_opts[0]
        self.timeseries_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=sel_timeseries, choices=self.timeseries_opts)
        timeseries_sizer.Add(wx.StaticText(self, label="Time Series"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.timeseries_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        sel_model = self.model
        if sel_model not in self.model_opts:
            sel_model = self.model_opts[0]
        self.model_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=sel_model, choices=self.model_opts)

        self.modelfiletxt = wx.StaticText(self, label=self.modelfile)        
        browsebutton = wx.Button(self, wx.ID_ANY, 'Choose...')
        browsebutton.Bind(wx.EVT_BUTTON, self.OnBrowse)
        
        timeseries_sizer.Add(wx.StaticText(self, label="Model Architecture"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.model_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(wx.StaticText(self, label="Save Model to File"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(browsebutton, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(spinner_sizer)
        top_sizer.Add(float_sizer)

        return [top_sizer, timeseries_sizer]
        
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
        params['model'] = self.model_combobox.GetValue()
        return params
        
        
class AETraining(AbstractAnalyzer):

    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Autoencoder: Train"
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

    def get_icon(self):
        source = files(flim.resources).joinpath('aetrain.png')
        return wx.Bitmap(str(source))        

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
	        'timeseries': 'Treatment',
	        'modelfile': '',
            'grouping': ['FOV','Cell'],
            'features': ['FLIRR','FAD a1'],
            'model': 'Autoencoder 2'
	    }
	 
    def run_configuration_dialog(self, parent):
        dlg = AETrainingConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            epoches=self.params['epoches'], 
            batch_size=self.params['batch_size'],
            weight_decay=self.params['weight_decay'],
            learning_rate=self.params['learning_rate'],
            timeseries=self.params['timeseries'],
            model=self.params['model'],
            modelfile=self.params['modelfile'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params
   
    def _create_datasets(self):
        cat_columns = list(self.params['grouping'])
        cat_columns.append(self.params['timeseries'])
        columns = list(cat_columns)
        columns.extend(self.params['features'])
        self.data_copy = self.data[columns].copy()
        data_set = self.data[self.params['features']]
        counts = self.data_copy.groupby(cat_columns).count()

        FOV = self.data_copy.loc[:,self.params['grouping'][0]]
        FOV_u = np.unique(FOV)
        timepoint = self.data_copy.loc[:,self.params['timeseries']]
        tp_u = np.unique(timepoint)

        # Split data into training and test sets
        training_set = np.zeros([1, data_set.shape[1]])
        val_set = np.zeros([1, data_set.shape[1]])

        for t in range(len(tp_u)):
            mask_time = (timepoint == tp_u[t])
            data_t = self.data_copy[mask_time]

            for i in range(len(FOV_u)):
                col = self.params['grouping'][0]
                data_len = data_t[data_t[col]==FOV_u[i]]
                cell = data_len[self.params['grouping'][1]]
                cell = np.array(list(map(int, cell)))
                n_c = np.unique(cell)
                k = int(np.around(0.7 * len(n_c)))

                mask_train = (cell <= k)
                mask_val = (cell > k)
                data_t_mask = data_len[mask_train][self.params['features']]
                data_v_mask = data_len[mask_val][self.params['features']]
                training_set = np.append(training_set, data_t_mask, axis=0)
                val_set = np.append(val_set, data_v_mask, axis=0)

        training_set = training_set[1:]
        val_set = val_set[1:]

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
        t_set = np.array(self.training_set)
        v_set = np.array(self.val_set)
        training_frame = pd.DataFrame(t_set, index=None, columns=self.params['features'])
        val_frame = pd.DataFrame(v_set, index=None, columns=self.params['features'])

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
        aeclasses = autoencoder.get_autoencoder_classes()
        ae = autoencoder.create_instance(aeclasses[self.params['model']], nb_param=self.param)
        #ae = AE(self.param)
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
        torch.save(ae, self.params['modelfile'])

        fig, ax = plt.subplots(constrained_layout=True)
        ax.plot(loss_train, 'b-', label='train-loss')
        ax.plot(loss_val, 'r-', label='val-loss')
        ax.grid('on')
        ax.set_ylabel('loss')
        ax.set_xlabel('epoch')
        ax.legend(['training', 'testing'], loc='upper right')
        self._add_picker(fig)
        return {'loss': fig}
