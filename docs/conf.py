# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

# The docs are built without FLIMAnalyzer's GUI and heavy dependencies
# (docs/requirements.txt); autodoc imports these as mocks.
autodoc_mock_imports = [
    "graphviz",
    "pendulum",
    "prefect",
    "pubsub",
    "pydot",
    "setuptools_scm",
    "torch",
    "wx",
]

# wx.lib.newevent.NewEvent() is unpacked at import time, which a mock can't do
import types

_newevent = types.ModuleType("wx.lib.newevent")
_newevent.NewEvent = lambda: (type("Event", (), {}), object())
_newevent.NewCommandEvent = _newevent.NewEvent
sys.modules["wx.lib.newevent"] = _newevent

# The plugins subclass Prefect 1's Task and are instantiated when flim is imported,
# which a mock can't do (endless recursion): a stand-in for the names flim imports
# from the top-level package; its submodules are mocked.
_prefect = types.ModuleType("prefect")
_prefect.__path__ = []


class _Task:
    def __init__(self, name=None, **kwargs):
        self.name = name


_prefect.Task = _Task
_prefect.task = lambda *args, **kwargs: (args[0] if args and callable(args[0]) else (lambda f: f))
for _name in ("Flow", "Parameter", "unmapped", "flatten", "tags"):
    setattr(_prefect, _name, type(_name, (), {"__init__": lambda self, *a, **k: None}))
_prefect.config = types.SimpleNamespace(flows=types.SimpleNamespace(checkpointing=False))
sys.modules["prefect"] = _prefect


# -- Project information -----------------------------------------------------

project = 'FLIM Analyzer'
copyright = '2021, UVA Keck Center for Cellular Imaging'
author = 'UVA Keck Center for Cellular Imaging: Karsten Siller, Brian Mbogo, Jiaxin Zhang'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'myst_parser',
    'sphinx_rtd_theme']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'docs']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_theme_options = {
    "collapse_navigation" : False
}

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}
