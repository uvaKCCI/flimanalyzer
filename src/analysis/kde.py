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

default_linestyles = ['-','--',':', '-.']

class KDE(AbstractAnalyzer):
    

    def __init__(self, data, categories, features, classifier=None, importancehisto=True, n_estimators=100, test_size=0.3):
        AbstractAnalyzer.__init__(self, data, categories, features, classifier=classifier, importancehisto=importancehisto, n_estimators=n_estimators, test_size=test_size)
        self.name = "KDE Plot"
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def execute(self):
        results = {}
        for header in sorted(self.features):
            bins = 100
            minx = self.data[header].min() #hconfig[0]
            maxx = self.data[header].max() #hconfig[1]
            logging.debug (f"Creating kde plot for {str(header)}, bins={str(bins)}")
            fig, ax = plt.subplots()
            fig, ax = self.grouped_kdeplot(ax, self.data, header, groups=self.categories, hist=False, bins=bins, kde_kws={'clip':(minx, maxx)})
            ax.set_xlim(minx, maxx)
            results[f'KDE Plot: {header}'] = (fig,ax)
        return results
    
    
    def grouped_kdeplot(self,ax, data, column, title=None, groups=[], dropna=True, linestyles=None, pivot_level=1, **kwargs):
    
        if data is None or not column in data.columns.values:
            return None, None
        plt.rcParams.update({'figure.autolayout': True})
    
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()    
        if groups is None:
            groups = []
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()    
    
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
            kde_args = {}
            newkwargs['kde_kws'] = kde_args
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
            for name, groupdata in gs:
                if (len(groupdata[column]) > 0):
                    kde_args.update({
                            'label': self.fix_label(name),})
                    if len(styles) > index:
                        newkwargs['color'] = styles[index]['color']
                        newkwargs['kde_kws']['linestyle'] = styles[index]['linestyle']
                    logging.debug (f"NEWKWARGS: {newkwargs}")
                    logging.debug (f"len(groupdata[column])={len(groupdata[column])}")
                    sns.distplot(groupdata[column], **newkwargs)
                index += 1
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
    
        plt.rcParams.update({'figure.autolayout': False})
        return fig, ax,
            
