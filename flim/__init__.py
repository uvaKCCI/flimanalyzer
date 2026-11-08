# Importing flim does not import the tools or the GUI. The tools are registered when
# flim.tools is imported, so flim.core can be used without wxPython.

try:  # written by versioningit when flimanalyzer is built (installed)
    from flim._version import __version__
except ImportError:  # a source tree without an installed build
    __version__ = "unknown"
