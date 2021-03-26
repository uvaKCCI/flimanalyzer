#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  4 05:16:56 2018

@author: khs3z
"""

import logging
import numpy as np
import numbers
import core
import core.configuration as cfg
from core.analyzer import dataanalyzer

TRP_RZERO = 2.1
ONE_SIXTH = 1.0/6 

def percentile(n):
    def percentile_(x):
        return np.nanpercentile(x, n)
    percentile_.__name__ = '%s percentile' % n
    return percentile_    

def nadph_perc(nadph_t2):
    return ((nadph_t2 - 1500) / (4400-1500)) * 100

def nadh_perc(nadph_perc):
    return 100.0 - nadph_perc

def tm(a1perc, t1, a2perc, t2):
    return ((a1perc * t1) + (a2perc * t2))/100
    
def trp_Eperc_1(trp_tm, const=3100):
    if const != 0:
        return (1.0 - (trp_tm / const)) * 100
    else:
        return np.NaN
 
def trp_Eperc_2(trp_t1, trp_t2):
    if trp_t2 != 0:
        return (1.0 - (trp_t1 / trp_t2)) * 100
    else:
        return np.NaN

def trp_Eperc_3(trp_t1, const=3100):
    if const != 0:
        return (1.0 - (trp_t1 / const)) * 100
    else:
        return np.NaN

def trp_r(trp_Eperc):
    # 0<= Eperc < 100
    if trp_Eperc != 0:
        t = (100.0/trp_Eperc - 1)
        if t >= 0:
            return TRP_RZERO * t ** ONE_SIXTH
    return np.NaN
    
def ratio(v1, v2):
    if (v2 != 0):
        # force float values
        return float(v1) / v2
    else:
        return np.NaN


class defaultpreprocessor():
    
    def __init__(self, calculator=None):
        #if calculator is None:
        #    self.calculator = dataanalyzer()
        #else:
        #    self.calculator = calculator    
        self.newheaders = {
                "Exc1_-Ch1-_": "trp ",
                "Exc1_-Ch2-_": "NAD(P)H ",
                "Exc2_-Ch3-_": "FAD "
            }
        self.dropcolumns = [
                "Exc1_",
                "Exc2_",
                "Exc3_"
            ]
        self.calccolumns = [
                "NAD(P)H tm",
                "NAD(P)H a2[%]/a1[%]",
                "NADPH %",
                "NADPH/NADH",
                "NADH %",
                "trp tm",
                "trp E%1",
                "trp E%2",
                "trp E%3",
                "trp r1",
                "trp r2",
                "trp r3",
                "trp a1[%]/a2[%]",
                "FAD tm",
                "FAD a1[%]/a2[%]",
                "FAD photons/NAD(P)H photons",
                "NAD(P)H tm/FAD tm",
                "FLIRR",
                "NADPH a2/FAD a1"
            ]
        #self.additional_columns = []
        self.functions = {
                'NADPH %': [nadph_perc.__name__,['NAD(P)H t2']],
                'NAD(P)H tm': [tm.__name__,['NAD(P)H a1[%]','NAD(P)H t1','NAD(P)H a2[%]','NAD(P)H t2']],
                'NAD(P)H a2[%]/a1[%]': [ratio.__name__, ['NAD(P)H a2[%]', 'NAD(P)H a1[%]']],
                'NADH %': [nadh_perc.__name__,['NADPH %']],
                'NADPH/NADH': [ratio.__name__, ['NADPH %', 'NADH %']],
                'trp tm': [tm.__name__,['trp a1[%]','trp t1','trp a2[%]','trp t2']],
                'trp E%1': [trp_Eperc_1.__name__,['trp tm']],
                'trp E%2': [trp_Eperc_2.__name__,['trp t1','trp t2']],
                'trp E%3': [trp_Eperc_3.__name__,['trp t1']],
                'trp r1': [trp_r.__name__,['trp E%1']],
                'trp r2': [trp_r.__name__,['trp E%2']],
                'trp r3': [trp_r.__name__,['trp E%3']],
                'trp a1[%]/a2[%]': [ratio.__name__, ['trp a1[%]', 'trp a2[%]']],
                'FAD tm': [tm.__name__,['FAD a1[%]','FAD t1','FAD a2[%]','FAD t2']],
                'FAD a1[%]/a2[%]': [ratio.__name__, ['FAD a1[%]', 'FAD a2[%]']],
                'FAD photons/NAD(P)H photons': [ratio.__name__, ['FAD photons', 'NAD(P)H photons']],
                'NAD(P)H tm/FAD tm': [ratio.__name__,['NAD(P)H tm','FAD tm']],
                'FLIRR': [ratio.__name__, ['NAD(P)H a2[%]', 'FAD a1[%]']],
                'NADPH a2/FAD a1': [ratio.__name__, ['NAD(P)H a2', 'FAD a1']],
                }


    def get_config(self):
        config = {
            cfg.CONFIG_CALC_COLUMNS: dict(self.functions), #self.calculator.get_config(), #calccolumns,
            cfg.CONFIG_DROP_COLUMNS: self.dropcolumns,
            cfg.CONFIG_HEADERS: self.newheaders,
        }
        return config
    
        
    def columns_available(self, data, args):
        for arg in args:
            if not isinstance(arg, numbers.Number) and data.get(arg) is None:
                return False
        return True
    
    
    def set_replacementheaders(self, headers):
        self.newheaders = headers
        
        
    def get_replacementheaders(self):
        return self.newheaders
    

    def set_dropcolumns(self, cols):
        self.dropcolumns = cols
        
        
    def reorder_columns(data, first=[]):
        if first is None or len(first) == 0:
            first = sorted(data.select_dtypes(['object']).columns.values)
            first.extend(sorted(data.select_dtypes(['category']).columns.values))  
        newheaders = first
        newheaders.extend(sorted(set(data.columns.values)-set(first)))
        if len(newheaders) == len(data.columns):
            data = data.reindex(newheaders, axis=1)
        logging.debug (f"Reordered headers: {dataframe.columns.values}")
        return data
        
        
    def rename_headers(self, data, newheaders=None, preview=False):
        if data is None:
            return None
        if newheaders is None:
            newheaders = self.newheaders
        oldheaders = list(data.columns.values)
        currentheaders = [c for c in oldheaders]
        for newheader in newheaders:
            currentheaders = [c.replace(newheader, newheaders[newheader]) for c in currentheaders]
#        for newheader in newheaders:
#            currentheaders = currentheaders.replace(newheader, newheaders[newheader])
#        currentheaders = currentheaders.split('\t')
        changedheaders = {oldheaders[i]:currentheaders[i] for i in range(len(oldheaders)) if oldheaders[i]!=currentheaders[i]}
        if not preview:
            data.columns = currentheaders                
        return data, changedheaders 


    def calculate(self, data, inplace=True):
        calculated = []
        skipped = []
        if not inplace:
            data = data.copy()
        for acol in self.calccolumns:
            #if acol == 'NADH tm':
                #(NADH-a1% * NADH-t1) + (NADH-a2% * NADH-t2)/100
            if acol in self.functions:
                #NAD(P)H % = (('NAD(P)H t2') - 1500 / (4400-1500)) *100
                funcname = self.functions[acol][0]
                funcargs = self.functions[acol][1]
                funcobj = getattr(core.preprocessor,funcname) # self.functions[acol][0]
                func = np.vectorize(funcobj)
                if not self.columns_available(data, funcargs):
                    skipped.append(self.functions[acol])
                    continue
                data[acol] = func(*np.transpose(data[funcargs].values))
                calculated.append(self.functions[acol])
            else:
                skipped.append(self.functions[acol])
        return data, calculated, skipped


    def reorder_columns(self, data, first=[]):
        if first is None or len(first) == 0:
            first = sorted(data.select_dtypes(['object']).columns.values)
            first.extend(sorted(data.select_dtypes(['category']).columns.values))  
        newheaders = first
        newheaders.extend(sorted(set(data.columns.values)-set(first)))
        if len(newheaders) == len(data.columns):
            data = data.reindex(newheaders, axis=1)
        logging.debug (f"Reordered headers: {data.columns.values}")
        return data

    
    def drop_columns(self, data, drops=None, func='contains', dropemptyheader=True, inplace=True, preview=False):
        if data is None:
            return None
        if drops is None:
            drops = self.dropcolumns
        # need to create list of str in order for any function to  work
        # drops = [d.decode() for d in drops if len(d) > 0]    
        currentheaders = list(data.columns.values)
        droplist = []
        for header in currentheaders:
            found = False
            if func == 'startswith':
                found = any(header.startswith(d) for d in drops)
            elif func == 'endswith':
                found = any(header.endswith(d) for d in drops)
            elif func == 'contains':     
                found = any([d in header for d in drops])
            elif func == 'is':     
                found = any(header == d for d in drops)
            found = found or (dropemptyheader and header == ' ')    
            if found:
                droplist.append(header)
        if not preview:
            if inplace:
                data.drop(droplist, axis=1, inplace=inplace)   
            else:
                data = data.drop(droplist, axis=1, inplace=inplace)
        return data, droplist 
    
"""
    def drop_columns(self, data, drops=None, func='startswith', inplace=True, preview=False):
        if data is None:
            return None
        if drops is None:
            drops = self.dropcolumns
        currentheaders = list(data.columns.values)
        droplist = []
        for header in currentheaders:
            found = False
            for d in drops:
                print d, d.strip('*')
                if d.startswith('*'):
                    if d.endswith('*'):
                        func = 'contains'
                        found = header.contains(d.strip('*'))
                    else:
                        func = 'endswith'
                        found = header.endswith(d.strip('*'))
                elif d.endswith('*'):
                    found = header.startswith(d.strip('*'))
                else:
                    found = header == d
                if found:
                    droplist.append(header)
        if not preview:
            if inplace:
                data.drop(droplist, axis=1, inplace=inplace)   
            else:
                data = data.drop(droplist, axis=1, inplace=inplace)
        return data, droplist 
"""