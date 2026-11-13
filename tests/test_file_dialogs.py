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
