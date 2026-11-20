"""The packages whose versions a run records (flim.core.runner.recorded_packages)."""

from importlib.metadata import requires

import flim.core.runner as runner


def test_the_declared_dependencies_without_the_test_extra():
    names = runner.recorded_packages()
    assert {"numpy", "pandas", "prefect", "pydantic"} <= set(names)
    assert "pytest" not in names  # the test extra
    assert len(names) == len(set(names))
    # each comes from FLIMAnalyzer's installed metadata (dependencies and extras)
    declared = " ".join(requires("flimanalyzer"))
    assert all(name in declared for name in names)


def test_packages_of_plugin_tools_are_recorded(monkeypatch):
    class Dist:
        name = "flim-plugin-example"

    class Entry:
        dist = Dist()

    monkeypatch.setattr(
        "importlib.metadata.entry_points", lambda group: [Entry()] if group == "flimanalyzer.tools" else []
    )
    assert runner.recorded_packages()[-1] == "flim-plugin-example"


def test_a_dask_executor_adds_the_packages_that_run_its_tasks():
    import pytest

    pytest.importorskip("distributed")  # the dask extra

    class DaskTaskRunner:  # the name decides
        pass

    assert "dask" not in runner._versions()
    versions = runner._versions(DaskTaskRunner())
    assert {"dask", "distributed"} <= set(versions)


def test_versions_leave_out_what_is_not_installed(monkeypatch):
    monkeypatch.setattr(runner, "recorded_packages", lambda: ["numpy", "not-a-package-xyz"])
    versions = runner._versions()
    assert list(versions)[:2] == ["FLIMAnalyzer", "Python"]
    assert "numpy" in versions and "not-a-package-xyz" not in versions
