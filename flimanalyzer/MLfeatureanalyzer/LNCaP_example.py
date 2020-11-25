#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 11/20/20 4:21 AM
# @Author: Jiaxin_Zhang

from autoencoder1 import SAE
from LNCaP import LNCaPSingleCell

# FLIM parameter groups
t1 = ['FAD a1', 'FAD a2', 'FAD photons', 'FAD t1', 'FAD t2', 'NAD(P)H a1', 'NAD(P)H a2', 'NAD(P)H photons', 'NAD(P)H t1', 'NAD(P)H t2']
# t2 = ['FAD a1[%]', 'FAD photons', 'FAD t1', 'FAD t2', 'NAD(P)H a1[%]', 'NAD(P)H photons', 'NAD(P)H t1', 'NAD(P)H t2']

lncap = LNCaPSingleCell('LNCaP', 'Master-N_PhotFilter350-090620-new.csv', 'prostate_norm_relu_sae_g1_5feature.pkl', t1)
lncap.apply_model()
lncap.create_excel()
