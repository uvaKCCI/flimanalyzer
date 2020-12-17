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

def create_instance(clazz, data, categories, features):
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
        toolinstance = class_(data, categories, features)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(f"Error instantiating {modulename}.{classname} analysis tool.")
        toolinstance = None
    return toolinstance        
    
class AbstractAnalyzer(ABC):

    def __init__(self, data, categories, features):
        self.name = __name__
        self.data = data
        self.categories = categories
        self.features = features
        
    @abstractmethod
    def configure(self, params):
        pass
        
    @abstractmethod
    def get_required_categories(self):
        return []
    
    @abstractmethod
    def get_required_features(self):
        return []
    
    @abstractmethod
    def get_configuration_dialog(self):
        pass
    
    @abstractmethod
    def execute(self):
        pass   

