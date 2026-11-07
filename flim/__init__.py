# Importing flim does not load the tools or the GUI: tools register when flim.tools
# is imported (the application does that), so flim.core can be used without wxPython.

try:  # written by versioningit when flimanalyzer is built (installed)
    from flim._version import __version__
except ImportError:  # a source tree without an installed build
    __version__ = "unknown"
