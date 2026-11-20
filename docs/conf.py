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

sys.path.insert(0, os.path.abspath("../src"))

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

# src/flim/_version.py is written when flimanalyzer is installed; the docs import flim from
# the source tree (Read the Docs sets READTHEDOCS_VERSION, e.g. the tag)
if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "src", "flim", "_version.py")):
    _version = types.ModuleType("flim._version")
    _version.__version__ = os.environ.get("READTHEDOCS_VERSION", "dev")
    sys.modules["flim._version"] = _version

# wx.lib.newevent.NewEvent() is unpacked at import time, which a mock cannot do: a
# stand-in module replaces it
_newevent = types.ModuleType("wx.lib.newevent")
_newevent.NewEvent = lambda: (type("Event", (), {}), object())
_newevent.NewCommandEvent = _newevent.NewEvent
sys.modules["wx.lib.newevent"] = _newevent


# -- Project information -----------------------------------------------------

project = "FLIMAnalyzer"
copyright = "2021-2026, The University of Virginia"
author = "Karsten Siller, Jiaxin Zhang, Brian Mbogo"


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
# attributes of inline images, e.g. ![](plot.png){width="49%"} for two plots in a row
myst_enable_extensions = ["attrs_inline"]


def _skip_sklearn_members(app, what, name, obj, skip, options):
    # scikit-learn adds set_*_request methods to estimator subclasses; their
    # docstrings reference sklearn's own docs and are not part of flimanalyzer
    if getattr(obj, "__module__", "") and obj.__module__.startswith("sklearn"):
        return True
    return None


# images up to this many pixels wide (half on screen: two pixels per point) have
# little content: small dialogs and windows; icons up to ICON_WIDTH are left inline
SMALL_WIDTH = 1100
ICON_WIDTH = 64


def _narrow_tall_images(app, doctree):
    """Show tall or small screenshots at half the column width, on the right.

    Screenshots that are clearly taller than wide (dialogs), or at most `SMALL_WIDTH`
    pixels wide (little content), are shown at half the column width, and the text
    flows beside them; in the PDF they are half the text width. The screenshots are
    taken on a high-resolution screen (two pixels per point), and the theme shows an
    image at its pixel size up to the column width, so tall dialogs would fill
    several screens. Icons (up to `ICON_WIDTH` pixels) and images with a width set
    are left as they are.
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
        if width <= ICON_WIDTH:
            continue
        _to_own_block(node)
        # dialogs, and small images; large plots and windows stay as they are
        if height > 1.1 * width or width <= SMALL_WIDTH:
            node["width"] = "50%"
            node["align"] = "right"  # the text flows beside it
            _to_start_of_step(node)


def _to_own_block(image):
    """Move a screenshot out of its paragraph, to a block of its own.

    In the page source a screenshot often follows the text of a step on the next
    line, which puts it into the same paragraph. In the PDF an image in a paragraph
    starts after the text and ignores its alignment, so wide images run off the page.
    The image is moved directly after the paragraph; a paragraph that holds only the
    image is replaced by it. Images with text after them in the paragraph are left
    where they are.
    """
    from docutils import nodes

    paragraph = image.parent
    if not isinstance(paragraph, nodes.paragraph):
        return
    after = paragraph.children[paragraph.index(image) + 1 :]
    if any(child.astext().strip() for child in after):
        return
    for child in after:
        paragraph.remove(child)
    paragraph.remove(image)
    parent = paragraph.parent
    position = parent.index(paragraph)
    if paragraph.astext().strip():
        parent.insert(position + 1, image)
    else:
        parent.replace(paragraph, image)


def _to_start_of_step(image):
    """Move a floated image below the first paragraph of the step it is in.

    A float only lets the text after it flow beside it. The screenshots stand at the
    end of their step in the page source, so they are moved up: below the step's
    first paragraph (e.g. "In the Configuration: Bar Plot dialog, ..."), which keeps
    the full width.
    """
    from docutils import nodes

    block = image
    if isinstance(block.parent, nodes.paragraph):
        return  # an image inside a sentence: left where it is
    item = block.parent
    while item is not None and not isinstance(item, nodes.list_item):
        item = item.parent
    if item is None:
        return  # not in a step: left where it is
    block.parent.remove(block)
    first = item.children[0] if item.children else None
    item.insert(1 if isinstance(first, nodes.paragraph) else 0, block)


def setup(app):
    app.connect("autodoc-skip-member", _skip_sklearn_members)
    app.connect("doctree-read", _narrow_tall_images)

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "docs"]


# -- Options for LaTeX (PDF) output ------------------------------------------

# every image fits the page, also in height (a tall dialog would otherwise run off
# the bottom of the page), keeping its proportions
# xelatex: the pages use Unicode characters (μ, τ, −, √, ↗, ⌘) that pdflatex cannot set
latex_engine = "xelatex"
# long class names in the index have no break points: a smaller font, lines not
# justified
latex_elements = {
    "preamble": r"""
\usepackage[export]{adjustbox}
\setkeys{Gin}{max width=\linewidth,max height=0.8\textheight,keepaspectratio}
""",
    "printindex": r"\footnotesize\raggedright\printindex",
}


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

html_theme_options = {"collapse_navigation": False}
html_static_path = ["_static"]
html_css_files = ["custom.css"]

# the program icon, drawn by scripts/make_icons.py
html_logo = "../src/flim/resources/flimanalyzer.png"
html_favicon = "../src/flim/resources/flimanalyzer.ico"

