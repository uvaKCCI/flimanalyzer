"""Where the GUI shows tools: `category` (a menu, or a menu and submenus; empty: in no
menu) and a registered dialog (flim.gui.configdialog.shown_in_gui)."""

import warnings

import pytest

pytest.importorskip("wx")

import flim.gui.app  # noqa: F401,E402  (registers the dialogs)
import flim.tools  # noqa: F401,E402
import flim.workflow  # noqa: F401,E402
from flim.configs import SortConfig  # noqa: E402
from flim.core.config import TaskConfig  # noqa: E402
from flim.core.registry import category_path, tools  # noqa: E402
from flim.core.tool import Tool  # noqa: E402
from flim.gui.configdialog import has_dialog, shown_in_gui  # noqa: E402


def test_category_paths():
    class One:
        category = "Analysis"

    class Nested:
        category = ["Analysis", "Autoencoder"]

    class Hidden:
        category = None

    assert category_path(One) == ["Analysis"]
    assert category_path(Nested) == ["Analysis", "Autoencoder"]
    assert category_path(Hidden) == [] and category_path(object()) == []


# FLIMAnalyzer's tools with a category but not in the GUI, on purpose
NOT_IN_GUI = {"Collect Files"}  # its inputs are files: the GUI has no windows for them


def test_every_tool_of_flimanalyzer_with_a_category_has_a_registered_dialog():
    missing = {
        t.name for t in tools._tools.values()
        if category_path(t) and getattr(t, "definition", None) is None
        and t.__module__.split(".")[0] == "flim" and not has_dialog(t.config_class)
    }  # fmt: skip
    assert missing == NOT_IN_GUI


class PluginConfig(TaskConfig):
    """A config with no dialog registered for it or its bases."""


def _plugin_tool(module):
    class PluginSort(Tool[PluginConfig]):
        name = "Plugin Sort"
        category = "Data"

        def run(self, data, *, config):
            return {"Sorted": data}

    PluginSort.__module__ = module
    return PluginSort


def test_a_subclass_of_a_config_with_a_dialog_has_it_too():
    class MySort(SortConfig):
        pass

    assert has_dialog(MySort) and not has_dialog(TaskConfig)


def test_a_tool_without_a_dialog_is_shown_only_from_other_packages_with_a_warning():
    from flim.gui import configdialog

    configdialog._warned.discard("Plugin Sort")
    with pytest.warns(DeprecationWarning, match="no dialog registered.*hidden"):
        assert shown_in_gui(_plugin_tool("someplugin.tools"))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert shown_in_gui(_plugin_tool("flim.tools.extra")) is False  # ours: hidden


def test_hidden_tools_are_listed_apart(monkeypatch):
    monkeypatch.setattr(tools, "_tools", dict(tools._tools))
    hidden = _plugin_tool("flim.tools.extra")
    hidden.category = None
    tools.register(hidden)
    assert hidden in tools.hidden()
    assert all(hidden not in group for group in tools.by_category().values())
