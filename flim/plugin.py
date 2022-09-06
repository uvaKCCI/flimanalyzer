#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 10 12:45:21 2022

@author: khs3z
"""
import importlib
import inspect
import logging
import matplotlib.figure
import os
import pandas as pd
import pkgutil
import re
import typing
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Union,
    Tuple,
    Type,
)
from abc import ABC, abstractmethod
from prefect import Task, task


PLUGINS = {}
ALL_FEATURES = "all_features"


@task
def perm(a, b):
    combinations = list(itertools.product(a, b))
    return tuple(map(itemgetter(0), combinations)), tuple(
        map(itemgetter(1), combinations)
    )


@task
def product(x, y):
    return list(itertools.product(x, y))


@task
def select(listofdict, key_pattern="(.*?)", value_pattern=None):
    result = [
        v for entry in listofdict for k, v in entry.items() if re.search(key_pattern, k)
    ]
    if value_pattern:
        try:
            result = [
                element
                for r in result
                for element in r
                if (isinstance(r, list) and re.search(value_pattern, element))
            ]
        except:
            pass
    logging.debug(
        f"{key_pattern}, {value_pattern}: {[d.keys() for d in listofdict]},"
        f" result={result}"
    )
    return result


def plugin(plugintype):
    """Register an instantiated plugin to the PLUGINS dict."""

    if plugintype not in PLUGINS:
        PLUGINS[plugintype] = {}

    def wrapper_register_plugin(plugin_class):
        logging.debug(f"Registering {plugin_class}")
        pluginst = plugin_class()  # instantiate the plugin
        name = pluginst.name
        if name in get_plugin_class(name):
            raise NameConflictError(
                f"Plugin name conflict: '{name}'. Double check"
                " that all plugins have unique names."
            )

        PLUGINS[plugintype][name] = plugin_class
        return plugin_class

    return wrapper_register_plugin


def discover_plugin_classes(dirs=["data", "analysis", "workflow"]):
    """Creates labels and class objects for all Plugin subclasses in this package.

    Returns:
        dict: key-value pairs of analyzer labels and associated classes.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    available_tools = {}
    for dir in dirs:
        logging.debug(f"Searching {dir} for plugins.")
        pkdir = os.path.join(this_dir, dir)
        # pkdir = os.path.dirname(__file__)
        for module_loader, name, ispkg in pkgutil.iter_modules([pkdir]):
            importlib.import_module("." + name, __package__ + "." + dir)
        available_tools = {
            str(create_instance(cls)): cls for cls in AbstractPlugin.__subclasses__()
        }
        available_tools = {k: v for k, v in available_tools.items() if k != "None"}
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
    plugins = [create_instance(classes[name]) for name in classes]
    plugins = [p for p in plugins if p is not None]
    return plugins


def init_plugins_configs():
    """Creates a single configuration with default settings for a given group of Plugin objects.

    Args:
        list: plugin objects.

    Returns:
        dict: configuration parameters.
    """
    # plugins = init_plugins()
    config = {}
    for plugintype, subplugins in PLUGINS.items():
        for pname, pclass in subplugins.items():
            p = create_instance(pclass)
            config.update({p.name: p.get_default_parameters()})
    return config


def create_instance(clazz):
    """Creates analyzer instance.

    Args:
        clazz (class): analyzer class to instantiate.

    Returns:
        analyzer object (AbstractPlugin subclass)
    """
    if isinstance(clazz, str):
        modulename, _, classname = clazz.rpartition(".")
    elif inspect.isclass(clazz):
        modulename = clazz.__module__
        classname = clazz.__name__
    else:
        logging.error(f"Error instantiating {clazz} plugin tool.")
        modulename = "<unresolved>"
        classname = "<unresolved>"
        toolinstance = None
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        toolinstance = class_()  # , data_choices=data_choices)
    except Exception as err:
        logging.error(f"Error: {err}")
        logging.error(f"Error instantiating {modulename}.{classname} plugin tool.")
        toolinstance = None
    logging.debug(f"Plugin modulename={modulename}, classname={classname}")
    return toolinstance


class AbstractPlugin(Task):
    """Abstract class used to template plugins for data manipulation, analysis, plotting."""

    def __init__(
        self,
        name: str = __name__,
        input: Dict[str, Any] = input,
        input_select: str = None,
        **kwargs,
    ):
        """Initializes AbstractPlugin class with input and configuration parameters

        Args:
            name (str): display name
            input (Dict[str: Any]): data to process
            input_select (List[int|str]): list of input indices (if input is list) or list of strings (if input is dict)
            kwargs: configuration parameters
        """
        # get plugin specific defaults, pass non-plugin kwargs to superclass
        self.params = self.get_default_parameters()
        superkwargs = {k: v for k, v in kwargs.items() if k not in self.params}
        super().__init__(name=name, **superkwargs)
        # update plugin-specific kwargs
        self.params.update({k: v for k, v in kwargs.items() if k in self.params})
        self.set_input(input, input_select)

    def set_input(self, input: dict, input_select: list = []) -> dict:
        if isinstance(input, list):
            if isinstance(input[0], dict):
                # flatten list of dict
                # input = {k: entry[k] for entry in input for i,k in enumerate(entry.keys())}
                input = {
                    f"{k}-{i:04d}": v
                    for i, entry in enumerate(input)
                    for k, v in entry.items()
                }
        input_labels = None
        if isinstance(input, dict):
            if input_select is not None:
                if isinstance(input_select[0], int):
                    input_labels = list(input.keys())
                    input_values = list(input.values())
                    input = {input_labels[i]: input_values[i] for i in input_select}
                elif isinstance(input_select[0], str):
                    input = {
                        k: input[k]
                        for pattern in input_select
                        for k in input
                        if re.match(pattern, k)
                    }
        elif isinstance(input, list):
            if input_select is None or not isinstance(input_select[0], int):
                input_select = range(len(input))
            input = {str(i + 1): input[i] for i in input_select}
        else:
            input = {"1": input}
        self.input = input
        logging.debug(f"Setting input for {self.name} to {type(self.input)}")
        return input

    def get_description(self) -> str:
        """Returns a description for this analyzing module. This may include instructions on how to use the parameters.

        Returns:
            str: the description.

        """
        return self.name

    def get_icon(self) -> Any:
        """Returns icon for this analysis.

        Returns:
            wx.Bitmap: The bitmap of the icon.

        """
        return wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE)

    def _fix_label(self, label: str) -> str:
        """Removes special characters from label string.

        Args:
            label (str): the label to be fixed.

        Returns:
            str: modified label.

        """
        if not isinstance(label, str):
            if isinstance(label, list):
                label = ",".join(str(label))
            else:
                label = str(label)
        return str(label).replace("'", "").replace("(", "").replace(")", "")

    def _add_picker(self, figure: matplotlib.figure.Figure) -> None:
        """Enables picker to figure's axes, their children and grandchildren.

        Args:
            figure (matplotlib.figure.Figure): the figure for which the pickers will be enabled.
        """

        ax_list = figure.axes
        for ax in ax_list:
            ax.set_picker(True)
            for artist in ax.get_children():
                artist.set_picker(True)
                for c in artist.get_children():
                    c.set_picker(True)
            # ax.set_title(ax.get_title(), picker=True)
            ax.set_xlabel(ax.get_xlabel(), picker=True)
            ax.set_ylabel(ax.get_ylabel(), picker=True)

    def __repr__(self):
        return f"<{type(self).__name__}>: {self.name}"

    def __str__(self):
        return self.name

    def get_default_parameters(self) -> dict:
        """Provides the plugin's default parameters.

        Returns:
            dict: default parameters
        """
        defaults = {
            "grouping": [],
            "features": [],
            "input": {},
            "prefix": None,
            "autosave": False,
            "prefix": None,
            "working_dir": os.path.join(os.path.expanduser("~"), "FLIMAnalyzerResults"),
        }
        return defaults

    def get_parameters(self) -> dict:
        """Defines the plugins current parameters.

        Returns:
            dict: current parameters
        """
        return self.params

    def get_mapped_parameters(self) -> List[Dict[str, Any]]:
        """Provides a list of the plugins current parameters. Each list item defines a
        parameters for the smallest independent work unit. The list can be mapped for
        parallel flow execution.

        Returns:
            list[dict]: list of current parameters
        """
        return [self.params]

    def get_config_name(self) -> str:
        """Returns a string copy of plugin's name (self.name) in which whitespaces and non alphanumeric
        characters have been removed. It's used to defines the plugin's identifier in the
        config file.

        Returns:
           str: cleaned up plugin name
        """
        return "".join(e for e in self.name if e.isalnum())

    @abstractmethod
    def get_required_categories(self) -> List[str]:
        """Returns the category column names that are required in the input to be analyzed.

        Category columns use 'category' as dtype in Pandas DataFrame.

        Returns:
            list(str): list of column names.
        """
        return []

    @abstractmethod
    def get_required_features(self) -> List[str]:
        """Returns the non-category column names that are required in the input to be analyzed.

        Non-category columns are all those columns that do not use 'category' as dtype in Pandas dataframe.

        Returns:
            list(str): list of column names.
        """
        return ["any"]

    def run_configuration_dialog(
        self, parent: Any, data_choices: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """Executes the plugin's configuration dialog.

        The dialog is initialized with values of the analyzer's Config object.

        Args:
            parent: parent GUI element
            data_choices (dict): available data tables to choose from. Keys correspond to
                table names; values correspond to DataFrame objects.

        Returns:
            dict: The key:value pairs of specified config parameters.
        """
        return {}

    def input_definition(self) -> List[Type]:
        """Provides type definition of plugin's required input.

        Returns:
            list[type]: list of object types
        """
        return [pd.DataFrame]

    def output_definition(self) -> Dict[str, Type]:
        """Provides type definition of plugin's execute method.

        Returns:
            dict[type]: keys describe output object labels; values represent corresponding
                object types
        """
        return {f"Data: {self.name}": pd.DataFrame}

    def configure(self, input: dict = input, input_select: str = None, **kwargs):
        """Updates the configuration with the passed arguments.

        The configuration is updated not replaced, i.e values of matching keys are
        overwritten, values of non-matching keys remain unaltered.

        Args:
            kwargs: the new key:value pairs.
        """
        input = self.set_input(input=input, input_select=input_select)
        self.params.update(input=input, **kwargs)

    @abstractmethod
    def execute(self):
        """Executes the analysis using the analyzer's set input and configuration.

        Returns:
           dict: Dictionary of pandas.DataFrame and/or matplotlib.pyplot.Figure objects.
                 Keys represent window titles, values represent the DataFrame or Fugure
                 objects.
        """
        return {}

    def run(self, input={}, input_select=None, **kwargs):
        logging.debug(f"{self.name}: kwargs[features]={kwargs.get('features', None)}")
        self.configure(input=input, input_select=input_select, **kwargs)
        logging.debug(
            f"Executing {self.name}: task_run_name={self.task_run_name},"
            f" type(self.input)={type(self.input)}"
        )
        results = self.execute()
        if self.params["prefix"]:
            results = {f'{self.params["prefix"]}{k}': v for k, v in results.items()}
        return results


class DataBucket(AbstractPlugin):
    def __init__(self, name="Data Bucket", **kwargs):
        super().__init__(name=name, **kwargs)
        # self.name = self._get_input_label(input)

    def _get_input_label(self, input):
        if input is not None:
            if isinstance(input, dict):
                return "|".join(input.keys())
            else:
                return type(input).__name__
        else:
            return "Data"

    def output_definition(self):
        return {self.name: Any}

    # def configure(self, **kwargs):
    #    super().configure(**kwargs)

    def execute(self):
        # self.name = self._get_input_label(self.input)
        return self.input
        # return list(self.input.values())[0]

    def run(self, input={}, input_select=None, name=None, **kwargs):
        self.name = self._get_input_label(input)
        if name is not None:
            self.name = name
        # results = self.execute() #super().run(input={}, input_select=None, **kwargs)
        self.input = self.set_input(input=input, input_select=input_select)
        # results = self.input.values()
        # for k,v in self.input.items():
        #    print (f'\tk={k}, type(v)={type(v)}')
        return next(iter(self.input.values()))


# auto run on import to populate the PLUGIN dictionary
discover_plugin_classes()
