#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/3/20 10:11 PM
# @Author: Jiaxin_Zhang

import numpy as np
from torch.utils.data.dataset import Dataset


class datasets(Dataset):
    def __init__(self, data):
        self.data_arr = np.asarray(data)
        self.data_len = len(self.data_arr)

    def __getitem__(self, index):
        single_data = self.data_arr[index]
        return single_data

    def __len__(self):
        return self.data_len
