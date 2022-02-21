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
import torch.nn as nn
from abc import abstractmethod


def get_autoencoder_classes():
    pkdir = os.path.dirname(__file__)
    for (module_loader, name, ispkg) in pkgutil.iter_modules([pkdir]):
        importlib.import_module('.' + name, __package__)
    available_aes = {create_instance(cls).get_name(): cls for cls in AbsAutoencoder.__subclasses__()}
    return available_aes

def init_autoencoders():
    tools = get_autoencoder_classes()
    aes = [create_instance(tools[aname]) for aname in tools]
    return aes

def create_instance(clazz, **kwargs):
    if isinstance(clazz, str):
        modulename, _, classname = clazz.rpartition('.')
    elif inspect.isclass(clazz):
        modulename = clazz.__module__
        classname = clazz.__name__
    else:
        logging.error(f"Error instantiating {clazz} autoencoder.")        
    logging.debug(f"Autoencoder modulename={modulename}, classname={classname}, {kwargs}")
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        toolinstance = class_(**kwargs)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(f"Error instantiating {modulename}.{classname} autoencoder, {kwargs}")
        toolinstance = None
    return toolinstance  
    

class AbsAutoencoder(nn.Module):

    def __init__(self):
        super(AbsAutoencoder, self).__init__()
        self.name = __name__
        
    def get_name(self):
        return self.name
    
    @abstractmethod
    def get_description(self):
        return None
    
       
class Autoencoder_One(AbsAutoencoder):
    def __init__(self, nb_param=2, hidden_size=6):
        super(Autoencoder_One, self).__init__()
        self.name = "Autoencoder 1" 
        self.fc1 = nn.Linear(nb_param, hidden_size)
        self.fc4 = nn.Linear(hidden_size, nb_param)
        #self.activation1 = nn.Sigmoid()
        self.activation2 = nn.ReLU()
        #self.activation3 = nn.LeakyReLU()
        
    def forward(self, x):
        encoder_out = self.activation2(self.fc1(x))
        decoder_out = self.fc4(encoder_out)
        return encoder_out, decoder_out
        
    def get_description(self):
        return "This Autoencoder can be used to simulate new data based on an existing dataset."

        
class Autoencoder_Two(AbsAutoencoder):
    def __init__(self, nb_param=2, hidden_size_1=10, hidden_size_2=1):
        super(Autoencoder_Two, self).__init__()
        self.name = "Autoencoder 2" 
        self.fc1 = nn.Linear(nb_param, hidden_size_1)
        self.fc2 = nn.Linear(hidden_size_1, hidden_size_2)
        self.fc3 = nn.Linear(hidden_size_2, hidden_size_1)
        self.fc4 = nn.Linear(hidden_size_1, nb_param)
        #self.activation1 = nn.Sigmoid()
        self.activation2 = nn.ReLU()
        #self.activation3 = nn.LeakyReLU()

        
    def forward(self, x):
        x_out = self.activation2(self.fc1(x))
        encoder_out = self.activation2(self.fc2(x_out))
        y_out = self.activation2(self.fc3(encoder_out))
        decoder_out = self.fc4(y_out)
        return encoder_out, decoder_out
        
    def get_description(self):
        return "This Autoencoder is used for dimensionality reduction of the feature space of an existing dataset."

class VAE(AbsAutoencoder):
    def __init__(self, nb_param=2, hidden_size=6):
        super(VAE, self).__init__()
        self.name = "Variational Autoencoder"
        self.hidden_size = hidden_size
        self.fc1 = nn.Linear(nb_param, hidden_size*2)
        self.fc4 = nn.Linear(hidden_size, nb_param)
        self.activation1 = nn.Sigmoid()
        self.activation2 = nn.ReLU()
        self.activation3 = nn.LeakyReLU()#negative_slope=0.5)

    def reparameterize(self, mu, log_var):
        """
        :param mu: mean from the encoder's latent space
        :param log_var: log variance from the encoder's latent space
        """
        std = torch.exp(0.5*log_var) # standard deviation
        eps = torch.randn_like(std) # `randn_like` as we need the same size
        sample = mu + (eps * std) # sampling as if coming from the input space
        return sample

    def forward(self, x):
        x = self.activation2(self.fc1(x))
        encoder_out = x.view(-1, 2, self.hidden_size)
    
        mu = encoder_out[:, 0, :] # the first feature values as mean
        log_var = encoder_out[:, 1, :] # the other feature values as variance
        # get the latent vector through reparameterization
        z = self.reparameterize(mu, log_var)

        decoder_out = self.fc4(z)
        return z, decoder_out #, mu, log_var

    def get_description(self):
        return "[TEST]This Autoencoder is used for creating continuous augmented data"


'''vae = VAE()
vae = vae#.cuda()
criterion = nn.MSELoss()#.cuda()
optimizer = optim.RMSprop(vae.parameters(), lr = 1e-4, weight_decay = 1.5e-9)'''