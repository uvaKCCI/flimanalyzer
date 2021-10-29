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

class datasets(Dataset):

    def __init__(self, data, labels=[]):
        self.data_arr = np.asarray(data)
        self.data_len = len(self.data_arr)
        self.labels = labels
        #self.transform = transforms.Compose([transforms.ToTensor()])

    def __getitem__(self, index):
        single_data = self.data_arr[index]
        item_label = self.labels[index]
        #labels = [c for c in self.categories[index]]
        #labels.append(self.label)
        return single_data, '|'.join(item_label)

    def __len__(self):
        return self.data_len
        
        
class AETrainingConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', epoches=20, batch_size=200, learning_rate=1e-4, weight_decay=1e-7, timeseries='', model='', modelfile='', device='cpu'):
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

        spinner_sizer = wx.BoxSizer(wx.VERTICAL)
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

        float_sizer = wx.BoxSizer(wx.VERTICAL)
        float_sizer.Add(learning_sizer)
        float_sizer.Add(weight_sizer)

        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(self, wx.ID_ANY, style=wx.CB_READONLY, value=self.device, choices=['cpu', 'cuda'])
        device_sizer.Add(wx.StaticText(self, label="Device"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        device_sizer.Add(self.device_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

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
        top_sizer.Add(device_sizer)

        return [top_sizer, timeseries_sizer]
        
    def OnBrowse(self, event):
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
            'device': 'cpu'
        })
        return params
	 
    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AETrainingConfigDlg(parent, f'Configuration: {self.name}', self.data, 
            selectedgrouping=self.params['grouping'], 
            selectedfeatures=self.params['features'], 
            epoches=self.params['epoches'], 
            batch_size=self.params['batch_size'],
            weight_decay=self.params['weight_decay'],
            learning_rate=self.params['learning_rate'],
            timeseries=self.params['timeseries'],
            model=self.params['model'],
            modelfile=self.params['modelfile'],
            device=self.params['device'])
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return # implicit None
        self.params = dlg.get_selected()
        self.configure(**self.params)
        return self.params
   
    def _create_datasets(self):
        allcat_columns = [n for n in self.data.select_dtypes('category').columns]
        grouping = [n for n in self.params['grouping'] if n != self.params['timeseries']]
        cat_columns = list(grouping)
        cat_columns.append(self.params['timeseries'])
        columns = list(allcat_columns) # list(cat_columns)
        columns.extend(self.params['features'])
        print (f'allcat_columns: {allcat_columns}')
        print (f'cat_columns: {cat_columns}')
        print (f'columns: {columns}')

        g = self.data[columns].groupby(grouping)
        cat_groups = sorted(g.groups.keys())
        random.seed()
        train_cat = random.sample(cat_groups, k=int(np.around(0.7*len(cat_groups))))
        val_cat = [c for c in cat_groups if c not in train_cat]
        logging.debug ('Groups for training: {sorted(train_cat)}')
        logging.debug ('Groups for validation: {sorted(val_cat)}')
        train_df = pd.concat([g.get_group(group) for group in g.groups if group in train_cat] )
        val_df = pd.concat([g.get_group(group) for group in g.groups if group not in train_cat] )

        """"
        self.data_copy = self.data[columns].copy()
        data_set = self.data[self.params['features']]
        counts = self.data_copy.groupby(cat_columns).count()

        FOV = self.data_copy.loc[:,grouping[0]]
        FOV_u = np.unique(FOV)
        timepoint = self.data_copy.loc[:,self.params['timeseries']]
        tp_u = np.unique(timepoint)

        # Split data into training and test sets
        training_set = np.zeros([1, data_set.shape[1]])
        training_labels = np.zeros([1, len(allcat_columns)])
        val_set = np.zeros([1, data_set.shape[1]])
        val_labels = np.zeros([1, len(allcat_columns)])

        
        
        print (f'tp_u={tp_u}')
        print (f'FOV_u={FOV_u}')
        for t in range(len(tp_u)):
            mask_time = (timepoint == tp_u[t])
            data_t = self.data_copy[mask_time]

            for i in range(len(FOV_u)):
                col = grouping[0]
                data_len = data_t[data_t[col]==FOV_u[i]]
                cell = data_len[grouping[1]]
                cell = np.array(list(map(int, cell)))
                n_c = np.unique(cell)
                k = int(np.around(0.7 * len(n_c)))
                print (tp_u[t], FOV_u[i], 'cell', k, 'out of', n_c)

                mask_train = (cell <= k)
                mask_val = (cell > k)
                data_t_mask = data_len[mask_train][self.params['features']]
                data_v_mask = data_len[mask_val][self.params['features']]
                training_set = np.append(training_set, data_t_mask, axis=0)
                training_labels = np.append(training_labels, data_len[mask_train][allcat_columns], axis=0)
                val_set = np.append(val_set, data_v_mask, axis=0)
                val_labels = np.append(val_labels, data_len[mask_val][allcat_columns], axis=0)

        training_set = training_set[1:]
        training_labels = training_labels[1:]
        val_set = val_set[1:]
        val_labels = val_labels[1:]
        """
        lcols = list(allcat_columns)
        lcols.append('Label')
        train_df['Label'] = ['train'] * len(train_df)
        training_set = train_df[self.params['features']].to_numpy(dtype=np.float32)
        training_labels = train_df[lcols].to_numpy()
        val_df['Label'] = ['validate'] * len(val_df)
        val_set = val_df[self.params['features']].to_numpy(dtype=np.float32)
        val_labels = val_df[lcols].to_numpy()
        print ('train_labels',training_labels[:3])
        print ('val_labels',val_labels[:3])
        print(train_df.head())
        print(val_df.head())

        my_imputer = SimpleImputer(strategy="constant", fill_value=0)
        min_max_scaler = preprocessing.MinMaxScaler()

        #training_set = training_set.astype(float)
        training_set_1 = min_max_scaler.fit_transform(training_set)  # Normalization
        training_set = my_imputer.fit_transform(training_set_1)
        self.training_set = torch.FloatTensor(training_set)
        self.no_columns = self.training_set.size(1)
        logging.debug(f'Training set shape: {self.training_set.size()}')
        logging.debug(f'Training set contains {self.training_set.size(0)} rows, {self.training_set.size(1)} columns')


        #val_set = val_set.astype(float)
        val_set_1 = min_max_scaler.fit_transform(val_set)  # Normalization
        val_set = my_imputer.fit_transform(val_set_1)
        self.val_set = torch.FloatTensor(val_set)
        logging.debug(f'Val set shape: {self.val_set.size()}')
        logging.debug("Test set contains %d rows, %d columns" % (self.val_set.size(0), (self.val_set.size(1))))

        t_set = np.array(self.training_set)
        v_set = np.array(self.val_set)
        training_frame = pd.DataFrame(t_set, index=None, columns=self.params['features'])
        val_frame = pd.DataFrame(v_set, index=None, columns=self.params['features'])

        train_dataset = datasets(training_frame, labels=training_labels)
        val_dataset = datasets(val_frame, labels=val_labels)
        for i,item in enumerate(train_dataset):
            if i>10:
                break
            logging.debug(item)
        self.train_loader = torch.utils.data.DataLoader(dataset=train_dataset,
                                                        batch_size=self.params['batch_size'],
                                                        shuffle=True)
        self.val_loader = torch.utils.data.DataLoader(dataset=val_dataset,
                                                    batch_size=self.params['batch_size'],
                                                    shuffle=True)
        return self.train_loader

    def execute(self):
        logging.info('Training started.')
        self._create_datasets()
        aeclasses = autoencoder.get_autoencoder_classes()
        device = self.params['device']
        if self.params['device'] == 'cuda' and not torch.cuda.is_available():
            device = 'cpu'
            logging.info("CUDA selected, but no CUDA device available. Switching to CPU.")
        ae = autoencoder.create_instance(aeclasses[self.params['model']], nb_param=self.no_columns).to(device)
        criterion = nn.MSELoss()#.cuda()
        optimizer = optim.RMSprop(ae.parameters(), self.params['learning_rate'], self.params['weight_decay'])

        loss_train = []
        loss_val = []

        # Train the autoencoder
        labels = ['?'] * len(self.data)
        decoded = np.zeros((len(self.data),len(self.params['features'])))
        encoded = np.zeros((len(self.data),len(self.params['features'])))
        for epoch in range(1, self.params['epoches'] + 1):
            cum_loss = 0
            start = 0
            for (i, item) in enumerate(self.train_loader):
                batchinputs = item[0]#.cuda()
                batchlabels = item[1]
                encoder_out, decoder_out = ae(batchinputs)
                if epoch == self.params['epoches']-1:
                    end = start + len(batchinputs) 
                    labels[start:end] = batchlabels
                    batchout = decoder_out.detach().numpy()
                    decoded[start:end, 0:batchout.shape[1]] = batchout
                    encod = encoder_out.detach().numpy()
                    encoded[start:end, 0:encod.shape[1]] = encod
                    # print (f'encod.shape={encod.shape}, encoded.shape={encoded.shape}, outdated.shape={decoded.shape}')
                    start = end

                loss = criterion(decoder_out, batchinputs)
                cum_loss += loss.data.item()

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                if (i + 1) % 100 == 0:
                    logging.debug('Train-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))
                
            loss_train.append(cum_loss / (i + 1))
            
            cum_loss = 0
            for (i, item) in enumerate(self.val_loader):
                batchinputs = item[0]#.cuda()
                batchlabels = item[1]
                encoder_out, decoder_out = ae(batchinputs)
                if epoch == self.params['epoches']-1:
                    end = start + len(batchinputs) 
                    labels[start:end] = batchlabels
                    batchout = decoder_out.detach().numpy()
                    decoded[start:end, 0:batchout.shape[1]] = batchout
                    encod = encoder_out.detach().numpy()
                    encoded[start:end, 0:encod.shape[1]] = encod
                    start = end

                loss = criterion(decoder_out, batchinputs)
                cum_loss += loss.data.item()

            #np.savetxt(f'valoutput{i}.csv',decoder_out.detach().numpy(),delimiter=',')
            
            if (i + 1) % 100 == 0:
                logging.debug('Validation-epoch %d. Iteration %05d, Avg-Loss: %.4f' % (epoch, i + 1, cum_loss / (i + 1)))

            loss_val.append(cum_loss / (i + 1))
        
        lcols = [n for n in self.data.select_dtypes('category').columns]
        lcols.append('AE Label')
        print (labels[0])
        labels = [l.split('|') for l in labels]
        label_df = pd.DataFrame(labels, columns=lcols)

        decoded_df = pd.DataFrame(decoded, columns=self.params['features'])
        decoded_df['Label'] = [','.join(l) for l in labels]
        decoded_df['Label'] = decoded_df['Label'].astype('category')

        encoded_df = pd.DataFrame(encoded[:,0:encod.shape[1]], columns=[f'AE encoded {i}' for i in range(encod.shape[1])])
        encoded_df['Label'] = [','.join(l) for l in labels]
        encoded_df['Label'] = encoded_df['Label'].astype('category')
        
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
        return {'loss': fig, 'AE Train-Val Data': decoded_df, 'AE encoded': encoded_df, 'Labels': label_df}
