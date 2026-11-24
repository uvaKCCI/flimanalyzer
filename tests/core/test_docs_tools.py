"""Every tool in a menu has a screenshot of its dialog in the user guide."""

from flim.core.registry import category_path, tools

from .test_release_records import screenshots

# opens the system's file dialog, not a tool dialog
NO_DIALOG = {"Open Tables"}


def test_every_tool_dialog_has_a_screenshot():
    import flim.workflow  # noqa: F401  (registers the built-in workflows)

    in_menus = {t.name for t in tools._tools.values() if category_path(t)} - NO_DIALOG
    shot = {options.get("tool") for kind, options in screenshots().values() if kind == "dialog"}
    assert in_menus - shot == set(), "tool dialogs without a screenshot in docs/screenshots.py"
