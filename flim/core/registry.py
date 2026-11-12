"""Registry of tools: by name, by category (menu order) and by config class.

Tools of other packages are found through the `flimanalyzer.tools` entry point group;
importing the module an entry point names registers its tools.
"""

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any, Optional, TypeVar

if TYPE_CHECKING:
    from flim.core.tool import Tool

logger = logging.getLogger(__name__)

API_VERSION = 1  # tools declaring another api_version are not registered

# menu and tool panel order; categories not listed here follow, sorted by name
CATEGORY_ORDER = ("File", "Image", "Data", "Analysis", "Plot", "Workflow")

TOOLS_GROUP = "flimanalyzer.tools"
GUI_GROUP = "flimanalyzer.gui"


SHORT_NAME_LENGTH = 10  # Tool.short_name

# a tool class, for the decorators that return the class they register
ToolClassT = TypeVar("ToolClassT", bound="type[Tool]")


def _names(cls: type["Tool"]) -> set[str]:
    """Return a tool's name, former names and short name, case-folded."""
    names = {cls.name, *getattr(cls, "former_names", ()), getattr(cls, "short_name", "")}
    return {n.casefold() for n in names if n}


class ToolRegistry:
    """Tool classes by name."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._tools = {}  # name -> class

    def register(self, cls: ToolClassT) -> ToolClassT:
        """Register a tool class and return it.

        Registering a class again under its name has no effect.

        Args:
            cls: The tool class.

        Returns:
            The class.

        Raises:
            ValueError: If the class has no `name`, `category` or `config_class`,
                declares another `api_version`, has a `short_name` longer than
                `SHORT_NAME_LENGTH` characters, or another class is registered under
                its name, or one of its names (name, former names, short name)
                equals one of another class's names, ignoring case.
        """
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
        short = getattr(cls, "short_name", "")
        if short and len(short) > SHORT_NAME_LENGTH:
            raise ValueError(
                f"{cls.__qualname__}: short_name '{short}' is longer than"
                f" {SHORT_NAME_LENGTH} characters"
            )
        mine = _names(cls)
        for other in self._tools.values():
            if other is cls or other.name == cls.name:
                continue
            shared = mine & _names(other)
            if shared:
                raise ValueError(
                    f"Tool name conflict: {cls.__qualname__} and {other.__qualname__}"
                    f" both use '{sorted(shared)[0]}' (names, former names and short"
                    " names must differ, ignoring case)"
                )
        self._tools[cls.name] = cls
        return cls

    def unregister(self, name: str) -> None:
        """Remove the tool registered under a name; nothing if there is none."""
        self._tools.pop(name, None)

    def get(self, name: str) -> type["Tool"]:
        """Return the tool registered under a name.

        Args:
            name: The tool's name (not a former or short name).

        Returns:
            The tool class.

        Raises:
            KeyError: If no tool is registered under the name.
        """
        return self._tools[name]

    def __contains__(self, name: str) -> bool:
        """Return whether a tool is registered under the name."""
        return name in self._tools

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def categories(self) -> list[str]:
        """Return the categories of the registered tools, in menu order.

        The categories of `CATEGORY_ORDER` come first, in that order; the others
        follow, sorted by name.
        """
        present = {cls.category for cls in self._tools.values()}
        known = [c for c in CATEGORY_ORDER if c in present]
        return known + sorted(present - set(CATEGORY_ORDER))

    def by_category(self) -> dict[str, list[type["Tool"]]]:
        """Return the tools grouped by category (menu order), each sorted by name."""
        return {
            category: sorted(
                (cls for cls in self._tools.values() if cls.category == category),
                key=lambda cls: cls.name,
            )
            for category in self.categories()
        }

    def for_config(self, config: Any) -> Optional[type["Tool"]]:
        """Return the tool for a config class or instance.

        A config subclass without its own tool falls back to the tool of its nearest
        base class.

        Args:
            config: A config class or a config.

        Returns:
            The tool class; None if no tool takes the config or one of its bases.
        """
        config_class = config if isinstance(config, type) else type(config)
        by_config = {cls.config_class: cls for cls in self._tools.values()}
        for base in config_class.__mro__:
            if base in by_config:
                return by_config[base]
        return None


tools = ToolRegistry()


def register_tool(cls: ToolClassT) -> ToolClassT:
    """Register a tool in the default registry; a class decorator.

    Args:
        cls: The tool class.

    Returns:
        The class.

    Raises:
        ValueError: If the class can't be registered (see `ToolRegistry.register`).
    """
    return tools.register(cls)


def discover(group: str = TOOLS_GROUP) -> list[str]:
    """Import the modules of the entry points in `group`.

    A module that fails to import (e.g. an incompatible tool) is logged and skipped;
    the other entry points are still loaded.

    Args:
        group: The entry point group. Defaults to `flimanalyzer.tools`.

    Returns:
        The names of the entry points that loaded.
    """
    loaded = []
    for ep in entry_points(group=group):
        try:
            ep.load()
            loaded.append(ep.name)
        except Exception:
            logger.exception(
                f"Could not load {group} entry point '{ep.name}' ({ep.value})"
            )
    return loaded
