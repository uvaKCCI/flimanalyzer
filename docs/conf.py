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

# scipy (imported by scikit-learn) checks at import time whether values are torch
# tensors, with issubclass(..., torch.Tensor) when "torch" is loaded; a mocked torch
# has no Tensor class. Import them here, before autodoc mocks torch.
import scipy.stats  # noqa: E402,F401
import sklearn  # noqa: E402,F401

import types

# flim/_version.py is written when flimanalyzer is installed; the docs import flim from
# the source tree (Read the Docs sets READTHEDOCS_VERSION, e.g. the tag)
if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "flim", "_version.py")):
    _version = types.ModuleType("flim._version")
    _version.__version__ = os.environ.get("READTHEDOCS_VERSION", "dev")
    sys.modules["flim._version"] = _version

# wx.lib.newevent.NewEvent() is unpacked at import time, which a mock can't do: a
# stand-in module replaces it
_newevent = types.ModuleType("wx.lib.newevent")
_newevent.NewEvent = lambda: (type("Event", (), {}), object())
_newevent.NewCommandEvent = _newevent.NewEvent
sys.modules["wx.lib.newevent"] = _newevent


# -- Project information -----------------------------------------------------

project = "FLIMAnalyzer"
copyright = "2021-2026, UVA Keck Center for Cellular Imaging"
author = (
    "UVA Keck Center for Cellular Imaging: Karsten Siller, Brian Mbogo, Jiaxin Zhang"
)


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
# single backticks in docstrings are code (Google style)
default_role = "literal"
# Google-style "Attributes:" sections as field lists: as separate entries they would
# duplicate the attributes autodoc documents (e.g. dataclass fields)
napoleon_use_ivar = True

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


def _narrow_tall_images(app, doctree):
    """Show screenshots that are taller than wide at half the column width, on the right.

    The screenshots are taken on a high-resolution screen (two pixels per point),
    and the theme shows an image at its pixel size up to the column width, so tall
    dialogs would fill several screens. Images with a width set are left as they are.
    """
    from docutils import nodes
    from PIL import Image

    for node in doctree.findall(nodes.image):
        if "width" in node or "scale" in node:
            continue
        path = os.path.join(app.srcdir, node["uri"].lstrip("/"))
        try:
            with Image.open(path) as image:
                width, height = image.size
        except OSError:
            continue
        if height > width:
            node["width"] = "50%"
            node["align"] = "right"  # the text flows beside it
            _to_start_of_step(node)


def _to_start_of_step(image):
    """Move a floated image to the start of the numbered or bulleted step it is in.

    A float only lets the text after it flow beside it. The screenshots stand at the
    end of their step in the page source, so they are moved before the step's text.
    """
    from docutils import nodes

    block = image.parent if isinstance(image.parent, nodes.paragraph) else image
    if isinstance(block, nodes.paragraph) and len(block.children) != 1:
        return  # an image inside a sentence: left where it is
    item = block.parent
    while item is not None and not isinstance(item, nodes.list_item):
        item = item.parent
    if item is None:
        return  # not in a step: left where it is
    if block.parent is item and item.index(block) == 0:
        return  # already first
    block.parent.remove(block)
    item.insert(0, block)


def setup(app):
    app.connect("autodoc-skip-member", _skip_sklearn_members)
    app.connect("doctree-read", _narrow_tall_images)

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

html_theme_options = {"collapse_navigation": False}
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# the program icon, drawn by scripts/make_icons.py
html_logo = "../flim/resources/flimanalyzer.png"
html_favicon = "../flim/resources/flimanalyzer.ico"

