"""Configuration dialogs of tools, generated from their config classes.

``open_config_dialog(parent, Tool, config, data_choices)`` shows the dialog registered
for the tool's config class (``register_dialog``) or the generic :class:`ConfigDialog`.
The dialog lets the user pick the input tables, edit the config and choose whether
results are saved; it checks the config against the inputs while it is edited and
marks problems at their fields (errors keep OK disabled).
"""

import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import wx
import wx.grid
from pydantic import ValidationError
from wx.lib.scrolledpanel import ScrolledPanel

from flim.core.config import Issue, TaskConfig
from flim.core.execution import ExecutionOptions
from flim.core.schema import ColumnInfo, TableSchema
from flim.gui.editors import FieldErrors, FieldsPanel

SEVERITY_ORDER = ("error", "guessed", "warning")  # first: most severe


@dataclass
class DialogResult:
    config: TaskConfig
    inputs: list  # per InputSpec: a DataFrame, or a dict of them (many=True)
    input_names: list  # per InputSpec: a table name, or a list of names
    execution: ExecutionOptions


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
        # the level names of the first input's headers that has them
        header_levels=next((s.header_levels for s in flat if s.header_levels), []),
    )


class ConfigDialog(wx.Dialog):
    """Generic configuration dialog of a tool, built from its config class.

    Args:
        tool: the Tool class.
        config: the config to edit (default: the config class's defaults).
        data_choices: open tables by name; the first is the current one.
        selected: preselected table names per input (default: in order).
        execution: execution options; the dialog edits autosave and the folder.
        autosave_locked: results are always saved (workflows).
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
        self.issues: list[Issue] = []
        self._schema_cache: dict[str, TableSchema] = {}

        sizer = wx.BoxSizer(wx.VERTICAL)
        if tool.description:
            text = wx.StaticText(self, label=tool.description)
            text.Wrap(520)
            sizer.Add(text, 0, wx.ALL, 8)
        self.input_controls = self._input_controls(sizer, selected)

        self.scroll = ScrolledPanel(self)
        self.fields = self.create_fields(self.scroll)
        self.fields.on_change = self.validate
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        scroll_sizer.Add(self.fields, 1, wx.EXPAND)
        self.scroll.SetSizer(scroll_sizer)
        self.scroll.SetupScrolling(scroll_x=False)
        sizer.Add(self.scroll, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        self.status = wx.StaticText(self, label="")
        self.status.SetForegroundColour(wx.Colour(180, 0, 0))
        sizer.Add(self.status, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self._execution_controls(), 0, wx.EXPAND | wx.ALL, 8)
        buttons = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        self.ok_button = self.FindWindow(wx.ID_OK)  # FindWindowById: any window's
        self.ok_button.Bind(wx.EVT_BUTTON, self._on_ok)
        sizer.Add(buttons, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)

        self.fields.set_values(self.config)
        self._update_inputs()
        self.fields.set_values(self.config)  # columns are listed now
        self.validate()
        self._fit()

    # --- building ---

    def create_fields(self, parent) -> FieldsPanel:
        """The field editors; custom dialogs may add to or replace them."""
        return FieldsPanel(parent, type(self.config))

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

    def _execution_controls(self):
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.autosave = wx.CheckBox(self, label="Save results in")
        self.autosave.SetValue(self.execution.autosave or self.autosave_locked)
        if self.autosave_locked:
            self.autosave.Disable()
            self.autosave.SetToolTip("Workflows always save their results")
        self.autosave.Bind(wx.EVT_CHECKBOX, lambda e: self.validate())
        folder = self.execution.results_dir
        self.folder = wx.DirPickerCtrl(
            self, path="" if folder is None else str(folder), style=wx.DIRP_USE_TEXTCTRL
        )
        self.folder.Bind(wx.EVT_DIRPICKER_CHANGED, lambda e: self.validate())
        row.Add(self.autosave, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.folder, 1, wx.EXPAND)
        return row

    def fit_contents(self) -> None:
        """Fits the dialog to fields that appeared or disappeared (up to most of the
        screen; it scrolls beyond)."""
        self.fields.Layout()
        self._fit()

    def _fit(self):
        # a scrolled panel does not ask for its content's size: show all fields, up to
        # most of the screen, and scroll beyond that
        display = wx.GetDisplaySize()
        best = self.fields.GetBestSize()
        self.scroll.SetMinSize(
            (max(best.width + 20, 460), min(best.height + 4, int(display.height * 0.6)))
        )
        self.Layout()
        self.Fit()
        self.SetMinSize((420, min(self.GetSize().height, 300)))

    # --- inputs ---

    def _on_input(self, event):
        self._update_inputs()
        self.validate()

    def _update_inputs(self):
        """Tells the editors the columns and tables of the selected inputs."""
        self.fields.set_schema(combined_schema(self.input_schemas()))
        tables = []
        for value in self.selected_inputs():
            tables.extend(value.values() if isinstance(value, dict) else [value])
        self.fields.set_data([t for t in tables if isinstance(t, pd.DataFrame)])

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
        """Per input: the TableSchema of the selected table(s); None if none."""
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
        except FieldErrors as err:
            return None, [Issue(name, message) for name, message in err.errors.items()]
        try:
            config = type(self.config).model_validate(values)
        except ValidationError as err:
            return None, validation_issues(err)
        return config, list(self.tool.validate(config, self.input_schemas()))

    def execution_issues(self) -> list[Issue]:
        issues = []
        if self.autosave.GetValue() and not self.folder.GetPath():
            issues.append(Issue(None, "Choose the folder to save the results in"))
        for spec, names in zip(self.tool.inputs, self.selected_names()):
            if not spec.optional and not names:
                issues.append(Issue(None, f"Select the {spec.name} input"))
        return issues

    def validate(self) -> list[Issue]:
        """Checks the edited config, marks the fields with issues and enables OK."""
        config, issues = self.current_config()
        issues = issues + self.execution_issues()
        self.issues = issues
        by_field: dict[str, list[Issue]] = {}
        general = []
        for issue in issues:
            name = top_field(issue.field)
            if name in self.fields.editors:
                by_field.setdefault(name, []).append(issue)
            else:
                general.append(issue)
        for name, editor in self.fields.editors.items():
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
                self.fields.show_issue(name, severity, message)
            else:
                self.fields.show_issue(name, None)
        self.status.SetLabel(
            "\n".join(f"{i.step}: {i.message}" if i.step else i.message for i in general)
        )
        errors = [i for i in issues if i.severity == "error"]
        self.ok_button.Enable(config is not None and not errors)
        self.Layout()
        return issues

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

    def result(self) -> DialogResult:
        config, issues = self.current_config()
        if config is None:
            raise ValueError(f"The configuration is not valid: {issues}")
        autosave = self.autosave.GetValue()
        folder = self.folder.GetPath() or None
        execution = self.execution.model_copy(
            update={"autosave": autosave, "results_dir": folder}
        )
        return DialogResult(
            config=config,
            inputs=self.selected_inputs(),
            input_names=self.selected_names(),
            execution=ExecutionOptions.model_validate(execution.model_dump()),
        )
