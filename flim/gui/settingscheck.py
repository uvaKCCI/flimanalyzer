"""The choice the GUI offers when some settings of a settings file cannot be used."""

import logging
from pathlib import Path
from typing import Callable, Optional

import wx

from flim.core.paths import with_extension
from flim.core.settingsmgr import Pick, SettingsManager, file_description
from flim.core.settings import (
    SETTINGS_VERSION,
    SettingsCheck,
    check_settings_file,
    save_sections,
)

logger = logging.getLogger(__name__)

USE = "Use the settings that can be used; skip the others"
IGNORE = "Don't use this file"
UPDATE = "Update the file to the current version; remove the settings that can't be used"
OTHER = "Choose another file..."
LISTED = 8  # items listed per kind of finding in the dialog; the log lists all
REWRITE = "Update the file to the current version and add the settings"
SAVE_OTHER = "Save to another file..."


def _options(check: SettingsCheck) -> list[str]:
    """Return the options for a checked file; an unreadable file offers fewer."""
    return [IGNORE, OTHER] if check.error else [USE, IGNORE, UPDATE, OTHER]


def _confirm_update(check: SettingsCheck, parent: Optional[wx.Window]) -> bool:
    """Ask whether to replace the file with its usable settings; True for Yes."""
    message = (
        f"Replace {check.path} with the settings that can be used, in the current"
        " version?\n\nThe settings listed as unknown or invalid are removed from the"
        " file. This cannot be undone."
    )
    with wx.MessageDialog(
        parent, message, "Update Settings File", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING
    ) as dialog:
        return dialog.ShowModal() == wx.ID_YES


def _other_file(parent: Optional[wx.Window]) -> Optional[str]:
    """Ask for another settings file to open; None if cancelled."""
    with wx.FileDialog(
        parent,
        "Choose a Settings File",
        wildcard="JSON files (*.json)|*.json|All files|*",
        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
    ) as dialog:
        return dialog.GetPath() if dialog.ShowModal() == wx.ID_OK else None


def choose_settings(
    check: SettingsCheck,
    parent: Optional[wx.Window] = None,
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
        parent: The parent window; None for none.
        problems: A function of a check that returns whether it has problems that
            need the user's choice. Defaults to `SettingsCheck.problems`.

    Returns:
        The check whose sections to use (of this or another file), or None to use
        no file.
    """
    problems = problems or (lambda c: c.problems)
    while True:
        logger.warning(check.summary())
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
            logger.info(f"{check.path} not used")
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
            logger.info(f"{check.path} updated to the current version")
            return check_settings_file(check.path)
        path = _other_file(parent)
        if path is None:
            continue
        check = check_settings_file(path)
        if not problems(check):
            return check


def needs_rewrite(check: SettingsCheck) -> bool:
    """Return whether adding settings to a checked file rewrites more than they.

    That is the case if the file can be read and is of an older version or has
    settings that cannot be used.
    """
    return check.error is None and (
        check.version < SETTINGS_VERSION or bool(check.unknown or check.invalid)
    )


def confirm_rewrite(
    check: SettingsCheck, parent: Optional[wx.Window] = None
) -> Optional[str]:
    """Ask before settings are added to a file that would be rewritten.

    Args:
        check: The result of `check_settings_file` for the file.
        parent: The parent window; None for none.

    Returns:
        `REWRITE` to update the file, the path of another file to save to, or None
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


def _save_file(parent: Optional[wx.Window]) -> Optional[str]:
    """Ask for a file to save the settings to; None if cancelled."""
    with wx.FileDialog(
        parent,
        "Save Settings",
        wildcard="JSON files (*.json)|*.json|All files|*",
        style=wx.FD_SAVE,
    ) as dialog:
        return with_extension(dialog.GetPath(), ".json") if dialog.ShowModal() == wx.ID_OK else None


SKIP = "Skip App Settings"
STARTUP_COLUMNS = ("Default", "File", "Description", "Folder")
DEFAULT_MARK = "\u2713"  # check mark
MAKE_DEFAULT = "Make Default"
CLEAR_DEFAULT = "Clear Default"


class StartupSettingsDialog(wx.Dialog):
    """Dialog that asks which app settings file to start with.

    The table lists the files (default, file, folder). With a default set, its row is
    selected and Enter starts with it; without one, no row is selected and Enter
    starts without a file (`Skip App Settings`, also Esc). `Make Default` makes the
    selected file the default, `Clear Default` clears it; the check mark in the
    Default column shows the default at once, and the change applies with either
    button.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        files: list[Path],
        default: Optional[Path],
        warning: Optional[str] = None,
    ) -> None:
        """Create the dialog.

        Args:
            parent: The parent window; None for none.
            files: The files to list.
            default: The default app settings file, selected, and listed first if not
                in `files`; None if none is set.
            warning: A message shown in red above the list; None for none.
        """
        super().__init__(parent, title="App Settings File")
        self.files = list(files)
        if default is not None and default not in self.files:
            self.files.insert(0, default)
        self.default = default  # changed by Make Default and Clear Default
        self.table = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for i, title in enumerate(STARTUP_COLUMNS):
            self.table.InsertColumn(i, title)
        self._fill()
        self.table.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda event: self._update())
        self.table.Bind(wx.EVT_LIST_ITEM_DESELECTED, lambda event: self._update())
        self.table.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda event: self.EndModal(wx.ID_OK))
        self.make_default = wx.Button(self, label=MAKE_DEFAULT)
        self.make_default.Bind(wx.EVT_BUTTON, self._on_make_default)
        self.clear = wx.Button(self, label=CLEAR_DEFAULT)
        self.clear.Bind(wx.EVT_BUTTON, self._on_clear)
        # the Cancel id: Esc and closing the window skip too
        self.skip = wx.Button(self, wx.ID_CANCEL, SKIP)
        self.ok = wx.Button(self, wx.ID_OK)
        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(self.skip)
        buttons.AddButton(self.ok)
        buttons.Realize()

        sizer = wx.BoxSizer(wx.VERTICAL)
        if warning:
            text = wx.StaticText(self, label=warning)
            text.SetForegroundColour(wx.Colour(180, 0, 0))
            text.Wrap(520)
            sizer.Add(text, 0, wx.ALL, 8)
        sizer.Add(
            wx.StaticText(
                self,
                label="Start with an app settings file? Its settings apply to this session.",
            ),
            0,
            wx.ALL,
            8,
        )
        sizer.Add(self.table, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.make_default, 0, wx.RIGHT, 8)
        row.Add(self.clear, 0)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        # long folders are cut off at the right, not widen the dialog
        self.SetSize(min(max(self.GetSize().width, 560), 760), self.GetSize().height)
        if default is not None:
            self.select(self.files.index(default))
            self.ok.SetDefault()  # Enter: start with the default
        else:
            self.skip.SetDefault()  # Enter: start without a file
            self._update()

    def rows(self) -> list[tuple[str, str, str, str]]:
        """Return the table's rows: default mark, file name, description, folder.

        A folder in the home folder starts with `~`.
        """
        home = Path.home()
        rows = []
        for f in self.files:
            folder = f.parent
            if folder.is_relative_to(home):
                folder = Path("~") / folder.relative_to(home)
            rows.append(
                (DEFAULT_MARK if f == self.default else "", f.name, file_description(f), str(folder))
            )
        return rows

    def _fill(self) -> None:
        """Fill the table with `rows()` and fit the column widths."""
        self.table.DeleteAllItems()
        for row in self.rows():
            index = self.table.InsertItem(self.table.GetItemCount(), row[0])
            for column in range(1, len(row)):
                self.table.SetItem(index, column, row[column])
        self.table.SetColumnWidth(0, wx.LIST_AUTOSIZE_USEHEADER)
        for column in range(1, len(STARTUP_COLUMNS)):
            self.table.SetColumnWidth(column, wx.LIST_AUTOSIZE_USEHEADER)

    def select(self, index: int) -> None:
        """Select the row of file `index`."""
        self.table.Select(index)
        self.table.Focus(index)
        self._update()

    def selected(self) -> Optional[Path]:
        """Return the selected file; None if no row is selected."""
        index = self.table.GetFirstSelected()
        return self.files[index] if index >= 0 else None

    def _update(self) -> None:
        """Enable the buttons that apply to the selection and the default."""
        chosen = self.selected()
        self.make_default.Enable(chosen is not None and chosen != self.default)
        self.clear.Enable(self.default is not None)
        self.ok.Enable(chosen is not None)

    def _set_default(self, default: Optional[Path]) -> None:
        """Change the default and its check mark; the selection stays."""
        self.default = default
        for index, row in enumerate(self.rows()):
            self.table.SetItem(index, 0, row[0])
        self._update()

    def _on_make_default(self, event: wx.CommandEvent) -> None:
        """Make the selected file the default."""
        self._set_default(self.selected())

    def _on_clear(self, event: wx.CommandEvent) -> None:
        """Clear the default."""
        self._set_default(None)

    def result(self, answer: int) -> Pick:
        """Return the choice for the button the dialog ended with.

        Args:
            answer: `wx.ID_OK` (start with the selected file) or `wx.ID_CANCEL`
                (`Skip App Settings`).

        Returns:
            The file to start with (None when skipped), and the default after the
            changes made in the dialog, with either button.
        """
        chosen = self.selected()
        return Pick(chosen if answer == wx.ID_OK else None, self.default)


def pick_app_settings(
    files: list[Path],
    default: Optional[Path] = None,
    warning: Optional[str] = None,
    parent: Optional[wx.Window] = None,
) -> Pick:
    """Ask which app settings file to start with (`StartupSettingsDialog`).

    Args:
        files: The files in the app settings search path (`list_app_settings`).
        default: The default app settings file, preselected; None if none is set.
        warning: A message to show above the list, e.g. that a default was cleared;
            None for none.
        parent: The parent window; None for none.

    Returns:
        The file to start with (None for `Skip App Settings`) and the default from
        now on.
    """
    dialog = StartupSettingsDialog(parent, files, default, warning)
    try:
        picked = dialog.result(dialog.ShowModal())
    finally:
        dialog.Destroy()
    logger.info(f"App settings file chosen at startup: {picked.file or 'none'}")
    return picked


def offer_import_workflow(
    check: SettingsCheck,
    parent: Optional[wx.Window],
    settings_manager: SettingsManager,
) -> Optional[Path]:
    """Offer to save the import settings of a FLIMAnalyzer 0.6 file as a workflow file.

    If the file has such settings (`SettingsCheck.import_workflow`), the user is asked
    whether to save them as a workflow file, and where; the dialog opens in the first
    folder of the workflow search path, which is created if needed. Nothing is
    applied otherwise. The saved file is registered as a tool if no tool of its name
    is registered, and Import Tables' settings are set to run it and to read the
    files as the 0.6 settings did (`SettingsCheck.import_read`).

    Args:
        check: The result of `check_settings_file`.
        parent: The parent window; None for none.
        settings_manager: The session's settings manager, for the workflow search
            path and Import Tables' settings.

    Returns:
        The saved file; None if the file has no such settings or the user saved none.
    """
    import json

    from flim.core.registry import tools
    from flim.core.workflowfile import check_workflow_file, workflow_class, workflow_path

    data = getattr(check, "import_workflow", None)
    if not data:
        return None
    question = (
        f"{check.path.name} has import settings of FLIMAnalyzer 0.6 (delimiter,"
        " filename parser, renamed, dropped and calculated columns). FLIMAnalyzer now"
        " imports with workflow files, so these settings are not used.\n\nSave them as"
        " a workflow file, to run with File > Import Tables...?"
    )
    with wx.MessageDialog(parent, question, "Import settings", style=wx.YES_NO | wx.ICON_QUESTION) as dialog:
        dialog.SetYesNoLabels("Save as Workflow File...", "Don't Save")
        if dialog.ShowModal() != wx.ID_YES:
            return None
    folder = workflow_path(settings_manager.settings.workflow_paths)[0]
    folder.mkdir(parents=True, exist_ok=True)
    with wx.FileDialog(
        parent, "Save as Workflow File", defaultDir=str(folder),
        defaultFile=f"{check.path.stem}-import.json", wildcard="Workflow files (*.json)|*.json|All files|*",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    ) as dialog:  # fmt: skip
        if dialog.ShowModal() != wx.ID_OK:
            return None
        path = Path(with_extension(dialog.GetPath(), ".json"))
    path.write_text(json.dumps(data, indent=2) + "\n")
    result = check_workflow_file(path)
    if result.definition is not None and result.definition.name not in tools:
        tools.register(workflow_class(result.definition, path))
    if result.definition is not None:
        from flim.tools.readers import ImportTables

        settings = settings_manager.settings
        current = settings.tools.config(ImportTables)
        config = type(current).model_validate({
            **current.model_dump(), **getattr(check, "import_read", {}),
            "workflow": result.definition.name,
        })  # fmt: skip
        entry = settings.tools.entry(ImportTables)
        settings_manager.set_tool(ImportTables, config, entry.autosave if entry else None)
    return path
