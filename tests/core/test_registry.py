import logging
from types import SimpleNamespace

import pytest

from flim.core import registry
from flim.core.config import TaskConfig
from flim.core.registry import API_VERSION, ToolRegistry


def make_tool(name, category, config_class=TaskConfig, **attrs):
    return type(
        name,
        (),
        {"name": name, "category": category, "config_class": config_class, **attrs},
    )


def test_register_and_lookup():
    reg = ToolRegistry()
    tool = make_tool("Summary", "Data")
    assert reg.register(tool) is tool
    assert "Summary" in reg and len(reg) == 1
    assert reg.get("Summary") is tool
    reg.register(tool)  # registering the same class again is fine
    reg.unregister("Summary")
    assert "Summary" not in reg


def test_missing_attributes():
    reg = ToolRegistry()
    with pytest.raises(ValueError, match="category"):
        reg.register(type("T", (), {"name": "T", "config_class": TaskConfig}))


def test_name_conflict():
    reg = ToolRegistry()
    reg.register(make_tool("Summary", "Data"))
    with pytest.raises(ValueError, match="conflict"):
        reg.register(make_tool("Summary", "Data"))


def test_api_version():
    reg = ToolRegistry()
    reg.register(make_tool("Ok", "Data", api_version=API_VERSION))
    with pytest.raises(ValueError, match="API"):
        reg.register(make_tool("New", "Data", api_version=API_VERSION + 1))


def test_category_order():
    reg = ToolRegistry()
    for name, category in [
        ("Zplot", "Plot"),
        ("Aplot", "Plot"),
        ("Flow", "Workflow"),
        ("Seg", "Segmentation"),
        ("Conv", "Convert"),
        ("Stats", "Analysis"),
        ("Img", "Image"),
        ("Sum", "Data"),
    ]:
        reg.register(make_tool(name, category))
    assert reg.categories() == [
        "Image",
        "Data",
        "Analysis",
        "Plot",
        "Workflow",
        "Convert",
        "Segmentation",
    ]
    by_category = reg.by_category()
    assert list(by_category) == reg.categories()
    assert [t.name for t in by_category["Plot"]] == ["Aplot", "Zplot"]


def test_for_config_walks_the_mro():
    class AConfig(TaskConfig):
        pass

    class BConfig(AConfig):
        pass

    class CConfig(BConfig):
        pass

    reg = ToolRegistry()
    a = reg.register(make_tool("A", "Data", AConfig))
    b = reg.register(make_tool("B", "Data", BConfig))
    assert reg.for_config(AConfig) is a
    assert reg.for_config(BConfig()) is b
    assert reg.for_config(CConfig) is b  # nearest base with a tool
    assert reg.for_config(TaskConfig) is None


def test_register_tool_uses_default_registry(monkeypatch):
    reg = ToolRegistry()
    monkeypatch.setattr(registry, "tools", reg)
    tool = registry.register_tool(make_tool("X", "Data"))
    assert reg.get("X") is tool


def test_discover_isolates_errors(monkeypatch, caplog):
    loaded = []

    def ok():
        loaded.append("good")

    def broken():
        raise ImportError("needs a newer FLIMAnalyzer")

    eps = [
        SimpleNamespace(name="good", value="pkg.good", load=ok),
        SimpleNamespace(name="bad", value="pkg.bad", load=broken),
    ]
    groups = {}

    def fake_entry_points(group):
        groups["group"] = group
        return eps

    monkeypatch.setattr(registry, "entry_points", fake_entry_points)
    with caplog.at_level(logging.ERROR):
        assert registry.discover() == ["good"]
    assert loaded == ["good"]
    assert groups["group"] == "flimanalyzer.tools"
    assert "bad" in caplog.text and "pkg.bad" in caplog.text
    registry.discover(registry.GUI_GROUP)
    assert groups["group"] == "flimanalyzer.gui"


def test_discover_real_entry_points():
    # nothing registers these groups yet; must not fail
    assert isinstance(registry.discover(), list)
