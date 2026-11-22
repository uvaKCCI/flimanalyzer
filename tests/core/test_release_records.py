"""Checks of what a release leaves behind: changelog sections and the docs images.

Standard library only, no `flim` import: the docs job runs this file too
(`pytest --noconftest`), so pull requests that change only the docs are checked.
"""

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
IMAGES = DOCS / "images"
RESOURCES = ROOT / "src" / "flim" / "resources"
RELEASE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
FIRST_SECTION = (0, 5, 1)  # CHANGELOG.md has sections from 0.5.1 on


def _git(*args) -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True)
    return out.stdout.split()


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_every_release_has_a_changelog_section():
    """Each release up to the newest one in this branch's history has a section, also
    the patch releases of an older series, which are tagged on their maintenance
    branch (e.g. 0.6.3 on release/0.6.x, after 0.7.0): their section is copied into
    dev when they are published (RELEASING.md)."""
    try:
        _git("rev-parse", "HEAD")
    except subprocess.CalledProcessError:
        pytest.skip("not a git work tree (e.g. an sdist)")
    merged = [m for t in _git("tag", "--merged", "HEAD", "-l", "v*") if (m := RELEASE.match(t))]
    if not merged:
        # a shallow clone without tags: CI must fetch them (fetch-depth 0)
        assert not os.environ.get("CI"), "no release tags: check out with fetch-depth 0"
        pytest.skip("no release tags in this clone")
    newest = max(tuple(map(int, m.groups())) for m in merged)
    releases = {
        v for t in _git("tag", "-l", "v*") if (m := RELEASE.match(t))
        if FIRST_SECTION <= (v := tuple(map(int, m.groups()))) <= newest
    }
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = {
        tuple(map(int, m.groups()))
        for m in re.finditer(r"^## (\d+)\.(\d+)\.(\d+)(?: - \d{4}-\d{2}-\d{2})?$", changelog, re.M)
    }
    missing = sorted(".".join(map(str, v)) for v in releases - sections)
    assert not missing, f"CHANGELOG.md has no section for the released {missing}"


def screenshots() -> dict[str, tuple[str, dict]]:
    """docs/screenshots.py's SHOTS (image: (kind, options)), read without running it
    (it needs wx and macOS); option values that aren't literals are None."""
    tree = ast.parse((DOCS / "screenshots.py").read_text(encoding="utf-8"))
    (shots,) = [
        n.value for n in tree.body
        if isinstance(n, ast.Assign) and [getattr(t, "id", None) for t in n.targets] == ["SHOTS"]
    ]
    literal = lambda node: node.value if isinstance(node, ast.Constant) else None  # noqa: E731
    return {
        key.value: (kind.value, {k.value: literal(v) for k, v in zip(options.keys, options.values)})
        for key, (kind, options) in ((k, v.elts) for k, v in zip(shots.keys, shots.values))
    }


def screenshot_names() -> set[str]:
    """The images docs/screenshots.py makes."""
    return set(screenshots())


def docs_images() -> set[str]:
    return {
        p.relative_to(IMAGES).as_posix()
        for p in IMAGES.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    }


def linked_images() -> set[str]:
    linked = set()
    for page in DOCS.rglob("*"):
        if page.suffix in (".md", ".rst") and "_build" not in page.parts:
            text = page.read_text(encoding="utf-8")
            linked.update(re.findall(r"images/([\w./-]+\.(?:png|svg|gif|jpe?g))", text))
    return linked


def test_docs_images_are_screenshots_or_app_icons():
    """Every image is retaken by docs/screenshots.py or is a copy of the app's icon
    (the tool panel icons), so none shows an older version."""
    icons = {p.read_bytes() for p in RESOURCES.rglob("*.png")}
    others = sorted(
        name for name in docs_images() - screenshot_names()
        if (IMAGES / name).read_bytes() not in icons
    )
    assert not others, f"docs/images not made by docs/screenshots.py nor an app icon: {others}"
    absent = sorted(screenshot_names() - docs_images())
    assert not absent, f"docs/screenshots.py makes images that are not in docs/images: {absent}"


def test_docs_images_are_linked():
    unlinked = sorted(docs_images() - linked_images())
    assert not unlinked, f"docs/images not used by any page: {unlinked}"
    missing = sorted(linked_images() - docs_images())
    assert not missing, f"pages link images that don't exist: {missing}"
