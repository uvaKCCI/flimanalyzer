"""Registry of tools: by name, by category (menu order) and by config class.

Tools of other packages are found through the ``flimanalyzer.tools`` entry point group;
importing the module an entry point names registers its tools.
"""

import logging
from importlib.metadata import entry_points
from typing import Optional

API_VERSION = 1  # tools declaring another api_version are not registered

# menu and tool panel order; categories not listed here follow, sorted by name
CATEGORY_ORDER = ("Image", "Data", "Analysis", "Plot", "Workflow")

TOOLS_GROUP = "flimanalyzer.tools"
GUI_GROUP = "flimanalyzer.gui"


class ToolRegistry:
    def __init__(self):
        self._tools = {}  # name -> class

    def register(self, cls):
        """Registers a tool class; it needs ``name``, ``category`` and ``config_class``."""
        for attr in ("name", "category", "config_class"):
            if not getattr(cls, attr, None):
                raise ValueError(f"{cls.__qualname__} has no {attr}")
        api = getattr(cls, "api_version", API_VERSION)
        if api != API_VERSION:
            raise ValueError(
                f"{cls.__qualname__} needs FLIMAnalyzer tool API {api}, this is {API_VERSION}"
            )
        existing = self._tools.get(cls.name)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"Tool name conflict: '{cls.name}' is used by {existing.__qualname__}"
                f" and {cls.__qualname__}"
            )
        self._tools[cls.name] = cls
        return cls

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str):
        return self._tools[name]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def categories(self) -> list[str]:
        """Categories of the registered tools, in menu order."""
        present = {cls.category for cls in self._tools.values()}
        known = [c for c in CATEGORY_ORDER if c in present]
        return known + sorted(present - set(CATEGORY_ORDER))

    def by_category(self) -> dict[str, list]:
        """Tools grouped by category (menu order), each group sorted by name."""
        return {
            category: sorted(
                (cls for cls in self._tools.values() if cls.category == category),
                key=lambda cls: cls.name,
            )
            for category in self.categories()
        }

    def for_config(self, config) -> Optional[type]:
        """The tool for a config class or instance; a config subclass without its own
        tool falls back to the tool of its nearest base class."""
        config_class = config if isinstance(config, type) else type(config)
        by_config = {cls.config_class: cls for cls in self._tools.values()}
        for base in config_class.__mro__:
            if base in by_config:
                return by_config[base]
        return None


tools = ToolRegistry()


def register_tool(cls):
    """Class decorator registering a tool in the default registry."""
    return tools.register(cls)


def discover(group: str = TOOLS_GROUP) -> list[str]:
    """Imports the modules of the entry points in ``group``.

    A module that fails to import (e.g. an incompatible tool) is logged and skipped,
    so one broken add-on never stops the application.

    Returns:
        Names of the entry points that loaded.
    """
    loaded = []
    for ep in entry_points(group=group):
        try:
            ep.load()
            loaded.append(ep.name)
        except Exception:
            logging.exception(
                f"Could not load {group} entry point '{ep.name}' ({ep.value})"
            )
    return loaded
