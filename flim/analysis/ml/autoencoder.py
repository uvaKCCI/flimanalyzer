#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 10/27/20 3:22 PM
# @Author: Jiaxin_Zhang

import os
import pkgutil
import importlib
import inspect
import logging
import torch
import torch.optim as optim
import torch.nn as nn
from torch.autograd import Variable
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from abc import abstractmethod


def get_autoencoder_classes():
    pkdir = os.path.dirname(__file__)
    for module_loader, name, ispkg in pkgutil.iter_modules([pkdir]):
        importlib.import_module("." + name, __package__)
    available_aes = {
        create_instance(cls).get_name(): cls for cls in AbsAutoencoder.__subclasses__()
    }
    return available_aes


def init_autoencoders():
    tools = get_autoencoder_classes()
    aes = [create_instance(tools[aname]) for aname in tools]
    return aes


def create_instance(clazz, **kwargs):
    if isinstance(clazz, str):
        modulename, _, classname = clazz.rpartition(".")
    elif inspect.isclass(clazz):
        modulename = clazz.__module__
        classname = clazz.__name__
    else:
        logging.error(f"Error instantiating {clazz} autoencoder.")
    logging.debug(
        f"Autoencoder modulename={modulename}, classname={classname}, {kwargs}"
    )
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        toolinstance = class_(**kwargs)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(
            f"Error instantiating {modulename}.{classname} autoencoder, {kwargs}"
        )
        toolinstance = None

    return toolinstance


class AbsAutoencoder(nn.Module, BaseEstimator, TransformerMixin):
    def __init__(self):
        super(AbsAutoencoder, self).__init__()
        self.name = __name__

    def get_name(self):
        return self.name

    def fit(self, X):
        return self

    def transform(self, X):
        return X

    @abstractmethod
    def get_description(self):
        return None


class Autoencoder_One_Six(AbsAutoencoder): #used for simulation
    def __init__(self, nb_param=2, hidden_size=6):
        super().__init__()
        self.name = "AE Simulator 1-6"
        self.fc1 = nn.Linear(nb_param, hidden_size)
        self.fc4 = nn.Linear(hidden_size, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders):
        return self

    def transform(self, X):
        # return only decoder output
        X = Variable(torch.from_numpy(X))
        return self(X)

    def forward(self, x):
        encoder_out = self.activation2(self.fc1(x))
        decoder_out = self.fc4(encoder_out)
        return encoder_out, decoder_out

    def get_description(self):
        return (
            "This Autoencoder can be used to simulate new data based on an existing"
            " dataset."
        )


class Autoencoder_One_Three(AbsAutoencoder): #also for simulation but isnt used
    def __init__(self, nb_param=2, hidden_size=3):
        super().__init__()
        self.name = "AE Simulator 1-3"
        self.fc1 = nn.Linear(nb_param, hidden_size)
        self.fc4 = nn.Linear(hidden_size, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders):
        return self

    def transform(self, X):
        # return only decoder output
        X = Variable(torch.from_numpy(X))
        return self(X)

    def forward(self, x):
        encoder_out = self.activation2(self.fc1(x))
        decoder_out = self.fc4(encoder_out)
        return encoder_out, decoder_out

    def get_description(self):
        return (
            "This Autoencoder can be used to simulate new data based on an existing"
            " dataset."
        )


class Autoencoder_Two_Ten(AbsAutoencoder):
    def __init__(self, nb_param=2, hidden_size_1=10, hidden_size_2=1):
        super().__init__()
        self.name = "AE Dimensionality Reduction 2-10"
        self.fc1 = nn.Linear(nb_param, hidden_size_1)
        self.fc2 = nn.Linear(hidden_size_1, hidden_size_2)
        self.fc3 = nn.Linear(hidden_size_2, hidden_size_1)
        self.fc4 = nn.Linear(hidden_size_1, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders):
        return self

    def transform(self, X):
        # return only decoder output
        X = Variable(torch.from_numpy(X))
        return self(X)

    def forward(self, x):
        x_out = self.activation2(self.fc1(x))
        encoder_out = self.activation2(self.fc2(x_out))
        y_out = self.activation2(self.fc3(encoder_out))
        decoder_out = self.fc4(y_out)
        return encoder_out, decoder_out

    def get_description(self):
        return (
            "This Autoencoder is used for dimensionality reduction of the feature space"
            " of an existing dataset."
        )


class Autoencoder_Two_Five(AbsAutoencoder): #also not really used
    def __init__(self, nb_param=2, hidden_size_1=5, hidden_size_2=1):
        super().__init__()
        self.name = "AE Dimensionality Reduction 2-5"
        self.fc1 = nn.Linear(nb_param, hidden_size_1)
        self.fc2 = nn.Linear(hidden_size_1, hidden_size_2)
        self.fc3 = nn.Linear(hidden_size_2, hidden_size_1)
        self.fc4 = nn.Linear(hidden_size_1, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders):
        return self

    def transform(self, X):
        # return only decoder output
        X = Variable(torch.from_numpy(X))
        return self(X)

    def forward(self, x):
        x_out = self.activation2(self.fc1(x))
        encoder_out = self.activation2(self.fc2(x_out))
        y_out = self.activation2(self.fc3(encoder_out))
        decoder_out = self.fc4(y_out)
        return encoder_out, decoder_out

    def get_description(self):
        return (
            "This Autoencoder is used for dimensionality reduction of the feature space"
            " of an existing dataset."
        )
