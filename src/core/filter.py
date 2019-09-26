#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Fri May 18 07:53:29 2018

@author: khs3z
"""

class RangeFilter():
    
    def __init__(self,name='', rangelow=0, rangehigh=100, allowedmin=None, allowedmax=None, selected=False, params=None):
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
        
    
    def get_params(self):
        return {'name':self.name, 
                'rangelow':self.rangelow, 
                'rangehigh':self.rangehigh, 
                'allowedmin':self.allowedmin, 
                'allowedmax':self.allowedmax,
                'selected':self.selected}
    
    
    def set_params(self, params):
        self.name = params.get('name','')
        self.rangelow = params.get('rangelow',0) 
        self.rangehigh = params.get('rangehigh',100)
        self.allowedmin = params.get('allowedmin',None) 
        self.allowedmax = params.get('allowedmax',None)
        self.selected = params.get('selected', True)
        self.set_allowed(self.allowedmin, self.allowedmax)
        self.set_range(self.rangelow, self.rangehigh)
        
        
    def set_name(self, newname):
        if newname is not None and len(newname) > 0:
            self.name = newname
            
            
    def get_name(self):
        return self.name
    
    
    def select(self,sel=True):
        self.selected = sel
        
    
    def is_selected(self):
        return self.selected
        
    
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
            
    
    def get_parameters(self):
        return [self.name, self.selected, self.rangelow, self.rangehigh, self.allowedmin, self.allowedmax]