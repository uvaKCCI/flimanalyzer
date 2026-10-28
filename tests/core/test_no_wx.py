import subprocess
import sys

CORE_MODULES = [
    "flim",
    "flim.core.types",
    "flim.core.config",
    "flim.core.registry",
    "flim.core.execution",
    "flim.configs",
    "flim.core.schema",
    "flim.core.tool",
    "flim.tools",
]


def test_core_imports_without_wx():
    """The core modules must import with wx unavailable (CI also runs them without wx)."""
    code = (
        "import sys\n"
        "sys.modules['wx'] = None\n"  # any 'import wx' now raises ImportError
        f"for m in {CORE_MODULES!r}:\n"
        "    __import__(m)\n"
        "assert 'flim.plugin' not in sys.modules, 'importing flim must not load the tools'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
