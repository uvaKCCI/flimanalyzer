"""The choice the GUI offers when some settings of a settings file cannot be used."""

import logging
from pathlib import Path
from typing import Callable, Optional

import wx

from flim.core.settings import (
    SETTINGS_VERSION,
    SettingsCheck,
    check_settings_file,
    save_sections,
)

USE = "Use the settings that can be used; skip the others"
IGNORE = "Don't use this file"
UPDATE = "Update the file to the current version; remove the settings that can't be used"
OTHER = "Choose another file..."
LISTED = 8  # items listed per kind of finding in the dialog; the log lists all
REWRITE = "Update the file to the current version and add the settings"
SAVE_OTHER = "Save to another file..."


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


def needs_rewrite(check: SettingsCheck) -> bool:
    """Return whether adding settings to a checked file rewrites more than they: the
    file is of an older version or has settings that cannot be used."""
    return check.error is None and (
        check.version < SETTINGS_VERSION or bool(check.unknown or check.invalid)
    )


def confirm_rewrite(check: SettingsCheck, parent=None) -> Optional[str]:
    """Ask before settings are added to a file that would be rewritten.

    Args:
        check: The result of `check_settings_file` for the file.
        parent: The parent window.

    Returns:
        REWRITE to update the file, the path of another file to save to, or None
        (Cancel, or no other file chosen).
    """
    message = (
        check.summary(limit=LISTED)
        + "\n\nAdding the settings rewrites the file in the current version; the"
        " settings that can't be used are removed."
    )
    options = [REWRITE, SAVE_OTHER]
    with wx.SingleChoiceDialog(parent, message, "Save Settings", options) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        choice = options[dialog.GetSelection()]
    return REWRITE if choice == REWRITE else _save_file(parent)


def _save_file(parent) -> Optional[str]:
    with wx.FileDialog(
        parent,
        "Save Settings",
        wildcard="JSON files (*.json)|*.json",
        style=wx.FD_SAVE,
    ) as dialog:
        return dialog.GetPath() if dialog.ShowModal() == wx.ID_OK else None


NO_FILE = "No app settings file"


def pick_app_settings(files: list[Path], parent=None) -> Optional[Path]:
    """Ask which app settings file to start with.

    Args:
        files: The files in the app settings search path (`list_app_settings`).
        parent: The parent window.

    Returns:
        The chosen file, or None for no file (also on Cancel).
    """
    choices = [NO_FILE] + [f"{f.name}  ({f.parent})" for f in files]
    with wx.SingleChoiceDialog(
        parent,
        "Start with an app settings file? Its settings apply to this session.",
        "App Settings File",
        choices,
    ) as dialog:
        if dialog.ShowModal() != wx.ID_OK or dialog.GetSelection() == 0:
            logging.info("Started without an app settings file")
            return None
        chosen = files[dialog.GetSelection() - 1]
    logging.info(f"App settings file chosen at startup: {chosen}")
    return chosen
