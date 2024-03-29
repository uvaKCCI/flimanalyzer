#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/17/20 10:44 AM
# @Author: Jiaxin_Zhang

import copy
import itertools
import logging
import os
import random
from collections import defaultdict

import flim.analysis.ml.autoencoder as autoencoder
import flim.resources
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.optim as optim
import torch.utils.data
import wx
from flim import utils
from flim.gui.dialogs import BasicAnalysisConfigDlg
from flim.plugin import AbstractPlugin, plugin
from importlib_resources import files
from joblib import dump
from matplotlib.ticker import MaxNLocator
from sklearn import preprocessing
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder
from torch.utils.data.dataset import Dataset
from wx.lib.masked import NumCtrl


class datasets(Dataset):
    def __init__(self, data, labels=[]):
        self.data = np.asarray(data)
        self.data_len = len(self.data)
        self.labels = np.asarray(labels)
        # self.transform = transforms.Compose([transforms.ToTensor()])

    def __getitem__(self, index):
        single_item = self.data[index]
        item_label = self.labels[index]
        return single_item, item_label

    def __len__(self):
        return self.data_len


class AETrainingConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input={},
        description=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        epoches=20,
        batch_size=200,
        learning_rate=1e-4,
        weight_decay=1e-7,
        timeseries="",
        model="",
        modelfile="",
        device="cpu",
        rescale=False,
        checkpoint_interval=20,
        autosave=True,
        working_dir="",
    ):
        data = next(iter(input.values()))
        self.timeseries_opts = data.select_dtypes(include=["category"]).columns.values
        self.timeseries = timeseries
        self.epoches = epoches
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.model = model
        self.model_opts = [a for a in autoencoder.get_autoencoder_classes()]
        self.working_dir = working_dir
        self.modelfile = modelfile
        self.device = device
        self.rescale = rescale
        self.checkpoint_interval = checkpoint_interval
        super().__init__(
            parent,
            title,
            input=input,
            description=description,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=0,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )
        self._update_model_info(None)

    def get_option_panels(self):
        epoches_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.epoches_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, min=1, max=500, initial=self.epoches
        )
        epoches_sizer.Add(
            wx.StaticText(self.panel, label="Epoches"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        epoches_sizer.Add(
            self.epoches_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        batch_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # self.batchsize_spinner = wx.SpinCtrl(self.panel,wx.ID_ANY,min=1,max=4096,initial=self.batch_size)
        self.batchsize_input = wx.TextCtrl(
            self.panel, wx.ID_ANY, value=utils.to_str_sequence(self.batch_size)
        )  # NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        batch_sizer.Add(
            wx.StaticText(self.panel, label="Batch Size"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        batch_sizer.Add(
            self.batchsize_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        checkpoint_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.checkpoint_spinner = wx.SpinCtrl(
            self.panel, wx.ID_ANY, min=1, max=500, initial=self.checkpoint_interval
        )
        checkpoint_sizer.Add(
            wx.StaticText(self.panel, label="Save interval"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        checkpoint_sizer.Add(
            self.checkpoint_spinner, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        spinner_sizer = wx.BoxSizer(wx.VERTICAL)
        spinner_sizer.Add(epoches_sizer)
        spinner_sizer.Add(batch_sizer)
        spinner_sizer.Add(checkpoint_sizer)

        learning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.learning_input = wx.TextCtrl(
            self.panel, wx.ID_ANY, value=utils.to_str_sequence(self.learning_rate)
        )  # NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.learning_rate, fractionWidth=10)
        learning_sizer.Add(
            wx.StaticText(self.panel, label="Learning Rate"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        learning_sizer.Add(
            self.learning_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        weight_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.weight_input = wx.TextCtrl(
            self.panel, wx.ID_ANY, value=utils.to_str_sequence(self.weight_decay)
        )  # NumCtrl(self.panel,wx.ID_ANY, min=0.0, max=1.0, value=self.weight_decay, fractionWidth=10)
        weight_sizer.Add(
            wx.StaticText(self.panel, label="Weight Decay"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        weight_sizer.Add(
            self.weight_input, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        float_sizer = wx.BoxSizer(wx.VERTICAL)
        float_sizer.Add(learning_sizer)
        float_sizer.Add(weight_sizer)

        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.device_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=self.device,
            choices=["cpu", "cuda"],
        )
        self.rescale_checkbox = wx.CheckBox(
            self.panel, wx.ID_ANY, label="Rescale decoded"
        )
        self.rescale_checkbox.SetValue(self.rescale)
        device_sizer.Add(
            wx.StaticText(self.panel, label="Device"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        device_sizer.Add(
            self.device_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

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
        self.timeseries_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_timeseries,
            choices=self.timeseries_opts,
        )
        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Time Series"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(
            self.timeseries_combobox,
            0,
            wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL,
            5,
        )

        sel_model = self.model
        if sel_model not in self.model_opts:
            sel_model = self.model_opts[0]
        self.model_combobox = wx.ComboBox(
            self.panel,
            wx.ID_ANY,
            style=wx.CB_READONLY,
            value=sel_model,
            choices=self.model_opts,
        )
        self.model_combobox.Bind(wx.EVT_COMBOBOX, self._update_model_info)

        self.modelfiletxt = wx.StaticText(self.panel, label=self.modelfile)
        browsebutton = wx.Button(self.panel, wx.ID_ANY, "Choose...")
        browsebutton.Bind(wx.EVT_BUTTON, self._on_browse)

        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Model Architecture"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(
            self.model_combobox, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        timeseries_sizer.Add(
            wx.StaticText(self.panel, label="Save Model"),
            1,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        timeseries_sizer.Add(self.modelfiletxt, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        timeseries_sizer.Add(
            browsebutton, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )

        descr_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.model_descr = wx.TextCtrl(
            self.panel,
            value="None",
            size=(400, 100),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.SUNKEN_BORDER,
        )
        self.model_layers = wx.TextCtrl(
            self.panel,
            value="None",
            size=(400, 100),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.SUNKEN_BORDER,
        )
        descr_sizer.Add(self.model_descr, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        descr_sizer.Add(
            self.model_layers, 0, wx.ALL | wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5
        )
        # descr_sizer.Add(wx.StaticText(self, label="Weight Decay"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        # descr_sizer.Add(self.weight_input, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        all_sizer = wx.BoxSizer(wx.VERTICAL)
        all_sizer.Add(top_sizer)
        all_sizer.Add(timeseries_sizer)
        all_sizer.Add(descr_sizer)

        return [all_sizer]

    def _on_feature_selection(self, event):
        self._update_model_info(None)

    def OnSelectAll(self, event):
        super().OnSelectAll(event)
        self._update_model_info(None)

    def OnDeselectAll(self, event):
        super().OnDeselectAll(event)
        self._update_model_info(None)

    def _update_model_info(self, event):
        modelname = self.model_combobox.GetValue()
        # batch_size = self.batchsize_spinner.GetValue()
        aeclasses = autoencoder.get_autoencoder_classes()
        sel_features = [
            self.allfeatures[key] for key in self.cboxes if self.cboxes[key].GetValue()
        ]
        ae = autoencoder.create_instance(
            aeclasses[modelname], nb_param=len(sel_features)
        )
        if ae:
            descr = ae.get_description()
            layer_txt = "\n".join(
                str(ae).split("\n")[1:-1]
            )  # strip first and last line
        else:
            descr = "No input features or model defined"
            layer_txt = descr
        self.model_descr.Replace(0, self.model_descr.GetLastPosition(), descr)
        self.model_layers.Replace(0, self.model_layers.GetLastPosition(), layer_txt)

    def _on_browse(self, event):
        with wx.FileDialog(
            self, "Model File", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as fileDialog:
            fileDialog.SetPath(self.working_dir)
            fileDialog.SetFilename(self.modelfile)
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            fname = fileDialog.GetPath()
            self.working_dir, self.modelfile = os.path.split(fname)
            self.modelfiletxt.SetLabel(self.modelfile)

    def _get_selected(self):
        params = super()._get_selected()
        params["epoches"] = self.epoches_spinner.GetValue()
        params["batch_size"] = [
            int(i) for i in self.batchsize_input.GetValue().split(",")
        ]
        params["learning_rate"] = [
            float(i) for i in self.learning_input.GetValue().split(",")
        ]
        params["weight_decay"] = [
            float(i) for i in self.weight_input.GetValue().split(",")
        ]
        params["timeseries"] = self.timeseries_combobox.GetValue()
        params["working_dir"] = self.working_dir
        params["modelfile"] = self.modelfile
        params["model"] = self.model_combobox.GetValue()
        params["device"] = self.device_combobox.GetValue()
        params["rescale"] = self.rescale_checkbox.GetValue()
        params["checkpoint_interval"] = self.checkpoint_spinner.GetValue()
        return params


@plugin(plugintype="Analysis")
class AETraining(AbstractPlugin):
    def __init__(self, name="Autoencoder: Train", **kwargs):
        super().__init__(name=name, **kwargs)
        self.variables = self.params["features"]
        self.epoches = self.params["epoches"]
        self.timeseries = self.params["timeseries"]
        self.working_dir = self.params["working_dir"]
        self.modelfile = self.params["modelfile"]
        self.lr = self.params["learning_rate"]
        self.wd = self.params["weight_decay"]
        self.bs = self.params["batch_size"]
        self.device = self.params["device"]
        self.rescale = self.params["rescale"]
        self.checkpoint_interval = self.params["checkpoint_interval"]

    def get_description(self):
        descr = (
            "Train and save a new autoencoder model using selectable input features. "
            + "Training and validation datasets are randomly split based on the"
            " specified Data Grouping. "
            + "Device selection supports modeling on CPU or GPU (cuda) if available."
        )
        return descr

    def get_icon(self):
        source = files(flim.resources).joinpath("aetrain.png")
        return wx.Bitmap(str(source))

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any", "any"]

    def get_mapped_parameters(self):
        parallel_params = []
        sizes = self.params["batch_size"]
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        combinations = list(itertools.product(sizes, rates, decays))
        for size, rate, decay in combinations:
            param = self.params.copy()
            param["batch_size"] = [size]
            param["learning_rate"] = [rate]
            param["weight_decay"] = [decay]
            parallel_params.append(param)
        return parallel_params

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "epoches": 20,
                "learning_rate": [1e-4],
                "weight_decay": [1e-8],
                "batch_size": [128],
                "timeseries": "Treatment",
                "modelfile": "AEModel",
                "grouping": ["FOV", "Cell"],
                "features": [
                    "FAD a1",
                    "FAD a2",
                    "FAD t1",
                    "FAD t2",
                    "FAD photons",
                    "NAD(P)H a1",
                    "NAD(P)H a2",
                    "NAD(P)H t1",
                    "NAD(P)H t2",
                    "NAD(P)H photons",
                ],
                "model": "Autoencoder 2",
                "device": "cpu",
                "rescale": False,
                "create_plots": True,
                "train_size": 0.7,  # 0.0 < train_size < 1.0
                "checkpoint_interval": 20,
            }
        )
        return params

    def output_definition(self):
        output = {}
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        sizes = self.params["batch_size"]
        combinations = list(itertools.product(sizes, rates, decays))
        for size, rate, decay in combinations:
            output.update(
                {
                    f"Table: AE Loss-{size}-{rate}-{decay}": pd.DataFrame,
                    f"Table: AE Decoded-{size}-{rate}-{decay}": pd.DataFrame,
                    f"Table: AE Encoded-{size}-{rate}-{decay}": pd.DataFrame,
                    "Model File": str,
                }
            )
            if self.params["create_plots"]:
                output.update(
                    {
                        f"Plot: AE Loss-{size}-{rate}-{decay}": matplotlib.figure.Figure,
                    }
                )
        return output

    def run_configuration_dialog(self, parent, data_choices={}):
        dlg = AETrainingConfigDlg(
            parent,
            f"Configuration: {self.name}",
            input=self.input,
            description=self.get_description(),
            selectedgrouping=self.params["grouping"],
            selectedfeatures=self.params["features"],
            epoches=self.params["epoches"],
            batch_size=self.params["batch_size"],
            weight_decay=self.params["weight_decay"],
            learning_rate=self.params["learning_rate"],
            timeseries=self.params["timeseries"],
            model=self.params["model"],
            modelfile=self.params["modelfile"],
            device=self.params["device"],
            rescale=self.params["rescale"],
            checkpoint_interval=self.params["checkpoint_interval"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_CANCEL:
            dlg.Destroy()
            return  # implicit None
        params = dlg.get_selected()
        self.configure(**params)
        return self.params

    def _create_datasets(self, batch_size):
        train_size = self.params["train_size"]
        data = list(self.input.values())[0]
        allcat_columns = [n for n in data.select_dtypes("category").columns]
        grouping = [
            n for n in self.params["grouping"] if n != self.params["timeseries"]
        ]
        columns = list(allcat_columns)  # list(cat_columns)
        columns.extend(self.params["features"])

        # encode labels of all category columns
        label_encoders = defaultdict(LabelEncoder)
        data = data.loc[:, columns]
        data.loc[:, allcat_columns] = data.loc[:, allcat_columns].apply(
            lambda x: label_encoders[x.name].fit_transform(x)
        )

        random.seed()
        if len(grouping) > 0:
            # define logical groups first, then split into train and validation set.
            g = data[columns].groupby(grouping)
            cat_groups = sorted(g.groups.keys())
            train_cat = random.sample(
                cat_groups, k=int(np.around(train_size * len(cat_groups)))
            )
            val_cat = [c for c in cat_groups if c not in train_cat]
            logging.debug(f"Groups for training: {sorted(train_cat)}")
            logging.debug(f"Groups for validation: {sorted(val_cat)}")
            train_df = pd.concat(
                [g.get_group(group) for group in g.groups if group in train_cat]
            )
            val_df = pd.concat(
                [g.get_group(group) for group in g.groups if group not in train_cat]
            )
        else:
            train_df = data.sample(n=int(np.around(train_size * len(data))))
            val_df = pd.concat([data, train_df, train_df]).drop_duplicates(keep=False)
        logging.debug(train_df.describe())
        logging.debug(val_df.describe())

        # normalize data, create dataloaders
        my_imputer = SimpleImputer(strategy="constant", fill_value=0)
        train_scaler = preprocessing.MinMaxScaler()

        training_set = train_df[self.params["features"]].to_numpy(dtype=np.float32)
        train_scaler = train_scaler.fit(training_set)
        training_set = train_scaler.transform(training_set)
        my_imputer = my_imputer.fit(training_set)
        training_set = my_imputer.transform(training_set)
        train_labels = train_df[allcat_columns]
        train_dataset = datasets(training_set, labels=train_labels)
        train_loader = torch.utils.data.DataLoader(
            dataset=train_dataset, batch_size=batch_size, shuffle=True
        )
        logging.debug(f"Training set shape: {training_set.shape}")

        val_set = val_df[self.params["features"]].to_numpy(dtype=np.float32)
        # use train scaler & imputer to decrease information leak from train to validation set
        val_set = train_scaler.transform(val_set)
        val_set = my_imputer.transform(val_set)  # fit_transform(val_set)
        val_labels = val_df[allcat_columns]
        val_dataset = datasets(val_set, labels=val_labels)
        val_loader = torch.utils.data.DataLoader(
            dataset=val_dataset, batch_size=batch_size, shuffle=True
        )
        logging.debug(f"Val set shape: {val_set.shape}")

        return train_loader, val_loader, train_scaler, my_imputer, label_encoders

    def execute(self):
        data = next(iter(self.input.values()))
        logging.debug(f"aetrain on: {data.columns.values}")
        rates = self.params["learning_rate"]
        decays = self.params["weight_decay"]
        sizes = self.params["batch_size"]
        combinations = utils.combine(sizes, rates, decays)
        results = {}
        for size, rate, decay in combinations:
            (
                train_loader,
                val_loader,
                input_scaler,
                imputer,
                label_encoders,
            ) = self._create_datasets(size)
            r = self.train(
                data,
                rate,
                decay,
                size,
                train_loader,
                val_loader,
                input_scaler,
                imputer,
                label_encoders,
            )
            for key in r:
                if key in results:
                    r[key] = results[key] + r[key]
            results.update(r)
        return results

    def train(
        self,
        data,
        learning_rate,
        weight_decay,
        batch_size,
        train_loader,
        val_loader,
        input_scaler,
        imputer,
        label_encoders,
    ):
        results = {}
        modelfile = os.path.join(
            self.params["working_dir"],
            f'{self.params["modelfile"]}_{batch_size}_{learning_rate}_{weight_decay}',
        )
        logging.info("Training started.")
        aeclasses = autoencoder.get_autoencoder_classes()
        device = self.params["device"]
        if self.params["device"] == "cuda" and not torch.cuda.is_available():
            device = "cpu"
            logging.info(
                "CUDA selected, but no CUDA device available. Switching to CPU."
            )
        no_features = len(self.params["features"])
        ae = autoencoder.create_instance(
            aeclasses[self.params["model"]], nb_param=no_features
        ).to(device)
        criterion = nn.MSELoss()  # .cuda()
        optimizer = optim.RMSprop(ae.parameters(), learning_rate, weight_decay)

        loss_train = []
        loss_val = []

        # Train the autoencoder
        labels = []
        decoded = []  # np.zeros((len(self.data),len(self.params['features'])))
        encoded = []  # np.zeros((len(self.data),len(self.params['features'])))
        checkpoints = []
        for epoch in range(1, self.params["epoches"] + 1):
            cum_loss = 0
            train_samples = 0
            for i, (batchinputs, batchlabels) in enumerate(train_loader):
                encoder_out, decoder_out = ae(batchinputs) #runs inputs through autoencoder
                if epoch == self.params["epoches"]:
                    length = len(batchlabels)
                    # use int 0 to label as 'train'
                    labelarray = np.array(length * [0]).reshape(length, 1)
                    labelarray = np.concatenate([batchlabels, labelarray], axis=1)
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
                optimizer.step() #improve by one step based on the loss

            loss_train.append(cum_loss / (i + 1))
            logging.debug("Epoch %d., Train loss: %.4f" % (epoch, loss_train[-1]))

            cum_loss = 0
            for i, item in enumerate(val_loader): #validation step
                batchinputs = item[0]  # .cuda()
                batchlabels = item[1]
                encoder_out, decoder_out = ae(batchinputs)
                if epoch == self.params["epoches"]:
                    length = len(batchlabels)
                    # use int 1 to label as 'validation'
                    labelarray = np.array(length * [1]).reshape(length, 1)
                    labelarray = np.concatenate([batchlabels, labelarray], axis=1)
                    labels.append(labelarray)
                    batchout = decoder_out.detach().numpy()
                    decoded.append(batchout)
                    encod = encoder_out.detach().numpy()
                    encoded.append(encod)

                loss = criterion(decoder_out, batchinputs)
                cum_loss += loss.data.item()

            loss_val.append(cum_loss / (i + 1))
            logging.debug("Epoch %d., Test loss: %.4f" % (epoch, loss_val[-1]))

            if (
                epoch == self.params["epoches"]
                or epoch % self.params["checkpoint_interval"] == 0
            ):
                ae_clone = autoencoder.create_instance(
                    aeclasses[self.params["model"]], nb_param=no_features
                ).to(device)
                ae_clone.load_state_dict(ae.state_dict())
                checkpoints.append((epoch, ae_clone))

        logging.debug(f"train_samples={train_samples}")

        encoded = np.concatenate(encoded)
        decoded = np.concatenate(decoded)
        if self.params["rescale"]:
            decoded_train = input_scaler.inverse_transform(decoded[:train_samples])
            decoded_val = input_scaler.inverse_transform(decoded[train_samples:])
            decoded = np.concatenate([decoded_train, decoded_val])
        lcols = [n for n in data.select_dtypes("category").columns]
        lcols.append("Autoencoder")
        # create train/validation labels
        labels = np.concatenate(labels)
        label_df = pd.DataFrame(labels, columns=lcols)  # , dtype='category')
        label_encoders["Autoencoder"].fit(["training", "validation"])
        label_df = label_df.apply(lambda x: label_encoders[x.name].inverse_transform(x))
        label_df = label_df.astype("category")

        decoded_cols = [f"AE Recon {s}" for s in self.params["features"]]
        decoded_df = pd.concat(
            [label_df, pd.DataFrame(decoded, columns=decoded_cols, dtype=np.float32)],
            axis=1,
        )
        decoded_df = decoded_df.set_index(data.index)
        encoded_cols = [f"AE Encoded {i}" for i in range(encod.shape[1])]
        encoded_df = pd.concat(
            [
                label_df,
                pd.DataFrame(
                    encoded[:, 0 : encod.shape[1]],
                    columns=encoded_cols,
                    dtype=np.float32,
                ),
            ],
            axis=1,
        )
        encoded_df = encoded_df.set_index(data.index)

        epoch_list = [str(e) for e in range(1, self.params["epoches"] + 1)]
        parts = modelfile  # self.params["modelfile"].split(".")
        presuf = (
            ["".join(parts[: len(parts) - 1]), f".{parts[-1]}"]
            if len(parts) > 1
            else parts + [""]
        )
        all_model_files = {}
        for epoch, ae in checkpoints:
            f = (
                f"{presuf[0]}{presuf[1]}_epoch{epoch:04d}".replace(".model", "")
                + ".model"
            )
            pipeline = make_pipeline(imputer, input_scaler, ae)
            dump(
                pipeline,
                filename=f,
            )
            results[os.path.split(f)[1]] = pipeline
            all_model_files[epoch] = f

        loss_df = pd.DataFrame(
            {
                "Epoch": epoch_list,
                "Batch Size": [str(batch_size)] * len(epoch_list),
                "Learning Rate": [str(learning_rate)] * len(epoch_list),
                "Weight Decay": [str(weight_decay)] * len(epoch_list),
                "Training Loss": loss_train,
                "Validation Loss": loss_val,
                "Model File": [
                    all_model_files.get(e, "---")
                    for e in range(1, self.params["epoches"] + 1)
                ],
            }
        )

        loss_df["Epoch"] = loss_df["Epoch"].astype("category")
        loss_df["Batch Size"] = loss_df["Batch Size"].astype("category")
        loss_df["Learning Rate"] = loss_df["Learning Rate"].astype("category")
        loss_df["Weight Decay"] = loss_df["Weight Decay"].astype("category")

        logging.debug(f"loss_TrainingSet: {loss_train[-1]}")
        logging.debug(f"loss_TestSet: {loss_val[-1]}")
        logging.info("Training complete.")

        results.update(
            {
                f"Table: AE Loss-{batch_size}-{learning_rate}-{weight_decay}": loss_df,
                f"Table: AE Decoded-{batch_size}-{learning_rate}-{weight_decay}": decoded_df,
                f"Table: AE Encoded-{batch_size}-{learning_rate}-{weight_decay}": encoded_df,
                "Model File": [v for v in all_model_files.values()],
            }
        )
        if self.params["create_plots"]:
            fig, ax = plt.subplots(constrained_layout=True)
            ax.plot(range(1, len(loss_train) + 1), loss_train, "b-", label="train-loss")
            ax.plot(range(1, len(loss_val) + 1), loss_val, "r-", label="val-loss")
            ax.grid("on")
            ax.set_ylabel("loss")
            ax.set_xlabel("epoch")
            ax.legend(["training", "testing"], loc="upper right")
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            self._add_picker(fig)
            results.update(
                {
                    f"Plot: AE Loss-{batch_size}-{learning_rate}-{weight_decay}": fig,
                }
            )
        return results
