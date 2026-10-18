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


def test_no_unused_icons():
    resources = FLIM / "resources"
    code = "\n".join(path.read_text() for path in SOURCES)
    unused = sorted(p.name for p in resources.glob("*.png") if p.name not in code)
    assert not unused, f"icon files not used anywhere in flim/: {unused}"


def test_icons_are_32px_rgba():
    Image = pytest.importorskip("PIL.Image")
    wrong = {
        p.name: (im.size, im.mode)
        for p in sorted((FLIM / "resources").glob("*.png"))
        if p.name != "flimanalyzer.png"  # application icon
        for im in [Image.open(p)]
        if im.size != (32, 32) or im.mode != "RGBA"
    }
    assert not wrong, f"icons must be 32x32 RGBA: {wrong}"


def test_app_icon():
    Image = pytest.importorskip("PIL.Image")
    resources = FLIM / "resources"
    png = Image.open(resources / "flimanalyzer.png")
    assert png.size == (256, 256) and png.mode == "RGBA"
    ico = Image.open(resources / "flimanalyzer.ico")
    assert {(16, 16), (32, 32), (256, 256)} <= set(ico.info["sizes"])


def test_icons_have_no_red_or_orange():
    # colour-blind safe palette: groups are green and magenta, never red/orange
    # next to green (see scripts/make_icons.py)
    Image = pytest.importorskip("PIL.Image")
    import numpy as np

    offenders = {}
    for path in sorted((FLIM / "resources").glob("*.png")):
        rgba = np.asarray(Image.open(path).convert("RGBA")).reshape(-1, 4)
        hsv = np.asarray(Image.fromarray(rgba[None, :, :3]).convert("HSV"))[0] / 255.0
        hue = hsv[:, 0] * 360
        warm = (
            (rgba[:, 3] > 200)
            & (hsv[:, 1] > 0.45)
            & (hsv[:, 2] > 0.35)
            & ((hue < 50) | (hue > 345))
        )
        if warm.sum() > 4:
            offenders[path.name] = int(warm.sum())
    assert not offenders, f"icons with red/orange pixels: {offenders}"
