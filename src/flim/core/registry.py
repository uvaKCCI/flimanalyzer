"""Registry of tools: by name, by category (menu order) and by config class.

Tools of other packages are found through the `flimanalyzer.tools` entry point group;
importing the module an entry point names registers its tools.
"""

import logging
import warnings
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any, Optional, TypeVar

if TYPE_CHECKING:
    from flim.core.tool import Tool

logger = logging.getLogger(__name__)

API_VERSION = 1  # tools declaring another api_version are not registered

# menu and tool panel order; categories not listed here follow, sorted by name
CATEGORY_ORDER = ("File", "Image", "Data", "Analysis", "Plot", "Workflow")


def category_path(tool: Any) -> list[str]:
    """Return where the GUI shows a tool: its menu and submenus, from its `category`.

    Args:
        tool: The tool or workflow class.

    Returns:
        `[menu, submenu, ...]`; `["Analysis"]` for the category `"Analysis"`; empty
        for None or an empty category (in no menu).
    """
    category = getattr(tool, "category", None)
    if not category:
        return []
    return [category] if isinstance(category, str) else [str(c) for c in category]

TOOLS_GROUP = "flimanalyzer.tools"
GUI_GROUP = "flimanalyzer.gui"


SHORT_NAME_LENGTH = 10  # Tool.short_name

# a tool class, for the decorators that return the class they register
ToolClassT = TypeVar("ToolClassT", bound="type[Tool]")


# the release that removes the former names of tools (`Tool.former_names`)
FORMER_NAMES_REMOVED_IN = "0.8.0"
_warned_former: set[str] = set()  # the former names already warned about


def warn_former_name(cls: type["Tool"], name: str) -> None:
    """Warn that a tool was named by a former name, once per name and process.

    The warning is logged (shown in the terminal by flimbatch and flimsettings, and
    in the GUI's log), and issued as a `DeprecationWarning` for code that calls the
    API.

    Args:
        cls: The tool.
        name: The former name it was named by.
    """
    if name in _warned_former:
        return
    _warned_former.add(name)
    message = (
        f"the tool name '{name}' is deprecated and is removed in {FORMER_NAMES_REMOVED_IN};"
        f" use '{cls.name}'"
    )
    logger.warning(message)
    warnings.warn(message, DeprecationWarning, stacklevel=3)


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
            ValueError: If the class has no `name` or `config_class` (`category` may be
                empty: in no menu, see `category_path`),
                declares another `api_version`, has a `short_name` longer than
                `SHORT_NAME_LENGTH` characters, or another class is registered under
                its name, or one of its names (name, former names, short name)
                equals one of another class's names, ignoring case.
        """
        for attr in ("name", "config_class"):
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
        """Return the tool registered under a name, or that had the name before.

        A former name (`former_names`) is accepted, with a warning
        (`warn_former_name`), so that settings files, workflow files and command
        lines that name a renamed tool keep working until 0.8.0. Names are matched
        exactly; a short name is not accepted.

        Args:
            name: The tool's name or one of its former names.

        Returns:
            The tool class.

        Raises:
            KeyError: If no tool has the name or a former name equal to it.
        """
        if name in self._tools:
            return self._tools[name]
        for cls in self._tools.values():
            if name in getattr(cls, "former_names", ()):
                warn_former_name(cls, name)
                return cls
        raise KeyError(name)

    def current_name(self, name: str) -> Optional[str]:
        """Return the current name of a tool that had `name` before, without a warning.

        Args:
            name: A name.

        Returns:
            The current name if `name` is a former name of a registered tool; None
            otherwise (also for a current name).
        """
        if name in self._tools:
            return None
        for cls in self._tools.values():
            if name in getattr(cls, "former_names", ()):
                return cls.name
        return None

    def __contains__(self, name: str) -> bool:
        """Return whether a tool has the name or a former name equal to it (no warning)."""
        return name in self._tools or any(
            name in getattr(cls, "former_names", ()) for cls in self._tools.values()
        )

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def categories(self) -> list[str]:
        """Return the categories of the registered tools, in menu order.

        The categories of `CATEGORY_ORDER` come first, in that order; the others
        follow, sorted by name.
        """
        present = {path[0] for path in map(category_path, self._tools.values()) if path}
        known = [c for c in CATEGORY_ORDER if c in present]
        return known + sorted(present - set(CATEGORY_ORDER))

    def by_category(self) -> dict[str, list[type["Tool"]]]:
        """Return the tools grouped by menu (the first entry of their category).

        Menus in menu order, each sorted by name; tools without a category (see
        `hidden`) are left out.
        """
        return {
            category: sorted(
                (cls for cls in self._tools.values() if category_path(cls)[:1] == [category]),
                key=lambda cls: cls.name,
            )
            for category in self.categories()
        }

    def hidden(self) -> list[type["Tool"]]:
        """Return the tools without a category, sorted by name: in no menu, runnable by name."""
        return sorted(
            (cls for cls in self._tools.values() if not category_path(cls)),
            key=lambda cls: cls.name,
        )

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
        ValueError: If the class cannot be registered (see `ToolRegistry.register`).
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
