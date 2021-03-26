#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  4 04:02:09 2018

@author: khs3z
"""

import core.configuration as cfg
import logging
import os
import re
import importlib
import pkgutil

def get_available_parsers(pkdir='core.parser'):
    for (module_loader, name, ispkg) in pkgutil.iter_modules([pkdir]):
        importlib.import_module('.' + name, __package__)
    parser_classes = {cls.__name__: cls for cls in defaultparser.__subclasses__()}        
    return parser_classes

    
def instantiate_parser(fullname):
    namesplit = fullname.rpartition('.')
    if len(namesplit) != 3:
        return None
    modulename = fullname.rpartition('.')[0]
    classname = fullname.rpartition('.')[2]
    logging.debug(f"Parser modulename={modulename}, classname={classname}")
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        parserinstance = class_()
    except Exception:
        logging.error(f"Error instantiating {fullname} parser.")
        parserinstance = None
    return parserinstance    
    

class defaultparser(object):

    def __init__(self):
        self.init_patterns()
        self.compile_patterns()

    def is_readonly(self):
        return True
    
    def get_name(self):
        return "Default Parser"
    
    def init_patterns(self):
        self.regexpatterns = []
    
    
    def compile_patterns(self):
        if self.regexpatterns is not None and len(self.regexpatterns) > 0:
            self.compiledpatterns = {rp[cfg.CONFIG_PARSER_CATEGORY]:re.compile(rp[cfg.CONFIG_PARSER_REGEX]) for rp in self.regexpatterns if rp[cfg.CONFIG_PARSER_USE]}
        else:
            self.compiledpatterns = {}    

    def get_config(self):
        return {cfg.CONFIG_PARSER_CLASS:defaultparser.__name__, cfg.CONFIG_PARSER_PATTERNS:self.regexpatterns}
            
    def get_regexpatterns(self):
        return self.regexpatterns

        
    def set_regexpatterns(self, patterns):
        self.regexpatterns = patterns
        self.compile_patterns()        

        
    def parsefilename(self, fname):
        components = {'Directory':os.path.dirname(fname), 'File':os.path.basename(fname)}
        fname = fname.replace("\\",'/')
        for entry in self.regexpatterns:    
            # convert \ in windows style path to / in POSIX style
            if entry[PARSER_USE]:
                match = re.search(entry[PARSER_REGEX], fname)
                if match is not None:
                    matchstr = match.group(1)
                    if match.group(1) == '':
                        components[entry[PARSER_CATEGORY]] = '?'
                    else:
                        components[entry[PARSER_CATEGORY]] = str(matchstr)
        return components       



class no_parser(defaultparser):

    def set_regexpatterns(self, patterns):
        pass
    
    
    def parsefilename(self, fname):
        return {}

    
        
class celltype_compartment_fov_treatment_cell_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Cell line', cfg.CONFIG_PARSER_REGEX:r'.*/(.*?)/.*/'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Compartment', cfg.CONFIG_PARSER_REGEX:r'.*/(.*?)/'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Cell', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](\d*?)\.'}]


class compartment_fov_treatment_cell_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Compartment', cfg.CONFIG_PARSER_REGEX:r'.*/(.*?)/'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Cell', PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](\d*?)\.'}]


        
class compartment_treatment_fov_cell_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Compartment', cfg.CONFIG_PARSER_REGEX:r'.*/(.*?)/'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Cell', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](\d*?)\.'}]



class fov_treatment_cell_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Cell', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](\d*?)\.'}]
#                'FOV':r'[_-](.*?)[_-]',
#                'Treatment':r'[_-].*?[_-](.*?)[_-]',
#                'Cell':r'[_-].*?[_-].*?[_-](\d*?)\.'}


        
class treatment_fov_cell_parser(defaultparser):
        
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Cell', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](\d*?)\.'}]



class treatment_fov_time_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Time', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](\d*?)\.'}]



class treatment_time_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Treatment', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Time', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](\d*?)\.'}]


class fov_time_well_parser(defaultparser):
    
    def init_patterns(self):
        self.regexpatterns = [
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'FOV', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Time', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-](.*?)[_-]'},
                {cfg.CONFIG_PARSER_USE:True, cfg.CONFIG_PARSER_CATEGORY:'Well', cfg.CONFIG_PARSER_REGEX:r'.*/.*?[_-].*?[_-].*?[_-](.*?)\.'}]




#class hyphenparser(defaultparser):
#    
#    def init_patterns(self):
#        self.regexpatterns = {
#                'Treatment':r'[-](\d+?)',
#                'FOV':r'[-]\d*(\D+?)[_-]',
#                'Cell':r'[-].*?[_-].*?[_](\d*?)\.'}

