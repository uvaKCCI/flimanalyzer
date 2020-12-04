#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 12/3/20 10:11 PM
# @Author: Jiaxin_Zhang

import numpy as np
from torch.utils.data.dataset import Dataset

# col = data_copy.columns.values[len_info:]
# t_set = np.array(training_set)  # training_set or t_x_hidden
# v_set = np.array(val_set)  # val_set or v_x_hidden
# training_frame = pd.DataFrame(t_set, index=None, columns=col)
# val_frame = pd.DataFrame(v_set, index=None, columns=col)


class datasets(Dataset):
    def __init__(self, data):  # , label):
        self.data_arr = np.asarray(data)
        # self.label_arr = label.long()
        self.data_len = len(self.data_arr)

    def __getitem__(self, index):
        single_data = self.data_arr[index]
        # single_data_label = self.label_arr[index]
        # return (single_data, single_data_label)
        return single_data

    def __len__(self):
        return self.data_len

#
# if __name__ == "__main__":
#     train_dataset = datasets(training_frame)  # , label_t)
#     val_dataset = datasets(val_frame)  # , label_v)
#     train_loader = torch.utils.data.DataLoader(dataset=train_dataset,
#                                                batch_size=300,
#                                                shuffle=True)
#     val_loader = torch.utils.data.DataLoader(dataset=val_dataset,
#                                              batch_size=300,
#                                              shuffle=True)
    # print(train_dataset.single_data)
    # print(list(enumerate(val_loader)))