#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/17/20 10:44 AM
# @Author: Jiaxin_Zhang

from flim.analysis.absanalyzer import AbstractAnalyzer

import os
import random
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
from collections import defaultdict
from sklearn.preprocessing import LabelEncoder


class datasets(Dataset):

    def __init__(self, data, labels=[]):
        self.data = np.asarray(data)
        self.data_len = len(self.data)
        self.labels = np.asarray(labels)
        #self.transform = transforms.Compose([transforms.ToTensor()])

    def __getitem__(self, index):
        single_item = self.data[index]
        item_label = self.labels[index]
        return single_item, item_label

    def __len__(self):
        return self.data_len
        
        
class AETrainingConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, description=None, selectedgrouping=['None'], selectedfeatures='All', epoches=20, batch_size=200, learning_rate=1e-4, weight_decay=1e-7, timeseries='', model='', modelfile='', device='cpu', rescale=False):
        self.timeseries_opts = data.select_dtypes(include=['category']).columns.values
        self.timeseries = timeseries
        self.epoches = epoches
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.model = model
        self.model_opts = [a for a in autoencoder.get_autoencoder_classes()]
        self.modelfile = modelfile
        self.device = device
        self.rescale = rescale
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, description=description, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=0, optgridcols=1)
        self._update_model_info(None)
		    
    def get_option_panels(self):
        epoches_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.epoches_spinner = wx.SpinCtrl(self.panel,wx.ID_ANY,min=1,max=500,initial=self.epoches)
        epoches_sizer.Add(wx.StaticText(self.panel, label="Epoches"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        epoches_sizer.Add(self.epoches_spinner, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        batch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.batchsize_spinner = wx.SpinCtrl(self.panel,wx.ID_ANY,min=1,max=500,initial=self.batch_size)
        batch_sizer.Add(wx.StaticText(self.panel, label="Batch Size"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        batch_sizer.Add(self.batchsize_spinner, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        spinner_sizer = wx.BoxSizer(wx.VERTICAL)
        spinner_sizer.Add(epoches_sizer)
        spinner_sizer.Add(batch_sizer)

        learning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.learning_input = NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        learning_sizer.Add(wx.StaticText(self.panel, label="Learning Rate"), 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        learning_sizer.Add(self.learning_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        weight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.weight_input = NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.weight_decay, fractionWidth=10)
        weight_sizer.Add(wx.StaticText(self.panel, label="Weight Decay"), 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        weight_sizer.Add(self.weight_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        float_sizer = wx.BoxSizer(wx.VERTICAL)
        float_sizer.Add(learning_sizer)
        float_sizer.Add(weight_sizer)

        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=self.device, choices=['cpu', 'cuda'])
        self.rescale_checkbox = wx.CheckBox(self.panel, wx.ID_ANY, label="Rescale decoded")
        self.rescale_checkbox.SetValue(self.rescale)
        device_sizer.Add(wx.StaticText(self.panel, label="Device"), 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        device_sizer.Add(self.device_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        rescale_sizer = wx.BoxSizer(wx.VERTICAL)
        rescale_sizer.Add(device_sizer)
        rescale_sizer.Add(self.rescale_checkbox)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(spinner_sizer)
        top_sizer.Add(float_sizer)
        top_sizer.Add(rescale_sizer)

        timeseries_sizer = wx.BoxSizer(wx.HORIZONTAL)
        sel_timeseries = self.timeseries
        if sel_timeseries not in self.timeseries_opts:
            sel_timeseries = self.timeseries_opts[0]
        self.timeseries_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_timeseries, choices=self.timeseries_opts)
        timeseries_sizer.Add(wx.StaticText(self.panel, label="Time Series"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.timeseries_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        sel_model = self.model
        if sel_model not in self.model_opts:
            sel_model = self.model_opts[0]
        self.model_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_model, choices=self.model_opts)
        self.model_combobox.Bind(wx.EVT_COMBOBOX, self._update_model_info)
        
        self.modelfiletxt = wx.StaticText(self.panel, label=self.modelfile)        
        browsebutton = wx.Button(self.panel, wx.ID_ANY, 'Choose...')
        browsebutton.Bind(wx.EVT_BUTTON, self._on_browse)
        
        timeseries_sizer.Add(wx.StaticText(self.panel, label="Model Architecture"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.model_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(wx.StaticText(self.panel, label="Save Model"), 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(browsebutton, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        descr_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.model_descr = wx.TextCtrl(self.panel, value="None", size=(400,100), style=wx.TE_MULTILINE|wx.TE_READONLY|wx.SUNKEN_BORDER)
        self.model_layers = wx.TextCtrl(self.panel, value='None', size=(400,100), style=wx.TE_MULTILINE|wx.TE_READONLY|wx.SUNKEN_BORDER)
        descr_sizer.Add(self.model_descr, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        descr_sizer.Add(self.model_layers, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        #descr_sizer.Add(wx.StaticText(self, label="Weight Decay"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        #descr_sizer.Add(self.weight_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        all_sizer = wx.BoxSizer(wx.VERTICAL)
        all_sizer.Add(top_sizer)
        all_sizer.Add(timeseries_sizer)
        all_sizer.Add(descr_sizer)
        
        return [all_sizer]
        
    def _on_feature_selection(self, event):
        self._update_model_info(None)
    
    def _on_select_all(self, event):
        super()._on_select_all(event)
        self._update_model_info(None)
        
    def _on_deselect_all(self, event):
        super()._on_deselect_all(event)
        self._update_model_info(None)
        
    def _update_model_info(self, event):
        modelname = self.model_combobox.GetValue()
        batch_size = self.batchsize_spinner.GetValue()
        aeclasses = autoencoder.get_autoencoder_classes()
        sel_features = [self.allfeatures[key] for key in self.cboxes if self.cboxes[key].GetValue()]
        ae = autoencoder.create_instance(aeclasses[modelname], nb_param=len(sel_features))
        if ae:
            descr = ae.get_description()
            layer_txt = '\n'.join(str(ae).split('\n')[1:-1]) # strip first and last line
        else:  
            descr = 'No input features or model defined'
            layer_txt = descr
        self.model_descr.Replace(0, self.model_descr.GetLastPosition(), descr) 
        self.model_layers.Replace(0, self.model_layers.GetLastPosition(), layer_txt)
            
    def _on_browse(self, event):
        fpath = self.modelfiletxt.GetLabel()
        _,fname = os.path.split(fpath)
        with wx.FileDialog(self, 'Model File', style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as fileDialog:    
            fileDialog.SetPath(fpath)
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
        params['device'] = self.device_combobox.GetValue()
        params['rescale'] = self.rescale_checkbox.GetValue()
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
        self.device = self.params['device']
        self.rescale = self.params['rescale']

    def get_description(self):
        descr = "Train and save a new autoencoder model using selectable input features. " \
        + "Training and validation datasets are randomly split based on the specified Data Grouping. " \
        + "Device selection supports modeling on CPU or GPU (cuda) if available."
        return descr
        
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
        return ["any","any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
	        'epoches': 20, 
	        'learning_rate': 1e-4, 
	        'weight_decay': 1e-8, 
	        'batch_size': 128,
	        'timeseries': 'Treatment',
	        'modelfile': '',
            'grouping': ['FOV','Cell'],
            'features': ['FLIRR','FAD a1'],
            'model': 'Autoencoder 2',
            'device': 'cpu',
            'rescale': False,
        })
        return params
	 
    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AETrainingConfigDlg(parent, f'Configuration: {self.name}', self.data,
            description=self.get_description(), 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            epoches=self.params['epoches'], 
            batch_size=self.params['batch_size'],
            weight_decay=self.params['weight_decay'],
            learning_rate=self.params['learning_rate'],
            timeseries=self.params['timeseries'],
            model=self.params['model'],
            modelfile=self.params['modelfile'],
            device=self.params['device'],
            rescale=self.params['rescale'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params
   
    def _create_datasets(self):
        allcat_columns = [n for n in self.data.select_dtypes('category').columns]
        grouping = [n for n in self.params['grouping'] if n != self.params['timeseries']]
        columns = list(allcat_columns) # list(cat_columns)
        columns.extend(self.params['features'])

        # encode labels of all category columns
        label_encoders = defaultdict(LabelEncoder)
        data = self.data.loc[:,columns]
        data.loc[:,allcat_columns] = data.loc[:,allcat_columns].apply(lambda x: label_encoders[x.name].fit_transform(x))
        
        # define logical groups first, then split into train and validation set.
        g = data[columns].groupby(grouping)
        cat_groups = sorted(g.groups.keys())
        random.seed()
        train_cat = random.sample(cat_groups, k=int(np.around(0.7*len(cat_groups))))
        val_cat = [c for c in cat_groups if c not in train_cat]
        logging.debug (f'Groups for training: {sorted(train_cat)}')
        logging.debug (f'Groups for validation: {sorted(val_cat)}')
        train_df = pd.concat([g.get_group(group) for group in g.groups if group in train_cat] )
        val_df = pd.concat([g.get_group(group) for group in g.groups if group not in train_cat] )
        logging.debug(train_df.describe())
        logging.debug(val_df.describe())

        # normalize data, create dataloaders
        my_imputer = SimpleImputer(strategy="constant", fill_value=0)
        train_scaler = preprocessing.MinMaxScaler()
        training_set = train_df[self.params['features']].to_numpy(dtype=np.float32)
        training_set = train_scaler.fit_transform(training_set)
        training_set = my_imputer.fit_transform(training_set)
        train_labels = train_df[allcat_columns]
        train_dataset = datasets(training_set, labels=train_labels)
        train_loader = torch.utils.data.DataLoader(dataset=train_dataset,
                                                        batch_size=self.params['batch_size'],
                                                        shuffle=True)
        logging.debug(f'Training set shape: {training_set.shape}')

        val_scaler = preprocessing.MinMaxScaler()
        val_set = val_df[self.params['features']].to_numpy(dtype=np.float32)
        val_set = val_scaler.fit_transform(val_set)
        val_set = my_imputer.fit_transform(val_set)
        val_labels = val_df[allcat_columns]
        val_dataset = datasets(val_set, labels=val_labels)
        val_loader = torch.utils.data.DataLoader(dataset=val_dataset,
                                                        batch_size=self.params['batch_size'],
                                                        shuffle=True)
        logging.debug(f'Val set shape: {val_set.shape}')
                                                        
        return train_loader, val_loader, train_scaler, val_scaler, label_encoders

    def execute(self):
        logging.info('Training started.')
        train_loader, val_loader, train_scaler, val_scaler, label_encoders = self._create_datasets()
        aeclasses = autoencoder.get_autoencoder_classes()
        device = self.params['device']
        if self.params['device'] == 'cuda' and not torch.cuda.is_available():
            device = 'cpu'
            logging.info("CUDA selected, but no CUDA device available. Switching to CPU.")
        no_features = len(self.params['features'])    
        ae = autoencoder.create_instance(aeclasses[self.params['model']], nb_param=no_features).to(device)
        criterion = nn.MSELoss()#.cuda()
        optimizer = optim.RMSprop(ae.parameters(), self.params['learning_rate'], self.params['weight_decay'])

        loss_train = []
        loss_val = []

        # Train the autoencoder
        labels = []
        decoded = []#np.zeros((len(self.data),len(self.params['features'])))
        encoded = []#np.zeros((len(self.data),len(self.params['features'])))
        for epoch in range(1, self.params['epoches'] + 1):
            cum_loss = 0
            train_samples = 0
            for i, (batchinputs,batchlabels) in enumerate(train_loader):
                encoder_out, decoder_out = ae(batchinputs)
                if epoch == self.params['epoches']:
                    length = len(batchlabels)
                    # use int 0 to label as 'train'
                    labelarray = np.array(length*[0]).reshape(length,1)
                    labelarray = np.concatenate([batchlabels,labelarray], axis=1)
                    labels.append(labelarray)
                    batchout = decoder_out.detach().numpy()
                    decoded.append(batchout)
                    encod = encoder_out.detach().numpy()
                    encoded.append(encod)
                    train_samples += len(batchinputs) 

                loss = criterion(decoder_out, batchinputs)
                cum_loss += loss.data.item()

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                if (i + 1) % 100 == 0:
                    logging.debug('Train-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))
            loss_train.append(cum_loss / (i + 1))
            
            cum_loss = 0
            for (i, item) in enumerate(val_loader):
                batchinputs = item[0]#.cuda()
                batchlabels = item[1]
                encoder_out, decoder_out = ae(batchinputs)
                if epoch == self.params['epoches']:
                    length = len(batchlabels)
                    # use int 1 to label as 'validation'
                    labelarray = np.array(length*[1]).reshape(length,1)
                    labelarray = np.concatenate([batchlabels,labelarray], axis=1)
                    labels.append(labelarray)
                    batchout = decoder_out.detach().numpy()
                    decoded.append(batchout)
                    encod = encoder_out.detach().numpy()
                    encoded.append(encod)

                loss = criterion(decoder_out, batchinputs)
                cum_loss += loss.data.item()

            if (i + 1) % 100 == 0:
                logging.debug('Validation-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))
            loss_val.append(cum_loss / (i + 1))
        
        logging.debug(f'train_samples={train_samples}')

        encoded = np.concatenate(encoded)
        decoded = np.concatenate(decoded)
        if self.params['rescale']:
            decoded_train = train_scaler.inverse_transform(decoded[:train_samples])
            decoded_val = val_scaler.inverse_transform(decoded[train_samples:])
            decoded = np.concatenate([decoded_train, decoded_val])
        lcols = [n for n in self.data.select_dtypes('category').columns]
        lcols.append('Autoencoder')
        # create train/validation labels
        labels = np.concatenate(labels)
        label_df = pd.DataFrame(labels, columns=lcols)#, dtype='category')
        label_encoders['Autoencoder'].fit(['training','validation'])
        label_df = label_df.apply(lambda x: label_encoders[x.name].inverse_transform(x))
        label_df = label_df.astype('category')

        decoded_cols = [f'AE Recon {s}' for s in self.params['features']]
        decoded_df = pd.concat([label_df, pd.DataFrame(decoded, columns=decoded_cols, dtype=np.float32)], axis=1)
        encoded_cols = [f'AE Encoded {i}' for i in range(encod.shape[1])]
        encoded_df = pd.concat([label_df, pd.DataFrame(encoded[:,0:encod.shape[1]], columns=encoded_cols, dtype=np.float32)], axis=1)
        
        epoch_list = [str(e) for e in range(1,self.params['epoches']+1)]
        loss_df = pd.DataFrame({'Epoch':epoch_list, 'Training Loss':loss_train, 'Validation Loss':loss_val})
        loss_df['Epoch'] = loss_df['Epoch'].astype('category')
        
        logging.debug(f'loss_TrainingSet: {loss_train[-1]}')
        logging.debug(f'loss_TestSet: {loss_val[-1]}')
        logging.info('Training complete.')
        torch.save(ae, self.params['modelfile'])

        fig, ax = plt.subplots(constrained_layout=True)
        ax.plot(loss_train, 'b-', label='train-loss')
        ax.plot(loss_val, 'r-', label='val-loss')
        ax.grid('on')
        ax.set_ylabel('loss')
        ax.set_xlabel('epoch')
        ax.legend(['training', 'testing'], loc='upper right')
        self._add_picker(fig)
        return {'Plot: AE Loss': fig, 'AE Loss': loss_df, 'AE Train-Val Decoded': decoded_df, 'AE Train-Val Encoded': encoded_df}
