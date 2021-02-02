#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:18:30 2020

@author: khs3z
"""

import logging
import numpy as np
import pandas as pd
from analysis.absanalyzer import AbstractAnalyzer
import matplotlib.pyplot as plt

default_linestyles = ['-','--',':', '-.']

class FreqHisto(AbstractAnalyzer):
    

    def __init__(self, data, categories, features, classifier=None, importancehisto=True, n_estimators=100, test_size=0.3):
        AbstractAnalyzer.__init__(self, data, categories, features, classifier=classifier, importancehisto=importancehisto, n_estimators=n_estimators, test_size=test_size)
        self.name = "Frequency Histogram"
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def execute(self):
        results = {}
        for header in sorted(self.features):
            #hconfig = cols[header]
#            hconfig = self.config[CONFIG_HISTOGRAMS].get(header)
            mrange = (self.data[header].min(), self.data[header].max())
            bins = 100
            logging.debug (f"\tcreating frequency histogram plot for {header} with {bins} bins")     
            #categories = [col for col in self.flimanalyzer.get_importer().get_parser().get_regexpatterns()]
#            fig, ax = MatplotlibFigure()
            #fig = plt.figure(FigureClass=MatplotlibFigure)
            #ax = fig.add_subplot(111)
            fig, ax = plt.subplots()
            binvalues, binedges, groupnames, fig, ax = self.histogram(ax, self.data, header, groups=self.categories, normalize=100, range=mrange, stacked=False, bins=bins, histtype='step')                

            df = pd.DataFrame()
            df['bin edge low'] = binedges[:-1]
            df['bin edge high'] = binedges[1:]
            if len(binvalues.shape) == 1:
                df[groupnames[0]] = binvalues
            else:    
                for i in range(len(binvalues)):
                    df[groupnames[i]] = binvalues[i]
            df.reset_index()
            #bindata = core.plots.bindata(binvalues,binedges, groupnames)
            #bindata = bindata.reset_index()

            results[f'Frequency Histo Plot: {header}'] = (fig,ax)
            results[f'Frequency Histo Table: {header}'] = df
        return results
    
    
    def histogram(self,ax, data, column, title=None, groups=[], normalize=None, titlesuffix=None, **kwargs):
        # plt.rcParams.update({'figure.autolayout': True})
    
        if data is None or not column in data.columns.values:
            return None, None
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()    
        if groups is None:
            groups = []
                    
        newkwargs = kwargs.copy()
        #newkwargs.update({'range':(minx,maxx)})
        totalcounts = data[column].dropna(axis=0,how='all').count()
        pltdata = []
        weights = []
        groupnames = []
        if len(groups)==0:
            groupnames.append('all')
            pltdata = data[column].values
            newkwargs.update({'label':'all'})
            if normalize is not None:
                weights = np.ones_like(data[column].values)/float(totalcounts) * normalize
        else:
            groupeddata = data.groupby(groups)
            newkwargs.update({'label':list(groupeddata.groups)})
            for name,group in groupeddata:
                if len(group[column]) > 0:
                    groupnames.append(name)
                    pltdata.append(group[column].values)
                    totalcounts = group[column].count()            
                    if normalize is not None:
                        weights.append(np.ones_like(group[column].values)/float(totalcounts) * normalize)
        if normalize is not None:
            if normalize == 100:
                ax.set_ylabel('relative counts [%]')
                groupnames = [f"{n} [rel %]" for n in groupnames]
            else:
                ax.set_ylabel('relative counts (norm. to %.1f)' % normalize)
                
            newkwargs.update({
                    'weights':weights, 
                    'density':False
                    })
        else:
            ax.set_ylabel('counts')
    #    if newkwargs[range] is not None:    
    #        ax.set_xlim(newkwargs[range[0]],newkwargs[range[1]])
        ax.set_xlabel(column)
    
        if title is None:
            title = column.replace('\n', ' ')#.encode('utf-8')
            if len(groups) > 0:
                title = f"{title} grouped by {groups}"
        if len(title) > 0:
            ax.set_title(title)
    
        fig.set_size_inches(8,8)
    
        binvalues,binedges,patches = ax.hist(pltdata, **newkwargs)    
        if len(groups) > 0 and len(binvalues) > 1:
            h, labels = ax.get_legend_handles_labels()
            #labels = [l.encode('ascii','ignore').split(',')[1].strip(' \)') for l in labels]
            labels = [l.replace('\'','').replace('(','').replace(')','') for l in labels]
            no_legendcols = (len(binvalues)//30 + 1)
            chartbox = ax.get_position()
            ax.set_position([chartbox.x0, chartbox.y0, chartbox.width* (1-0.2 * no_legendcols), chartbox.height])
            ax.legend(labels=labels, loc='upper center', title=', '.join(groups), bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
    
        # plt.rcParams.update({'figure.autolayout': False})    
        return  np.array(binvalues), binedges, groupnames, fig, ax,    
                
