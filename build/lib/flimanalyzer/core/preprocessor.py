#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  4 05:16:56 2018

@author: khs3z
"""

def reorder_columns(dataframe, first=[]):
    if first is None or len(first) == 0:
        first = sorted(dataframe.select_dtypes(['object']).columns.values)
        first.extend(sorted(dataframe.select_dtypes(['category']).columns.values))  
    newheaders = first
    newheaders.extend(sorted(set(dataframe.columns.values)-set(first)))
    if len(newheaders) == len(dataframe.columns):
        dataframe = dataframe.reindex(newheaders, axis=1)
    print ("Reordered headers: %s" % dataframe.columns.values)
    return dataframe


class defaultpreprocessor():
    
    def __init__(self):
        self.newheaders = {}
        

    def set_replacementheaders(self, headers):
        self.newheaders = headers
        
        
    def get_replacementheaders(self):
        return self.newheaders
    

    def set_dropcolumns(self, cols):
        self.dropcolumns = cols
        
        
    def rename_headers(self, data, newheaders=None, preview=False):
        if data is None:
            return None
        if newheaders is None:
            newheaders = self.newheaders
        oldheaders = list(data.columns.values)
        currentheaders = [c for c in oldheaders]
#        print "OLD HEADERS", currentheaders, data.shape
        for newheader in newheaders:
            currentheaders = [c.replace(newheader, newheaders[newheader]) for c in currentheaders]
#        for newheader in newheaders:
#            currentheaders = currentheaders.replace(newheader, newheaders[newheader])
#        currentheaders = currentheaders.split('\t')
        changedheaders = {oldheaders[i]:currentheaders[i] for i in range(len(oldheaders)) if oldheaders[i]!=currentheaders[i]}
#        print "NEW HEADERS", currentheaders, data.shape
        if not preview:
            data.columns = currentheaders                
        return data, changedheaders 


    def drop_columns(self, data, drops=None, func='contains', dropemptyheader=True, inplace=True, preview=False):
        if data is None:
            return None
        if drops is None:
            drops = self.dropcolumns
        # need to create list of str in order for any function to  work
        drops = [d.decode() for d in drops if len(d) > 0]    
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