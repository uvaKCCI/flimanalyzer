#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 11/20/20 3:59 AM
# @Author: Jiaxin_Zhang

from autoencoder2 import SAE
from HeLa import HelaSingleCell

# FLIM parameter groups
t1 = ['FAD a1', 'FAD a2', 'FAD photons', 'FAD t1', 'FAD t2', 'NAD(P)H a1', 'NAD(P)H a2', 'NAD(P)H photons', 'NAD(P)H t1', 'NAD(P)H t2']
t2 = ['FAD a1[%]', 'FAD photons', 'FAD t1', 'FAD t2', 'NAD(P)H a1[%]', 'NAD(P)H photons', 'NAD(P)H t1', 'NAD(P)H t2']

hela = HelaSingleCell('HeLa', '9SR-Hela-Master-Python-Mito.csv', 'hela_norm_relu_sae_g1_6to1feature.pkl', t1)
hela.create_excel()