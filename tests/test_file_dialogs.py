"""File dialogs offer at least two file types.

On macOS, wxPython 4.2.5 fails with a C++ assertion (`nIndex < m_nCount`) when a
save dialog has only one file type; with a second type (`All files`) it works.
"""

import re
from pathlib import Path

import flim


def test_every_file_dialog_wildcard_has_two_file_types():
    root = Path(flim.__file__).parent
    single = [
        f"{path.relative_to(root)}: {wildcard}"
        for path in root.rglob("*.py")
        for wildcard in re.findall(r'wildcard="([^"]*)"', path.read_text())
        if wildcard.count("|") < 3
    ]
    assert single == []


def test_save_dialogs_of_formats_have_two_file_types():
    from flim.core.saving import PlotSaveOptions, TableSaveOptions
    from flim.gui.dialogs import _wildcard

    for options_class in (TableSaveOptions, PlotSaveOptions):
        wildcard, formats = _wildcard(options_class)
        assert wildcard.count("|") >= 3, (options_class.__name__, formats)


def test_with_extension_adds_a_missing_extension():
    from flim.core.paths import with_extension

    assert with_extension("/data/ranges", ".json") == "/data/ranges.json"
    assert with_extension("/data/ranges.JSON", ".json") == "/data/ranges.JSON"
    assert with_extension("/data/ranges.txt", ".json") == "/data/ranges.txt.json"


def test_json_save_dialogs_add_the_extension():
    """Each save dialog of a JSON file adds `.json` to the path it returns."""
    root = Path(flim.__file__).parent
    missing = []
    for path in root.rglob("*.py"):
        text = path.read_text()
        for match in re.finditer(r"wx\.FileDialog\((?:(?!\bwith\b)[\s\S]){0,700}?FD_SAVE", text):
            block = text[match.start(): match.start() + 1200]
            if "*.json" in block and 'with_extension(' not in block:
                missing.append(f"{path.relative_to(root)}:{text.count(chr(10), 0, match.start()) + 1}")
    assert missing == []
