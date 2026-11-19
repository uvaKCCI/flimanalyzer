"""The GUI's dialogs about settings files: their problems, and the choice at startup."""

import logging
from pathlib import Path
from collections.abc import Sequence
from typing import Optional

import wx

from flim.core.paths import with_extension
from flim.core.settingsmgr import Pick, SettingsManager, file_description
from flim.core.settings import (
    SETTINGS_VERSION,
    SettingsValidation,
)

logger = logging.getLogger(__name__)

LISTED = 8  # items listed per kind of finding in the dialog; the log lists all
REWRITE = "Update the file to the current version and add the settings"
SAVE_OTHER = "Save to another file..."


def show_problems(
    validation: SettingsValidation,
    parent: Optional[wx.Window] = None,
    outcome: str = "The file is not used.",
    title: str = "Settings File",
) -> None:
    """Show why a settings file can't be used, before it is refused.

    A file that can't be used at all (it can't be read, isn't a settings file, or is
    of a newer version) is an error; a file with settings that can't be used
    (unknown or invalid) is a warning that lists them. Either way the file is not
    used: every setting of a file must be usable, as in flimbatch. The log lists all
    problems.

    Args:
        validation: The result of `validate_settings_file`.
        parent: The parent window; None for none.
        outcome: What happens next, e.g. that nothing is loaded.
        title: The box's title.
    """
    logger.warning(validation.summary())
    icon = wx.ICON_ERROR if validation.error else wx.ICON_WARNING
    message = (
        f"{validation.summary(limit=LISTED)}\n\n{outcome} {validate_command(validation.path)}"
        " lists every problem."
    )
    wx.MessageBox(message, title, wx.OK | icon, parent)


def validate_command(path: Path) -> str:
    """Return the flimsettings command that validates a settings file, by its kind.

    `flimsettings tool --validate` for a tool file, `workflow --validate` for a
    workflow file (`steps`), else `app --validate`, also for a file that cannot be read.

    Args:
        path: The settings file.

    Returns:
        The command, with the path.
    """
    import json

    from flim.core.settings import is_tool_file

    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        data = None
    if is_tool_file(data):
        kind = "tool"
    elif isinstance(data, dict) and "steps" in data and "tools" not in data:
        kind = "workflow"
    else:
        kind = "app"
    return f"flimsettings {kind} --validate {path}"


UPDATE_FILE = "Update"
NOT_NOW = "Not Now"


def offer_update(validation: SettingsValidation, parent: Optional[wx.Window] = None) -> bool:
    """Offer to rewrite a settings file of an older version in the current one.

    Asked only for a file of an older version all of whose settings can be used.
    `Update` rewrites it (`flim.core.settings.update_settings_file`) and keeps the
    original next to it; `Not Now` leaves it as it is, to be asked again next time.

    Args:
        validation: The result of `validate_settings_file` for the file used.
        parent: The parent window; None for none.

    Returns:
        Whether the file was updated.
    """
    from flim.core.settings import update_settings_file

    if validation.problems or validation.version is None or validation.version >= SETTINGS_VERSION:
        return False
    question = (
        f"{validation.path.name} is in the format of an older FLIMAnalyzer version (schema"
        f" {validation.version}). Update it to the current format?\n\nThe original is kept"
        f" next to it as {validation.path.stem}.v{validation.version}{validation.path.suffix},"
        " which the older version can still read."
    )
    with wx.MessageDialog(
        parent, question, "Settings File", wx.YES_NO | wx.ICON_QUESTION
    ) as dialog:
        dialog.SetYesNoLabels(UPDATE_FILE, NOT_NOW)
        if dialog.ShowModal() != wx.ID_YES:
            return False
    try:
        backup = update_settings_file(validation.path)
    except (OSError, ValueError) as err:
        wx.MessageBox(f"Could not update {validation.path}:\n{err}", "Settings File", wx.OK | wx.ICON_ERROR, parent)
        return False
    logger.info(f"{validation.path} updated to the current format; the original is {backup}")
    return True


def needs_rewrite(validation: SettingsValidation) -> bool:
    """Return whether adding settings to a validated file rewrites more than they.

    That is the case if the file can be read and is of an older version or has
    settings that cannot be used.
    """
    return validation.error is None and (
        validation.version < SETTINGS_VERSION or bool(validation.unknown or validation.invalid)
    )


def confirm_rewrite(
    validation: SettingsValidation, parent: Optional[wx.Window] = None
) -> Optional[str]:
    """Ask before settings are added to a file that would be rewritten.

    Args:
        validation: The result of `validate_settings_file` for the file.
        parent: The parent window; None for none.

    Returns:
        `REWRITE` to update the file, the path of another file to save to, or None
        (Cancel, or no other file chosen).
    """
    message = (
        validation.summary(limit=LISTED)
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
BROWSE = "Browse..."
CLEAR_DEFAULT = "Clear Default"


class StartupSettingsDialog(wx.Dialog):
    """Dialog that asks which app settings file to start with.

    The table lists the files (default, file, folder). With a default set, its row is
    selected and Enter starts with it; without one, no row is selected and Enter
    starts without a file (`Skip App Settings`, also Esc). `Make Default` makes the
    selected file the default, `Clear Default` clears it; the check mark in the
    Default column shows the default at once, and the change applies with either
    button. `Browse...` adds a file from another folder to the list and selects it;
    a folder outside the search path can be added to it (`added_folder`).
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        files: list[Path],
        default: Optional[Path],
        warning: Optional[str] = None,
        search_path: Sequence[Path] = (),
    ) -> None:
        """Create the dialog.

        Args:
            parent: The parent window; None for none.
            files: The files to list.
            default: The default app settings file, selected, and listed first if not
                in `files`; None if none is set.
            warning: A message shown in red above the list; None for none.
            search_path: The app settings search path; `Browse...` offers to add a
                file's folder that is not in it. Defaults to none.
        """
        super().__init__(parent, title="App Settings File")
        self.files = list(files)
        if default is not None and default not in self.files:
            self.files.insert(0, default)
        self.default = default  # changed by Make Default and Clear Default
        self.search_path = [Path(f).expanduser().resolve() for f in search_path]
        self.added_folder: Optional[Path] = None  # Browse...: added to the search path
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
        self.browse = wx.Button(self, label=BROWSE)
        self.browse.Bind(wx.EVT_BUTTON, self._on_browse)
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
        row.AddStretchSpacer()
        row.Add(self.browse, 0)
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

    def _on_browse(self, event: wx.CommandEvent) -> None:
        """Add a file from another folder to the list and select it."""
        with wx.FileDialog(
            self,
            "Choose an App Settings File",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = Path(dialog.GetPath())
        self.add_file(path)
        folder = path.parent.resolve()
        if folder not in self.search_path and folder != self.added_folder:
            question = (
                f"Add this folder to your app settings search path?\n\n{folder}\n\n"
                "The GUI then lists its files when it starts, and -s finds them by name."
            )
            with wx.MessageDialog(
                self, question, "App Settings File", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
            ) as dialog:
                if dialog.ShowModal() == wx.ID_YES:
                    self.added_folder = folder

    def add_file(self, path: Path) -> None:
        """Add a file to the list, if it is not listed, and select it."""
        if path not in self.files:
            self.files.append(path)
            self._fill()
        self.select(self.files.index(path))
        self.ok.SetDefault()

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
        return Pick(chosen if answer == wx.ID_OK else None, self.default, self.added_folder)


def pick_app_settings(
    files: list[Path],
    default: Optional[Path] = None,
    warning: Optional[str] = None,
    parent: Optional[wx.Window] = None,
    search_path: Sequence[Path] = (),
) -> Pick:
    """Ask which app settings file to start with (`StartupSettingsDialog`).

    Args:
        files: The files in the app settings search path (`list_app_settings`).
        default: The default app settings file, preselected; None if none is set.
        warning: A message to show above the list, e.g. that a default was cleared;
            None for none.
        parent: The parent window; None for none.
        search_path: The app settings search path, for `Browse...`.

    Returns:
        The file to start with (None for `Skip App Settings`), the default from
        now on, and a folder to add to the search path (`Browse...`), if any.
    """
    dialog = StartupSettingsDialog(parent, files, default, warning, search_path)
    try:
        picked = dialog.result(dialog.ShowModal())
    finally:
        dialog.Destroy()
    logger.info(f"App settings file chosen at startup: {picked.file or 'none'}")
    return picked


def offer_import_workflow(
    validation: SettingsValidation,
    parent: Optional[wx.Window],
    settings_manager: SettingsManager,
) -> Optional[Path]:
    """Offer to save the import settings of a FLIMAnalyzer 0.6 file as a workflow file.

    If the file has such settings (`SettingsValidation.import_workflow`), the user is asked
    whether to save them as a workflow file, and where; the dialog opens in the first
    folder of the workflow search path, which is created if needed. Nothing is
    applied otherwise. The saved file is registered as a tool if no tool of its name
    is registered, and Import Tables' settings are set to run it and to read the
    files as the 0.6 settings did (`SettingsValidation.import_read`).

    Args:
        validation: The result of `validate_settings_file`.
        parent: The parent window; None for none.
        settings_manager: The session's settings manager, for the workflow search
            path and Import Tables' settings.

    Returns:
        The saved file; None if the file has no such settings or the user saved none.
    """
    import json

    from flim.core.registry import tools
    from flim.core.workflowfile import validate_workflow_file, workflow_class

    data = getattr(validation, "import_workflow", None)
    if not data:
        return None
    question = (
        f"{validation.path.name} has import settings of FLIMAnalyzer 0.6 (delimiter,"
        " filename parser, renamed, dropped and calculated columns). FLIMAnalyzer now"
        " imports with workflow files, so these settings are not used.\n\nSave them as"
        " a workflow file, to run with File > Import Tables...?"
    )
    with wx.MessageDialog(parent, question, "Import settings", style=wx.YES_NO | wx.ICON_QUESTION) as dialog:
        dialog.SetYesNoLabels("Save as Workflow File...", "Don't Save")
        if dialog.ShowModal() != wx.ID_YES:
            return None
    folder = settings_manager.workflow_search_path()[0]
    folder.mkdir(parents=True, exist_ok=True)
    with wx.FileDialog(
        parent, "Save as Workflow File", defaultDir=str(folder),
        defaultFile=f"{validation.path.stem}-import.json", wildcard="Workflow files (*.json)|*.json|All files|*",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    ) as dialog:  # fmt: skip
        if dialog.ShowModal() != wx.ID_OK:
            return None
        path = Path(with_extension(dialog.GetPath(), ".json"))
    path.write_text(json.dumps(data, indent=2) + "\n")
    result = validate_workflow_file(path)
    if result.definition is not None and result.definition.name not in tools:
        tools.register(workflow_class(result.definition, path))
    if result.definition is not None:
        from flim.tools.readers import ImportTables

        settings = settings_manager.settings
        current = settings.tools.config(ImportTables)
        config = type(current).model_validate({
            **current.model_dump(), **getattr(validation, "import_read", {}),
            "workflow": result.definition.name,
        })  # fmt: skip
        entry = settings.tools.entry(ImportTables)
        settings_manager.set_tool(ImportTables, config, entry.autosave if entry else None)
    return path
