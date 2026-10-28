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
from flim.core.runner import TaskCancelled, call_plugin, map_plugin, select
from flim.core.tool import RunContext

PLUGINS = {}
ALL_FEATURES = "all_features"


def plugin(plugintype):
    """Register an instantiated plugin to the PLUGINS dict."""

    if plugintype not in PLUGINS:
        PLUGINS[plugintype] = {}

    def wrapper_register_plugin(plugin_class):
        logging.debug(f"Registering {plugin_class}")
        if plugintype == "Plot" and "draws_figures" not in vars(plugin_class):
            plugin_class.draws_figures = True
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


class AbstractPlugin:
    """Abstract class used to template plugins for data manipulation, analysis, plotting.

    Calling a plugin instance (``plugin(input=..., **params)``) or its ``map`` method
    inside :func:`flim.core.runner.run_flow` runs it as a Prefect task.
    """

    # node style in the workflow graph
    graph_kind = "plugin"
    # True if the whole task draws with pyplot: such tasks hold
    # flim.core.runner.pyplot_lock, as pyplot is not thread-safe. Set automatically
    # for Plot plugins; plugins that plot only at the end can instead hold the lock
    # around their plotting code.
    draws_figures = False

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
        self.name = name if name is not None else type(self).__name__
        # get plugin specific defaults, ignore kwargs that are not plugin parameters
        self.params = self.get_default_parameters()
        ignored = [k for k in kwargs if k not in self.params]
        if ignored:
            logging.debug(f"{self.name}: ignoring unknown arguments {ignored}")
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
            "saveconfig": False,
            "config_file": os.path.join(
                os.path.expanduser("~"), "FLIMAnalyzerResults", "configuration.json"
            ),
            "autosave": False,
            "working_dir": os.path.join(os.path.expanduser("~"), "FLIMAnalyzerResults"),
        }
        return defaults

    def get_parameters(self) -> dict:
        """Defines the plugins current parameters.

        Returns:
            dict: current parameters
        """
        return self.params.copy()

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

    def validate(self):
        """Validates the parameters currently set for the plugin.

        Returns:
            boolean: True if set parameters satisfy plugin's requirements
        """
        return True

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

    def run_tool(self, tool_class, *inputs) -> dict:
        """Runs a :class:`flim.core.tool.Tool` with this plugin's parameters.

        Adapter for the plugins whose computation moved to ``flim.tools``; results are
        keyed by display name, the prefix is added by :meth:`run`.
        """
        tool = tool_class()
        tool._cancel_token = getattr(self, "_cancel_token", None)
        tool._output_dir = self.params.get("working_dir")
        config = tool.config_class.from_legacy_params(self.params)
        tool.context = RunContext.for_config(
            config, cancel_token=tool._cancel_token, output_dir=tool._output_dir
        )
        return tool.display_names(tool.run(*inputs, config=config))

    def cancel(self, message: str = "Cancelled"):
        """Stops this task by raising :class:`~flim.core.runner.TaskCancelled`.

        Call it only from :meth:`execute`. Inside a flow, the task is recorded as
        cancelled and tasks that use its results are not run; other tasks continue.
        Outside a flow, the exception reaches the caller.

        Args:
            message: reason, shown in the log and the run summary.
        """
        raise TaskCancelled(message)

    def check_cancelled(self):
        """Stops this task (see :meth:`cancel`) if the user cancelled the run.

        Call it regularly from long-running :meth:`execute` methods, e.g. once per
        epoch or per group. Does nothing outside a flow.
        """
        token = getattr(self, "_cancel_token", None)
        if token is not None and token.is_set():
            self.cancel("Run cancelled by the user")

    def run(self, input={}, input_select=None, **kwargs):
        logging.debug(f"{self.name}: kwargs[features]={kwargs.get('features', None)}")
        self.configure(input=input, input_select=input_select, **kwargs)
        logging.debug(f"Executing {self.name}: type(self.input)={type(self.input)}")
        for data in self.input.values():
            if isinstance(input, pd.DataFrame) and len(data) == 0:
                raise ValueError("Dataframe is enmpty.")
        results = self.execute()
        if self.params["prefix"]:
            results = {f'{self.params["prefix"]}{k}': v for k, v in results.items()}
        return results

    def __call__(self, **kwargs):
        """Runs the plugin with ``kwargs``; as a Prefect task when inside a flow.

        Args:
            kwargs: arguments for :meth:`run`; ``task_tags`` (str or list) sets the
                task's tags, which also determine where autosaved results go.

        Returns:
            TaskOutput inside a flow, otherwise the plugin's results.
        """
        return call_plugin(self, **kwargs)

    def map(self, **kwargs):
        """Calls the plugin once per element of each argument not wrapped in
        ``prefect.unmapped``.

        Returns:
            list: one result handle per call.
        """
        return map_plugin(self, **kwargs)


class DataBucket(AbstractPlugin):
    graph_kind = "output"

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
