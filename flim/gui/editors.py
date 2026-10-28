"""Editors for config fields: one wx control per field kind (flim.core.fields).

An editor shows a value (``set``), reads it back (``get``, raising ValueError for text
that is not a valid value) and calls ``on_change`` when the user edits it. Column
editors offer the columns of the input tables (``set_schema``).
"""

import json
from pathlib import Path
from typing import Any, Callable, Optional

import wx
import wx.grid

from flim.core.fields import FieldSpec, describe, visible
from flim.core.schema import TableSchema

NONE_LABEL = "(none)"


class Editor:
    """Base of the field editors."""

    expands = False  # takes the full width of the dialog (lists, tables)
    grows = True  # if it expands: also gets taller when the dialog does

    def __init__(self, parent: wx.Window, spec: FieldSpec):
        self.spec = spec
        self.on_change: Optional[Callable[["Editor"], None]] = None
        self.control = self.create(parent)
        if spec.description:
            self.control.SetToolTip(spec.description)

    def create(self, parent) -> wx.Window:
        raise NotImplementedError

    def get(self) -> Any:
        raise NotImplementedError

    def set(self, value) -> None:
        raise NotImplementedError

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """The input's columns (None: unknown)."""

    def set_data(self, tables: list) -> None:
        """The selected input tables (DataFrames), e.g. for ranges of values."""

    def refresh(self, panel: "FieldsPanel") -> None:
        """Called when any field of the panel changed (fields that depend on others)."""

    def changed(self, event=None):
        if self.on_change is not None:
            self.on_change(self)
        if event is not None:
            event.Skip()


class BoolEditor(Editor):
    def create(self, parent):
        control = wx.CheckBox(parent, label="")
        control.Bind(wx.EVT_CHECKBOX, self.changed)
        return control

    def get(self):
        return self.control.GetValue()

    def set(self, value):
        self.control.SetValue(bool(value))


class ChoiceEditor(Editor):
    """A Literal (or an optional bool: automatic, yes, no)."""

    def create(self, parent):
        if self.spec.kind == "bool":  # optional bool
            self.values = [None, True, False]
            labels = ["Automatic", "Yes", "No"]
        else:
            self.values = ([None] if self.spec.optional else []) + list(
                self.spec.choices
            )
            labels = [NONE_LABEL if v is None else str(v) for v in self.values]
        control = wx.Choice(parent, choices=labels)
        control.Bind(wx.EVT_CHOICE, self.changed)
        return control

    def get(self):
        index = self.control.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Select a value")
        return self.values[index]

    def set(self, value):
        if value in self.values:
            self.control.SetSelection(self.values.index(value))


class TextEditor(Editor):
    """Text, and numbers typed as text (int, float, number, mixed, numbers)."""

    def create(self, parent):
        if self.spec.kind == "mixed":
            control = wx.ComboBox(parent, choices=[str(c) for c in self.spec.choices])
        else:
            control = wx.TextCtrl(parent)
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def get(self):
        text = self.control.GetValue().strip()
        kind = self.spec.kind
        if text == "" and self.spec.optional:
            return None
        if kind == "text":
            return text
        if kind == "numbers":
            items = [t.strip() for t in text.replace(";", ",").split(",") if t.strip()]
            return [self._number(t, self.spec.item_type) for t in items]
        if kind == "mixed" and text in [str(c) for c in self.spec.choices]:
            return next(c for c in self.spec.choices if str(c) == text)
        return self._number(text, {"int": int, "float": float}.get(kind))

    @staticmethod
    def _number(text, kind=None):
        try:
            if kind is int:
                return int(text)
            if kind is float:
                return float(text)
            value = float(text)  # int or float
            return (
                int(value)
                if value.is_integer() and "." not in text and "e" not in text.lower()
                else value
            )
        except ValueError:
            raise ValueError(f"'{text}' is not a number") from None

    def set(self, value):
        if value is None:
            text = ""
        elif isinstance(value, (list, tuple)):
            text = ", ".join(str(v) for v in value)
        else:
            text = str(value)
        self.control.ChangeValue(text)


class IntEditor(Editor):
    """An int with bounds: a spin control."""

    def create(self, parent):
        bounds = self.spec.bounds
        low = bounds.get("ge", bounds["gt"] + 1 if "gt" in bounds else -(10**9))
        high = bounds.get("le", bounds["lt"] - 1 if "lt" in bounds else 10**9)
        control = wx.SpinCtrl(parent, min=int(low), max=int(high))
        control.Bind(wx.EVT_SPINCTRL, self.changed)
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def get(self):
        return self.control.GetValue()

    def set(self, value):
        self.control.SetValue(int(value))


def set_combo_items(combo: wx.ComboBox, items: list) -> None:
    """Replaces the items of a combo box (``Set`` appends to them on macOS, and
    ``Clear`` only clears the text)."""
    for index in reversed(range(combo.GetCount())):
        combo.Delete(index)
    if items:
        combo.Append(items)


def fit_rows(
    control: wx.Window, rows: int, fewest: int = 3, most: int = 10, fixed=False
) -> None:
    """Makes a list control tall enough for ``rows`` items (within fewest..most);
    ``fixed``: exactly that tall (lists that should not grow with the dialog)."""
    height = control.GetCharHeight() + 6  # about one row of a list
    size = (-1, max(fewest, min(rows, most)) * height + 6)
    control.SetMinSize(size)
    if fixed:
        control.SetMaxSize(size)
        control.SetInitialSize(size)
    control.GetParent().Layout()


class ColumnEditor(Editor):
    """One column of the input; any name can be typed if the columns are unknown."""

    def create(self, parent):
        control = wx.ComboBox(parent, choices=[])
        control.Bind(wx.EVT_COMBOBOX, self.changed)
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def set_schema(self, schema):
        value = self.control.GetValue()
        names = [] if schema is None else schema.by_role(self.spec.role)
        set_combo_items(self.control, ([""] if self.spec.optional else []) + names)
        self.control.ChangeValue(value)

    def get(self):
        value = self.control.GetValue().strip()
        if value == "":
            if self.spec.optional:
                return None
            raise ValueError("Select a column")
        return value

    def set(self, value):
        self.control.ChangeValue("" if value is None else str(value))


class ValueEditor(Editor):
    """A value of the category column named by another field (``column_field``)."""

    def create(self, parent):
        control = wx.ComboBox(parent, choices=[])
        control.Bind(wx.EVT_COMBOBOX, self.changed)
        control.Bind(wx.EVT_TEXT, self.changed)
        self.schema = None
        return control

    def set_schema(self, schema):
        self.schema = schema

    def refresh(self, panel):
        self.update_choices(panel.value_of(self.spec.column_field))

    def update_choices(self, column: Optional[str]) -> None:
        """Offers the values of ``column`` (if the input's schema knows them)."""
        info = None if self.schema is None or not column else self.schema.column(column)
        levels = (
            [] if info is None or info.levels is None else [str(v) for v in info.levels]
        )
        value = self.control.GetValue()
        if levels != self.control.GetItems():
            set_combo_items(self.control, levels)
            self.control.ChangeValue(value)

    def get(self):
        value = self.control.GetValue().strip()
        if value == "" and self.spec.optional:
            return None
        return value

    def set(self, value):
        self.control.ChangeValue("" if value is None else str(value))


class _CheckList(Editor):
    """Checked items of a list, in list order."""

    expands = True

    def create(self, parent):
        self.panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.extra_controls(self.panel, sizer)
        self.list = wx.CheckListBox(self.panel, choices=[])
        self.list.Bind(wx.EVT_CHECKLISTBOX, self.changed)
        sizer.Add(self.list, 1, wx.EXPAND)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, checked in (("Select All", True), ("Deselect All", False)):
            button = wx.Button(self.panel, label=label, style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, lambda e, c=checked: self.check_all(c))
            buttons.Add(button, 0, wx.TOP | wx.RIGHT, 3)
        sizer.Add(buttons)
        self.panel.SetSizer(sizer)
        self.items: list = []
        return self.panel

    def extra_controls(self, panel, sizer):
        pass

    def set_items(self, items, checked):
        self.items = list(items) + [c for c in checked if c not in items]
        self.list.Set([str(i).replace("\n", " ") for i in self.items])
        self.list.SetCheckedItems([self.items.index(c) for c in checked])
        fit_rows(self.list, len(self.items), most=10)

    def checked(self) -> list:
        return [self.items[i] for i in self.list.GetCheckedItems()]

    def check_all(self, checked: bool):
        self.list.SetCheckedItems(list(range(len(self.items))) if checked else [])
        self.changed()


class MultiChoiceEditor(_CheckList):
    def create(self, parent):
        panel = super().create(parent)
        self.set_items(self.spec.choices, [])
        return panel

    def get(self):
        return self.checked()

    def set(self, value):
        self.set_items(self.spec.choices, [v for v in self.spec.choices if v in value])


class FeaturesEditor(_CheckList):
    """Feature columns, or "all" (if allowed)."""

    def extra_controls(self, panel, sizer):
        self.all = None
        if self.spec.allow_all:
            self.all = wx.CheckBox(panel, label="All features")
            self.all.Bind(wx.EVT_CHECKBOX, self._on_all)
            sizer.Add(self.all, 0, wx.BOTTOM, 3)

    def _on_all(self, event):
        self.list.Enable(not self.all.GetValue())
        self.changed(event)

    def set_schema(self, schema):
        checked = self.checked()
        self.set_items(
            [] if schema is None else schema.by_role(self.spec.role), checked
        )

    def get(self):
        if self.all is not None and self.all.GetValue():
            return "all"
        return self.checked()

    def set(self, value):
        is_all = value == "all"
        if self.all is not None:
            self.all.SetValue(is_all)
            self.list.Enable(not is_all)
        self.set_items(self.items, [] if is_all or value is None else list(value))


class CategoriesEditor(Editor):
    """Category columns in a chosen order (grouping): check them and move them."""

    expands = True
    grows = False  # as tall as its columns

    def create(self, parent):
        self.panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.automatic = None
        if self.spec.optional:  # None: chosen by the tool
            self.automatic = wx.CheckBox(self.panel, label="Automatic")
            self.automatic.Bind(wx.EVT_CHECKBOX, self._on_automatic)
            sizer.Add(self.automatic, 0, wx.BOTTOM, 3)
        self.items: list = []
        self.rearrange = wx.RearrangeCtrl(self.panel, order=[], items=[])
        self.rearrange.GetList().Bind(wx.EVT_CHECKLISTBOX, self.changed)
        for button in self.rearrange.GetChildren():
            if isinstance(button, wx.Button):
                button.Bind(wx.EVT_BUTTON, self._on_move)
        sizer.Add(self.rearrange, 1, wx.EXPAND)
        self.panel.SetSizer(sizer)
        return self.panel

    def _on_move(self, event):
        event.Skip()
        wx.CallAfter(self.changed)

    def _on_automatic(self, event):
        self.rearrange.Enable(not self.automatic.GetValue())
        self.changed(event)

    def _show(self, items, checked):
        self.items = list(items) + [c for c in checked if c not in items]
        # checked ones first, in their order, then the others
        order = [self.items.index(c) for c in checked] + [
            ~i for i, item in enumerate(self.items) if item not in checked
        ]
        labels = [self.items[i if i >= 0 else ~i] for i in order]
        rearrange_list = self.rearrange.GetList()
        rearrange_list.Set(labels)
        for position, i in enumerate(order):
            rearrange_list.Check(position, i >= 0)
        fit_rows(rearrange_list, len(labels), fewest=2, most=8, fixed=True)

    def checked(self) -> list:
        rearrange_list = self.rearrange.GetList()
        return [
            rearrange_list.GetString(i)
            for i in range(rearrange_list.GetCount())
            if rearrange_list.IsChecked(i)
        ]

    def set_schema(self, schema):
        self._show(
            [] if schema is None else schema.by_role(self.spec.role), self.checked()
        )

    def get(self):
        if self.automatic is not None and self.automatic.GetValue():
            return None
        return self.checked()

    def set(self, value):
        if self.automatic is not None:
            self.automatic.SetValue(value is None)
            self.rearrange.Enable(value is not None)
        self._show(self.items, [] if value is None else list(value))


class PathEditor(Editor):
    def create(self, parent):
        control = wx.FilePickerCtrl(parent, style=wx.FLP_USE_TEXTCTRL | wx.FLP_OPEN)
        control.Bind(wx.EVT_FILEPICKER_CHANGED, self.changed)
        return control

    def get(self):
        path = self.control.GetPath()
        if not path and self.spec.optional:
            return None
        return Path(path)

    def set(self, value):
        self.control.SetPath("" if value is None else str(value))


class PathsEditor(Editor):
    expands = True

    def create(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.list = wx.ListBox(panel, style=wx.LB_EXTENDED)
        self.list.SetMinSize((-1, 70))
        sizer.Add(self.list, 1, wx.EXPAND)
        buttons = wx.BoxSizer(wx.VERTICAL)
        for label, handler in (("Add...", self._on_add), ("Remove", self._on_remove)):
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.LEFT | wx.BOTTOM, 3)
        sizer.Add(buttons)
        panel.SetSizer(sizer)
        return panel

    def _on_add(self, event):
        with wx.FileDialog(
            self.control, "Select files", style=wx.FD_OPEN | wx.FD_MULTIPLE
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.set(self.get() + [Path(p) for p in dialog.GetPaths()])
                self.changed()

    def _on_remove(self, event):
        for index in sorted(self.list.GetSelections(), reverse=True):
            self.list.Delete(index)
        self.changed()

    def get(self):
        return [Path(p) for p in self.list.GetItems()]

    def set(self, value):
        self.list.Set([str(p) for p in value or []])


class ModelEditor(Editor):
    """A nested config, in a collapsible section."""

    expands = True

    def create(self, parent):
        self.pane = wx.CollapsiblePane(parent, label=self.spec.title)
        self.pane.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self._on_toggle)
        self.fields = FieldsPanel(self.pane.GetPane(), self.spec.model)
        self.fields.on_change = lambda: self.changed()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.fields, 1, wx.EXPAND)
        self.pane.GetPane().SetSizer(sizer)
        self.value = None
        return self.pane

    def _on_toggle(self, event):
        window = wx.GetTopLevelParent(self.pane)
        window.Layout()
        window.Fit()

    def get(self):
        try:
            return self.fields.values(self.value)
        except FieldErrors as err:
            raise ValueError(
                "; ".join(f"{k}: {v}" for k, v in err.errors.items())
            ) from None

    def set(self, value):
        self.value = value
        self.fields.set_values(value)

    def set_schema(self, schema):
        self.fields.set_schema(schema)

    def set_data(self, tables):
        self.fields.set_data(tables)


class ModelsEditor(Editor):
    """A list of nested configs (with simple fields) as an editable table.

    Subclasses may add buttons (``extra_buttons``) and a first column for dict keys
    (``key_title``: the value is then a dict key -> config).
    """

    expands = True
    key_title = None

    def extra_buttons(self) -> list:
        """(label, handler) of further buttons below the table."""
        return []

    def create(self, parent):
        model = self.spec.model
        self.columns = [
            s for s in visible(describe(model)) if s.kind not in ("model", "models")
        ]
        self.offset = 1 if self.key_title else 0
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, len(self.columns) + self.offset)
        if self.key_title:
            self.grid.SetColLabelValue(0, self.key_title)
        for i, column in enumerate(self.columns):
            self.grid.SetColLabelValue(i + self.offset, column.title)
        self.grid.SetRowLabelSize(30)
        self.grid.SetMinSize((-1, 110))
        self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.changed)
        sizer.Add(self.grid, 1, wx.EXPAND)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in [
            ("Add Row", self._on_add),
            ("Remove Rows", self._on_remove),
        ] + self.extra_buttons():
            button = wx.Button(panel, label=label, style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.TOP | wx.RIGHT, 3)
        sizer.Add(buttons)
        panel.SetSizer(sizer)
        return panel

    def _on_add(self, event):
        self.grid.AppendRows(1)
        self.changed()

    def _on_remove(self, event):
        rows = sorted(
            set(self.grid.GetSelectedRows()) | {self.grid.GetGridCursorRow()},
            reverse=True,
        )
        for row in rows:
            if 0 <= row < self.grid.GetNumberRows():
                self.grid.DeleteRows(row)
        self.changed()

    def rows(self) -> list[tuple[str, dict]]:
        """(key, values) of each row; text is converted by the config's validation."""
        rows = []
        for row in range(self.grid.GetNumberRows()):
            values = {}
            for col, column in enumerate(self.columns):
                text = self.grid.GetCellValue(row, col + self.offset).strip()
                if text != "":
                    values[column.name] = text
            key = self.grid.GetCellValue(row, 0).strip() if self.key_title else ""
            rows.append((key, values))
        return rows

    def add_row(self, values: dict, key: str = "") -> None:
        row = self.grid.GetNumberRows()
        self.grid.AppendRows(1)
        if self.key_title:
            self.grid.SetCellValue(row, 0, key)
        for col, column in enumerate(self.columns):
            cell = values.get(column.name)
            self.grid.SetCellValue(
                row, col + self.offset, "" if cell is None else str(cell)
            )

    def get(self):
        if self.key_title:
            return {key: values for key, values in self.rows() if key}
        return [values for _, values in self.rows()]

    def set(self, value):
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        items = (
            value.items() if isinstance(value, dict) else [("", v) for v in value or []]
        )
        for key, item in items:
            self.add_row(
                item if isinstance(item, dict) else item.model_dump(), str(key)
            )
        self.grid.AutoSizeColumns()


class ModelMapEditor(ModelsEditor):
    """A dict of nested configs by key (e.g. per feature): the key is the first column."""

    @property
    def key_title(self):
        return {"feature": "Feature", "category": "Column"}.get(self.spec.role, "Key")


class JsonEditor(Editor):
    """Anything else, as JSON text."""

    expands = True

    def create(self, parent):
        control = wx.TextCtrl(parent, style=wx.TE_MULTILINE)
        control.SetMinSize((-1, 60))
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def get(self):
        try:
            return json.loads(self.control.GetValue() or "null")
        except json.JSONDecodeError as err:
            raise ValueError(f"Not valid JSON: {err.msg}") from None

    def set(self, value):
        self.control.ChangeValue(json.dumps(_jsonable(value)))


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    return value


def editor_class(spec: FieldSpec) -> type[Editor]:
    """The editor for a field kind."""
    if spec.kind == "bool":
        return ChoiceEditor if spec.optional else BoolEditor
    if spec.kind == "int" and not spec.optional:
        return IntEditor
    if spec.kind == "columns":
        return FeaturesEditor if spec.role == "feature" else CategoriesEditor
    return {
        "choice": ChoiceEditor,
        "multichoice": MultiChoiceEditor,
        "column": ColumnEditor,
        "value": ValueEditor,
        "path": PathEditor,
        "paths": PathsEditor,
        "model": ModelEditor,
        "models": ModelsEditor,
        "modelmap": ModelMapEditor,
        "json": JsonEditor,
    }.get(spec.kind, TextEditor)


# (config class, field name) -> editor class, for fields that need their own widget
_FIELD_EDITORS: dict = {}


def register_editor(config_class, field_name: str):
    """Class decorator: the editor of one field of a config class (and subclasses)."""

    def register(editor):
        _FIELD_EDITORS[(config_class, field_name)] = editor
        return editor

    return register


def editor_for(model: type, spec: FieldSpec) -> type[Editor]:
    for base in model.__mro__:
        if (base, spec.name) in _FIELD_EDITORS:
            return _FIELD_EDITORS[(base, spec.name)]
    return editor_class(spec)


# fields shared by many tools, shown after a tool's own settings
GENERAL_FIELDS = ("grouping", "features", "prefix", "random_seed")


class FieldsPanel(wx.Panel):
    """Editors for the visible fields of a config class, with issue markers.

    Small fields share a two-column grid (label, editor); lists and tables take the
    full width; nested configs come last, in collapsible sections.
    """

    def __init__(self, parent, model: type, exclude=()):
        super().__init__(parent)
        self.model = model
        self.on_change: Optional[Callable[[], None]] = None
        self.editors: dict[str, Editor] = {}
        self.markers: dict[str, wx.StaticBitmap] = {}
        specs = [s for s in visible(describe(model)) if s.name not in exclude]
        # the tool's own settings first, general ones (prefix, seed) after
        small = [s for s in specs if not editor_for(model, s).expands]
        small = [s for s in small if s.name not in GENERAL_FIELDS] + [
            s for s in small if s.name in GENERAL_FIELDS
        ]
        large = [s for s in specs if editor_for(model, s).expands and s.kind != "model"]
        large = [s for s in large if s.name not in GENERAL_FIELDS] + [
            s for s in large if s.name in GENERAL_FIELDS
        ]
        nested = [s for s in specs if s.kind == "model"]

        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=3, vgap=4, hgap=6)
        grid.AddGrowableCol(1)
        for spec in small:
            grid.Add(self._label(spec), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(self._editor(spec).control, 1, wx.EXPAND)
            grid.Add(self._marker(spec), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 4)
        for spec in large:
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.Add(self._label(spec), 0, wx.RIGHT, 6)
            row.Add(self._marker(spec), 0)
            sizer.Add(row, 0, wx.LEFT | wx.TOP, 4)
            editor = self._editor(spec)
            sizer.Add(editor.control, 1 if editor.grows else 0, wx.EXPAND | wx.ALL, 4)
        for spec in nested:
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.Add(self._editor(spec).control, 1, wx.EXPAND)
            row.Add(self._marker(spec), 0, wx.TOP, 4)
            sizer.Add(row, 0, wx.EXPAND | wx.ALL, 4)
        self.SetSizer(sizer)

    def _label(self, spec):
        label = wx.StaticText(self, label=spec.title)
        if spec.description:
            label.SetToolTip(spec.description)
        return label

    def _editor(self, spec):
        editor = editor_for(self.model, spec)(self, spec)
        editor.on_change = self._on_editor_change
        self.editors[spec.name] = editor
        return editor

    def _marker(self, spec):
        marker = wx.StaticBitmap(self, bitmap=_marker_bitmap("error"))
        marker.Hide()
        self.markers[spec.name] = marker
        return marker

    def set_values(self, config) -> None:
        for name, editor in self.editors.items():
            editor.set(getattr(config, name))
        self.refresh()

    def values(self, config) -> dict:
        """The config's values with the edited ones; raises FieldErrors."""
        values = {name: getattr(config, name) for name in type(config).model_fields}
        errors = {}
        for name, editor in self.editors.items():
            try:
                values[name] = editor.get()
            except ValueError as err:
                errors[name] = str(err)
        if errors:
            raise FieldErrors(errors)
        return values

    def _on_editor_change(self, editor):
        self.refresh()
        if self.on_change:
            self.on_change()

    def value_of(self, name: str):
        """The edited value of a field; None if it is not shown or not valid."""
        editor = self.editors.get(name)
        try:
            return editor.get() if editor else None
        except ValueError:
            return None

    def refresh(self) -> None:
        """Lets editors that depend on other fields update (e.g. value choices)."""
        for editor in self.editors.values():
            editor.refresh(self)

    def set_schema(self, schema) -> None:
        for editor in self.editors.values():
            editor.set_schema(schema)
        self.refresh()

    def set_data(self, tables: list) -> None:
        for editor in self.editors.values():
            editor.set_data(tables)

    def show_issue(self, name: str, severity: Optional[str], message: str = "") -> None:
        marker = self.markers.get(name)
        if marker is None:
            return
        if severity is None:
            marker.Hide()
        else:
            marker.SetBitmap(_marker_bitmap(severity))
            marker.SetToolTip(message)
            marker.Show()
        self.Layout()


class FieldErrors(Exception):
    """Text in editors that is not a valid value: field name -> message."""

    def __init__(self, errors: dict):
        super().__init__(errors)
        self.errors = errors


_ART = {"error": wx.ART_ERROR, "warning": wx.ART_WARNING, "guessed": wx.ART_WARNING}


def _marker_bitmap(severity: str) -> wx.Bitmap:
    return wx.ArtProvider.GetBitmap(_ART[severity], wx.ART_MENU, (16, 16))
