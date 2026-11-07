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
