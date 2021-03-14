#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:35:56 2020

@author: khs3z
"""

from abc import ABC, abstractmethod
import logging
import importlib
import inspect
import os
import pkgutil
import importlib

def get_analyzer_classes():
    pkdir = os.path.dirname(__file__)
    for (module_loader, name, ispkg) in pkgutil.iter_modules([pkdir]):
        importlib.import_module('.' + name, __package__)
    available_tools = {str(create_instance(cls, None)): cls for cls in AbstractAnalyzer.__subclasses__()}
    return available_tools

def init_analyzers():
    tools = get_analyzer_classes()
    analyzers = [create_instance(tools[aname], None) for aname in tools]
    return analyzers

def init_default_config(analyzers):
    config = {}
    for a in analyzers:
        config.update({a.name: a.get_default_parameters()})
    return config

def create_instance(clazz, data):
    if isinstance(clazz, str):
        modulename, _, classname = clazz.rpartition('.')
    elif inspect.isclass(clazz):
        modulename = clazz.__module__
        classname = clazz.__name__
    else:
        logging.error(f"Error instantiating {clazz} analysis tool.")        
    logging.debug(f"Analysis Tool modulename={modulename}, classname={classname}")
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        toolinstance = class_(data)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(f"Error instantiating {modulename}.{classname} analysis tool.")
        toolinstance = None
    return toolinstance        
    
class AbstractAnalyzer(ABC):

    def __init__(self, data, **kwargs):
        self.name = __name__
        self.data = data
        self.params = self.get_default_parameters()
        self.params.update({**kwargs})

    def fix_label(self, label):
    	if not isinstance(label, str):
    		label = ','.join(label)
    	return str(label).replace('\'','').replace('(','').replace(')','')
    	
    	
    def _add_picker(self, figure):
        ax_list = figure.axes
        for ax in ax_list:
        	ax.set_picker(True)
        	#print (ax)
        	for artist in ax.get_children():
        		#print (artist)
        		artist.set_picker(True)
        		for c in artist.get_children():
        			c.set_picker(True)
        	#ax.set_title(ax.get_title(), picker=True)
        	ax.set_xlabel(ax.get_xlabel(), picker=True)
        	ax.set_ylabel(ax.get_ylabel(), picker=True)


    def __repr__(self):
        return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_default_parameters(self):
        return {'grouping': [], 'features': []}

    def get_parameters(self):
        return self.params

    def get_config_name(self):
        return ''.join(e for e in self.name if e.isalnum())
        
    def configure(self, **kwargs):
        self.params.update(**kwargs)
        
    @abstractmethod
    def get_required_categories(self):
        return []
    
    @abstractmethod
    def get_required_features(self):
        return ['any']
    
    def run_configuration_dialog(self, parent):
        return {}
    
    @abstractmethod
    def execute(self):
        pass   


