#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 12:45:21 2022

@author: khs3z
"""
import logging
import inspect
import os
import pkgutil
import importlib
from abc import ABC, abstractmethod
from prefect import Task
import pandas as pd
import matplotlib.figure
import os


PLUGINS = {}

def plugin(plugintype):
    """Register an instantiated plugin to the PLUGINS dict."""

    if plugintype not in PLUGINS:
        PLUGINS[plugintype] = {}

    def wrapper_register_plugin(plugin_class):
        logging.debug(f'Registering {plugin_class}')
        pluginst = plugin_class(None) #instantiate the plugin 
        name = pluginst.name
        if name in get_plugin_class(name):
            raise NameConflictError(
            f"Plugin name conflict: '{name}'. Double check" \
             " that all plugins have unique names.")

        PLUGINS[plugintype][name] = plugin_class
        return plugin_class 

    return wrapper_register_plugin

def discover_plugin_classes(dirs=['data','analysis','workflow']):
    """Creates labels and class objects for all Plugin subclasses in this package.
    
    Returns:
        dict: key-value pairs of analyzer labels and associated classes. 
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    available_tools = {}
    for dir in dirs:
        logging.debug(f'Searching {dir} for plugins.')
        pkdir = os.path.join(this_dir, dir)
        #pkdir = os.path.dirname(__file__)
        for (module_loader, name, ispkg) in pkgutil.iter_modules([pkdir]):
            importlib.import_module('.' + name, __package__ + "." + dir)
        available_tools = {str(create_instance(cls, None)): cls for cls in AbstractPlugin.__subclasses__()}
        available_tools = {k:v for k,v in available_tools.items() if k != 'None'}
    return available_tools

def get_plugin_class(key, tosearch=PLUGINS):
    for k, v in tosearch.items():
        if k == key:
            yield v
        if isinstance(v, dict):
              for result in get_plugin_class(key, tosearch=v):
                yield result
        elif isinstance(v, list):
            for d in v:
                for result in get_plugin_class(key, tosearch=d):
                    yield result
                        
def init_plugins():
    """Initializes an instance for each individual Plugin subclass in this package.
    
    Returns:
        list: analyzer object instances.
    """    
    classes = get_plugin_classes()
    plugins = [create_instance(classes[name], None) for name in classes]
    plugins = [p for p in plugins if p is not None]
    return plugins

def init_plugins_configs():
    """Creates a single configuration with default settings for a given group of Plugin objects.
    
    Args:
        list: plugin objects.
    
    Returns:
        dict: configuration parameters.
    """
    #plugins = init_plugins()
    config = {}
    for plugintype, subplugins in PLUGINS.items():
        for pname, pclass in subplugins.items():
            p = create_instance(pclass, None)
            config.update({p.name: p.get_default_parameters()})
    return config

def create_instance(clazz, data):
    """Creates analyzer instance.
    
    Args:
        clazz (class): analyzer class to instantiate.
        data (pandas.DataFrame): DataFrame to be used by analyzer instance
        # data_choices (dict): available dataframes. Keys are window names/labels, values are associated dataframes
    
    Returns:
        analyzer object (AbstractPlugin subclass)
    """     
    if isinstance(clazz, str):
        modulename, _, classname = clazz.rpartition('.')
    elif inspect.isclass(clazz):
        modulename = clazz.__module__
        classname = clazz.__name__
    else:
        logging.error(f"Error instantiating {clazz} plugin tool.")  
        modulename = '<unresolved>'
        classname = '<unresolved>'
        toolinstance = None      
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        toolinstance = class_(data) #, data_choices=data_choices)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(f"Error instantiating {modulename}.{classname} plugin tool.")
        toolinstance = None
    logging.debug(f"Plugin modulename={modulename}, classname={classname}")
    return toolinstance       


class AbstractPlugin(Task):
    """Abstract class used to template analysis classes."""

    def __init__(self, data, *args, input_select=None, **kwargs):#data, **kwargs):
        """Initializes AbstractPlugin class with data and configuration parameters
        
        Args:
            data (pandas.DatFrame): DataFrame to be analyzed.
            kwargs: configuration parameters
        """
        # get tool specific defaults, pass non-tool args and kwargs to superclass 
        self.params = self.get_default_parameters()
        superkwargs = {k:v for k,v in kwargs.items() if k not in self.params}
        super().__init__(*args, **superkwargs)
        #self.name = __name__
        self.set_input(data, input_select)
        # update tool-specific kwargs
        self.params.update({k:v for k,v in kwargs.items() if k in self.params})        
        
        #self.name = __name__
        #self.data = data
        #self.params = self.get_default_parameters()
        #self.params.update({**kwargs})
        
    def set_input(self, data, input_select):
        input_labels = None
        if isinstance(data,dict):
            input_labels = list(data.keys())
            if input_select is None or isinstance(input_select[0], int):
                data = list(data.values())
            else:
                # convert to list of data
                data = [data[k] for k in input_select]
                # convert to list of int
                input_select = range(len(input_select))
        if isinstance(data,list):
            if input_labels is None:
                input_labels = ['Data'] * len(data)
            if input_select is None:
            	self.data = data
            	self.input_labels = input_labels
            elif len(input_select) == 1 and max(input_select) < len(data):
                self.data = data[input_select[0]]
                self.input_labels = input_labels[input_select[0]]
            else:
                self.data = [data[i] for i in input_select if i < len(data)]
                self.input_labels = [input_labels[i] for i in input_select if i < len(input_labels)]
        else:
            self.data = data
            self.input_label = 'Data'
        logging.debug (f'Setting input for {self.name} to {type(data)}')

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
        return f'<{type(self).__name__}>: {self.name}'

    def __str__(self):
        return self.name

    def get_default_parameters(self):
        return {'grouping': [], 'features': [], 'input': {}}

    def get_parameters(self):
        return self.params

    def get_config_name(self):
        return ''.join(e for e in self.name if e.isalnum())

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

    def input_definition(self):
        return [pd.DataFrame]
        
    def output_definition(self):
        return {f'Data: {self.name}':pd.DataFrame}
        
    def configure(self, **kwargs):
        """Updates the configuration with the passed arguments.
        
        The configuration is updated not replaced, i.e values of matching keys are 
        overwritten, values of non-matching keys remain unaltered.
        
        Args:
            kwargs: the new key:value pairs.  
        """
        self.params.update(**kwargs)
        
    @abstractmethod
    def execute(self):
        """Executes the analysis using the analyzer's set data and configuration.
        
        Returns:
           dict: Dictionary of pandas.DataFrame and/or matplotlib.pyplot.Figure objects.
                 Keys represent window titles, values represent the DataFrame or Fugure 
                 objects.
        """
        return {} 

    def run(self, data=[], input_select=None, **kwargs):
        self.set_input(data, input_select)
        self.configure(**kwargs)
        return self.execute() 


class DataBucket(AbstractPlugin):

    def __init__(self, data, *args, name='Data Bucket', **kwargs):
        super().__init__(data, *args, name=name, **kwargs)
        #self.name = self._get_input_label(data)
    
    def _get_input_label(self, data):
        if data is not None:
            return type(data).__name__
        else:
            return 'Data'
         
    def output_definition(self):
        return {self.name: None}
        
    def configure(self, **kwargs):
        pass
        
    def execute(self):
        self.name = self._get_input_label(self.data)
        logging.debug (f'Executing {self.name} -- type(self.data)={type(self.data)}')
        return self.data
    
    def run(self, name=None, data=[], input_select=None, **kwargs):
        if name is not None:
            self.name = name
        return super().run(data=data, input_select=input_select, **kwargs)
        
        
# auto run on import to populate the PLUGIN dictionary
discover_plugin_classes()