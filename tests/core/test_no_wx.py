import subprocess
import sys

CORE_MODULES = [
    "flim",
    "flim.core.types",
    "flim.core.config",
    "flim.core.registry",
    "flim.core.execution",
    "flim.configs",
    "flim.core.fields",
    "flim.core.schema",
    "flim.core.tool",
    "flim.tools",
    "flim.batch",
]
# every module of these packages (not subpackages)
CORE_PACKAGES = [
    "flim.core",
    "flim.tools",
    "flim.configs",
    "flim.workflow",
]

# raises ImportError for wx and torch, as when they are not installed
BLOCK = """
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in ('wx', 'torch'):
            raise ModuleNotFoundError(f'No module named {name!r}')
sys.meta_path.insert(0, Block())
"""


def run(code):
    result = subprocess.run(
        [sys.executable, "-c", BLOCK + code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_core_imports_without_wx():
    """The core modules must import with wx unavailable (CI also runs them without wx)."""
    run(
        f"for m in {CORE_MODULES!r}:\n"
        "    if m != 'flim.tools':\n"
        "        __import__(m)\n"
        "assert 'flim.tools' not in sys.modules, 'importing the core must not load the tools'\n"
        "import flim.tools\n"
    )


def test_all_core_modules_import_without_wx_and_torch():
    """Everything but the GUI."""
    run(
        "import importlib, pkgutil\n"
        f"for package in {CORE_PACKAGES!r}:\n"
        "    for m in pkgutil.iter_modules(importlib.import_module(package).__path__):\n"
        "        if not m.ispkg:\n"
        "            importlib.import_module(f'{package}.{m.name}')\n"
        "from flim.core.registry import tools\n"
        "counts = {c: len(t) for c, t in tools.by_category().items()}\n"
        "assert counts == {'Data': 8, 'Analysis': 12, 'Plot': 11, 'Workflow': 3}, counts\n"
    )


def test_the_application_explains_a_missing_wxpython():
    script = (
        "import sys\n"
        "sys.modules['wx'] = None  # as if not installed\n"
        "from flim import analyzerapp\n"
        "sys.argv = ['flimanalyzer', '--no-prefect-server']\n"
        "analyzerapp.main()\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 1
    assert 'pip install "flimanalyzer[gui]"' in result.stderr
