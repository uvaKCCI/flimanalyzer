"""Configuration dialogs of tools, generated from their config classes.

``open_config_dialog(parent, Tool, config, data_choices)`` shows the dialog registered
for the tool's config class (``register_dialog``) or the generic :class:`ConfigDialog`.
The dialog lets the user pick the input tables, edit the config and choose whether
results are saved; it checks the config against the inputs while it is edited and
marks problems at their fields (errors keep OK disabled).
"""

import logging
import json
import os
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

import pandas as pd
import wx
import wx.grid
from pydantic import ValidationError
from wx.lib.scrolledpanel import ScrolledPanel

from flim.core.config import Issue, TaskConfig
from flim.core.workflow import Workflow
from flim.core.execution import ExecutionOptions
from flim.core.paths import canonical_folder, folder_problem
from flim.core.schema import ColumnInfo, TableSchema
from flim.core.settings import read_tool_settings, tool_settings, write_tool_settings
from flim.gui.editors import FieldErrors, FieldsPanel
from flim.gui.formats import FormatsBox

logger = logging.getLogger(__name__)

SEVERITY_ORDER = ("error", "guessed", "warning")  # first: most severe


@dataclass
class DialogResult:
    config: TaskConfig
    inputs: list  # per InputSpec: a DataFrame, or a dict of them (many=True)
    input_names: list  # per InputSpec: a table name, or a list of names
    execution: ExecutionOptions  # for the run: the results folder is resolved
    # for the tool's settings: no results folder if the tool follows the default
    stored_autosave: Optional[Any] = None


_DIALOGS: dict = {}


def register_dialog(*config_classes):
    """Class decorator: the dialog for these config classes (and their subclasses)."""

    def register(dialog):
        for config_class in config_classes:
            _DIALOGS[config_class] = dialog
        return dialog

    return register


def dialog_class(config_class: type) -> type["ConfigDialog"]:
    for base in config_class.__mro__:
        if base in _DIALOGS:
            return _DIALOGS[base]
    return ConfigDialog


def open_config_dialog(parent, tool, config=None, **kwargs) -> Optional[DialogResult]:
    """Shows the configuration dialog of ``tool`` (a Tool class); None if cancelled."""
    dialog = dialog_class(tool.config_class)(parent, tool, config, **kwargs)
    try:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        return dialog.result()
    finally:
        dialog.Destroy()


def top_field(path: Optional[str]) -> Optional[str]:
    """``"range_filters[0].column"`` → ``"range_filters"``."""
    return None if not path else re.split(r"[.\[]", path, maxsplit=1)[0]


def validation_issues(error: ValidationError) -> list[Issue]:
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


def combined_schema(schemas) -> Optional[TableSchema]:
    """The columns of all selected inputs (None if there are none)."""
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

    Args:
        tool: the Tool class.
        config: the config to edit (default: the config class's defaults).
        data_choices: open tables by name; the first is the current one.
        selected: preselected table names per input (default: the i-th table for
            the i-th input, all tables for an input with many=True).
        execution: execution options; the dialog edits autosave and the folder.
        autosave_locked: "Save results in" is checked and cannot be unchecked.
    """

    def __init__(
        self,
        parent,
        tool,
        config=None,
        data_choices: Optional[dict] = None,
        selected: Optional[list] = None,
        execution: Optional[ExecutionOptions] = None,
        autosave_locked: bool = False,
        strict: Optional[bool] = None,
        default_folder=None,
        on_make_default: Optional[Callable] = None,
    ):
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
        # the app's default results folder (None: no "Use the default folder"), and
        # what makes a folder the default (SettingsManager)
        self.default_folder = Path(default_folder) if default_folder else None
        self.on_make_default = on_make_default
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
        for label, tip, handler in (
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
        ):
            button = wx.Button(self, label=label)
            button.SetToolTip(tip)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.RIGHT, 4)
        self.settings_message = wx.StaticText(self, label="")
        buttons.Add(self.settings_message, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 4)
        settings_box.Add(buttons, 0, wx.EXPAND | wx.TOP, 4)
        sizer.Add(settings_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

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

    def output_field_names(self) -> list[str]:
        """Return the config's fields shown in the Output section (e.g. the result
        prefix), from their `section`."""
        from flim.core.fields import describe

        return [s.name for s in describe(type(self.config)) if s.section == "output"]

    def create_fields(self, parent) -> FieldsPanel:
        """The editors of the Settings section; custom dialogs may add to or replace
        them. The Output section's fields (`output_field_names`) are not among them."""
        return FieldsPanel(parent, type(self.config), exclude=self.output_field_names())

    def panels(self) -> list:
        """Return the FieldsPanels of the config: Settings, and Output if it has
        fields."""
        return [p for p in (self.fields, getattr(self, "output_fields", None)) if p]

    def set_values(self, config) -> None:
        """Show a config in the fields of both sections."""
        for panel in self.panels():
            panel.set_values(config)

    def _input_controls(self, sizer, selected) -> list:
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
        """Return the kinds of output (e.g. `table`, `plot`) the dialog offers formats
        for: those the tool declares, or all kinds with save options if it declares
        none (e.g. workflows, whose outputs are known only when they run)."""
        from flim.core.saving import save_options_classes

        classes = save_options_classes()
        kinds = []
        for output in self.tool.outputs:
            kind = output.type.kind
            if kind in classes and kind not in kinds:
                kinds.append(kind)
        return kinds or sorted(classes, key=lambda k: (k != "table", k))

    def _execution_controls(self):
        outer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.autosave = wx.CheckBox(self, label="Save results in")
        self.autosave.SetValue(self.execution.autosave.enabled or self.autosave_locked)
        if self.autosave_locked:
            self.autosave.Disable()
            self.autosave.SetToolTip("Workflows always save their results")
        self.autosave.Bind(wx.EVT_CHECKBOX, lambda e: self.validate())
        folder = self.execution.autosave.results_dir
        self.folder = wx.DirPickerCtrl(
            self, path="" if folder is None else str(folder), style=wx.DIRP_USE_TEXTCTRL
        )
        self.folder.Bind(wx.EVT_DIRPICKER_CHANGED, lambda e: self.validate())
        row.Add(self.autosave, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.folder, 1, wx.EXPAND)
        outer.Add(row, 0, wx.EXPAND)
        self.use_default = self.make_default = None
        if self.default_folder is not None:
            # follow the app's default folder, or keep a folder of the tool's own
            row = wx.BoxSizer(wx.HORIZONTAL)
            self.use_default = wx.CheckBox(self, label="Use the default folder")
            self.use_default.SetToolTip(
                "The tool saves in the app's default results folder, also when it changes"
            )
            self.use_default.Bind(wx.EVT_CHECKBOX, lambda e: self._follow_default())
            self.make_default = wx.Button(self, label="Make Default Folder")
            self.make_default.SetToolTip("Tools without a folder of their own save here")
            self.make_default.Bind(wx.EVT_BUTTON, lambda e: self._make_default())
            row.Add(self.use_default, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
            row.Add(self.make_default, 0)
            outer.Add(row, 0, wx.LEFT | wx.TOP, 4)
            self.use_default.SetValue(self._is_default(folder))
            self._follow_default()
        # the formats in an "Output" box: a column per kind of output, its fields
        # (generated from the data type's save options) one under the other
        self.formats = FormatsBox(
            self, self.save_kinds(), self.execution.autosave.formats, on_change=self.validate
        )
        outer.Add(self.formats, 0, wx.EXPAND | wx.TOP, 4)
        return outer

    def set_formats(self, formats) -> None:
        """Show formats (AutosaveConfig.formats) in the Output box."""
        self.formats.set(formats)

    def _is_default(self, folder) -> bool:
        """Whether a tool's stored folder means the default: none, or the default
        folder itself (settings from before a tool could follow the default)."""
        if folder is None or self.default_folder is None:
            return True
        return canonical_folder(str(folder)) == canonical_folder(str(self.default_folder))

    def _follow_default(self) -> None:
        """Show the default folder, greyed, while the tool follows it."""
        follows = bool(self.use_default and self.use_default.GetValue())
        if follows:
            self.folder.SetPath(str(self.default_folder))
        self.folder.Enable(not follows)
        if self.make_default is not None:
            self.make_default.Enable(not follows)
        if hasattr(self, "formats"):  # not while the dialog is being built
            self.validate()

    def _make_default(self) -> None:
        """Make the folder the app's default results folder; the tool then follows it."""
        folder = canonical_folder(self.folder.GetPath())
        if not folder or folder_problem(folder) or self.on_make_default is None:
            return
        self.on_make_default(Path(folder))
        self.default_folder = Path(folder)
        self.use_default.SetValue(True)
        self._follow_default()

    def save_formats(self) -> tuple[list, dict]:
        """Return the formats chosen in the dialog, and an error per format field."""
        return self.formats.formats()

    def fit_contents(self) -> None:
        """Fits the dialog to fields that appeared or disappeared (up to most of the
        screen; it scrolls beyond)."""
        self.fields.Layout()
        self._fit()

    def _fit(self):
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

    def _on_input(self, event):
        self._update_inputs()
        self.validate()

    def _update_inputs(self):
        """Tells the editors the columns and tables of the selected inputs."""
        for panel in self.panels():
            panel.set_schema(combined_schema(self.input_schemas()))
        tables = []
        for value in self.selected_inputs():
            tables.extend(value.values() if isinstance(value, dict) else [value])
        for panel in self.panels():
            panel.set_data([t for t in tables if isinstance(t, pd.DataFrame)])

    def selected_names(self) -> list:
        names = []
        for spec, control in zip(self.tool.inputs, self.input_controls):
            if spec.many:
                names.append([control.GetString(i) for i in control.GetCheckedItems()])
            else:
                names.append(control.GetStringSelection() or None)
        return names

    def selected_inputs(self) -> list:
        values = []
        for names in self.selected_names():
            if isinstance(names, list):
                values.append({n: self.data_choices[n] for n in names})
            else:
                values.append(self.data_choices.get(names))
        return values

    def _schema(self, name) -> TableSchema:
        if name not in self._schema_cache:
            data = self.data_choices[name]
            if isinstance(data, pd.DataFrame):
                self._schema_cache[name] = TableSchema.from_frame(data)
            else:
                self._schema_cache[name] = TableSchema.unknown()
        return self._schema_cache[name]

    def input_schemas(self) -> list:
        """Per input: the TableSchema of the selected table (a dict of them by name
        for an input with many=True); None if no table is selected."""
        schemas = []
        for names in self.selected_names():
            if isinstance(names, list):
                schemas.append({n: self._schema(n) for n in names})
            else:
                schemas.append(self._schema(names) if names else None)
        return schemas

    # --- checking ---

    def current_config(self) -> tuple[Optional[TaskConfig], list[Issue]]:
        """The edited config (None if invalid) and its issues."""
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
        issues = []
        enabled = self.autosave.GetValue()
        self.formats.Enable(enabled)
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
        """Checks the edited config and the execution options, marks the fields with
        issues, shows the other issues below the fields, enables OK only if there
        are no errors, and returns all issues."""
        config, issues = self.current_config()
        issues = issues + self.execution_issues()
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

    def _on_load_settings(self, event):
        with wx.FileDialog(
            self,
            f"Load Settings: {self.tool.name}",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.load_settings(dialog.GetPath())

    def _on_save_settings(self, event):
        # no overwrite prompt: an existing file is updated, not replaced
        with wx.FileDialog(
            self,
            f"Save Settings: {self.tool.name}",
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_SAVE,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.save_settings(dialog.GetPath())

    def _tool_entry(self, path):
        """Return the tool's settings in a file: a config alone, or the tool's section
        of a settings file. If some of the tool's settings in a settings file cannot be
        used, the user chooses what to do (flim.gui.settingscheck.choose_settings),
        possibly another file; `_loaded_from` is set to the file used.

        Returns:
            The ToolSettings, None if the file has none for the tool, or False if the
            user chose not to use a file.
        """
        from flim.core.settings import ToolSettingsMap, check_settings_file
        from flim.gui.settingscheck import choose_settings

        self._loaded_from = path
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict) and "classname" in data:  # a config alone
            return read_tool_settings(path, self.tool)
        check = check_settings_file(path)
        if check.tool_problems(self.tool):
            check = choose_settings(check, self, problems=lambda c: c.tool_problems(self.tool))
            if check is None:
                return False
        self._loaded_from = check.path
        return ToolSettingsMap.model_validate(check.sections.get("tools", {})).entry(self.tool)

    def load_settings(self, path) -> bool:
        """Uses the tool's settings in a settings file (see
        flim.core.settings.read_tool_settings): config, autosave (unless locked)
        and results folder. False, with a message, if the file has no settings for
        the tool or cannot be read."""
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
            self.folder.SetPath(str(entry.autosave.results_dir))
        self._follow_default()
        if entry.autosave.formats:
            self.set_formats(entry.autosave.formats)
        self.validate()
        self.fit_contents()
        self.settings_message.SetLabel(f"Loaded from {name}")
        return True

    def save_settings(self, path) -> bool:
        """Puts the edited settings into the tool's section of a settings file (see
        flim.core.settings.write_tool_settings). If the file is of an older version or
        has settings that cannot be used, the user is asked first: update the file (it
        is rewritten in the current version without those settings), save to another
        file, or cancel. False, with a message, if the settings are not valid, the
        user cancels or the file cannot be written."""
        from flim.core.settings import check_settings_file, save_sections
        from flim.gui.settingscheck import REWRITE, confirm_rewrite, needs_rewrite

        self.commit_edits()
        config, issues = self.current_config()
        if config is None:
            self.settings_message.SetLabel("Not saved: the settings are not valid")
            return False
        entry = tool_settings(config, self._autosave(stored=True))
        while os.path.exists(path):
            check = check_settings_file(path)
            if not needs_rewrite(check):
                break
            answer = confirm_rewrite(check, self)
            if answer is None:
                self.settings_message.SetLabel("Not saved")
                return False
            if answer == REWRITE:
                sections = dict(check.sections)
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

    def _saved(self, path, write) -> bool:
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

    def _on_ok(self, event):
        # a table cell still being edited keeps its text in the cell editor (clicking
        # OK does not end the edit on all platforms): take it, then check again
        if self.commit_edits():
            self.validate()
        if self.ok_button.IsEnabled():
            event.Skip()  # closes the dialog

    def commit_edits(self) -> bool:
        """Ends the edits of table cells, keeping the edited values; True if any."""
        committed = False
        windows = [self]
        while windows:
            window = windows.pop()
            if isinstance(window, wx.grid.Grid) and window.IsCellEditControlEnabled():
                window.DisableCellEditControl()  # saves the value (cell changed)
                committed = True
            windows.extend(window.GetChildren())
        return committed

    def _autosave(self, stored: bool = False):
        """Return the dialog's autosave settings: whether, where, in which formats.

        Args:
            stored: For the tool's settings: no folder if the tool follows the
                default folder. Otherwise the folder the run saves in.
        """
        from flim.core.saving import AutosaveConfig

        formats, _ = self.save_formats()
        follows = bool(self.use_default and self.use_default.GetValue())
        folder = None if stored and follows else canonical_folder(self.folder.GetPath()) or None
        return AutosaveConfig(
            enabled=self.autosave.GetValue(), results_dir=folder, formats=formats
        )

    def result(self) -> DialogResult:
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
