"""The choice the GUI offers when some settings of a settings file cannot be used."""

import logging
from typing import Callable, Optional

import wx

from flim.core.settings import SettingsCheck, check_settings_file, save_sections

USE = "Use the settings that can be used; skip the others"
IGNORE = "Don't use this file"
UPDATE = "Update the file to the current version; remove the settings that can't be used"
OTHER = "Choose another file..."
LISTED = 8  # items listed per kind of finding in the dialog; the log lists all


def _options(check: SettingsCheck) -> list[str]:
    """Return the options for a checked file; a file that cannot be read offers no
    settings to use or keep."""
    return [IGNORE, OTHER] if check.error else [USE, IGNORE, UPDATE, OTHER]


def _confirm_update(check: SettingsCheck, parent) -> bool:
    message = (
        f"Replace {check.path} with the settings that can be used, in the current"
        " version?\n\nThe settings listed as unknown or invalid are removed from the"
        " file. This cannot be undone."
    )
    with wx.MessageDialog(
        parent, message, "Update Settings File", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
    ) as dialog:
        return dialog.ShowModal() == wx.ID_YES


def _other_file(parent) -> Optional[str]:
    with wx.FileDialog(
        parent,
        "Choose a Settings File",
        wildcard="JSON files (*.json)|*.json|All files|*",
        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
    ) as dialog:
        return dialog.GetPath() if dialog.ShowModal() == wx.ID_OK else None


def choose_settings(
    check: SettingsCheck,
    parent=None,
    problems: Optional[Callable[[SettingsCheck], bool]] = None,
) -> Optional[SettingsCheck]:
    """Ask the user how to use a settings file some of whose settings cannot be used.

    The dialog lists what cannot be used and what was converted, and offers to use
    the settings that can be used, not to use the file, to update the file to the
    current version (after a confirmation), or to choose another file. Another file
    is checked in the same way; if it has problems, the dialog is shown again.
    Closing the dialog with Cancel does not use the file.

    Args:
        check: The result of `check_settings_file`.
        parent: The parent window.
        problems: Whether a check has problems that need the user's choice; defaults
            to `SettingsCheck.problems`.

    Returns:
        The check whose sections to use (of this or another file), or None to use
        no file.
    """
    problems = problems or (lambda c: c.problems)
    while True:
        logging.warning(check.summary())
        options = _options(check)
        with wx.SingleChoiceDialog(
            parent,
            check.summary(limit=LISTED) + "\n\nWhat should FLIMAnalyzer do?",
            "Settings File",
            options,
        ) as dialog:
            choice = options[dialog.GetSelection()] if dialog.ShowModal() == wx.ID_OK else IGNORE
        if choice == USE:
            return check
        if choice == IGNORE:
            logging.info(f"{check.path} not used")
            return None
        if choice == UPDATE:
            if not _confirm_update(check, parent):
                continue
            try:
                save_sections(check.sections, check.path)
            except OSError as err:
                wx.MessageBox(
                    f"Could not update {check.path}:\n{err}",
                    "Update Settings File",
                    wx.OK | wx.ICON_ERROR,
                )
                continue
            logging.info(f"{check.path} updated to the current version")
            return check_settings_file(check.path)
        path = _other_file(parent)
        if path is None:
            continue
        check = check_settings_file(path)
        if not problems(check):
            return check
