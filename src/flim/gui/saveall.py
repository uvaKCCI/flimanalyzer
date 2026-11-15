"""File > Save All Windows... and the question when quitting with unsaved windows."""

import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Optional, Union

import wx

from flim.core.paths import canonical_folder, folder_problem
from flim.core.saving import SaveOptions
from flim.gui.formats import FormatsBox

CANCEL, REVIEW, SAVE_ALL, DISCARD = "cancel", "review", "save all", "discard"
LISTED = 10  # unsaved windows listed in the quit dialog


class SaveAllDialog(wx.Dialog):
    """A dialog that asks for the folder and the formats to save all open windows in.

    The windows are saved into a new subfolder of the folder, named after the date
    and time (`flim.core.saving.save_all`).
    """

    def __init__(
        self,
        parent: wx.Window,
        folder: Optional[Union[str, os.PathLike]],
        kinds: Iterable[str],
    ) -> None:
        """Create the dialog.

        Args:
            parent: The main window.
            folder: The folder shown first; None for an empty field.
            kinds: The kinds of the open windows' values, e.g. `["table", "plot"]`.
        """
        super().__init__(parent, title="Save All Windows")
        text = wx.StaticText(
            self,
            label="The open windows are saved in a new folder, named after the date and"
            " time, in this folder. Tables are saved with all their rows.",
        )
        text.Wrap(460)
        self.folder = wx.DirPickerCtrl(
            self, path=str(folder or ""), style=wx.DIRP_USE_TEXTCTRL
        )
        self.folder.Bind(wx.EVT_DIRPICKER_CHANGED, lambda e: self.validate())
        self.formats = FormatsBox(self, kinds, on_change=self.validate)
        box = wx.StaticBoxSizer(wx.VERTICAL, self, "Output")
        box.Add(self.formats, 0, wx.ALL, 2)
        self.message = wx.StaticText(self, label="")
        self.message.SetForegroundColour(wx.Colour(180, 0, 0))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(text, 0, wx.ALL, 8)
        sizer.Add(self.folder, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(box, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(self.message, 0, wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.validate()

    def validate(self) -> list[str]:
        """Validate the folder and the formats, and show the first problem.

        The formats' fields with errors are marked, and OK is enabled only without
        problems.

        Returns:
            The problems, as messages; empty if there are none.
        """
        problems = []
        folder = self.folder.GetPath()
        if not folder:
            problems.append("Choose the folder to save the windows in")
        elif problem := folder_problem(folder):
            problems.append(problem)
        _, errors = self.formats.formats()
        self.formats.show_errors(errors)
        if errors:
            problems.append("Choose at least one format for each kind of window")
        self.message.SetLabel(problems[0] if problems else "")
        ok = self.FindWindowById(wx.ID_OK)
        if ok is not None:
            ok.Enable(not problems)
        return problems

    def result(self) -> tuple[Path, list[SaveOptions]]:
        """Return the chosen folder (canonical path) and the chosen formats."""
        formats, _ = self.formats.formats()
        return Path(canonical_folder(self.folder.GetPath())), formats


def ask_save_all(
    parent: wx.Window,
    folder: Optional[Union[str, os.PathLike]],
    kinds: Iterable[str],
) -> Optional[tuple[Path, list[SaveOptions]]]:
    """Ask for the folder and the formats to save all open windows in.

    Args:
        parent: The main window.
        folder: The folder shown first; None for an empty field.
        kinds: The kinds of the open windows' values, e.g. `["table", "plot"]`.

    Returns:
        The folder and the formats (see `SaveAllDialog.result`), or None if the
        dialog is cancelled.
    """
    with SaveAllDialog(parent, folder, kinds) as dialog:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.result()


class QuitDialog(wx.Dialog):
    """A dialog that asks what to do with unsaved windows before quitting.

    The choices are Cancel (do not quit), Review... (window by window), Save All
    Windows... and Discard All. The dialog lists the first `LISTED` window titles.

    Attributes:
        choice: The choice: `CANCEL`, `REVIEW`, `SAVE_ALL` or `DISCARD`; `CANCEL`
            until a button is clicked.
    """

    def __init__(self, parent: wx.Window, titles: Sequence[str]) -> None:
        """Create the dialog.

        Args:
            parent: The main window.
            titles: The titles of the unsaved windows.
        """
        super().__init__(parent, title="Quit FLIMAnalyzer")
        shown = "\n".join(titles[:LISTED]) + ("\n..." if len(titles) > LISTED else "")
        plural = "s have" if len(titles) > 1 else " has"
        text = wx.StaticText(
            self, label=f"{len(titles)} window{plural} unsaved results:\n\n{shown}"
        )
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.choice = CANCEL
        for label, choice in (
            ("Cancel", CANCEL),
            ("Review...", REVIEW),
            ("Save All Windows...", SAVE_ALL),
            ("Discard All", DISCARD),
        ):
            button = wx.Button(self, wx.ID_CANCEL if choice == CANCEL else wx.ID_ANY, label)
            button.Bind(wx.EVT_BUTTON, lambda e, c=choice: self._choose(c))
            buttons.Add(button, 0, wx.LEFT, 6)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(text, 0, wx.ALL, 12)
        sizer.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        self.SetSizerAndFit(sizer)

    def _choose(self, choice: str) -> None:
        """Keep the choice and close the dialog."""
        self.choice = choice
        self.EndModal(wx.ID_CANCEL if choice == CANCEL else wx.ID_OK)


def ask_quit(parent: wx.Window, titles: Sequence[str]) -> str:
    """Ask what to do with unsaved windows before quitting.

    Args:
        parent: The main window.
        titles: The titles of the unsaved windows.

    Returns:
        `CANCEL`, `REVIEW`, `SAVE_ALL` or `DISCARD`; `CANCEL` also when the dialog is
        closed.
    """
    with QuitDialog(parent, titles) as dialog:
        dialog.ShowModal()
        return dialog.choice


def ask_review(parent: wx.Window, title: str) -> str:
    """Ask whether to save one window.

    Args:
        parent: The main window.
        title: The window's title.

    Returns:
        `save`, `skip` (Don't Save), or `CANCEL` (Cancel, or the dialog closed).
    """
    with wx.MessageDialog(
        parent,
        f"Save {title}?",
        "Quit FLIMAnalyzer",
        style=wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
    ) as dialog:
        dialog.SetYesNoCancelLabels("Save", "Don't Save", "Cancel")
        answer = dialog.ShowModal()
    return {wx.ID_YES: "save", wx.ID_NO: "skip"}.get(answer, CANCEL)
