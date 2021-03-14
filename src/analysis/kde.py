#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
from analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt
import seaborn as sns
from gui.dialogs import BasicAnalysisConfigDlg
import wx

default_linestyles = ['-','--',':', '-.']

class KDE(AbstractAnalyzer):
    

    def __init__(self, data, classifier=None, importancehisto=True, n_estimators=100, test_size=0.3, **kwargs):
        AbstractAnalyzer.__init__(self, data, classifier=classifier, importancehisto=importancehisto, n_estimators=n_estimators, test_size=test_size, **kwargs)
        self.name = "KDE Plot"
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def run_configuration_dialog(self, parent):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = BasicAnalysisConfigDlg(parent, f'Configuration: {self.name}', self.data, selectedgrouping=selgrouping, selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        results = {}
        for header in sorted(self.params['features']):
            bins = 100
            minx = self.data[header].min() #hconfig[0]
            maxx = self.data[header].max() #hconfig[1]
            logging.debug (f"Creating kde plot for {str(header)}, bins={str(bins)}")
            fig, ax = self.grouped_kdeplot(self.data, header, groups=self.params['grouping'], hist=False, bins=bins, kde_kws={'clip':(minx, maxx)})
            ax.set_xlim(minx, maxx)
            results[f'KDE Plot: {header}'] = (fig,ax)
        return results
    
    
    def grouped_kdeplot(self, data, column, title=None, groups=[], dropna=True, linestyles=None, pivot_level=1, **kwargs):
    
        if data is None or not column in data.columns.values:
            return None, None
        #plt.rcParams.update({'figure.autolayout': True})
    
        fig, ax = plt.subplots(constrained_layout=True)
        if groups is None:
            groups = []
    
        newkwargs = kwargs.copy()
        # ensure autoscaling of y axis
        #newkwargs['auto'] = None
        newkwargs['ax'] = ax
        
        cols = [c for c in groups]
        cols.append(column)
        if dropna:
            data = data[cols].dropna(how='any', subset=[column])
        fig.set_figheight(6)
        fig.set_figwidth(12)
    
        kde_args = newkwargs.get('kde_kws')
        if not kde_args:
            newkwargs['kde_kws'] = {}
        if len(groups) > 0:
            gs = data.groupby(groups)
            styles = []
            if linestyles is None and len(groups) == 2:
                uniquevalues = [data[g].unique() for g in groups]
                if len(uniquevalues[0]) <= len(sns.color_palette()) and len(uniquevalues[1]) <= len(default_linestyles):
                    colors = [c for c in sns.color_palette()[:len(uniquevalues[0])]]
                    linestyles = [ls for ls in default_linestyles[:len(uniquevalues[1])]]
                    for c in colors:
                        for ls in linestyles:
                            styles.append({'color':c, 'linestyle': ls})
            logging.debug(f"styles={styles}")
            index = 0
            labels = []
            for name, groupdata in gs:
                if (len(groupdata[column]) > 0):
                    name_fixed = self.fix_label(name)
                    kde_args.update({
                            'label': name_fixed,})
                    if len(styles) > index:
                        newkwargs['color'] = styles[index]['color']
                        newkwargs['kde_kws']['linestyle'] = styles[index]['linestyle']
                    logging.debug (f"NEWKWARGS: {newkwargs}")
                    logging.debug (f"len(groupdata[column])={len(groupdata[column])}")
                    sns.distplot(groupdata[column], **newkwargs)
                    labels.append(name_fixed)
                index += 1
            no_legendcols = (len(groups)//30 + 1)
            ax.legend()
            # ax.legend(labels=labels, loc='upper left', title=', '.join(groups), bbox_to_anchor= (1.0, 1.0), fontsize='small', ncol=no_legendcols)
        else:        
            sns.distplot(data[column], **newkwargs)
        ax.autoscale(enable=True, axis='y')    
        ax.set_ylim(0,None)
        if title is None:
            title = column.replace('\n', ' ')#.encode('utf-8')
            if len(groups) > 0:
                title = f"{title} grouped by {groups}"
        if len(title) > 0:
            ax.set_title(title)
        
        # plt.rcParams.update({'figure.autolayout': False})
        self._add_picker(fig)
        return fig, ax
            
