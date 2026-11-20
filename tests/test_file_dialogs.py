"""File dialogs offer at least two file types, and save dialogs select the first.

On macOS, wxPython 4.2.5 fails with a C++ assertion (`nIndex < m_nCount`) when a
save dialog has only one file type; with a second type (`All files`) it works. With
`All files` selected, the macOS panel adds `.txt` to a name typed without an
extension, so save dialogs select the first type before they are shown.
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


def test_json_save_dialogs_select_json_and_add_the_extension():
    root = Path(flim.__file__).parent / "gui"
    for path in root.rglob("*.py"):
        text = path.read_text()
        for match in re.finditer(r'wildcard="(?:JSON|json) files[^"]*",\s*style=wx.FD_SAVE', text):
            after = text[match.end() : match.end() + 400]
            assert "SetFilterIndex(0)" in after, path
            assert 'with_extension(' in after, path


def test_with_extension():
    from flim.core.paths import with_extension

    assert with_extension("a", ".json") == "a.json"
    assert with_extension("a.JSON", ".json") == "a.JSON"
    assert with_extension(Path("dir/a"), ".json") == "dir/a.json"
