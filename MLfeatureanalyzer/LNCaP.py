#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 11/20/20 4:19 AM
# @Author: Jiaxin_Zhang

import os
import numpy as np
import pandas as pd
import torch
import torch.utils.data
from torch.autograd import Variable
from sklearn import preprocessing
from sklearn.impute import SimpleImputer
import xlsxwriter

from dir import mkdir
from columnname import getColumnName


class LNCaPSingleCell(object):
    def __init__(self, cell_line, data_filename, autoencoder, t):
        self.cell_line = cell_line
        self.data = pd.read_csv('../data/' + data_filename)
        self.sae = torch.load('../ae/' + autoencoder, map_location='cpu')
        self.t = t

    def create_excel(self):
        self.data.rename(columns={'FLIRR':'FLIRR (NAD(P)H a2[%]/FAD a1[%])'}, inplace=True)

        ind=list(self.data.columns)
        ind_tre = ind.index('Treatment')
        len_info = ind_tre+1

        # FLIM parameters
        g=self.data.loc[:,self.t]
        info=self.data.iloc[:,0:len_info]
        data_set = pd.concat([info, g],axis=1)
        data_copy=data_set.copy()

        FOV=data_copy.loc[:,'FOV']
        FOV_u=np.unique(FOV)
        timepoint=data_copy.loc[:,'Treatment']
        tp_u=np.unique(timepoint)

        # Sort timepoints for LNCaP
        k = []
        for i in tp_u[1:]:
            k.append(int(i[1:]))
        k = np.sort(k)
        m = []
        for j in k:
            m.append('t' + str(j))
        tp_u = np.append(tp_u[0], m)

        print('FOV: ',FOV_u)
        print('Timepoint: ',tp_u)

        f=self.data.loc[:,'FLIRR (NAD(P)H a2[%]/FAD a1[%])'] # FLIRR (NAD(P)H a2[%]/FAD a1[%]) or FLIRR
        data_set_f=pd.concat([data_set,f],axis=1)

        data_set=np.array(data_set)

        # Getting features
        min_max_scaler = preprocessing.MinMaxScaler()

        data_all=np.array(data_set[:,len_info:])
        data_all = data_all.astype(float)
        my_imputer = SimpleImputer(strategy="constant",fill_value=0)
        data_all = min_max_scaler.fit_transform(data_all) # Normalization
        data_all = my_imputer.fit_transform(data_all)
        data_all = torch.FloatTensor(data_all)
        # print('original:\n',data_all)

        data_input = Variable(data_all)
        features, reconstructed = self.sae(data_input)
        params = self.sae.state_dict()

        features = torch.squeeze(features)
        # print('Features shape:',features.shape)
        # print('Features:\n',features.data)
        # print('Reconstructed:\n',reconstructed.data)
        # print('weight shape:',params['fc1.weight'].shape)
        # print('weight:\n',params['fc1.weight'])
        # print('bias shape:\n',params['fc1.bias'].shape)
        # print('bias:\n',params['fc1.bias'])
        # print('\n')

        # Store data and plots in excels
        print("\nCreating excels for single cells......")
        for fov in FOV_u:
            print('\nFoV: ',fov)
            for nb_f in range(1, 2):  # features.shape[1]+1): # (1,2)
                n = 'feature'# + str(nb_f)
                m = 'FLIRR'
                fn = n + '_' + m

                num_tp = tp_u.shape[0]

                mask_fov = data_copy['FOV'] == fov
                mask_fov = np.array(mask_fov)
                mask_ctrl = data_copy['Treatment'] == tp_u[0]
                cell_u = np.unique(data_copy['Cell'][mask_fov][mask_ctrl])
                for tp in range(1, len(tp_u)):
                    mask_tp = data_copy['Treatment'] == tp_u[tp]
                    cell_uu = np.unique(data_copy['Cell'][mask_fov][mask_tp])
                    cell_u = np.intersect1d(cell_u, cell_uu)

                for c in range(len(cell_u)):
                    mkpath = '../' + self.cell_line + '_single_cell/FOV' + fov + '/'  # direction of excels
                    mkdir(mkpath)

                    sheet1 = 'FOV ' + fov + str(cell_u[c])
                    sheet2 = 'plot ' + fov + str(cell_u[c])
                    sheet3 = 'stat ' + fov + str(cell_u[c])
                    workbook = xlsxwriter.Workbook(mkpath + fn + '_' + fov + str(cell_u[c]) + '.xlsx')
                    worksheet1 = workbook.add_worksheet(sheet1)
                    worksheet2 = workbook.add_worksheet(sheet2)
                    worksheet3 = workbook.add_worksheet(sheet3)

                    x = ['#DC143C', '#7FE0F3', 'yellow', '#7FF387', '#EE82EE', '#696969', '#0000CD', '#FF8C00', '#006400',
                         '#9932CC']  # 10 timepoints
                    headings = []
                    headings_cell = tp_u
                    for h in range(len(tp_u)):
                        headings.extend(
                            ['feature' + str(h), 'edge' + str(h), 'count' + str(h), 'percent' + str(h), 'FLIRR' + str(h),
                             'f_edge' + str(h), 'f_count' + str(h), 'f_percent' + str(h)])
                    rows_cell = ['Mean', 'SD', 'Median', 'SEM']

                    fov_cell = np.zeros((4, 1))
                    fov_cell_f = np.zeros((4, 1))

                    for t in range(len(tp_u)):
                        mask_cell = (data_copy['FOV'] == fov) & (data_copy['Cell'] == cell_u[c]) & (
                                    data_copy['Treatment'] == tp_u[t])
                        feature_t = np.array(features[mask_cell].data)
                        data_t = np.array(data_set_f[mask_cell])
                        L1 = feature_t[:,nb_f-1] # feature # For Hela: L1=feature_t; For prostate: L1=feature_t[:,nb_f-1]
                        L2 = data_t[:, -1] # FLIRR

                        tp_cell = np.array([np.mean(L1), np.std(L1), np.median(L1), np.std(L1) / np.sqrt(len(L1))])
                        tp_cell = tp_cell.reshape(len(tp_cell), 1)
                        fov_cell = np.hstack((fov_cell, tp_cell))
                        tp_cell_f = np.array([np.mean(L2), np.std(L2), np.median(L2), np.std(L2) / np.sqrt(len(L2))])
                        tp_cell_f = tp_cell_f.reshape(len(tp_cell_f), 1)
                        fov_cell_f = np.hstack((fov_cell_f, tp_cell_f))

                        xcount, xl = np.histogram(L1, bins=10)
                        ycount, yl = np.histogram(L2, bins=10)

                        ## flipping
                        # L1_n=1-L1
                        # cell_L1_n=1-cell_L1
                        # xl_n=1-xl
                        # xl_n=xl_n[xl_n.argsort()]
                        # xcount_n=xcount[::-1]

                        d1 = 100 * xcount / sum(xcount)  # xcount or xcount_n
                        d2 = 100 * ycount / sum(ycount)

                        L = np.stack((L1, L2), axis=1)
                        L = L[L[:, 0].argsort()]

                        workfomat = workbook.add_format()
                        workfomat.set_num_format('0.0000')

                        worksheet1.write_row('A1', headings)
                        worksheet1.write_column(getColumnName(8 * t + 1) + '2', L1, workfomat)  # L1 or L1_n or cell_L1 or cell_L1_n
                        worksheet1.write_column(getColumnName(8 * t + 2) + '2', xl, workfomat)  # xl or xl_n
                        worksheet1.write_column(getColumnName(8 * t + 3) + '2', xcount)  # xcount or xcount_n
                        worksheet1.write_column(getColumnName(8 * t + 4) + '2', d1)
                        worksheet1.write_column(getColumnName(8 * t + 5) + '2', L2, workfomat)  # L2 or cell_L2
                        worksheet1.write_column(getColumnName(8 * t + 6) + '2', yl, workfomat)
                        worksheet1.write_column(getColumnName(8 * t + 7) + '2', ycount)
                        worksheet1.write_column(getColumnName(8 * t + 8) + '2', d2)

                        feature_cell = [np.mean(L1), np.std(L1), np.median(L1), np.std(L1) / np.sqrt(len(L1))]
                        flirr_cell = [np.mean(L2), np.std(L2), np.median(L2), np.std(L2) / np.sqrt(len(L2))]
                        worksheet3.write_row('B1', headings_cell)
                        worksheet3.write_column('A2', ['Mean', 'SD', 'Median', 'SEM', 'f_Mean', 'f_SD', 'f_Median', 'f_SEM'])
                        worksheet3.write_column(getColumnName(t + 2) + '2', feature_cell, workfomat)
                        worksheet3.write_column(getColumnName(t + 2) + '6', flirr_cell, workfomat)

                        tp_len = len(tp_u)
                        if t == tp_len - 1:
                            continue

                        # Single timepoint for feature
                        chart1 = workbook.add_chart({'type': 'scatter',
                                                     'subtype': 'smooth_with_markers'})
                        chart1.set_size({'width': 1000,
                                         'height': 700})
                        chart1.add_series({
                            'name': str(tp_u[t + 1]),
                            'categories': [sheet1, 1, 8 * (t + 1) + 1, 101, 8 * (t + 1) + 1],
                            'values': [sheet1, 1, 8 * (t + 1) + 3, 101, 8 * (t + 1) + 3],
                            'line': {'color': x[t + 1]},
                            'marker': {'type': 'square',
                                       'size,': 5,
                                       'border': {'color': x[t + 1]},
                                       'fill': {'color': x[t + 1]}
                                       }
                        })

                        chart1.add_series({
                            'name': str(tp_u[0]),
                            'categories': [sheet1, 1, 8 * 0 + 1, 101, 8 * 0 + 1],
                            'values': [sheet1, 1, 8 * 0 + 3, 101, 8 * 0 + 3],
                            'line': {'color': x[0]},
                            'marker': {'type': 'square',
                                       'size,': 5,
                                       'border': {'color': x[0]},
                                       'fill': {'color': x[0]}
                                       }
                        })

                        chart1.set_title({'name': 'FOV ' + fov})  # FOV
                        chart1.set_x_axis({'name': n,
                                           })

                        chart1.set_style(11)

                        worksheet2.insert_chart('D' + str(38 * t + 3), chart1, {'x_offset': 25, 'y_offset': 10})

                    # Single timepoint for FLIRR
                    for j in range(len(tp_u)):
                        if j == tp_len - 1:
                            continue

                        chart2 = workbook.add_chart({'type': 'scatter',
                                                     'subtype': 'smooth_with_markers'})
                        chart2.set_size({'width': 1000,
                                         'height': 700})
                        chart2.add_series({
                            'name': str(tp_u[j + 1]),
                            'categories': [sheet1, 1, 8 * (j + 1) + 5, 101, 8 * (j + 1) + 5],
                            'values': [sheet1, 1, 8 * (j + 1) + 7, 101, 8 * (j + 1) + 7],
                            'line': {'color': x[j + 1]},
                            'marker': {'type': 'square',
                                       'size,': 5,
                                       'border': {'color': x[j + 1]},
                                       'fill': {'color': x[j + 1]}
                                       }
                        })

                        chart2.add_series({
                            'name': str(tp_u[0]),
                            'categories': [sheet1, 1, 6 * 0 + 5, 101, 6 * 0 + 5],
                            'values': [sheet1, 1, 6 * 0 + 7, 101, 6 * 0 + 7],
                            'line': {'color': x[0]},
                            'marker': {'type': 'square',
                                       'size,': 5,
                                       'border': {'color': x[0]},
                                       'fill': {'color': x[0]}
                                       }
                        })

                        chart2.set_title({'name': 'FOV ' + fov})
                        chart2.set_x_axis({'name': m,
                                           })

                        chart2.set_style(11)

                        worksheet2.insert_chart('X' + str(38 * j + 3), chart2, {'x_offset': 25, 'y_offset': 10})

                    # Full timepoint for feature
                    chart3 = workbook.add_chart({'type': 'scatter',
                                                 'subtype': 'smooth_with_markers'})
                    chart3.set_size({'width': 1000,
                                     'height': 700})
                    for i in range(len(tp_u)):
                        chart3.add_series({
                            'name': str(tp_u[i]),
                            'categories': [sheet1, 1, 8 * i + 1, 101, 8 * i + 1],
                            'values': [sheet1, 1, 8 * i + 3, 101, 8 * i + 3],
                            'line': {'color': x[i]},
                            'marker': {'type': 'square',
                                       'size,': 5,
                                       'border': {'color': x[i]},
                                       'fill': {'color': x[i]}
                                       }
                        })

                    chart3.set_title({'name': 'FOV ' + fov})
                    chart3.set_x_axis({'name': n,
                                       })

                    chart3.set_style(11)

                    worksheet2.insert_chart('D' + str(38 * (num_tp - 1) + 3), chart3, {'x_offset': 25, 'y_offset': 10})

                    # Full timepoint for FLIRR
                    chart4 = workbook.add_chart({'type': 'scatter',
                                                 'subtype': 'smooth_with_markers'})
                    chart4.set_size({'width': 1000,
                                     'height': 700})
                    for i in range(len(tp_u)):
                        chart4.add_series({
                            'name': str(tp_u[i]),
                            'categories': [sheet1, 1, 8 * i + 5, 101, 8 * i + 5],
                            'values': [sheet1, 1, 8 * i + 7, 101, 8 * i + 7],
                            'line': {'color': x[i]},
                            'marker': {'type': 'square',
                                       'size,': 5,
                                       'border': {'color': x[i]},
                                       'fill': {'color': x[i]}
                                       }
                        })

                    chart4.set_title({'name': 'FOV ' + fov})
                    chart4.set_x_axis({'name': m,
                                       })

                    chart4.set_style(11)

                    worksheet2.insert_chart('X' + str(38 * (num_tp - 1) + 3), chart4, {'x_offset': 25, 'y_offset': 10})

                    for a in range(8):
                        chart5 = workbook.add_chart({'type': 'column'})
                        chart5.set_size({'width': 600,
                                         'height': 400})

                        chart5.add_series({'values': [sheet3, a + 1, 1, a + 1, len(tp_u)],
                                           'categories': [sheet3, 0, 1, 0, len(tp_u)]
                                           })

                        if a < 4:
                            chart5.set_title({'name': 'Feature ' + rows_cell[a]})
                            worksheet3.insert_chart('A' + str(20 + 23 * a), chart5, {'x_offset': 25, 'y_offset': 10})
                        if a >= 4:
                            chart5.set_title({'name': 'FLIRR ' + rows_cell[a - 4]})
                            worksheet3.insert_chart('L' + str(20 + 23 * (a - 4)), chart5, {'x_offset': 25, 'y_offset': 10})
                        chart5.set_style(11)

                    workbook.close()
                    print('cell ', cell_u[c])
