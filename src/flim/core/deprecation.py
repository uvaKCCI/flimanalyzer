"""Deprecated names of modules: still importable, with a `DeprecationWarning`.

A module that renamed or moved a public name keeps the old name for at least one
minor release:

    from flim.core.deprecation import deprecated_names

    __getattr__ = deprecated_names(__name__, {"old_name": ("flim.core.columns", "new_name", "0.8.0")})
"""

import importlib
import warnings
from collections.abc import Callable
from typing import Any


def deprecated_names(
    module: str, names: dict[str, tuple[str, str, str]]
) -> Callable[[str], Any]:
    """Return a module `__getattr__` that resolves deprecated names, with a warning.

    Args:
        module: The name of the module that defines the `__getattr__`.
        names: For each deprecated name: the module and the name that replace it,
            and the version that removes the deprecated name.

    Returns:
        The function to assign to the module's `__getattr__` (PEP 562). For a
        deprecated name it issues a `DeprecationWarning` and returns the
        replacement; for any other name it raises `AttributeError`.
    """

    def __getattr__(name: str) -> Any:
        if name not in names:
            raise AttributeError(f"module {module!r} has no attribute {name!r}")
        target_module, target, removed_in = names[name]
        warnings.warn(
            f"{module}.{name} is deprecated and is removed in {removed_in};"
            f" use {target_module}.{target}",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(importlib.import_module(target_module), target)

    return __getattr__
