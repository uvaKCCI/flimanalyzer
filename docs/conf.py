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

sys.path.insert(0, os.path.abspath(".."))

# The docs are built without installing flimanalyzer's heavy and GUI dependencies
# (see the "docs" dependency group in pyproject.toml); autodoc imports these as mocks.
autodoc_mock_imports = [
    "prefect",
    "prefect_dask",
    "torch",
    "wx",
]

# wx.lib.newevent.NewEvent() is unpacked at import time, which a mock can't do
import types

_newevent = types.ModuleType("wx.lib.newevent")
_newevent.NewEvent = lambda: (type("Event", (), {}), object())
_newevent.NewCommandEvent = _newevent.NewEvent
sys.modules["wx.lib.newevent"] = _newevent


# -- Project information -----------------------------------------------------

project = "FLIMAnalyzer"
copyright = "2021, UVA Keck Center for Cellular Imaging"
author = (
    "UVA Keck Center for Cellular Imaging: Karsten Siller, Brian Mbogo, Jiaxin Zhang"
)


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_rtd_theme",
]

# generate one API page per module (codedocs/index.rst) at build time
autosummary_generate = True

# anchors for Markdown headings up to level 3, e.g. [link](#open-data-file)
myst_heading_anchors = 3


def _skip_sklearn_members(app, what, name, obj, skip, options):
    # scikit-learn adds set_*_request methods to estimator subclasses; their
    # docstrings reference sklearn's own docs and are not part of flimanalyzer
    if getattr(obj, "__module__", "") and obj.__module__.startswith("sklearn"):
        return True
    return None


def setup(app):
    app.connect("autodoc-skip-member", _skip_sklearn_members)

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "docs"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_theme_options = {"collapse_navigation": False}

# application icon, drawn by scripts/make_icons.py
html_logo = "../flim/resources/flimanalyzer.png"
html_favicon = "../flim/resources/flimanalyzer.ico"

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}
