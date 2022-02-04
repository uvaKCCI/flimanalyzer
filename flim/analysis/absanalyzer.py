#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 14:35:56 2020

@author: khs3z
"""

from abc import ABC, abstractmethod
import logging
import inspect
import os
import pkgutil
import importlib
import wx

def get_analyzer_classes():
    """Creates labels and class objects for all AbstractAnalyzer subclasses in this package.
    
    Returns:
        dict: key-value pairs of analyzer labels and associated classes. 
    """
    
    pkdir = os.path.dirname(__file__)
    for (module_loader, name, ispkg) in pkgutil.iter_modules([pkdir]):
        importlib.import_module('.' + name, __package__)
    available_tools = {str(create_instance(cls, None)): cls for cls in AbstractAnalyzer.__subclasses__()}
    return available_tools

def init_analyzers():
    """Initializes an analyzer instance for each individual AbstractAnalyzer subclass in this package.
    
    Returns:
        list: analyzer object instances.
    """    
    tools = get_analyzer_classes()
    analyzers = [create_instance(tools[aname], None) for aname in tools]
    return analyzers

def init_default_config(analyzers):
    """Creates a single configuration with default settings for a given group of Analyzer objects.
    
    Args:
        list: analyzer objects.
    
    Returns:
        dict: configuration parameters.
    """
    config = {}
    for a in analyzers:
        config.update({a.name: a.get_default_parameters()})
    return config

def create_instance(clazz, data):
    """Creates analyzer instance.
    
    Args:
        clazz (class): analyzer class to instantiate.
        data (pandas.DataFrame): DataFrame to be used by analyzer instance
        # data_choices (dict): available dataframes. Keys are window names/labels, values are associated dataframes
    
    Returns:
        analyzer object (AbstractAnalyzer subclass)
    """     
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
        toolinstance = class_(data) #, data_choices=data_choices)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(f"Error instantiating {modulename}.{classname} analysis tool.")
        toolinstance = None
    return toolinstance        


class AbstractAnalyzer(ABC):
    """Abstract class used to template analysis classes."""

    def __init__(self, data, **kwargs):
        """Initializes AbstractAnalyzer class with data and configuration parameters
        
        Args:
            data (pandas.DatFrame): DataFrame to be analyzed.
            kwargs: configuration parameters
        """
        self.name = __name__
        self.data = data
        self.params = self.get_default_parameters()
        self.params.update({**kwargs})
        
    def get_description(self):
        """Returns a description for this analyzing module. This may include instructions on how to use the parameters.

        Returns:
            String: the description.

        """
        return self.name
            
    def get_icon(self):
        """Returns icon for this analysis.

        Returns:
            wx.Bitmap: The bitmap of the icon.

        """
        return wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE)
        
        
    def _fix_label(self, label):
        """Removes special characters from label string.
        
        Args:
            label (str): the label to be fixed.
             
        Returns:
            str: modified label.

        """
        if not isinstance(label, str):
            if isinstance(label, list):
                label = ','.join(str(label))
            else:
                label = str(label)
        return str(label).replace('\'','').replace('(','').replace(')','')
    	
    	
    def _add_picker(self, figure):
        """Enables picker to figure's axes, their children and grandchildren.
        
        Args:
            figure (Figure): the figure for which the pickers will be enabled. 
        """
        
        ax_list = figure.axes
        for ax in ax_list:
        	ax.set_picker(True)
        	for artist in ax.get_children():
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
        return {'grouping': [], 'features': [], 'input': {}}

    def get_parameters(self):
        return self.params

    def get_config_name(self):
        return ''.join(e for e in self.name if e.isalnum())
        
    def configure(self, **kwargs):
        """Updates the configuration with the passed arguments.
        
        The configuration is updated not replaced, i.e values of matching keys are 
        overwritten, values of non-matching keys remain unaltered.
        
        Args:
            kwargs: the new key:value pairs.  
        """
        self.params.update(**kwargs)
        
    @abstractmethod
    def get_required_categories(self):
        """Returns the category column names that are required in the data to be analyzed. 
        
        Category columns use 'category' as dtype in Pandas dataframe.
        
        Returns:
            list(str): List of column names.
        """
        return []
    
    @abstractmethod
    def get_required_features(self):
        """Returns the non-category column names that are required in the data to be analyzed. 
        
        Non-category columns are all those columns that do not use 'category' as dtype in Pandas dataframe.

        Returns:
            list(str): List of column names.
        """
        return ['any']
    
    def run_configuration_dialog(self, parent, data_choices={}):
        """Executes the anaylzer's configuration dialog.
        
        The dialog is initialized with values of the analyzer's Config object.
        
        Returns:
            dict: The specified key:value pairs.
        """    
        return {}
    
    @abstractmethod
    def execute(self):
        """Executes the analysis using the analyzer's set data and configuration.
        
        Returns:
           dict: Dictionary of pandas.DataFrame and/or matplotlib.pyplot.Figure objects.
                 Keys represent window titles, values represent the DataFrame or Fugure 
                 objects.
        """
        return {}   


