#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/3/20 10:33 PM
# @Author: Jiaxin_Zhang

from AE_training import AEtraining

t1 = ['FAD a1', 'FAD a2', 'FAD photons', 'FAD t1', 'FAD t2', 'NAD(P)H a1', 'NAD(P)H a2', 'NAD(P)H photons', 'NAD(P)H t1', 'NAD(P)H t2']

train = AEtraining('9SR-Hela-Master-Python-Mito.csv', t1, 20, 1e-4, 1e-7, 300)
train.create_datasets()
train.load_data()
train.training()
