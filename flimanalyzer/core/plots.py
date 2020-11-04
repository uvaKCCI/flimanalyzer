#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May  5 14:53:15 2018

@author: khs3z
"""

import logging
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
import seaborn as sns
from pubsub import pub
from gui.events import NEW_PLOT_WINDOW


default_linestyles = ['-','--',':', '-.']

def normalize(value, totalcounts):
    return value / totalcounts


def bindata(binvalues, binedges, groupnames):
    df = pd.DataFrame()
    df['bin edge low'] = binedges[:-1]
    df['bin edge high'] = binedges[1:]
    if len(binvalues.shape) == 1:
        df[groupnames[0]] = binvalues
    else:    
        for i in range(len(binvalues)):
            df[groupnames[i]] = binvalues[i]
    return df

    
def grouped_meanbarplot_new(ax, data, column, groups=[], dropna=True, pivot_level=1, **kwargs):
    if data is None or not column in data.columns.values:
        return None, None
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()    
    
    if groups is None:
        groups = []
    if len(groups)==0:
        mean = pd.DataFrame(data={'all':[data[column].mean()]}, index=[column])#.to_frame()
        std = pd.DataFrame(data={'all':[data[column].std()]}, index=[column])#.to_frame()
        mean.plot.barh(ax=ax, xerr=std)#,figsize=fsize,width=0.8)
    else:    
        sns.barplot(data=data[column], hue=groups[0]);
            
    
def grouped_meanbarplot(ax, data, column, title=None, groups=[], dropna=True, pivot_level=1, **kwargs):
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.autolayout': True})
    if data is None or not column in data.columns.values:
        return None, None
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()    
    
    if groups is None:
        groups = []
    if len(groups)==0:
        mean = pd.DataFrame(data={'all':[data[column].mean()]}, index=[column])#.to_frame()
        std = pd.DataFrame(data={'all':[data[column].std()]}, index=[column])#.to_frame()
        ticklabels = ''#mean.index.values
        mean.plot.barh(ax=ax, xerr=std)#,figsize=fsize,width=0.8)
    else:    
        cols = [c for c in groups]
        cols.append(column)
        if dropna:
            groupeddata = data[cols].dropna(how='any', subset=[column]).groupby(groups)
        else:    
            groupeddata = data[cols].groupby(groups)
#        groupeddata = data[cols].groupby(groups)
#        print data.reset_index().set_index(groups).index.unique()
        #df.columns = [' '.join(col).strip() for col in df.columns.values]
        mean = groupeddata.mean()
        std = groupeddata.std()
        no_bars = len(mean)
        if pivot_level < len(groups):
            unstack_level = list(range(pivot_level))
            logging.debug (f"PIVOTING: {pivot_level}, {unstack_level}")
            mean = mean.unstack(unstack_level)
            std = std.unstack(unstack_level)
            mean = mean.dropna(how='all', axis=0)
            std = std.dropna(how='all', axis=0)
        ticklabels = mean.index.values
        bwidth = 0.8# * len(ticklabels)/no_bars 
        fig.set_figheight(1 + no_bars//8)
        fig.set_figwidth(6)
        mean.plot.barh(ax=ax,xerr=std,width=bwidth)           
    
    
    if len(groups) > 1:
        # ticklabels is an array of tuples --> convert individual tuples into string 
#        ticklabels = [', '.join(l) for l in ticklabels]
        ticklabels = [str(l).replace('\'','').replace('(','').replace(')','') for l in ticklabels]
        h, labels = ax.get_legend_handles_labels()
        #labels = [l.encode('ascii','ignore').split(',')[1].strip(' \)') for l in labels]
        labels = [l.split(',')[1].strip(' \)') for l in labels]
        ax.set_ylabel = ', '.join(groups[pivot_level:])
        no_legendcols = (len(groups)//30 + 1)
        chartbox = ax.get_position()
        ax.set_position([chartbox.x0, chartbox.y0, chartbox.width * (1-0.2 * no_legendcols), chartbox.height])
#        ax.legend(loc='upper center', labels=grouplabels, bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
        ax.legend(labels=labels,  title=', '.join(groups[0:pivot_level]), loc='upper center', bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
        legend = ax.get_legend()
        ax.add_artist(legend)
    else:
        legend = ax.legend()
        legend.remove()
    ax.set_yticklabels(ticklabels)
    if title is None:
        title = column.replace('\n', ' ').encode('utf-8')
    if len(title) > 0:
        ax.set_title(title)

    #fig.tight_layout(pad=1.5)
    plt.rcParams.update({'figure.autolayout': False})
    return fig,ax
    

def grouped_boxplot(ax, data, column, title=None, groups=[], dropna=True, pivot_level=1, **kwargs):
    if data is None or not column in data.columns.values:
        return None, None

    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.autolayout': True})
    
    if groups is None:
        groups = []
    newkwargs = kwargs.copy()
    newkwargs.update({
            'column':column,
            'ax':ax})
    if len(groups) > 0: 
        newkwargs.update({'by':groups})
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()    
    
    cols = [c for c in groups]
    cols.append(column)
    if dropna:
        data = data[cols].dropna(how='any', subset=[column])
    fig.set_figheight(6)
    fig.set_figwidth(12)
    data.boxplot(**newkwargs)
    
    miny = min(0,data[column].min()) * 1.05
    maxy = max(0,data[column].max()) * 1.05
    logging.debug (f'title={title}')
    ax.set_ylim(miny, maxy)
    if title is None:
        title = column.replace('\n', ' ').encode('utf-8')
    if len(title) > 0:
        ax.set_title(title)
    plt.rcParams.update({'figure.autolayout': False})
    return fig,ax    


def grouped_scatterplot(ax, data, combination,  title=None, groups=[], dropna=True, pivot_level=1, **kwargs):
    col1 = combination[0]
    col2 = combination[1]
    if data is None or not col1 in data.columns.values or not col2 in data.columns.values:
        return None, None

    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.autolayout': True})
    
    if groups is None:
        groups = []
    newkwargs = kwargs.copy()
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()    
    
    cols = [c for c in groups]
    cols.extend(combination)
    if dropna:
        data = data[cols].dropna(how='any', subset=combination)
    fig.set_figheight(6)
    fig.set_figwidth(12)

    logging.debug (f"NEWKWARGS: {newkwargs}")
    if len(groups) > 0:
        groups = data.groupby(groups)
        for name, group in groups:
            newkwargs.update({'label':name})
            ax.scatter(group[col1], group[col2], **newkwargs)
    else:        
        ax.scatter(data[col1], data[col2], **newkwargs)
    
    miny = min(0,data[col1].min()) * 1.05
    maxy = max(0,data[col1].max()) * 1.05
    ax.set_xlim(miny, maxy)
    ax.set_xlabel(col1.encode('ascii'))
    miny = min(0,data[col2].min()) * 1.05
    maxy = max(0,data[col2].max()) * 1.05
    ax.set_ylim(miny, maxy)
    ax.set_ylabel(col2.encode('utf-8'))
    
    if len(groups) > 0:
        h, labels = ax.get_legend_handles_labels()
        #labels = [l.encode('ascii','ignore').split(',')[1].strip(' \)') for l in labels]
        labels = [l.replace('\'','').replace('(','').replace(')','') for l in labels]
        no_legendcols = (len(groups)//30 + 1)
        chartbox = ax.get_position()
        ax.set_position([chartbox.x0, chartbox.y0, chartbox.width* (1-0.2 * no_legendcols), chartbox.height])
        ax.legend(labels=labels, loc='upper center', bbox_to_anchor= (1 + (0.2 * no_legendcols), 1.0), fontsize='small', ncol=no_legendcols)
        
    plt.rcParams.update({'figure.autolayout': False})
    return fig,ax    



def fix_label(label):
    return str(label).replace('\'','').replace('(','').replace(')','')


def grouped_kdeplot(ax, data, column, title=None, groups=[], dropna=True, linestyles=None, pivot_level=1, **kwargs):
    if data is None or not column in data.columns.values:
        return None, None
    import matplotlib.pyplot as plt
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
        print (styles)
        index = 0
        for name, groupdata in gs:
            kde_args.update({
                    'label': fix_label(name),})
            if len(styles) > index:
                newkwargs['color'] = styles[index]['color']
                newkwargs['kde_kws']['linestyle'] = styles[index]['linestyle']
            print ("NEWKWARGS:", newkwargs)     
            sns.distplot(groupdata[column], **newkwargs)
            index += 1
    else:        
        sns.distplot(data[column], **newkwargs)
    ax.autoscale(enable=True, axis='y')    
    ax.set_ylim(0,None)
    if title is None:
        title = column.replace('\n', ' ').encode('utf-8')
    if len(title) > 0:
        ax.set_title(title)

    plt.rcParams.update({'figure.autolayout': False})
    return fig, ax,
    
    
    
def histogram(ax, data, column, title=None, groups=[], normalize=None, titlesuffix=None, **kwargs):
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.autolayout': True})

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
            groupnames.append(name)
            pltdata.append(group[column].values)
            totalcounts = group[column].count()            
            if normalize is not None:
                weights.append(np.ones_like(group[column].values)/float(totalcounts) * normalize)
    if normalize is not None:
        if normalize == 100:
            ax.set_ylabel('relative counts [%]')
        else:
            ax.set_ylabel('relative counts (norm. to %.1f)' % normalize)
            
        newkwargs.update({
                'weights':weights, 
                'normed':False
                })
    else:
        ax.set_ylabel('counts')
#    if newkwargs[range] is not None:    
#        ax.set_xlim(newkwargs[range[0]],newkwargs[range[1]])
    ax.set_xlabel(column)

    if title is None:
        title = column.replace('\n', ' ').encode('utf-8')
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

    plt.rcParams.update({'figure.autolayout': False})    
    return  np.array(binvalues), binedges, groupnames, fig, ax,

    
def stacked_histogram(ax, data, column, title=None, groups=[], minx=None, maxx=None, normalize=None, **kwargs):
    import matplotlib.pyplot as plt

    if data is None or not column in data.columns.values:
        return None, None
    if ax is None:
        fig, ax = plt.subplots() #plt.Figure(FigureClass=MatplotlibFigure)
    else:
        fig = ax.get_figure()    

    totalcounts = data[column].dropna(axis=0,how='all').count()
    newkwargs = kwargs.copy()
    newkwargs.update({'stacked':True, 'range':(minx,maxx)})
    pltdata = []
    weights = []
    if groups is None or len(groups)==0:
        pltdata = data[column].values
        newkwargs.update({'label':'all'})
        if normalize is not None:
            weights = np.ones_like(data[column].values)/float(totalcounts) * normalize
    else:
        groupeddata = data.groupby(groups)
        newkwargs.update({'label':list(groupeddata.groups)})
        for name,group in groupeddata:
            pltdata.append(group[column].values)            
            if normalize is not None:
                weights.append(np.ones_like(group[column].values)/float(totalcounts) * normalize)
    if normalize is not None:
        if normalize == 100:
            ax.set_ylabel('relative counts [%]')
        else:
            ax.set_ylabel('relative counts (norm. to %.1f)' % normalize)
            
        newkwargs.update({
                'weights':weights, 
                'normed':False
                })
    else:
        ax.set_ylabel('counts')

    if title is None:
        title = column.replace('\n', ' ').encode('utf-8')
    if len(title) > 0:
        ax.set_title(title)

    ax.set_xlim(minx,maxx)
    ax.set_xlabel(column)
    ax.hist(pltdata, **newkwargs)
    ax.legend()
    return fig, ax


#class MatplotlibFigure(Figure):
#    
#    def show(self, *args, **kwargs):
#        Figure.show(self, *args, **kwargs) 
#        pub.sendMessage(NEW_PLOT_WINDOW, figure=self)
