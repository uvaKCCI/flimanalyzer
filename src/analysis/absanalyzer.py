#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:35:56 2020

@author: khs3z
"""

from abc import ABC, abstractmethod
import logging
import importlib

def instantiate_tool(modulename, classname, data, categories, features):
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
        self.data = data
        self.categories = categories
        self.features = features
        
        
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


