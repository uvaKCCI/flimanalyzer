import ast
import re
from pathlib import Path

import pytest

FLIM = Path(__file__).resolve().parent.parent / "flim"
SOURCES = sorted(p for p in FLIM.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(FLIM)))
def test_no_duplicate_methods(path):
    # a second definition silently replaces the first, e.g. two get_icon()
    tree = ast.parse(path.read_text())
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        names = [
            n.name
            for n in cls.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not any(
                isinstance(d, ast.Attribute) and d.attr in ("setter", "deleter")
                for d in n.decorator_list
            )
        ]
        duplicates = {n for n in names if names.count(n) > 1}
        assert not duplicates, f"{cls.name} defines {duplicates} more than once"


def test_referenced_icons_exist():
    resources = FLIM / "resources"
    referenced = {
        name
        for path in SOURCES
        for name in re.findall(r'joinpath\("([^"]+\.png)"\)', path.read_text())
    }
    assert referenced, "no icon references found"
    missing = sorted(n for n in referenced if not (resources / n).exists())
    assert not missing, f"missing icon files: {missing}"
