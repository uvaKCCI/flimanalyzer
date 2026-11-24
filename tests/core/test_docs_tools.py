"""Every tool in a menu has a screenshot of its dialog in the user guide."""

from flim.core.registry import category_path, tools

from .test_release_records import screenshots

# opens the system's file dialog, not a tool dialog
NO_DIALOG = {"Open Tables"}

# no screenshot yet (found 2026-11-21); each is removed here when docs/screenshots.py
# makes one. The test fails if this list is out of date in either direction
KNOWN_MISSING = {
    "Autoencoder Augment Data",
    "Autoencoder Run",
    "Basic FLIRR Analysis",
    "Calculate",
    "Directory/File to Source",
    "Drop Columns",
    "FLIM Data Augmentation Tuning",
    "FLIM Feature Analysis",
    "Fuse Categories",
    "Import Tables",
    "Pivot",
    "Rename Columns",
    "Scale",
    "Separate Categories",
    "Unpivot",
}


def test_every_tool_dialog_has_a_screenshot():
    import flim.workflow  # noqa: F401  (registers the built-in workflows)

    in_menus = {t.name for t in tools._tools.values() if category_path(t)} - NO_DIALOG
    shot = {options.get("tool") for kind, options in screenshots().values() if kind == "dialog"}
    missing = in_menus - shot
    assert missing - KNOWN_MISSING == set(), "tool dialogs without a screenshot in docs/screenshots.py"
    assert KNOWN_MISSING - missing == set(), "now have a screenshot (or are gone): remove from KNOWN_MISSING"
