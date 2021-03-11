#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 18 07:53:29 2018

@author: khs3z
"""

import logging
import numpy as np

class Filter:
    
    def __init__(self, name, selected=False, params=None, descr=''):
        if name is None:
            self.name = 'Basic Filter'
        else:
            self.name = name
        self.selected = selected    
        self.parameters = params    
        self.description = descr
    
    def set_params(self, params):
        self.parameters = params
        
    def set_parameter_item(self, key, value):
        self.parameters[key] = value
    
    def get_paramter_item(self, key):
        return self.parameters.get(key)
    
    def set_name(self, newname):
        if newname is not None and len(newname) > 0:
            self.name = newname
                    
    def get_name(self):
        return self.name

    def get_description(self):
        if self.description is None:
            return 'Not provided.'
        else:
            return self.description
    
    def get_params(self):
        return self.parameters
  
    def select(self,sel=True):
        self.selected = sel
        
    def is_selected(self):
        return self.selected
                  
    def apply(self, data):
        return data
    
    def get_dropped(self, data):
    	return []
        

class SeriesFilter(Filter):
    
    def __init__(self, *args, **kwargs):
        super.__init__(self, args, kwargs)
        
    
    
class RangeFilter(Filter):
    
    def __init__(self,name='', rangelow=0, rangehigh=100, allowedmin=None, allowedmax=None, selected=False, dropna=True, params=None):
        if params:
            self.set_params(params)
        else:    
            self.name = name
            self.allowedmin = allowedmin
            self.allowedmax = allowedmax
            self.rangelow = rangelow
            self.rangehigh = rangehigh
            self.set_allowed(allowedmin, allowedmax)
            self.set_range(rangelow,rangehigh)
            self.selected = selected
            self.dropna = dropna
        
    
    def get_params(self):
        return {'name':self.name, 
                'rangelow':self.rangelow, 
                'rangehigh':self.rangehigh, 
                'allowedmin':self.allowedmin, 
                'allowedmax':self.allowedmax,
                'selected':self.selected,
                'dropna':self.dropna}
    
    
    def set_params(self, params):
        self.name = params.get('name','')
        self.rangelow = params.get('rangelow',0) 
        self.rangehigh = params.get('rangehigh',100)
        self.allowedmin = params.get('allowedmin',None) 
        self.allowedmax = params.get('allowedmax',None)
        self.selected = params.get('selected', True)
        self.dropna = params.get('dropna', True)
        self.set_allowed(self.allowedmin, self.allowedmax)
        self.set_range(self.rangelow, self.rangehigh)
        
            
    def clip_range(self):
        if self.allowedmin is not None and self.rangelow < self.allowedmin:
            self.rangelow = self.allowedmin
        if self.allowedmax is not None and self.rangehigh > self.allowedmax:
            self.rangemax = self.allowedmax
        return self.rangelow, self.rangehigh    
        
        
    def set_range(self, low, high):
        self.rangelow = low
        self.rangehigh = high
#        if low <= high:
#            self.rangelow = low
#            self.rangehigh = high
#        else:
#            self.rangelow = high
#            self.rangehigh = low
        return self.clip_range()
    
    
    def set_rangelow(self, low):
        self.set_range(low, self.rangehigh)
    
    
    def set_rangehigh(self, high):
        self.set_range(self.rangelow, high)
        
        
    def get_range(self):
        return self.rangelow, self.rangehigh
   
    
    def get_rangelow(self):
        return self.rangelow
    
    
    def get_rangehigh(self):
        return self.rangehigh
    
    
    def is_identical_range(self, rlow, rhigh):
        return rlow == self.rangelow and rhigh == self.rangehigh
    
    
    def set_allowed(self, mina, maxa):
        self.allowedmin = mina
        self.allowedmax = maxa
        if mina is not None and maxa is not None and mina > maxa:
            self.allowedmin = maxa
            self.allowedmax = mina
        self.clip_range()
            
    
    #def get_parameters(self):
    #    return [self.name, self.selected, self.rangelow, self.rangehigh, self.allowedmin, self.allowedmax, self.dropna]
        
    def apply_filter(self, data, inplace=True):
    	droppedrows = self.get_dropped(data)
    	filtereddata = data.drop(droppedrows, inplace=inplace)
    	return filtereddata
    	
    	
    def get_dropped(self, data):
        if self.name not in data.columns.values:
            return []
        low,high = self.get_range()
        logging.debug (f"{self.is_selected()}, filtering {self.name}: {low}, {high}")
        droppedrows = []
        if self.dropna:
            droppedrows = np.flatnonzero((data[self.name] != data[self.name]) | (data[self.name] > high) | (data[self.name] < low))
        else:    
            droppedrows = np.flatnonzero((data[self.name] > high) | (data[self.name] < low))
        logging.debug(f"dropped rows: {droppedrows}")    
        return droppedrows