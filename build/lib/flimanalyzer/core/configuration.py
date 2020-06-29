#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  5 12:45:21 2018

@author: khs3z
"""
import json
import collections
from core.filter import RangeFilter

CONFIG_ROOT = 'root'
CONFIG_IMPORT = 'import'
CONFIG_PREPROCESS = 'preprocess'
CONFIG_DELIMITER = 'delimiter'
CONFIG_PARSERCLASS = 'parser'
CONFIG_HEADERS = 'headers'
CONFIG_EXCLUDE_FILES = 'exclude files'
CONFIG_DROP_COLUMNS = 'drop columns'
CONFIG_CALC_COLUMNS = 'calculate columns'
CONFIG_FILTERS = 'filters'
CONFIG_RANGEFILTERS = 'range filters'
CONFIG_ANALYSIS ='analysis'
CONFIG_HISTOGRAMS = 'histograms'
CONFIG_CATEGORIES = 'categories'
CONFIG_SCATTER = 'scatter'


class Config():
    
    def __init__(self):
        self.parameters = {}
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
        print ("Configuration.UPDATE: keys=", parameters.keys(), "in", parentkeys)
        if parentkeys is not None:
            print ("\tparentkeys", parentkeys)
            parentconfig = self.get(parentkeys)
            if parentconfig is None or not isinstance(parentconfig, dict):
                print ("\tparentconfig is None not dict")
                if addmissing:
                    params = self.parameters
                    for key in parentkeys:
                        if not key in params or params[key] is None:
                            print ("\tcreating missing key",key, "for", parentkeys)
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
        if isinstance(searchkey, collections.Iterable) and not isinstance(searchkey, str) and not isinstance(searchkey, bytes) and len(searchkey) > 1:            
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
            if isinstance(searchkey, collections.Iterable) and not isinstance(searchkey, str) and not isinstance(searchkey, bytes):
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
        return return_value(None,[], returnkeys)
    
    
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
                self.parameters = json.load(fp, object_hook=self._to_utf)
                self.modified = False
                return True
        except:
            if defaultonfail:
                self.parameters = self.create_default()
            return False
            
    
    def write_to_json(self, configfile):
        with open(configfile, 'w') as fp:
            #config = dict(self.config)
            #filters = self.get(searchkey=CONFIG_FILTERS)
            #for key in filters:
            #    #print filters[key]
            #    filters[key] = filters[key].get_params_asdict()
            json.dump(self.parameters, fp, sort_keys=True, indent=4)
            self.modified = False
            
    
    def is_not_None(self,searchkeys):
        print ("validating searchkeys", searchkeys,self.get(searchkeys) is not None)
        return self.get(searchkeys) is not None


    def _get_required_keys(self):
        return ((CONFIG_ROOT,CONFIG_IMPORT,CONFIG_EXCLUDE_FILES),
                       (CONFIG_ROOT,CONFIG_IMPORT,CONFIG_DELIMITER),
                       (CONFIG_ROOT,CONFIG_IMPORT,CONFIG_PARSERCLASS),
                       (CONFIG_ROOT,CONFIG_PREPROCESS,CONFIG_HEADERS),
                       (CONFIG_ROOT,CONFIG_PREPROCESS,CONFIG_DROP_COLUMNS),
                       (CONFIG_ROOT,CONFIG_PREPROCESS,CONFIG_CALC_COLUMNS),
                       (CONFIG_ROOT,CONFIG_ANALYSIS,CONFIG_HISTOGRAMS),
                       (CONFIG_ROOT,CONFIG_ANALYSIS,CONFIG_CATEGORIES),
                       (CONFIG_ROOT,CONFIG_FILTERS,CONFIG_RANGEFILTERS))
                
    
    def get_nodekeys(self):
        nodes = [tuple(key[:-1]) for key in self.get_keys() if len(key) > 1]
        return sorted(set(nodes))
    
        
    def get_keys(self, startin=None):
        keys = []
        if startin is None:
            startin = self.parameters
        if isinstance(startin, dict):   
            for key in startin:
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
            print ("\ttrying to find", longkey[-1],"and update",longkey)
            params,oldkey = config.get(longkey[-1], returnkeys=True)
            while config.remove(oldkey):
                print ("\tremoved existing", oldkey)
            if params is not None:    
                updated, notfound = config.update({longkey[-1]:params},longkey[:-1])
                print ("\ttrying to update", longkey)
            else:
                print ("\tadding default for", longkey)
                updated, notfound = config.update({longkey[-1]:default.get(longkey)}, longkey[:-1])                                
            for u in updated:
                print ("\tupdate for", u, "successful")
            for nf in notfound:
                print ("\tnot found/failed", nf)
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
        parameters = {
            CONFIG_IMPORT: {
                CONFIG_EXCLUDE_FILES: [],
                CONFIG_DELIMITER:'\t',
                CONFIG_PARSERCLASS: 'core.parser.defaultparser',
                },
            CONFIG_PREPROCESS: {
                CONFIG_HEADERS: {
                    'Exc1_-Ch1-_':'trp ', 
                    'Exc1_-Ch2-_':'NAD(P)H ', 
                    'Exc2_-Ch3-_':'FAD '},
                CONFIG_DROP_COLUMNS: [
                    'Exc1_',
                    'Exc2_',
                    'Exc3_',], 
                CONFIG_CALC_COLUMNS: [
                    'NAD(P)H tm', 'NAD(P)H a2[%]/a1[%]', 
                    'NADPH %','NADPH/NADH', #'NAD(P)H %','NAD(P)H/NADH', 
                    'NADH %',  
                    'trp tm', 
                    'trp E%1', 'trp E%2', 'trp E%3', 
                    'trp r1', 'trp r2', 'trp r3', 
                    'trp a1[%]/a2[%]', 
                    'FAD tm', 'FAD a1[%]/a2[%]', 'FAD photons/NAD(P)H photons',
                    'NAD(P)H tm/FAD tm',
                    'FLIRR',
                    'NADPH a2/FAD a1'],
                },
            CONFIG_ANALYSIS: {
                CONFIG_HISTOGRAMS: {
                    'trp t1': [0,8000,81,['Treatment']],
                    'trp t2': [0,8000,81,['Treatment']],
                    'trp tm': [0,4000,81,['Treatment']],
                    'trp a1[%]': [0,100,21,['Treatment']],
                    'trp a2[%]': [0,100,21,['Treatment']],
                    'trp a1[%]/a2[%]': [0,2,81,['Treatment']],
                    'trp E%1': [0,100,21,['Treatment']],
                    'trp E%2': [0,100,21,['Treatment']],
                    'trp E%3': [0,100,21,['Treatment']],
                    'trp r1': [0,100,21,['Treatment']],
                    'trp r2': [0,100,21,['Treatment']],
                    'trp r3': [0,100,21,['Treatment']],
                    'trp chi': [0,4.7,81,['Treatment']],
                    'trp photons': [0,160,81,['Treatment']],
                    'NAD(P)H t1': [0,800,81,['Treatment']],
                    'NAD(P)H t2': [0,400,81,['Treatment']],
                    'NAD(P)H tm': [0,2000,81,['Treatment']],
                    'NAD(P)H photons': [0,2000,81,['Treatment']],
                    'NAD(P)H a2[%]': [0,100,51,['Treatment']],
        #                    'NAD(P)H %': [0,99,34,['Treatment']],
                    'NADPH %': [0,99,34,['Treatment']],
                    'NADH %': [0,100,51,['Treatment']],
                    'NAD(P)H/NADH': [0,3,31,['Treatment']],
                    'NAD(P)H chi': [0.7,4.7,81,['Treatment']],
                    'FAD t1': [0,4000,81,['Treatment']],
                    'FAD t2': [1000,7000,81,['Treatment']],
                    'FAD tm': [0,4000,81,['Treatment']],
                    'FAD a1[%]': [0,100,51,['Treatment']],
                    'FAD a2[%]': [0,100,21,['Treatment']],
                    'FAD a1[%]/a2[%]': [0,16,81,['Treatment']],
                    'FAD chi': [0.7,4.7,81,['Treatment']],
                    'FAD photons': [0,800,81,['Treatment']],
                    'FLIRR': [0,2.4,81,['Treatment']],
                    'NADPH a2/FAD a1': [0,10,101,['Treatment']],
                    },
                CONFIG_CATEGORIES: {
                    'trp t1': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp t2': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp tm': [[0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 30], [str(i) for i in range(1,9)]],
                    'trp a1[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp a2[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp a1[%]/a2[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp E%1': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp E%2': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp E%3': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp r1': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp r2': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp r3': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp chi': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'trp photons': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NAD(P)H t1': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NAD(P)H t2': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NAD(P)H tm': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NAD(P)H photons': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NAD(P)H a2[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
        #                    'NAD(P)H %': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NADPH %': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NADH %': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NADPH/NADH': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'NAD(P)H chi': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD t1': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD t2': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD tm': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD a1[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD a2[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD a1[%]/a2[%]': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FLIRR': [[-300, -20, -10.0, 0, 10.0, 20, 300], [str(i) for i in range(1,7)]],
                    'FAD chi': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    'FAD photons': [[1.0, 2.0, 3.0, 4.0], [str(i) for i in range(1,4)]],
                    }, 
                },            
            CONFIG_FILTERS: {
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
            },            
        }
        self.parameters = {CONFIG_ROOT:parameters}            


if __name__ == '__main__':
    config = Config()
    config.create_default()
    
    # Test get
    cfg, keys = config.get([CONFIG_FILTERS], returnkeys=True)
    print (keys)
    cfg = config.get([CONFIG_PARSERCLASS], returnkeys=False)
    print (json.dumps(cfg, sort_keys=True, indent=4, separators=(',', ': ')), "\n")
    
    # get root parameter dict
    print (config.get(),"\n")

    # Test get_parent
    pcfg,pkeys = config.get_parent(['FAD chi'], returnkeys=True)
    print (pkeys, "\n")
    pcfg = config.get_parent(['FAD chi'], returnkeys=False)
    print (pcfg, "\n")

    # Test update
    updated, notfound = config.update({CONFIG_PARSERCLASS: 'my.parser'}, [CONFIG_ROOT, CONFIG_IMPORT])
    print ("updated:", updated)
    print ("not found:", notfound)
    print (config.get(CONFIG_PARSERCLASS, returnkeys=True),"\n")
    
    # Test validate
    missing,invalid = config.validate()
    print ("missing keys:", missing)
    print ("invalid keys:", invalid, "\n")
    
    # Test get_keys
    print ("keys\n", "\n".join(str(k) for k in config.get_keys()), "\n")
    
    # Test get_node_keys
    print ("node keys\n", "\n".join(str(k) for k in config.get_nodekeys()), "\n")
    
