"""The package's version (Python Packaging User Guide, single-sourcing the version)."""

import importlib.metadata

import flim


def test_version_matches_the_installed_package():
    # the runtime version and the package metadata report the same version (both are
    # written at build time; a stale editable install has both stale, so this doesn't
    # detect that)
    assert flim.__version__ == importlib.metadata.version("flimanalyzer")


def test_version_is_a_real_version():
    assert flim.__version__ not in ("", "unknown", "0.0.0")


def test_source_tree_without_a_build_reports_unknown(monkeypatch):
    # flim/_version.py is written at build time; without it (a source tree that was
    # never installed) importing flim still works. A None entry in sys.modules makes
    # the import of flim._version raise ImportError.
    import importlib
    import sys

    monkeypatch.setitem(sys.modules, "flim._version", None)
    try:
        assert importlib.reload(flim).__version__ == "unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(flim)  # the real version again for the other tests
    assert flim.__version__ == importlib.metadata.version("flimanalyzer")
