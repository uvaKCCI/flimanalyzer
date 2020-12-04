#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 10/27/20 1:38 PM
# @Author: Jiaxin_Zhang

import torch.nn as nn


class AE(nn.Module):
    def __init__(self, nb_param):
        super(AE, self).__init__()
        self.fc1 = nn.Linear(nb_param, 6)
        self.fc2 = nn.Linear(6, 1)
        self.fc3 = nn.Linear(1, 6)
        self.fc4 = nn.Linear(6, nb_param)
        self.activation1 = nn.Sigmoid()
        self.activation2 = nn.ReLU()
        self.activation3 = nn.LeakyReLU()

    def forward(self, x):
        x_out = self.activation2(self.fc1(x))
        encoder_out = self.activation2(self.fc2(x_out))
        y_out = self.activation2(self.fc3(encoder_out))
        decoder_out = self.fc4(y_out)
        return encoder_out, decoder_out
