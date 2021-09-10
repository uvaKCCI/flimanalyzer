#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  5 12:45:21 2018

@author: khs3z
"""

import logging
import json
import collections
from flim.core.filter import RangeFilter
from flim.core.importer import dataimporter
from flim.core.preprocessor import defaultpreprocessor
from flim.analysis.absanalyzer import init_analyzers, init_default_config

CONFIG_USE = 'Use'
CONFIG_ROOT = 'root'
CONFIG_IMPORT = 'import'
CONFIG_CATEGORY_COLUMNS = 'category cols'
CONFIG_FITTING_COLUMNS = 'fitting columns'
CONFIG_PARSER = 'fname parser'
CONFIG_PARSER_CLASS = 'Class'
CONFIG_PARSER_PATTERNS = 'Patterns'
CONFIG_PARSER_USE = 'Use'
CONFIG_PARSER_CATEGORY = 'Category'
CONFIG_PARSER_REGEX = 'Regex'

CONFIG_PREPROCESS = 'preprocess'
CONFIG_DELIMITER = 'delimiter'
CONFIG_HEADERS = 'rename'
CONFIG_INCLUDE_FILES = 'include files'
CONFIG_EXCLUDE_FILES = 'exclude files'
CONFIG_DROP_COLUMNS = 'drop'
CONFIG_CALC_COLUMNS = 'calculate'
CONFIG_FILTERS = 'filters'
CONFIG_SHOW_DROPPED = 'show dropped'
CONFIG_RANGEFILTERS = 'range filters'
CONFIG_SERIESFILTERS = 'series filters'
CONFIG_DATA_DISPLAY = 'display'
CONFIG_ANALYSIS ='analysis'
CONFIG_HISTOGRAMS = 'histograms'
CONFIG_SCATTER = 'scatter'


class Config():
    
    def __init__(self):
        self.parameters = {}
        self.filename = None
        self.modified = False
        
        
    def is_modified(self):
        return self.modified
    
    
    def remove(self, searchkey):
        params,keys = self.get(searchkey, returnkeys=True)
        if params is None and len(keys) == 0:
            # does not exist
            return False
        if len(keys) == 1 and keys[0] == CONFIG_ROOT:
            self.parameters = {}
        else:    
            del self.get_parent(searchkey=keys)[keys[-1]]            
        self.modified = True
        return True
        
    
    def update(self, parameters, parentkeys=None, addmissing=True):
        updated = {}
        notfound = {}
        logging.debug (f"Configuration.UPDATE: keys={parameters.keys()} in {parentkeys}")
        if parentkeys is not None:
            logging.debug (f"\tparentkeys={parentkeys}")
            parentconfig = self.get(parentkeys)
            if parentconfig is None or not isinstance(parentconfig, dict):
                logging.debug ("\tparentconfig is None or not a dictionary")
                if addmissing:
                    params = self.parameters
                    for key in parentkeys:
                        if not key in params or params[key] is None:
                            logging.debug (f"\tcreating missing key {key} for {parentkeys}")
                            params[key] = {}
                        params = params[key]
                    parentconfig = params    
                else:        
                    return {}, parameters
        for key in parameters:
            if parentkeys is None:
                parentconfig = self.get_parent(key, self.parameters)
            if parentconfig is not None:
                parentconfig[key] = parameters[key]    
                updated.update({key:parameters[key]})
            else:
                if addmissing:
                    self.parameters.update({key:parameters[key]})
                    updated.update({key:parameters[key]})
                else:    
                    notfound.update({key:parameters[key]})
        self.modified = self.modified or len(updated) > 0
        return updated, notfound
    
    
    def get_parent(self, searchkey, parameters=None, returnkeys=False):
        if searchkey == CONFIG_ROOT:
            return None
        if not parameters:
            parameters = self.parameters
        if isinstance(searchkey, collections.abc.Iterable) and not isinstance(searchkey, str) and not isinstance(searchkey, bytes) and len(searchkey) > 1:            
            parentconfig, parentkeys = self.get(searchkey[:-1], returnkeys=True)
            lastsearchkey = searchkey[-1]
        else:
            _,keys = self.get(searchkey, returnkeys=True)
            parentconfig, parentkeys = self.get(keys[:-1], returnkeys=True)
            lastsearchkey = keys[-1]
        if not parentconfig or lastsearchkey not in parentconfig:
            parentconfig = None
            parentkeys = []
        if returnkeys:
            return parentconfig, parentkeys
        else:
            return parentconfig
                
        
    def get(self, searchkey=None, startin=None, returnkeys=False):
        
        def return_value(cfg, keys, returnkeys):
            if returnkeys:
                return cfg, keys
            else:
                return cfg
        if searchkey is None: # and startin is None:
            return return_value(self.parameters, None , returnkeys)
        if startin is None:
            startin = self.parameters
        if isinstance(startin, dict):
            if isinstance(searchkey, collections.abc.Iterable) and not isinstance(searchkey, str) and not isinstance(searchkey, bytes):
                if len(searchkey) == 0:
                    return return_value(None,[], returnkeys)
                params, keys = self.get(searchkey[0], startin=startin, returnkeys=True)
                if params is None:
                    return return_value(None,[], returnkeys)
                for pk in searchkey[1:]:
                    params = params.get(pk)
                    if params is None:
                        return return_value(None,[], returnkeys)
                keys.extend(searchkey[1:]) 
#                print "found ", searchkey, "in", keys  
                return return_value(params, keys, returnkeys)
            else:
                if searchkey in startin:
                    return return_value(startin[searchkey], [searchkey], returnkeys)
                else:
                    for key in startin:
                        subparams = startin[key]
                        if subparams is not None:
                            subconfig, keys = self.get(searchkey, startin=subparams, returnkeys=True)
                            if subconfig is not None:
                                keys.insert(0,key)
    #                            print "found ", searchkey, "in", keys  
                                return return_value(subconfig, keys, returnkeys)
        return return_value(None, [], returnkeys)
    
    
    def _to_utf(self, data, ignore_dicts = False):
        # if this is a unicode string, return its string representation
        if isinstance(data, str):
            return data.encode('utf-8')
        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [ self._to_utf(item, ignore_dicts=True) for item in data ]
        # if this is a dictionary, return dictionary of byteified keys and values
        # but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            return {
                self._to_utf(key, ignore_dicts=True): self._to_utf(value, ignore_dicts=True)
                for key, value in data.iteritems()
            }
        # if it's anything else, return it in its original form
        return data    


    def read_from_json(self, configfile, defaultonfail=True):
        try:    
            with open(configfile, 'r') as fp:
                self.parameters = json.load(fp) #, object_hook=self._to_utf)
                self.modified = False
                self.filename = configfile
            return True
        except:
            if defaultonfail:
                self.create_default()
                self.modified = False
                self.filename = None
            return False
            
    
    def write_to_json(self, configfile):
        try:
            with open(configfile, 'w') as fp:
                json.dump(self.parameters, fp, sort_keys=True, indent=4)
                self.modified = False
                self.filename = configfile
        except:
            logging.error(f'Config file could not be saved to {configile}')    
            
    
    def is_not_None(self,searchkeys):
        logging.debug (f"validating searchkeys {searchkeys}, {self.get(searchkeys) is not None}")
        return self.get(searchkeys) is not None


    def _get_required_keys(self):
        return ((CONFIG_ROOT,CONFIG_IMPORT,CONFIG_EXCLUDE_FILES),
                       (CONFIG_ROOT,CONFIG_IMPORT,CONFIG_DELIMITER),
                       (CONFIG_ROOT,CONFIG_IMPORT,CONFIG_FITTING_COLUMNS),
                       (CONFIG_ROOT,CONFIG_PREPROCESS,CONFIG_HEADERS),
                       (CONFIG_ROOT,CONFIG_PREPROCESS,CONFIG_DROP_COLUMNS),
                       (CONFIG_ROOT,CONFIG_PREPROCESS,CONFIG_CALC_COLUMNS),
                       (CONFIG_ROOT,CONFIG_ANALYSIS,CONFIG_HISTOGRAMS),
                       (CONFIG_ROOT,CONFIG_FILTERS,CONFIG_RANGEFILTERS),
                       (CONFIG_ROOT,CONFIG_FILTERS,CONFIG_SERIESFILTERS))
                
    
    def get_nodekeys(self):
        nodes = [tuple(key[:-1]) for key in self.get_keys() if len(key) > 1]
        return sorted(set(nodes))
    
        
    def get_keys(self, startin=None):
        keys = []
        if startin is None:
            startin = self.parameters
        else:
            startin = self.get(startin)    
        if isinstance(startin, dict):   
            for key in startin:
                print (key)
                keys.append([key])
                childrenkeys = self.get_keys(startin[key])
                for c in childrenkeys:
                    keylist = [key]
                    keylist.extend(c)
                    keys.append(keylist)
        return keys
    
        
    def fix(self):
        default = Config()
        default.create_default()
        config = Config()
        # initialize with copy of paramters so a failed fix will not affect the original
        config.update(dict(self.parameters))
        missing,invalid = self.validate()
        for longkey in set(missing + invalid):
            logging.debug (f"\ttrying to find {longkey[-1]} and update {longkey}")
            params,oldkey = config.get(longkey[-1], returnkeys=True)
            while config.remove(oldkey):
                logging.debug (f"\tremoved existing {oldkey}")
            if params is not None:    
                updated, notfound = config.update({longkey[-1]:params},longkey[:-1])
                logging.debug (f"\ttrying to update {longkey}")
            else:
                logging.debug (f"\tadding default for {longkey}")
                updated, notfound = config.update({longkey[-1]:default.get(longkey)}, longkey[:-1])                                
            for u in updated:
                logging.debug (f"\tupdate for {u} successful")
            for nf in notfound:
                logging.debug (f"\tnot found/failed {nf}")
        if config.is_valid():
            self.update(config.get())
            return True
        else:
            return False
            
        
    def validate(self):
        missing_keys = []
        invalid_keys = []
        for longkey in self._get_required_keys():
            parentdict = self.get(longkey[:-1])
            if parentdict is None or longkey[-1] not in parentdict:
                missing_keys.append(longkey)
            elif parentdict[longkey[-1]] is None:
                invalid_keys.append(longkey)    
        return missing_keys,invalid_keys        
        
        
    def is_valid(self):
        for key in self._get_required_keys():
            if not self.is_not_None(key):
                return False
        return True
        
       
    def create_default(self):
        import_config = dataimporter().get_config()
        preprocess_config = defaultpreprocessor().get_config()
        analyzers = init_analyzers()
        analysis_config = init_default_config(analyzers)
        analysis_config[CONFIG_HISTOGRAMS] = []

        datadisplay = [{'name': aname, 'min': 'auto', 'max': 'auto', 'bins': 100} for aname in ['trp t1','trp t2','trp tm']]

        parameters = {
            CONFIG_IMPORT: import_config,
            CONFIG_PREPROCESS: preprocess_config,  
            CONFIG_DATA_DISPLAY: datadisplay,        
            CONFIG_ANALYSIS: analysis_config,
          
            CONFIG_FILTERS: {
                CONFIG_USE: False,
                CONFIG_SHOW_DROPPED: True,
                CONFIG_RANGEFILTERS:[
                        RangeFilter('trp t1',0,2500).get_params(),
                        RangeFilter('trp t2',0,8000).get_params(),
                        RangeFilter('trp tm',0,4000,selected=False).get_params(),
                        RangeFilter('trp a1[%]',0,100).get_params(),
                        RangeFilter('trp a2[%]',0,100).get_params(),
                        RangeFilter('trp a1[%]/a2[%]',0,2).get_params(),
                        RangeFilter('trp E%1',0,100).get_params(),
                        RangeFilter('trp E%2',0,100).get_params(),
                        RangeFilter('trp E%3',0,100).get_params(),
                        RangeFilter('trp r1',0,15).get_params(),
                        RangeFilter('trp r2',0,3).get_params(),
                        RangeFilter('trp r3',0,3).get_params(),
                        RangeFilter('trp chi',0,4.7, selected=True).get_params(),
                        RangeFilter('trp photons',0,160).get_params(),
                        RangeFilter('NAD(P)H t1',0,1000).get_params(),
                        RangeFilter('NAD(P)H t2',0,8000).get_params(),
                        RangeFilter('NAD(P)H tm',0,2000).get_params(),
                        RangeFilter('NAD(P)H photons',0,2000).get_params(),
                        RangeFilter('NAD(P)H a2[%]',0,100).get_params(),
            #                    RangeFilter('NAD(P)H %',0,99).get_params(),
                        RangeFilter('NADPH %',0,99).get_params(),
                        RangeFilter('NADH %',0,100).get_params(),
                        RangeFilter('NADPH/NADH',0,3).get_params(),
                        RangeFilter('NAD(P)H chi',0.7,4.7, selected=True).get_params(),
                        RangeFilter('FAD t1',0,1500).get_params(),
                        RangeFilter('FAD t2',1000,8000).get_params(),
                        RangeFilter('FAD tm',0,2500).get_params(),
                        RangeFilter('FAD a1[%]',0,100).get_params(),
                        RangeFilter('FAD a2[%]',0,100).get_params(),
                        RangeFilter('FAD a1[%]/a2[%]',0,16).get_params(),
                        RangeFilter('FLIRR',0,2.4).get_params(),
                        RangeFilter('FAD chi',0.7,4.7, selected=True).get_params(),
                        RangeFilter('FAD photons',0,800).get_params(),
                        RangeFilter('FAD photons/NAD(P)H photons',0,2).get_params(),
                ],
                CONFIG_SERIESFILTERS:[
                ],
            },            
        }
        self.parameters = {CONFIG_ROOT:parameters}            


if __name__ == '__main__':
    config = Config()
    config.create_default()
    cfg = config.get()
    print (json.dumps(cfg, sort_keys=True, indent=4, separators=(',', ': ')))
    
    # Test get
    cfg, keys = config.get([CONFIG_FILTERS], returnkeys=True)
    print (keys)
    cfg = config.get([CONFIG_PARSER_CLASS], returnkeys=False)
    print (json.dumps(cfg, sort_keys=True, indent=4))
    
    # get root parameter dict
    print (config.get())

    # Test get_parent
    pcfg,pkeys = config.get_parent(['FAD chi'], returnkeys=True)
    print (pkeys)
    pcfg = config.get_parent(['FAD chi'], returnkeys=False)
    print (pcfg)

    # Test update
    updated, notfound = config.update({CONFIG_PARSER_CLASS: 'my.parser'}, [CONFIG_ROOT, CONFIG_IMPORT])
    print (f"updated: {updated}")
    print (f"not found: {notfound}")
    print (config.get(CONFIG_PARSER_CLASS, returnkeys=True))
    
    # Test validate
    missing,invalid = config.validate()
    print (f"missing keys: {missing}")
    print (f"invalid keys: {invalid}")
    
    # Test get_keys
    print ("keys\n", "\n".join(str(k) for k in config.get_keys()), "\n")
    
    # Test get_node_keys
    print ("node keys\n", "\n".join(str(k) for k in config.get_nodekeys()), "\n")
    

    
