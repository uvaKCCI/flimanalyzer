#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import itertools
import pandas as pd
from flim.analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
from importlib_resources import files
import flim.resources
import numpy as np
import matplotlib.ticker as mtick


class BarPlotConfigDlg(BasicAnalysisConfigDlg):

    def __init__(self, parent, title, data, selectedgrouping=['None'], selectedfeatures='All', orientation='vertical', ordering=[], ebar='+/-', etype='std', dropna=True, bartype='single'):
        self.orientation = orientation
        self.ordering = ordering
        self.ebar = ebar
        self.etype = etype
        self.sel_bartype = bartype
        self.dropna = dropna
        BasicAnalysisConfigDlg.__init__(self, parent, title, data, selectedgrouping=selectedgrouping, selectedfeatures=selectedfeatures, optgridrows=1, optgridcols=0)
		    
    def get_option_panels(self):
        osizer = wx.BoxSizer(wx.HORIZONTAL)
        orientation_opts = ['vertical', 'horizontal']
        sel_orientation = self.orientation
        if sel_orientation not in orientation_opts:
            sel_orientation = orientation_opts[0]
        self.orientation_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_orientation, choices=orientation_opts)
        osizer.Add(wx.StaticText(self.panel, label="Orientation "), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        osizer.Add(self.orientation_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        ssizer = wx.BoxSizer(wx.HORIZONTAL)
        bartype_opts = ['single', 'stacked', '100% stacked']
        sel_bartype = self.sel_bartype
        if sel_bartype not in bartype_opts:
            sel_bartype = bartype_opts[0]
        self.bartype_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_bartype, choices=bartype_opts)
        self.dropna_cb = wx.CheckBox(self.panel, id=wx.ID_ANY, label="Drop N/A")
        self.dropna_cb.SetValue(self.dropna)
        ssizer.Add(self.bartype_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        ssizer.Add(self.dropna_cb, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        ebar_opts = ['+/-', '+', 'None']
        sel_ebar = self.ebar
        if sel_ebar not in ebar_opts:
            sel_ebar = ebar_opts[0]
        self.ebar_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_ebar, choices=ebar_opts)
        self.ebar_combobox.Bind(wx.EVT_COMBOBOX, self.OnErroBarChange)
        bsizer.Add(wx.StaticText(self.panel, label="Error Bar"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        bsizer.Add(self.ebar_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)

        tsizer = wx.BoxSizer(wx.HORIZONTAL)
        etype_opts = ['std', 's.e.m.']
        sel_etype = self.etype
        if sel_etype not in sel_etype:
            sel_etype = sel_etype[0]
        self.etype_combobox = wx.ComboBox(self.panel, wx.ID_ANY, style=wx.CB_READONLY, value=sel_etype, choices=etype_opts)
        self.etype_combobox.Enable(sel_ebar != 'None')
        tsizer.Add(wx.StaticText(self.panel, label="Error Type"), 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        tsizer.Add(self.etype_combobox, 0, wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL, 5)
        
        return [osizer, ssizer, bsizer, tsizer]
        
    def _get_selected(self):
        params = super()._get_selected()
        params['ordering'] = []
        params['orientation'] = self.orientation_combobox.GetValue()
        params['bar type'] = self.bartype_combobox.GetValue()
        params['dropna'] = self.dropna_cb.GetValue()
        params['error bar'] = self.ebar_combobox.GetValue()
        params['error type'] = self.etype_combobox.GetValue()
        return params
        
    def OnErroBarChange(self, event):
        ebar = self.ebar_combobox.GetValue()
        self.etype_combobox.Enable(ebar != 'None')


class BarPlot(AbstractAnalyzer):
    
    def __init__(self, data, **kwargs):
        AbstractAnalyzer.__init__(self, data, **kwargs)
        self.name = "Bar Plot"
    
    #def __repr__(self):
    #    return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('barplot.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'display': ['auto','auto'],
            'grouping': [],
            'features': [],
            'ordering': {},
            'orientation': 'vertical', # 'horizontal'
            'bar type': 'single', # 'stacked', '100% stacked' 
            'dropna': True,
            'error bar': '+/-', # '+', 'None'
            'error type': 'std', # 's.e.m'
        })
        return params
                
    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        ordering = self.params['ordering']
        orientation = self.params['orientation']
        etype = self.params['error type']
        ebar = self.params['error bar']
        bartype = self.params['bar type']
        dropna = self.params['dropna']
        dlg = BarPlotConfigDlg(parent, f'Configuration: {self.name}', self.data, 
        	selectedgrouping=selgrouping, 
        	selectedfeatures=selfeatures, 
        	ordering=ordering, 
        	orientation=orientation,
        	bartype=bartype,
        	dropna=dropna,
        	ebar=ebar,
        	etype=etype)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        results = {}
        features = self.params['features']
        grouping = self.params['grouping']
        bartype = self.params['bar type']
        dropna = self.params['dropna']
        stacked = bartype != 'single'
        if stacked:
            logging.debug (f"\tcreating stacked mean bar plot for {features}")
            # pass and stack all features
            fig = self.grouped_meanbarplot(self.data, features, categories=grouping, dropna=dropna, bartype=bartype)
            results[f"Mean Bar Plot: {'|'.join(features)}"] = fig            
        else:    
            # pass one feature per plot
            for feature in sorted(features):
                logging.debug (f"\tcreating mean bar plot for {feature}")
                fig = self.grouped_meanbarplot(self.data, [feature], categories=grouping, dropna=dropna, bartype=bartype)
                results[f"Mean Bar Plot: {feature}"] = fig
        return results
    
    
    def grouped_meanbarplot(self, data, feature, ax=None, title=None, bartype='single', categories=[], dropna=True, pivot_level=1, **kwargs):
        stacked = not bartype == 'single'
        #plt.rcParams.update({'figure.autolayout': True})
        a = all(e in data.columns.values for e in feature)
        if data is None or not a:
            return None, None
        if ax is None:
            fig, ax = plt.subplots() #constrained_layout=True)
        else:
            fig = ax.get_figure()
        capsize = 6
        if categories is None:
            categories = []
        if len(categories)==0:
            mean = pd.DataFrame(columns=feature)
            mean.loc[0] = data[feature].mean()
            if self.params['error bar'] != 'None':
                error = pd.DataFrame(columns=feature)
                if self.params['error type'] == 'std':
                    error.loc[0] = data[feature].std()
                else:
                    error.loc[0] = data[feature].sem()
            else:
                error = None
            if bartype == '100% stacked':
                # sum all columns, than devide means[all columns] by sum (row-by-row) and convert to percent
                sum = mean.abs().sum(axis=1)
                mean = mean.div(sum, axis=0) * 100.0
                if error is not  None:
                    error = error.div(sum, axis=0) * 100.0
            if self.params['error bar'] == '+':
                error_vals = error.to_numpy().flatten()
                error = [[np.zeros_like(error_vals), error_vals]]
            ticklabels = ''#mean.index.values
            if self.params['orientation'] == 'horizontal':
                mean.plot.barh(ax=ax, xerr=error, stacked=stacked, capsize=capsize, barsabove=True)#,figsize=fsize,width=0.8)
            else:
                mean.plot.bar(ax=ax, yerr=error, stacked=stacked, capsize=capsize, barsabove=True)#,figsize=fsize,width=0.8)            
        else:    
            cols = [c for c in categories]
            cols.extend(feature)
            if dropna:
                groupeddata = data[cols].dropna(how='any', subset=feature).groupby(categories, observed=True)
            else:    
                groupeddata = data[cols].groupby(categories, observed=True)
            mean = groupeddata.mean()
            if self.params['error bar'] != 'None':
                if self.params['error type'] == 'std':
                    error = groupeddata.std()
                else:
                    error = groupeddata.sem()
            else:
                error = None
            if bartype == '100% stacked':
                # sum all columns, than devide means[all columns]  by sum (row-by-row)
                sum = mean.abs().sum(axis=1)
                mean = mean.div(sum, axis=0) * 100.0
                if error is not None:
                    error = error.div(sum, axis=0) * 100.0
            num_bars = len(mean)
            if not stacked and pivot_level < len(categories):
                unstack_level = list(range(pivot_level))
                logging.debug (f"Unstacking: {pivot_level}, {unstack_level}")
                mean = mean.unstack(unstack_level)
                mean = mean.dropna(how='all', axis=0)
                if error is not None:
                    error = error.unstack(unstack_level)
                    error = error.dropna(how='all', axis=0)
            if self.params['error bar'] == '+':
                error = error.transpose()
                dim = error.shape
                zeros = np.zeros_like(error)
                C = np.empty((error.shape[0]+zeros.shape[0], error.shape[1]))
                C[::2,:] = zeros
                C[1::2,:] = error
                error = C
                error = error.reshape([dim[0],2,dim[1]])              
            ticklabels = mean.index.values
            bwidth = 0.8# * len(ticklabels)/num_bars 
            fig.set_figheight(1 + num_bars//8)
            fig.set_figwidth(6)
            if self.params['orientation'] == 'horizontal':
                mean.plot.barh(ax=ax, xerr=error, width=bwidth, stacked=stacked, capsize=capsize)           
            else:
                mean.plot.bar(ax=ax, yerr=error, width=bwidth, stacked=stacked, capsize=capsize)           
        
        if len(categories) > 1 or stacked:
            ticklabels = [str(l).replace('\'','').replace('(','').replace(')','') for l in ticklabels]
            h, labels = ax.get_legend_handles_labels()
            if stacked:
                ltitle = ''
                labels = feature
            elif len(categories) > 1:    
                ltitle = ', '.join(categories[0:pivot_level])
                labels = [l.replace('\'','').replace('(','').replace(')','') for l in labels]
                labels = [', '.join(label.split(',')[1:]) for label in labels]

                if self.params['orientation'] == 'horizontal':
                    ax.set_ylabel(', '.join(categories[pivot_level:]))
                else:
                    ax.set_xlabel(', '.join(categories[pivot_level:]))            
            no_legendcols = (len(categories)//30 + 1)
            chartbox = ax.get_position()
            if bartype == '100% stacked':
                ax.yaxis.set_major_formatter(mtick.PercentFormatter())
            ax.set_position([chartbox.x0, chartbox.y0, chartbox.width * (1-0.2 * no_legendcols), chartbox.height])
    #        ax.legend(loc='upper center', labels=grouplabels, bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
            legend = ax.legend(labels=labels,  title=ltitle, loc='upper left', bbox_to_anchor= (1.0, 1.0), fontsize='small', ncol=no_legendcols)
            #legend = ax.legend(labels=labels,  title=', '.join(categories[0:pivot_level]), loc='upper center')
            #ax.add_artist(legend)
        else:
            legend = ax.legend()
            legend.remove()
        if self.params['orientation'] == 'horizontal':
            ax.set_yticklabels(ticklabels)
        else:
            ax.set_xticklabels(ticklabels)        
        if title is None:
            title = '|'.join(feature).replace('\n', ' ') #.encode('utf-8')
            if len(categories) > 0:
                title = f"{title} grouped by {categories}"
        if len(title) > 0:
            ax.set_title(title)
    
        #fig.tight_layout()
        #plt.rcParams.update({'figure.autolayout': False})
        
        self._add_picker(fig)
        return fig
