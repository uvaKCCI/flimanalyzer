"""Configuration dialogs of tools, generated from their config classes.

`open_config_dialog(parent, tool, config, data_choices=...)` shows the dialog
registered for the tool's config class (`register_dialog`) or the generic
`ConfigDialog`. The dialog lets the user pick the input tables, edit the config and
choose whether results are saved; it validates the config against the inputs while it
is edited and marks problems at their fields (errors keep OK disabled).
"""

import logging
import warnings
import json
import os
from pathlib import Path
import re
from dataclasses import dataclass
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Union

import pandas as pd
import wx
import wx.grid
from pydantic import ValidationError
from wx.lib.scrolledpanel import ScrolledPanel

from flim.core.config import Issue, TaskConfig
from flim.core.workflow import Workflow
from flim.core.execution import ExecutionOptions
from flim.core.paths import canonical_folder, folder_problem, resolved_folder, stored_folder, with_extension
from flim.core.schema import ColumnInfo, TableSchema
from flim.core.settings import read_tool_settings, tool_settings, write_tool_settings
from flim.gui.editors import FieldErrors, FieldsPanel
from flim.gui.formats import FormatsBox

if TYPE_CHECKING:
    from flim.core.saving import AutosaveConfig, SaveOptions
    from flim.core.settings import ToolSettings
    from flim.core.settingsmgr import SettingsManager
    from flim.core.tool import Tool

logger = logging.getLogger(__name__)

SEVERITY_ORDER = ("error", "guessed", "warning")  # first: most severe


@dataclass
class DialogResult:
    """What a configuration dialog returns when it is closed with OK.

    Attributes:
        config: The edited config.
        inputs: Per input of the tool: the selected table, or for an input with
            `many=True` a dict of the selected tables by name.
        input_names: Per input of the tool: the selected table's name, or for an
            input with `many=True` a list of names.
        execution: The execution options of the run; its results folder is
            resolved (the default folder if the tool follows it).
        stored_autosave: The autosave settings to store in the tool's settings: no
            results folder if the tool follows the default folder.
    """

    config: TaskConfig
    inputs: list  # per InputSpec: a DataFrame, or a dict of them (many=True)
    input_names: list  # per InputSpec: a table name, or a list of names
    execution: ExecutionOptions  # for the run: the results folder is resolved
    # for the tool's settings: no results folder if the tool follows the default
    stored_autosave: Optional[Any] = None


_DIALOGS: dict = {}
_settings_manager: Optional["SettingsManager"] = None  # the session's (see bind_presets)


def bind_presets(settings_manager: Optional["SettingsManager"]) -> None:
    """Use a session's settings for the saved presets of the `PresetsDialog` dialogs.

    Args:
        settings_manager: The SettingsManager of the session; None for no saved
            presets.
    """
    global _settings_manager
    _settings_manager = settings_manager


def register_dialog(
    *config_classes: type,
) -> Callable[[type["ConfigDialog"]], type["ConfigDialog"]]:
    """Return a class decorator that registers a dialog for config classes.

    The dialog is used for these config classes and their subclasses (see
    `dialog_class`).

    Args:
        *config_classes: The config classes.

    Returns:
        The decorator; it returns the dialog class unchanged.
    """

    def register(dialog: type["ConfigDialog"]) -> type["ConfigDialog"]:
        for config_class in config_classes:
            _DIALOGS[config_class] = dialog
        return dialog

    return register


def has_dialog(config_class: type) -> bool:
    """Return whether a dialog is registered for a config class or one of its bases.

    Registering (`register_dialog`), also of the generic `ConfigDialog`, says that the
    tool can be fully configured in the GUI. The shared bases of all configs don't
    count.

    Args:
        config_class: The config class of a tool.

    Returns:
        True if a dialog is registered for the class or a base of it.
    """
    from pydantic import BaseModel

    from flim.core.config import BaseConfig, TaskConfig

    shared = {TaskConfig, BaseConfig, BaseModel, object}
    return any(base in _DIALOGS for base in config_class.__mro__ if base not in shared)


_warned: set = set()  # tools of other packages warned about (once each)


def shown_in_gui(tool: type["Tool"]) -> bool:
    """Return whether the GUI offers a tool in its menus and tool panel.

    A workflow file always (it is configured by its file); a tool or workflow only
    with a registered dialog (`has_dialog`). A tool of another package without one is
    still shown in this version, with a `DeprecationWarning` (from 0.8.0 it isn't).
    Where a tool is shown also depends on its `category`.

    Args:
        tool: The tool or workflow class.

    Returns:
        True if the GUI offers it.
    """
    if getattr(tool, "definition", None) is not None or has_dialog(tool.config_class):
        return True
    if tool.__module__.split(".")[0] == "flim":
        return False  # FLIMAnalyzer's own: not configurable in the GUI yet
    if tool.name not in _warned:
        _warned.add(tool.name)
        message = (
            f"{tool.name}: no dialog registered for {tool.config_class.__name__};"
            " shown with the generic dialog until 0.8.0, then hidden. Register one with"
            " flim.gui.configdialog.register_dialog (also ConfigDialog itself)."
        )
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        logger.warning(message)
    return True


def dialog_class(config_class: type) -> type["ConfigDialog"]:
    """Return the dialog class for a config class.

    Args:
        config_class: The config class of a tool.

    Returns:
        The dialog registered for the class or its nearest base class
        (`register_dialog`), or `ConfigDialog` if none is registered.
    """
    for base in config_class.__mro__:
        if base in _DIALOGS:
            return _DIALOGS[base]
    return ConfigDialog


def open_config_dialog(
    parent: Optional[wx.Window],
    tool: type["Tool"],
    config: Optional[TaskConfig] = None,
    **kwargs: Any,
) -> Optional[DialogResult]:
    """Show the configuration dialog of a tool as a modal dialog.

    Args:
        parent: The parent window.
        tool: The tool class.
        config: The config to edit. Defaults to None: the config class's defaults.
        **kwargs: Further arguments of the dialog (see `ConfigDialog`).

    Returns:
        The result, or None if the dialog was cancelled.
    """
    dialog = dialog_class(tool.config_class)(parent, tool, config, **kwargs)
    try:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.result()
    finally:
        dialog.Destroy()


def top_field(path: Optional[str]) -> Optional[str]:
    """Return the top-level field of a field path.

    Args:
        path: The path of a field, e.g. `range_filters[0].column`.

    Returns:
        The first name of the path, e.g. `range_filters`; None if `path` is None or
        empty.
    """
    return None if not path else re.split(r"[.\[]", path, maxsplit=1)[0]


def validation_issues(error: ValidationError) -> list[Issue]:
    """Return the errors of a pydantic validation as issues.

    Args:
        error: The validation error.

    Returns:
        One issue per error, at the field path of the error, or None for the config
        as a whole (for example `range_filters[0].column`), with the message without
        the prefix `Value error,`.
    """
    issues = []
    for e in error.errors():
        path = ""
        for part in e["loc"]:
            path += (
                f"[{part}]"
                if isinstance(part, int)
                else (f".{part}" if path else str(part))
            )
        message = e["msg"].removeprefix("Value error, ")
        issues.append(Issue(path or None, message))
    return issues


def combined_schema(
    schemas: list[Union[TableSchema, dict[str, TableSchema], None]],
) -> Optional[TableSchema]:
    """Return a schema with the columns of all selected inputs.

    Args:
        schemas: Per input: its schema, a dict of schemas by table name (an input
            with `many=True`), or None if no table is selected.

    Returns:
        The columns of all schemas (a column name that occurs more than once: its
        first occurrence); complete if all schemas are; the header level names of
        the first schema that has them. None if there are no schemas.
    """
    flat = []
    for s in schemas:
        flat.extend(s.values() if isinstance(s, dict) else [s])
    flat = [s for s in flat if s is not None]
    if not flat:
        return None
    columns: dict[str, ColumnInfo] = {}
    for s in flat:
        for c in s.columns:
            columns.setdefault(c.name, c)
    return TableSchema(
        columns=list(columns.values()),
        complete=all(s.complete for s in flat),
        # the header level names of the first input that has them
        header_levels=next((s.header_levels for s in flat if s.header_levels), []),
    )


class ConfigDialog(wx.Dialog):
    """Generic configuration dialog of a tool, built from its config class.

    The dialog has three sections: Input (the input tables, shown only if there are
    `data_choices`), Settings (the editors of the config's fields) and Output (the
    fields of the `output` section, whether and where the results are saved, and
    the formats). Each change is validated (`validate`); OK is enabled only while
    there are no errors.
    """

    def __init__(
        self,
        parent: Optional[wx.Window],
        tool: type["Tool"],
        config: Optional[TaskConfig] = None,
        data_choices: Optional[dict[str, Any]] = None,
        selected: Optional[list[Union[str, list[str], None]]] = None,
        execution: Optional[ExecutionOptions] = None,
        autosave_locked: bool = False,
        strict: Optional[bool] = None,
        default_folder: Union[str, os.PathLike, None] = None,
        on_make_default: Optional[Callable[[Path], Any]] = None,
        keep_relative: bool = True,
    ) -> None:
        """Build the dialog and show the config, its inputs and output options.

        Args:
            parent: The parent window.
            tool: The tool class.
            config: The config to edit. Defaults to None: the config class's
                defaults.
            data_choices: The open tables by name; the first is the current one.
                Defaults to None: no Input section.
            selected: Per input: the preselected table name, or for an input with
                `many=True` a list of names. Defaults to None: the i-th table for
                the i-th input, all tables for an input with `many=True`.
            execution: The execution options; the dialog edits their autosave
                settings (whether to save, the folder and the formats). Defaults to
                None: the default options.
            autosave_locked: Whether `Save results` is checked and cannot be
                unchecked (workflows). Defaults to False.
            strict: For workflows: the `strict` of the validation of a config whose
                `strict` is None. Defaults to None.
            default_folder: The GUI's default results folder. Defaults to None: no
                `Use the default folder` and `Make Default Folder`.
            on_make_default: Called with the folder when the user makes it the
                default results folder. Defaults to None.
            keep_relative: Whether a folder inside the default folder is kept
                relative to it. False when the default folder is only the start
                folder (no `results_dir` set), which can differ from one session to
                the next: folders are then kept as full paths. Defaults to True.
        """
        super().__init__(
            parent,
            title=f"Configuration: {tool.name}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.tool = tool
        self.config = config if config is not None else tool.config_class()
        self.data_choices = dict(data_choices or {})
        self.execution = execution or ExecutionOptions()
        self.autosave_locked = autosave_locked
        self.strict = strict  # workflows: the default of a config whose strict is None
        # the GUI's default results folder (None: no "Use the default folder"), and
        # what makes a folder the default (SettingsManager)
        self.default_folder = Path(default_folder) if default_folder else None
        self.on_make_default = on_make_default
        self.keep_relative = keep_relative
        self.issues: list[Issue] = []
        self._schema_cache: dict[str, TableSchema] = {}

        sizer = wx.BoxSizer(wx.VERTICAL)
        if tool.description:
            text = wx.StaticText(self, label=tool.description)
            text.Wrap(520)
            sizer.Add(text, 0, wx.ALL, 8)
        # three sections, all visible: Input (the data), Settings (the tool's fields),
        # Output (the fields that name the results, and how they are saved); a
        # field's section comes from the config (flim.core.fields, `section`)
        if self.data_choices:
            input_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Input")
            self.input_controls = self._input_controls(input_box, selected)
            sizer.Add(input_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        else:
            self.input_controls = []
        output_names = self.output_field_names()

        settings_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Settings")
        self.scroll = ScrolledPanel(self)
        self.fields = self.create_fields(self.scroll)
        self.fields.on_change = self.validate
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        scroll_sizer.Add(self.fields, 1, wx.EXPAND)
        self.scroll.SetSizer(scroll_sizer)
        self.scroll.SetupScrolling(scroll_x=False)
        settings_box.Add(self.scroll, 1, wx.EXPAND)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, tip, handler in self.settings_buttons():
            button = wx.Button(self, label=label)
            button.SetToolTip(tip)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 4)
        self.settings_message = wx.StaticText(self, label="")
        buttons.Add(self.settings_message, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)
        settings_box.Add(buttons, 0, wx.EXPAND | wx.TOP, 4)
        sizer.Add(settings_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        # what the tool does with the first row (Tool.example), if it shows that
        self.example = wx.StaticText(self, label="")
        self.example.Hide()
        sizer.Add(self.example, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.status = wx.StaticText(self, label="")
        self.status.SetForegroundColour(wx.Colour(180, 0, 0))
        sizer.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        output_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Output")
        self.output_fields = None
        if output_names:
            hidden = [n for n in type(self.config).model_fields if n not in output_names]
            self.output_fields = FieldsPanel(self, type(self.config), exclude=hidden)
            self.output_fields.on_change = self.validate
            output_box.Add(self.output_fields, 0, wx.EXPAND)
        output_box.Add(self._execution_controls(), 0, wx.EXPAND | wx.TOP, 4)
        sizer.Add(output_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        ok_cancel = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(ok_cancel, 0, wx.EXPAND | wx.ALL, 8)
        # FindWindow searches this dialog's children; FindWindowById all windows
        self.ok_button = self.FindWindow(wx.ID_OK)
        self.ok_button.Bind(wx.EVT_BUTTON, self._on_ok)
        self.SetSizer(sizer)

        self.set_values(self.config)
        self._update_inputs()
        self.set_values(self.config)  # columns are listed now
        self.validate()
        self._fit()

    # --- building ---

    def selected_tables(self) -> list[pd.DataFrame]:
        """Return the selected input tables that are DataFrames.

        The tables of an input with `many=True` are included.
        """
        tables = []
        for value in self.selected_inputs():
            tables.extend(value.values() if isinstance(value, dict) else [value])
        return [t for t in tables if isinstance(t, pd.DataFrame)]

    def data_issues(self, config: Optional[TaskConfig]) -> list[Issue]:
        """Show the tool's example line and validate the config against the input data.

        The example line comes from `Tool.example`, the validation from
        `Tool.validate_data`, both with the selected tables. An exception in them is
        logged, not shown; the example line is then hidden.

        Args:
            config: The edited config; None if it is not valid.

        Returns:
            The issues; empty if `config` is None or the validation raised an exception.
        """
        if config is None:
            self._show_example(None)
            return []
        tables = self.selected_tables()
        try:
            self._show_example(self.tool.example(config, tables))
            return list(self.tool.validate_data(config, tables))
        except Exception:
            logger.exception(f"{self.tool.name}: the validation of the data failed")
            self._show_example(None)
            return []

    def _show_example(self, line: Optional[str]) -> None:
        """Show the example line below the settings; hide it if `line` is empty."""
        if not hasattr(self, "example"):
            return
        self.example.SetLabel(f"Example: {line}" if line else "")
        self.example.Show(bool(line))

    def output_field_names(self) -> list[str]:
        """Return the names of the config's fields shown in the Output section.

        These are the fields whose `section` is `output`, e.g. the prefix of the
        results' names.
        """
        from flim.core.fields import describe

        return [s.name for s in describe(type(self.config)) if s.section == "output"]

    def create_fields(self, parent: wx.Window) -> FieldsPanel:
        """Return the editors of the Settings section.

        Subclasses can override this to add editors or replace them. The fields of
        the Output section (`output_field_names`) are left out.

        Args:
            parent: The window of the editors (the scrolled panel of the section).

        Returns:
            The panel of the editors.
        """
        return FieldsPanel(parent, type(self.config), exclude=self.output_field_names())

    def panels(self) -> list[FieldsPanel]:
        """Return the editor panels: Settings, and Output if it has fields."""
        return [p for p in (self.fields, getattr(self, "output_fields", None)) if p]

    def settings_buttons(
        self,
    ) -> list[tuple[str, str, Callable[[wx.CommandEvent], None]]]:
        """Return the buttons below the Settings section.

        Subclasses can override this to add buttons.

        Returns:
            One `(label, tooltip, handler)` tuple per button: `Load Settings...` and
            `Save Settings...`. Each handler is bound to the button's click.
        """
        return [
            (
                "Load Settings...",
                "This tool's settings from a settings file",
                self._on_load_settings,
            ),
            (
                "Save Settings...",
                "Adds or updates this tool's settings in a settings file; its other"
                " settings are kept",
                self._on_save_settings,
            ),
        ]

    def set_values(self, config: TaskConfig) -> None:
        """Show a config in the fields of the Settings and Output sections."""
        for panel in self.panels():
            panel.set_values(config)

    def _input_controls(
        self,
        sizer: wx.Sizer,
        selected: Optional[list[Union[str, list[str], None]]],
    ) -> list[Union[wx.Choice, wx.CheckListBox]]:
        """Add a table choice per input to `sizer`; return the controls."""
        controls = []
        if not self.data_choices:
            return controls
        names = list(self.data_choices)
        grid = wx.FlexGridSizer(cols=2, vgap=4, hgap=6)
        grid.AddGrowableCol(1)
        for i, spec in enumerate(self.tool.inputs):
            label = spec.name.replace("_", " ").capitalize()
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            choice = selected[i] if selected and i < len(selected) else None
            if spec.many:
                control = wx.CheckListBox(self, choices=names)
                checked = choice if isinstance(choice, list) else names
                control.SetCheckedItems([names.index(n) for n in checked if n in names])
                control.SetMinSize((-1, 60))
                control.Bind(wx.EVT_CHECKLISTBOX, self._on_input)
            else:
                control = wx.Choice(self, choices=names)
                default = choice if choice in names else names[min(i, len(names) - 1)]
                control.SetStringSelection(default)
                control.Bind(wx.EVT_CHOICE, self._on_input)
            grid.Add(control, 1, wx.EXPAND)
            controls.append(control)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        return controls

    def save_kinds(self) -> list[str]:
        """Return the kinds of output the dialog offers formats for, e.g. `table`.

        Returns:
            The kinds the tool makes (`Tool.output_kinds`; a workflow file's: its
            steps') that have save options, in that order.
        """
        from flim.core.saving import save_options_classes

        classes = save_options_classes()
        return [kind for kind in self.tool.output_kinds() if kind in classes]

    def _execution_controls(self) -> wx.BoxSizer:
        """Build `Save results` and, below it, the folder and the formats controls.

        `Use the default folder` and `Make Default Folder` are added only if there
        is a default folder.
        """
        outer = wx.BoxSizer(wx.VERTICAL)
        self.autosave = wx.CheckBox(self, label="Save results")
        self.autosave.SetValue(self.execution.autosave.enabled or self.autosave_locked)
        if self.autosave_locked:
            self.autosave.Disable()
            self.autosave.SetToolTip("Workflows always save their results")
        self.autosave.Bind(wx.EVT_CHECKBOX, lambda e: self.validate())
        outer.Add(self.autosave, 0)
        indent = 20  # the controls that depend on `Save results`
        folder = self.execution.autosave.results_dir
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.folder_label = wx.StaticText(self, label="Folder:")
        self.folder = wx.DirPickerCtrl(
            self, path="" if folder is None else str(folder), style=wx.DIRP_USE_TEXTCTRL
        )
        self.folder.Bind(wx.EVT_DIRPICKER_CHANGED, lambda e: self._on_folder())
        row.Add(self.folder_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.folder, 1, wx.EXPAND)
        outer.AddSpacer(4)
        outer.Add(row, 0, wx.EXPAND | wx.LEFT, indent)
        self.use_default = self.make_default = self.folder_note = None
        # the tool's own folder while the field shows the default folder (kept only
        # while the dialog is open: a tool that follows the default stores no folder)
        self._own_folder = ""
        if self.default_folder is not None:
            # follow the GUI's default folder, or keep a folder of the tool's own
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.use_default = wx.CheckBox(self, label="Use the default folder")
            self.use_default.SetToolTip(
                "The tool saves in the app's default results folder, also when it changes"
            )
            self.use_default.Bind(wx.EVT_CHECKBOX, lambda e: self._on_use_default())
            self.make_default = wx.Button(self, label="Make Default Folder")
            self.make_default.SetToolTip("Tools without a folder of their own save here")
            self.make_default.Bind(wx.EVT_BUTTON, lambda e: self._make_default())
            row.Add(self.use_default, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
            row.Add(self.make_default, 0)
            outer.AddSpacer(4)
            outer.Add(row, 0, wx.LEFT, indent + self.folder_label.GetBestSize().width + 6)
            # how the tool's own folder is kept (`stored_folder`)
            self.folder_note = wx.StaticText(self, label="")
            outer.AddSpacer(2)
            outer.Add(
                self.folder_note, 0, wx.LEFT, indent + self.folder_label.GetBestSize().width + 6
            )
            follows = self._is_default(folder)
            self.use_default.SetValue(follows)
            if not follows:
                self._own_folder = self._shown_folder(folder)
                self.folder.SetPath(self._own_folder)
            self._follow_default()
        # the formats in an "Output" box: a column per kind of output, its fields
        # (generated from the data type's save options) one under the other
        self.formats = FormatsBox(
            self, self.save_kinds(), self.execution.autosave.formats, on_change=self.validate
        )
        outer.AddSpacer(4)
        outer.Add(self.formats, 0, wx.EXPAND | wx.LEFT, indent)
        return outer

    def set_formats(self, formats: Sequence["SaveOptions"]) -> None:
        """Show formats (`AutosaveConfig.formats`) in the Output section."""
        self.formats.set(formats)

    def _is_default(self, folder: Union[str, os.PathLike, None]) -> bool:
        """Return whether a stored or shown folder means the default folder."""
        if folder is None or self.default_folder is None:
            return True
        return stored_folder(self._shown_folder(folder), self.default_folder) is None

    def _shown_folder(self, folder: Union[str, os.PathLike, None]) -> str:
        """Return the path the folder field shows for a stored folder.

        A folder relative to the default folder is shown as the folder inside it.
        """
        if not folder:
            return ""
        if self.default_folder is None:
            return str(folder)
        return str(resolved_folder(folder, self.default_folder))

    def _on_folder(self) -> None:
        """Update the controls after the folder field changed."""
        self._update_output_controls()
        self.validate()

    def _on_use_default(self) -> None:
        """Switch the folder field between the default and the tool's own folder."""
        if self.use_default.GetValue():
            self._own_folder = self.folder.GetPath()
        else:
            self.folder.SetPath(self._own_folder or str(self.default_folder))
        self._follow_default()

    def _follow_default(self) -> None:
        """Show the default folder while the tool follows it; update the controls."""
        if self.use_default is not None and self.use_default.GetValue():
            self.folder.SetPath(str(self.default_folder))
        self._update_output_controls()
        if hasattr(self, "formats"):  # not while the dialog is being built
            self.validate()

    def _update_output_controls(self) -> None:
        """Enable the output controls that apply to `Save results` and the folder."""
        saving = self.autosave.GetValue()
        follows = bool(self.use_default and self.use_default.GetValue())
        self.folder_label.Enable(saving)
        self.folder.Enable(saving and not follows)
        if self.use_default is not None:
            self.use_default.Enable(saving)
            path = self.folder.GetPath()
            usable = bool(path) and not folder_problem(path) and not self._is_default(path)
            self.make_default.Enable(saving and not follows and usable)
        if hasattr(self, "formats"):
            self.formats.Enable(saving)
        if self.folder_note is not None:
            self.folder_note.SetLabel(self._folder_note(follows))
            self.folder_note.Enable(saving)

    def _folder_note(self, follows: bool) -> str:
        """Return how the tool's folder is kept: inside the default folder or not."""
        path = self.folder.GetPath()
        if follows or not path:
            return ""
        kept = stored_folder(path, self.default_folder)
        if kept is None:
            return "The default folder."
        if not kept.is_absolute() and self.keep_relative:
            return f"Inside the default folder, kept as {kept}: it moves with the default folder."
        if not kept.is_absolute():
            return "Kept as this path (no results folder set: the default is the start folder)."
        return "Outside the default folder, kept as this path."

    def _make_default(self) -> None:
        """Make the folder the GUI's default results folder; the tool follows it."""
        folder = canonical_folder(self.folder.GetPath())
        if not folder or folder_problem(folder) or self.on_make_default is None:
            return
        self.on_make_default(Path(folder))
        self.default_folder = Path(folder)
        self._own_folder = folder
        self.use_default.SetValue(True)
        self._follow_default()

    def save_formats(self) -> tuple[list["SaveOptions"], dict[str, str]]:
        """Return the formats chosen in the dialog and the errors of the fields.

        Returns:
            The formats and an empty dict; or, if a format field is not valid or a
            kind of output has no format, an empty list and an error message per
            field name.
        """
        return self.formats.formats()

    def fit_contents(self) -> None:
        """Fit the dialog to fields that were shown or hidden.

        The dialog grows up to most of the screen's height; the Settings section
        scrolls beyond that.
        """
        self.fields.Layout()
        self._fit()

    def _fit(self) -> None:
        """Size the dialog to the fields, within the usable part of the screen."""
        # a scrolled panel does not ask for its content's size: show all fields, up to
        # most of the screen, and scroll beyond that
        index = wx.Display.GetFromWindow(self)
        usable = wx.Display(max(index, 0)).GetClientArea()  # without taskbar or menu bar
        best = self.fields.GetBestSize()
        width = max(best.width + 20, 460)
        self.scroll.SetMinSize((width, min(best.height + 4, int(usable.height * 0.6))))
        self.Layout()
        self.Fit()
        # the whole dialog, buttons included, stays on the usable part of the screen
        excess = self.GetSize().height - int(usable.height * 0.95)
        if excess > 0:
            scroll = self.scroll.GetMinSize().height
            self.scroll.SetMinSize((width, max(scroll - excess, 120)))
            self.Layout()
            self.Fit()
        self.SetMinSize((420, min(self.GetSize().height, 300)))

    # --- inputs ---

    def _on_input(self, event: wx.CommandEvent) -> None:
        """Handle a change of the selected input tables."""
        self._update_inputs()
        self.validate()

    def _update_inputs(self) -> None:
        """Pass the columns and tables of the selected inputs to the editors."""
        for panel in self.panels():
            panel.set_schema(combined_schema(self.input_schemas()))
        tables = []
        for value in self.selected_inputs():
            tables.extend(value.values() if isinstance(value, dict) else [value])
        frames = [t for t in tables if isinstance(t, pd.DataFrame)]
        self._tables = frames
        for panel in self.panels():
            panel.set_data(frames)
        self._fill_proposals(frames)

    def _fill_proposals(self, tables: list[pd.DataFrame]) -> None:
        """Fill the tool's proposals (`Tool.proposals`) into fields that are empty."""
        config, _ = self.current_config()
        if config is None or not tables:
            return
        try:
            proposals = self.tool.proposals(config, tables)
        except Exception:
            logger.exception(f"{self.tool.name}: the proposals failed")
            return
        for panel in self.panels():
            for name, value in proposals.items():
                editor = panel.editors.get(name)
                if editor is not None and not getattr(config, name, None):
                    editor.set(value)

    def selected_names(self) -> list[Union[str, list[str], None]]:
        """Return the names of the selected tables.

        Returns:
            Per input: the selected table's name (None if none is selected), or for
            an input with `many=True` the list of checked names.
        """
        names = []
        for spec, control in zip(self.tool.inputs, self.input_controls):
            if spec.many:
                names.append([control.GetString(i) for i in control.GetCheckedItems()])
            else:
                names.append(control.GetStringSelection() or None)
        return names

    def selected_inputs(self) -> list[Any]:
        """Return the selected tables.

        Returns:
            Per input: the selected table (None if none is selected), or for an
            input with `many=True` a dict of the checked tables by name.
        """
        values = []
        for names in self.selected_names():
            if isinstance(names, list):
                values.append({n: self.data_choices[n] for n in names})
            else:
                values.append(self.data_choices.get(names))
        return values

    def _schema(self, name: str) -> TableSchema:
        """Return the schema of an open table (cached); unknown if not a DataFrame."""
        if name not in self._schema_cache:
            data = self.data_choices[name]
            if isinstance(data, pd.DataFrame):
                self._schema_cache[name] = TableSchema.from_frame(data)
            else:
                self._schema_cache[name] = TableSchema.unknown()
        return self._schema_cache[name]

    def input_schemas(self) -> list[Union[TableSchema, dict[str, TableSchema], None]]:
        """Return the schemas of the selected tables.

        Returns:
            Per input: the schema of the selected table (None if none is selected),
            or for an input with `many=True` a dict of schemas by table name.
        """
        schemas = []
        for names in self.selected_names():
            if isinstance(names, list):
                schemas.append({n: self._schema(n) for n in names})
            else:
                schemas.append(self._schema(names) if names else None)
        return schemas

    # --- validation ---

    def current_config(self) -> tuple[Optional[TaskConfig], list[Issue]]:
        """Return the edited config and its issues.

        The values of the editors are validated by the config class, then validated
        by the tool against the input schemas (`Tool.validate`; for workflows with
        the dialog's `strict`).

        Returns:
            The config and the tool's issues; or None and the issues of the editors
            or the validation if the values are not valid.
        """
        try:
            values = self.fields.values(self.config)
            if self.output_fields is not None:
                edited = self.output_fields.values(self.config)
                values.update({n: edited[n] for n in self.output_fields.editors})
        except FieldErrors as err:
            return None, [Issue(name, message) for name, message in err.errors.items()]
        try:
            config = type(self.config).model_validate(values)
        except ValidationError as err:
            return None, validation_issues(err)
        if issubclass(self.tool, Workflow):
            issues = self.tool.validate(config, self.input_schemas(), strict=self.strict)
        else:
            issues = self.tool.validate(config, self.input_schemas())
        return config, list(issues)

    def execution_issues(self) -> list[Issue]:
        """Validate the output controls and the inputs; mark the format fields.

        The output controls are enabled as `Save results` and the folder allow.

        Returns:
            The issues: while results are saved, a kind of output without a valid
            format and a missing or unusable folder; and each required input
            without a selected table.
        """
        issues = []
        enabled = self.autosave.GetValue()
        self._update_output_controls()
        _, errors = self.save_formats()
        self.formats.show_errors(errors, enabled)
        if enabled and errors:
            issues.append(Issue(None, "Choose at least one format for each kind of result"))
        if enabled:
            if not self.folder.GetPath():
                issues.append(Issue(None, "Choose the folder to save the results in"))
            elif problem := folder_problem(self.folder.GetPath()):
                issues.append(Issue(None, problem))
        for spec, names in zip(self.tool.inputs, self.selected_names()):
            if not spec.optional and not names:
                issues.append(Issue(None, f"Select the {spec.name} input"))
        return issues

    def validate(self) -> list[Issue]:
        """Validate the edited config, the input data and the execution options.

        Fields that do not apply to the input tables are hidden. The issues of a
        field are marked at it, the other issues are shown below the settings. OK is
        enabled only if the config is valid and there are no errors.

        Returns:
            All issues; they are also stored in `issues`.
        """
        config, issues = self.current_config()
        if config is not None:
            hidden = self.tool.inapplicable_fields(config, getattr(self, "_tables", []))
            for panel in self.panels():
                panel.set_inapplicable(hidden)
        issues = issues + self.data_issues(config) + self.execution_issues()
        self.issues = issues
        by_field: dict[str, list[Issue]] = {}
        general = []
        panel_of = {n: p for p in self.panels() for n in p.editors}
        for issue in issues:
            name = top_field(issue.field)
            if name in panel_of:
                by_field.setdefault(name, []).append(issue)
            else:
                general.append(issue)
        for name, panel in panel_of.items():
            editor = panel.editors[name]
            field_issues = by_field.get(name, [])
            editor.show_issues(field_issues)  # e.g. markers in the rows of a table
            if field_issues:
                severity = min(
                    (i.severity for i in field_issues), key=SEVERITY_ORDER.index
                )
                message = "\n".join(
                    f"{i.field}: {i.message}" if i.field != name else i.message
                    for i in field_issues
                )
                panel.show_issue(name, severity, message)
            else:
                panel.show_issue(name, None)
        self.status.SetLabel(
            "\n".join(f"{i.step}: {i.message}" if i.step else i.message for i in general)
        )
        errors = [i for i in issues if i.severity == "error"]
        self.ok_button.Enable(config is not None and not errors)
        self.Layout()
        return issues

    # --- settings files ---

    def _on_load_settings(self, event: wx.CommandEvent) -> None:
        """Ask for a settings file and load the tool's settings from it."""
        with wx.FileDialog(
            self,
            f"Load Settings: {self.tool.name}",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.load_settings(dialog.GetPath())

    def _on_save_settings(self, event: wx.CommandEvent) -> None:
        """Ask for a settings file and save the tool's settings in it."""
        # no overwrite prompt: an existing file is updated, not replaced
        with wx.FileDialog(
            self,
            f"Save Settings: {self.tool.name}",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_SAVE,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.save_settings(with_extension(dialog.GetPath(), ".json"))

    def _tool_entry(
        self, path: Union[str, os.PathLike]
    ) -> Union["ToolSettings", None, Literal[False]]:
        """Return the tool's settings in a file.

        The file is a config alone or a settings file with a section of the tool.
        If some of the tool's settings in a settings file cannot be used, the user
        chooses what to do (`flim.gui.settingsvalidation.choose_settings`), possibly
        another file; `_loaded_from` is set to the file used.

        Returns:
            The ToolSettings, None if the file has none for the tool, or False if the
            user chose not to use a file.
        """
        from flim.core.settings import ToolSettingsMap, validate_settings_file
        from flim.gui.settingsvalidation import choose_settings

        self._loaded_from = path
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict) and "classname" in data:  # a config alone
            return read_tool_settings(path, self.tool)
        validation = validate_settings_file(path)
        if validation.tool_problems(self.tool):
            validation = choose_settings(validation, self, problems=lambda c: c.tool_problems(self.tool))
            if validation is None:
                return False
        self._loaded_from = validation.path
        return ToolSettingsMap.model_validate(validation.sections.get("tools", {})).entry(self.tool)

    def load_settings(self, path: Union[str, os.PathLike]) -> bool:
        """Show the tool's settings from a file in the dialog.

        The file is a config alone, a tool file or a settings file (see
        `_tool_entry`). The
        dialog shows the config, whether results are saved (unless locked), the
        folder and the formats. A message next to the buttons tells the result.

        Args:
            path: The file.

        Returns:
            True if the settings were loaded; False if the user chose not to use the
            file, the file has no settings for the tool, or it cannot be read (with
            a message).
        """
        name = os.path.basename(path)
        try:
            entry = self._tool_entry(path)
            if entry is False:  # the user chose not to use a file
                return False
            name = os.path.basename(self._loaded_from)
            if entry is None:
                self.settings_message.SetLabel(f"No {self.tool.name} settings in {name}")
                return False
            if entry.config is not None:
                config = self.tool.config_class.model_validate(entry.config)
            else:
                config = self.tool.config_class.from_legacy_params(entry.legacy or {})
        except Exception as err:
            logger.exception(f"Settings in {path} could not be read")
            self.settings_message.SetLabel(f"Could not load {name}: {err}")
            return False
        self.config = config
        self.set_values(config)
        if not self.autosave_locked:
            self.autosave.SetValue(entry.autosave.enabled)
        if self.use_default is not None:
            self.use_default.SetValue(self._is_default(entry.autosave.results_dir))
        if entry.autosave.results_dir and not (self.use_default and self.use_default.GetValue()):
            self._own_folder = self._shown_folder(entry.autosave.results_dir)
            self.folder.SetPath(self._own_folder)
        self._follow_default()
        if entry.autosave.formats:
            self.set_formats(entry.autosave.formats)
        self.validate()
        self.fit_contents()
        self.settings_message.SetLabel(f"Loaded from {name}")
        return True

    def save_settings(self, path: Union[str, os.PathLike]) -> bool:
        """Save the edited settings as a tool file, or in a settings file's section.

        A new file becomes a tool file (the shape of a workflow step, without the
        folder); in an existing settings file, the tool's section is replaced and the
        other settings are kept (see `flim.core.settings.write_tool_settings`). If the
        file is of an older
        version or has settings that cannot be used, the user is asked first:
        update the file (it is rewritten in the current version without those
        settings), save to another file, or cancel. A message next to the buttons
        tells the result.

        Args:
            path: The settings file.

        Returns:
            True if the settings were saved; False if they are not valid, the user
            cancelled or the file cannot be written (with a message).
        """
        from flim.core.settings import validate_settings_file, save_sections
        from flim.gui.settingsvalidation import REWRITE, confirm_rewrite, needs_rewrite

        self.commit_edits()
        config, issues = self.current_config()
        if config is None:
            self.settings_message.SetLabel("Not saved: the settings are not valid")
            return False
        entry = tool_settings(config, self._autosave(stored=True))
        while os.path.exists(path):
            validation = validate_settings_file(path)
            if not needs_rewrite(validation):
                break
            answer = confirm_rewrite(validation, self)
            if answer is None:
                self.settings_message.SetLabel("Not saved")
                return False
            if answer == REWRITE:
                sections = dict(validation.sections)
                tools = {
                    name: value
                    for name, value in sections.get("tools", {}).items()
                    if name not in getattr(self.tool, "former_names", ())
                }
                tools[self.tool.name] = entry.model_dump(mode="json")
                sections["tools"] = tools
                return self._saved(path, lambda: save_sections(sections, path))
            path = answer
        return self._saved(path, lambda: write_tool_settings(path, self.tool, entry))

    def _saved(self, path: Union[str, os.PathLike], write: Callable[[], Any]) -> bool:
        """Call `write` and show the result; False, with a message, if it fails."""
        name = os.path.basename(path)
        try:
            write()
        except Exception as err:
            logger.exception(f"Settings could not be saved to {path}")
            self.settings_message.SetLabel(f"Could not save to {name}: {err}")
            return False
        self.settings_message.SetLabel(f"Saved to {name}")
        return True

    # --- result ---

    def _on_ok(self, event: wx.CommandEvent) -> None:
        """Close the dialog if the config, with pending cell edits, has no errors."""
        # a table cell still being edited keeps its text in the cell editor (clicking
        # OK does not end the edit on all platforms): take it, then validate again
        if self.commit_edits():
            self.validate()
        if self.ok_button.IsEnabled():
            event.Skip()  # closes the dialog

    def commit_edits(self) -> bool:
        """End the edits of table cells in the dialog, keeping the edited values.

        Returns:
            True if a cell was being edited.
        """
        committed = False
        windows = [self]
        while windows:
            window = windows.pop()
            if isinstance(window, wx.grid.Grid) and window.IsCellEditControlEnabled():
                window.DisableCellEditControl()  # saves the value (cell changed)
                committed = True
            windows.extend(window.GetChildren())
        return committed

    def _autosave(self, stored: bool = False) -> "AutosaveConfig":
        """Return the dialog's autosave settings: whether, where, in which formats.

        Args:
            stored: True for the tool's settings: no folder if the tool follows the
                default folder or its folder is the default folder, a relative path
                if it is inside the default folder (`stored_folder`). False: the
                folder the run saves in.
        """
        from flim.core.saving import AutosaveConfig

        formats, _ = self.save_formats()
        follows = bool(self.use_default and self.use_default.GetValue())
        path = canonical_folder(self.folder.GetPath()) or None
        if stored and follows:
            folder = None
        elif stored and path and self.default_folder is not None:
            folder = stored_folder(path, self.default_folder)  # relative inside it
            if folder is not None and not self.keep_relative and not folder.is_absolute():
                folder = Path(path)
        else:
            folder = path
        return AutosaveConfig(
            enabled=self.autosave.GetValue(), results_dir=folder, formats=formats
        )

    def result(self) -> DialogResult:
        """Return the edited config, the selected inputs and the execution options.

        Returns:
            The result.

        Raises:
            ValueError: If the edited config is not valid.
        """
        config, issues = self.current_config()
        if config is None:
            raise ValueError(f"The configuration is not valid: {issues}")
        execution = self.execution.model_copy(update={"autosave": self._autosave()})
        return DialogResult(
            config=config,
            inputs=self.selected_inputs(),
            input_names=self.selected_names(),
            execution=ExecutionOptions.model_validate(execution.model_dump()),
            stored_autosave=self._autosave(stored=True),
        )


class PresetsDialog(ConfigDialog):
    """A configuration dialog with buttons for presets of its settings.

    The buttons are `Load Preset...`, `Save as Preset...` and `Remove Presets...`.
    A preset is a `name` and the `settings` it sets: the values of `preset_fields`.
    Saved presets are in the user settings file (`presets` > the tool's name); the
    presets of `built_in_presets` can't be replaced or removed.

    Attributes:
        preset_fields: The config fields that a preset sets.
    """

    preset_fields: tuple[str, ...] = ()

    def settings_buttons(
        self,
    ) -> list[tuple[str, str, Callable[[wx.CommandEvent], None]]]:
        """Return the buttons of the base class and the buttons for presets."""
        return super().settings_buttons() + [
            ("Load Preset...", "Settings of a built-in or saved preset", self._on_load_preset),
            ("Save as Preset...", "Save these settings as a preset, to load later", self._on_save_preset),
            ("Remove Presets...", "Remove saved presets", self._on_remove_presets),
        ]

    def built_in_presets(self) -> list[dict]:
        """Return the built-in presets, each a `name` and its `settings`; none here."""
        return []

    def saved_presets(self) -> list[dict]:
        """Return the presets saved in the user settings file.

        Presets that are not valid are left out, with a warning in the log.

        Returns:
            One dict per preset: its `name` and its `settings`; empty if no settings
            manager is bound (`bind_presets`).
        """
        if _settings_manager is None:
            return []
        presets, current = [], self._current().model_dump()
        for data in _settings_manager.settings.tool_presets(self.tool):
            try:
                settings = {k: v for k, v in data["settings"].items() if k in self.preset_fields}
                self.tool.config_class.model_validate({**current, **settings})
                presets.append({"name": str(data["name"]), "settings": settings})
            except (KeyError, TypeError, ValueError) as err:
                logger.warning(f"Saved {self.tool.name} preset not valid, not offered: {err}")
        return presets

    def save_presets(self, presets: list[dict]) -> None:
        """Replace the saved presets in the user settings file.

        Nothing is saved if no settings manager is bound (`bind_presets`).

        Args:
            presets: One dict per preset: its `name` and its `settings`.
        """
        if _settings_manager is not None:
            _settings_manager.set_presets(self.tool, presets)

    def _current(self) -> TaskConfig:
        """Return the edited config, or the dialog's config if it is not valid."""
        config, _ = self.current_config()
        return config if config is not None else self.config

    def apply_preset(self, preset: dict) -> None:
        """Show a preset's settings in the fields; the other fields are kept."""
        data = {**self._current().model_dump(), **preset["settings"]}
        self.set_values(self.tool.config_class.model_validate(data))
        self.validate()
        self.settings_message.SetLabel(f"Preset {preset['name']}")

    def _on_load_preset(self, event: wx.CommandEvent) -> None:
        """Ask for a built-in or saved preset and show its settings."""
        built_in, saved = self.built_in_presets(), self.saved_presets()
        if not built_in and not saved:
            self.settings_message.SetLabel("No saved presets")
            return
        labels = [p["name"] for p in built_in] + [f"{p['name']} (saved)" for p in saved]
        with wx.SingleChoiceDialog(self, "Preset:", "Load Preset", labels) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            preset = (built_in + saved)[dialog.GetSelection()]
        self.apply_preset(preset)

    def _on_save_preset(self, event: wx.CommandEvent) -> None:
        """Ask for a name and save the values of `preset_fields` as a preset.

        A saved preset of the same name is replaced; a built-in preset's name is
        refused with a message.
        """
        with wx.TextEntryDialog(self, "Name of the preset:", "Save as Preset") as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            name = dialog.GetValue().strip()
        if not name:
            return
        if name in [p["name"] for p in self.built_in_presets()]:
            wx.MessageBox(f"'{name}' is a built-in preset; choose another name.", "Save as Preset")
            return
        data = self._current().model_dump(mode="json")
        settings = {field: data[field] for field in self.preset_fields}
        presets = [p for p in self.saved_presets() if p["name"] != name]  # same name: replaced
        self.save_presets(presets + [{"name": name, "settings": settings}])
        self.settings_message.SetLabel(f"Saved as preset {name}")

    def _on_remove_presets(self, event: wx.CommandEvent) -> None:
        """Ask for saved presets and remove them."""
        saved = self.saved_presets()
        if not saved:
            self.settings_message.SetLabel("No saved presets")
            return
        names = [p["name"] for p in saved]
        with wx.MultiChoiceDialog(self, "Saved presets to remove:", "Remove Presets", names) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            remove = {names[i] for i in dialog.GetSelections()}
        self.save_presets([p for p in saved if p["name"] not in remove])
        self.settings_message.SetLabel(f"{len(remove)} presets removed")
