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

from flim.core.fields import FieldSpec, describe, field_order, visible
from flim.core.schema import TableSchema
from flim.core.validation import guess_column

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

    def show_issues(self, issues: list) -> None:
        """The issues of this field (paths like ``"features['FLIRR']"``), e.g. to mark
        the rows of a table they are about; the dialog marks the field itself."""

    def refresh(self, panel: "FieldsPanel") -> None:
        """Called when any field of the panel changed (fields that depend on others)."""

    def set_allowed(self, allowed: Optional[tuple]) -> None:
        """The values allowed now (None: all), see BaseConfig.allowed_values."""

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
            labels = [self._label(v) for v in self.values]
        self.all_values = list(self.values)
        control = wx.Choice(parent, choices=labels)
        control.Bind(wx.EVT_CHOICE, self.changed)
        return control

    def _label(self, value) -> str:
        if value is None:
            return NONE_LABEL
        return str(self.spec.labels.get(value, value))

    def get(self):
        index = self.control.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Select a value")
        return self.values[index]

    def set(self, value):
        if value in self.values:
            self.control.SetSelection(self.values.index(value))

    def set_allowed(self, allowed):
        values = [v for v in self.all_values if allowed is None or v in allowed]
        if values == self.values:
            return
        current = self.values[self.control.GetSelection()] if self.values else None
        self.values = values
        self.control.Set([self._label(v) for v in values])
        # keep the value if still allowed, else the first allowed (the default)
        self.control.SetSelection(values.index(current) if current in values else 0)


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

    def set_allowed(self, allowed):
        # only some columns allowed (e.g. one of the selected features): those
        if allowed is None or len(allowed) < 2:
            return
        names = [str(a) for a in allowed if a is not None]
        if names == self.control.GetItems():
            return
        value = self.control.GetValue()
        set_combo_items(self.control, names)
        self.control.ChangeValue(value if value in names else names[0])


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
        column = panel.value_of(self.spec.column_field)
        if isinstance(column, list):  # e.g. grouping: its first column
            column = column[0] if column else None
        self.update_choices(column)

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
        self.buttons = []
        for label, checked in (("Select All", True), ("Deselect All", False)):
            button = wx.Button(self.panel, label=label, style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, lambda e, c=checked: self.check_all(c))
            buttons.Add(button, 0, wx.TOP | wx.RIGHT, 3)
            self.buttons.append(button)
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


def _one_line(name) -> str:
    return str(name).replace("\n", " ")


class FeaturesEditor(_CheckList):
    """Feature columns, or "all" (if allowed)."""

    def create(self, parent):
        panel = super().create(parent)
        self.list.Unbind(wx.EVT_CHECKLISTBOX)
        self.list.Bind(wx.EVT_CHECKLISTBOX, self._on_check)
        return panel

    def extra_controls(self, panel, sizer):
        self.all = None
        self.selection: list = []  # the selection before "All features" was checked
        # the checked features, also those the input lacks (e.g. the settings of a run
        # on another table): checked again with an input that has them
        self.wanted: list = []
        self.features: list = []  # the input's features
        self.known = False  # all of the input's features are known
        self.note = wx.StaticText(panel, label="")  # the wanted ones not shown
        self.note.SetForegroundColour(wx.Colour(120, 120, 120))
        self.note.Hide()
        sizer.Add(self.note, 0, wx.BOTTOM, 3)
        if self.spec.allow_all:
            self.all = wx.CheckBox(panel, label="All features")
            self.all.Bind(wx.EVT_CHECKBOX, self._on_all)
            sizer.Add(self.all, 0, wx.BOTTOM, 3)

    def is_all(self) -> bool:
        return self.all is not None and self.all.GetValue()

    def _show_all(self, is_all: bool) -> None:
        """All features: all shown checked, the list and its buttons disabled."""
        if is_all:
            self.list.SetCheckedItems(list(range(len(self.items))))
        for control in [self.list] + self.buttons:
            control.Enable(not is_all)

    def _on_all(self, event):
        if self.is_all():
            self.selection = self.checked()
        elif self.selection:  # back to the selection made before; else all stay checked
            self.list.SetCheckedItems(
                [self.items.index(f) for f in self.selection if f in self.items]
            )
        self._show_all(self.is_all())
        self.changed(event)

    def _remember(self) -> None:
        """The checked features, and the wanted ones the input lacks."""
        self.wanted = self.checked() + [w for w in self.wanted if w not in self.items]

    def _on_check(self, event):
        self._remember()
        self.changed(event)

    def check_all(self, checked: bool):
        self.list.SetCheckedItems(list(range(len(self.items))) if checked else [])
        self._remember()
        self.changed()

    def set_schema(self, schema):
        if not self.is_all():
            self._remember()
        self.known = schema is not None and schema.complete
        self.features = [] if schema is None else schema.by_role(self.spec.role)
        self.set_items(self.features, [] if self.is_all() else self._shown())
        self._show_all(self.is_all())

    def _shown(self) -> list:
        """The wanted features shown checked: those of the input if all are known
        (else all of them: they may be in the input). A wanted feature the input
        lacks is replaced by the closest of its features (a guess), if there is one."""
        if not self.known:
            self._show_note([])
            return list(self.wanted)
        shown, notes, unused = [], [], []
        for f in self.wanted:
            if f in self.features:
                shown.append(f)
                continue
            guess, _ = guess_column(f, self.features)
            if guess is None or guess in self.wanted:
                unused.append(f)
            else:
                shown.append(guess)
                notes.append(f"{_one_line(f)} \u2192 {_one_line(guess)}")
        lines = []
        if notes:
            lines.append("Guessed: " + ", ".join(notes))
        if unused:
            names = ", ".join(_one_line(f) for f in unused)
            lines.append(f"Not in this input (not used): {names}")
        self._show_note(lines)
        return list(dict.fromkeys(shown))

    def _show_note(self, lines: list) -> None:
        if lines:
            self.note.SetLabel("\n".join(lines))
            self.note.SetToolTip(self.note.GetLabel())
        if bool(lines) != self.note.IsShown():
            self.note.Show(bool(lines))
            self.panel.Layout()

    def get(self):
        if self.is_all():
            return "all"
        return self.checked()

    def set(self, value):
        is_all = value == "all"
        if self.all is not None:
            self.all.SetValue(is_all)
        self.selection = []
        self.wanted = [] if is_all or value is None else list(value)
        self.set_items(self.features, self._shown())
        self._show_all(is_all)


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


def relayout(window) -> None:
    """Fits the dialog of ``window`` to fields that appeared or disappeared."""
    top = wx.GetTopLevelParent(window)
    if hasattr(top, "fit_contents"):
        top.fit_contents()
    elif top is not None:
        top.Layout()


class ModelEditor(Editor):
    """A nested config: its fields in a titled group, or in a collapsed section if
    it is advanced (``Field(json_schema_extra={"advanced": True})``, or a class with
    ``advanced = True``, such as Resources)."""

    expands = True

    def create(self, parent):
        self.value = None
        sizer = wx.BoxSizer(wx.VERTICAL)
        if self.spec.advanced:
            self.pane = wx.CollapsiblePane(parent, label=self.spec.title)
            self.pane.Bind(
                wx.EVT_COLLAPSIBLEPANE_CHANGED, lambda e: relayout(self.pane)
            )
            self.fields = FieldsPanel(self.pane.GetPane(), self.spec.model)
            sizer.Add(self.fields, 1, wx.EXPAND)
            self.pane.GetPane().SetSizer(sizer)
            control = self.pane
        else:
            control = wx.Panel(parent)
            box = wx.StaticBoxSizer(wx.VERTICAL, control, self.spec.title)
            self.fields = FieldsPanel(box.GetStaticBox(), self.spec.model)
            box.Add(self.fields, 1, wx.EXPAND)
            control.SetSizer(box)
        self.fields.on_change = lambda: self.changed()
        return control

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


class _RowIssues:
    """Marks the rows of a grid editor that issues are about (``_row_of``): a marker
    drawn by _MarkedTextRenderer, and the messages as the row's tooltip."""

    def _init_row_issues(self) -> wx.grid.GridCellAttr:
        self.marks: dict = {}  # row -> severity of its issues
        self.row_messages: dict = {}  # row -> its issues' messages
        attr = wx.grid.GridCellAttr()
        attr.SetRenderer(_MarkedTextRenderer(self.marks))
        return attr

    def show_issues(self, issues):
        self.marks.clear()
        self.row_messages.clear()
        for issue in issues:
            row = self._row_of(issue.field)
            if row is None:
                continue
            current = self.marks.get(row)
            if current is None or SEVERITIES.index(issue.severity) < SEVERITIES.index(
                current
            ):
                self.marks[row] = issue.severity
            self.row_messages.setdefault(row, []).append(issue.message)
        self.grid.ForceRefresh()

    def _on_motion(self, event):
        x, y = self.grid.CalcUnscrolledPosition(event.GetPosition())
        messages = self.row_messages.get(self.grid.YToRow(y))
        window = self.grid.GetGridWindow()
        text = "\n".join(messages) if messages else ""
        if window.GetToolTipText() != text:
            window.SetToolTip(text)
        event.Skip()


SEVERITIES = ("error", "guessed", "warning")  # first: most severe


class ModelsEditor(_RowIssues, Editor):
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
        # rows with issues: a marker in the first column, the messages as tooltip
        self._init_row_issues()
        self._set_choices({c.name: c.choices for c in self.columns if c.choices})
        self.grid.GetGridWindow().Bind(wx.EVT_MOTION, self._on_motion)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.changed)
        sizer.Add(self.grid, 1, wx.EXPAND)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        item = self.item_name()
        for label, handler in [
            (f"Add {item}", self._on_add),
            (f"Remove {item}s", self._on_remove),
        ] + self.extra_buttons():
            button = wx.Button(panel, label=label, style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.TOP | wx.RIGHT, 3)
        sizer.Add(buttons)
        panel.SetSizer(sizer)
        return panel

    def item_name(self) -> str:
        """What a row is, for the buttons: "Rules" → "Rule"."""
        title = self.spec.title
        return title[:-1] if title.endswith("s") and len(title) > 1 else "Row"

    def _set_choices(self, choices: dict) -> None:
        """Cells of the columns in ``choices`` (name -> values) are edited with a
        drop-down of the values (none: text); the first column marks rows with
        issues."""
        for col, column in enumerate(self.columns):
            col += self.offset
            values = choices.get(column.name)
            if col and values is None:
                continue
            attr = wx.grid.GridCellAttr()
            if col == 0:
                attr.SetRenderer(_MarkedTextRenderer(self.marks))
            if values is not None:
                attr.SetEditor(wx.grid.GridCellChoiceEditor([str(v) for v in values]))
            self.grid.SetColAttr(col, attr)
        if self.offset:  # the key column
            attr = wx.grid.GridCellAttr()
            attr.SetRenderer(_MarkedTextRenderer(self.marks))
            self.grid.SetColAttr(0, attr)

    def set_schema(self, schema):
        # column cells: a drop-down of the input's columns of the role (unknown: text)
        if schema is None:
            return
        choices = {c.name: c.choices for c in self.columns if c.choices}
        for column in self.columns:
            if column.kind == "column":
                choices[column.name] = schema.by_role(column.role)
        self._set_choices(choices)

    def _row_of(self, path) -> Optional[int]:
        """The row of a path into this field: "rules[1].min" (a list) or
        "ranges['FLIRR']" (a dict with keys in the first column)."""
        rest = (path or "")[len(self.spec.name) :].lstrip(".")
        if self.key_title:
            rest = rest.removeprefix("['")
            keys = [key for key, _ in self.rows()]
            matches = [i for i, k in enumerate(keys) if k and rest.startswith(k)]
            return max(matches, key=lambda i: len(keys[i])) if matches else None
        number = rest.removeprefix("[").split("]")[0].split(".")[0]
        return int(number) if number.isdigit() else None

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


class _MarkedTextRenderer(wx.grid.GridCellStringRenderer):
    """Draws a cell's text and, in rows with issues, the issue marker at its right."""

    def __init__(self, marks: dict):
        super().__init__()
        self.marks = marks  # row -> severity

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        super().Draw(grid, attr, dc, rect, row, col, isSelected)
        severity = self.marks.get(row)
        if severity:
            bitmap = _marker_bitmap(severity)
            x = rect.x + rect.width - bitmap.GetWidth() - 2
            y = rect.y + (rect.height - bitmap.GetHeight()) // 2
            dc.DrawBitmap(bitmap, x, y, True)

    def GetBestSize(self, grid, attr, dc, row, col):
        size = super().GetBestSize(grid, attr, dc, row, col)
        return wx.Size(size.width + 20, size.height)  # room for the marker

    def Clone(self):
        return _MarkedTextRenderer(self.marks)


class FeatureSettingsEditor(_RowIssues, Editor):
    """Features with settings (a dict of configs by feature, e.g. ranges): one row
    for each feature of the input; "Use" selects it, and its settings are edited in
    the same row. Empty settings are the config's defaults. Checking a feature fills
    an empty min and max with the feature's range in the data."""

    expands = True

    def create(self, parent):
        self.columns = [
            s
            for s in visible(describe(self.spec.model))
            if s.kind not in ("model", "models", "modelmap")
        ]
        self.features: list[str] = []
        self.ranges: dict = {}  # feature -> (min, max) in the data
        self.panel = None  # the FieldsPanel, known once it refreshes this editor
        self.synced: set = set()  # settings now kept the same in all rows
        self.last_edited: dict = (
            {}
        )  # setting -> the feature whose value was edited last
        self.disabled: set = set()  # settings now not used (greyed out)
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(panel)
        self.grid.CreateGrid(0, 2 + len(self.columns))
        self.grid.SetColLabelValue(0, "Use")
        self.grid.SetColLabelValue(1, "Feature")
        for i, column in enumerate(self.columns):
            self.grid.SetColLabelValue(i + 2, column.title)
        use = wx.grid.GridCellAttr()
        use.SetRenderer(wx.grid.GridCellBoolRenderer())
        use.SetReadOnly(True)  # toggled by a click, see _on_click
        use.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetColAttr(0, use)
        name = self._init_row_issues()  # the feature column shows the markers
        name.SetReadOnly(True)
        self.grid.SetColAttr(1, name)
        self.grid.GetGridWindow().Bind(wx.EVT_MOTION, self._on_motion)
        self.grid.SetRowLabelSize(0)
        self.grid.SetMinSize((-1, 150))
        self.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self._on_click)
        self.grid.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self._on_cell_changed)
        self.grid.Bind(wx.grid.EVT_GRID_TABBING, self._on_tab)
        sizer.Add(self.grid, 1, wx.EXPAND)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
            ("Select All", lambda e: self.use_all(True)),
            ("Deselect All", lambda e: self.use_all(False)),
            ("Load Feature Settings...", self._on_load),
            ("Save Feature Settings...", self._on_save),
        ):
            button = wx.Button(panel, label=label, style=wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.TOP | wx.RIGHT, 3)
        sizer.Add(buttons)
        self.message = wx.StaticText(panel, label="")
        sizer.Add(self.message, 0, wx.TOP, 3)
        panel.SetSizer(sizer)
        return panel

    # --- settings files ---

    def _on_load(self, event):
        with wx.FileDialog(
            self.control,
            "Load feature settings",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.load_settings(dialog.GetPath())

    def _on_save(self, event):
        with wx.FileDialog(
            self.control,
            "Save feature settings",
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.save_settings(dialog.GetPath())

    def load_settings(self, path) -> tuple[list, list]:
        """Applies the settings in a file to the matching features (which stay
        checked or unchecked); returns the applied and the skipped features."""
        names = [c.name for c in self.columns]
        try:
            with open(path) as f:
                settings = find_feature_settings(json.load(f), names)
        except (OSError, ValueError) as err:
            self.message.SetLabel(f"Could not read {Path(path).name}: {err}")
            return [], []
        if settings is None:
            self.message.SetLabel(f"No feature settings in {Path(path).name}")
            return [], []
        state = self._state()
        applied = [f for f in settings if f in state]
        skipped = [f for f in settings if f not in state]
        for feature in applied:
            used, _ = state[feature]
            texts = [_cell_text(settings[feature].get(c.name)) for c in self.columns]
            state[feature] = (used, texts)
        self._show(self.features, state)
        # loaded settings are per feature and used: settings kept the same in all
        # rows, or not used, no more
        flags = {**self.synced_settings(), **self.disabled_settings()}
        for flag in flags.values():
            if self.panel is not None and flag in self.panel.editors:
                self.panel.editors[flag].set(False)
        self.synced.clear()
        if self.panel is not None:
            self.refresh(self.panel)
        message = f"Applied the settings of {len(applied)} features"
        if skipped:
            message += f"; {len(skipped)} are not in the table"
        self.message.SetLabel(message)
        self.changed()
        return applied, skipped

    def save_settings(self, path) -> None:
        """Writes the settings of the checked features, {feature: {name: value}};
        settings that are not valid are left out."""
        settings = {}
        for feature, values in self.get().items():
            try:
                model = self.spec.model.model_validate(values)
            except ValueError:
                continue
            settings[feature] = model.model_dump(exclude={"classname", "version"})
        with open(path, "w") as f:
            json.dump(settings, f, indent=2)
        self.message.SetLabel(f"Saved the settings of {len(settings)} features")

    # --- rows ---

    def is_used(self, row) -> bool:
        return self.grid.GetCellValue(row, 0) == "1"

    def use(self, row, used=True) -> None:
        self.grid.SetCellValue(row, 0, "1" if used else "")
        if used:
            self._take_synced(row)
            # empty settings with a default (e.g. bins): show the default
            for column in self.columns:
                default = self.spec.model.model_fields[column.name].default
                col = self._column(column.name)
                if default is not None and self.grid.GetCellValue(row, col) == "":
                    self.grid.SetCellValue(row, col, _cell_text(default))
        if used:  # empty limits: the feature's range in the data
            feature = self.features[row]
            names = [c.name for c in self.columns]
            limits = next(
                (p for p in (("min", "max"), ("low", "high")) if set(p) <= set(names)),
                None,
            )
            # one value only (constant column): no range, the plot handles it
            constant = feature in self.ranges and len(set(self.ranges[feature])) == 1
            fill = limits and not set(limits) & self.disabled and not constant
            if feature in self.ranges and fill:
                for name, value in zip(limits, self.ranges[feature]):
                    col = names.index(name) + 2
                    if self.grid.GetCellValue(row, col) == "":
                        self.grid.SetCellValue(row, col, f"{value:g}")
        self._style_row(row)
        self.grid.ForceRefresh()

    def _take_synced(self, row) -> None:
        """A newly checked row gets the settings that are the same in all rows."""
        for name in self.synced:
            col = self._column(name)
            others = [
                r for r in range(len(self.features)) if r != row and self.is_used(r)
            ]
            if col is not None and others:
                self.grid.SetCellValue(row, col, self.grid.GetCellValue(others[0], col))

    def use_all(self, used: bool) -> None:
        for row in range(len(self.features)):
            self.use(row, used)
        self._fit_columns()
        self.changed()

    def _fit_columns(self) -> None:
        """Columns as wide as their values (filled-in ranges)."""
        self.grid.AutoSizeColumns(setAsMin=False)
        self.grid.SetColSize(0, max(self.grid.GetColSize(0), 40))

    # --- settings that are the same in all rows (e.g. bins, config.synced_settings) ---

    def synced_settings(self) -> dict:
        """settings field -> config field that keeps it the same in all rows."""
        model = getattr(self.panel, "model", None)
        return dict(getattr(model, "synced_settings", {}))

    def _column(self, name):
        names = [c.name for c in self.columns]
        return names.index(name) + 2 if name in names else None

    def sync_column(self, name, value=None) -> None:
        """Sets setting ``name`` of all rows to ``value`` (default: the value of the
        row edited last; else of the first checked row, or the first row)."""
        col = self._column(name)
        if col is None or not self.features:
            return
        if value is None:
            feature = self.last_edited.get(name)
            if feature in self.features:
                row = self.features.index(feature)
            else:
                rows = [r for r in range(len(self.features)) if self.is_used(r)] or [0]
                row = rows[0]
            value = self.grid.GetCellValue(row, col)
        for row in range(len(self.features)):
            self.grid.SetCellValue(row, col, value)

    # --- issues in rows ---

    def _row_of(self, path) -> Optional[int]:
        """The row a path into this field is about, e.g. "features['FAD t1'].min"."""
        rest = (path or "")[len(self.spec.name) :].lstrip(".").removeprefix("['")
        matches = [i for i, f in enumerate(self.features) if rest.startswith(f)]
        return max(matches, key=lambda i: len(self.features[i])) if matches else None

    def disabled_settings(self) -> dict:
        """settings field -> config field that makes it unused (greyed out)."""
        model = getattr(self.panel, "model", None)
        return dict(getattr(model, "disabled_settings", {}))

    def _set_disabled(self, disabled: set) -> None:
        """Greys out (and makes read-only) the columns of settings that are not used;
        their values are kept."""
        if disabled == self.disabled:
            return
        self.disabled = disabled
        self._style_rows()

    def _style_row(self, row) -> None:
        """Unchecked rows are grey, and their settings read-only; so are the settings
        not used now (disabled), also in checked rows."""
        grey = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        normal = self.grid.GetDefaultCellTextColour()
        used = self.is_used(row)
        self.grid.SetCellTextColour(row, 1, normal if used else grey)
        for column in self.columns:
            col = self._column(column.name)
            editable = used and column.name not in self.disabled
            self.grid.SetReadOnly(row, col, not editable)
            self.grid.SetCellTextColour(row, col, normal if editable else grey)

    def _style_rows(self) -> None:
        for row in range(len(self.features)):
            self._style_row(row)
        self.grid.ForceRefresh()

    def refresh(self, panel):
        self.panel = panel
        for setting, flag in self.synced_settings().items():
            on = bool(panel.value_of(flag))
            if on and setting not in self.synced:
                self.synced.add(setting)
                self.sync_column(setting)
            elif not on:
                self.synced.discard(setting)
        self._set_disabled(
            {s for s, flag in self.disabled_settings().items() if panel.value_of(flag)}
        )

    def _on_cell_changed(self, event):
        col = event.GetCol()
        name = self.columns[col - 2].name if col >= 2 else None
        if name is not None:
            self.last_edited[name] = self.features[event.GetRow()]
        if name in self.synced:
            self.sync_column(name, self.grid.GetCellValue(event.GetRow(), col))
        self.changed(event)

    def _on_tab(self, event):
        """Tab moves to the next editable cell (Shift+Tab: the previous one), on to
        the next row; focus stays in the table. Leaving it with Tab put the focus on
        the check boxes above it (e.g. Same bins for all), where a key toggled them."""
        cells = [
            (row, col)
            for row in range(self.grid.GetNumberRows())
            for col in range(2, self.grid.GetNumberCols())
            if not self.grid.IsReadOnly(row, col)
        ]
        if not cells:
            return
        current = (event.GetRow(), event.GetCol())
        if event.ShiftDown():
            before = [c for c in cells if c < current]
            row, col = before[-1] if before else cells[-1]
        else:
            after = [c for c in cells if c > current]
            row, col = after[0] if after else cells[0]
        self.grid.SetGridCursor(row, col)
        self.grid.MakeCellVisible(row, col)

    def _on_click(self, event):
        if event.GetCol() == 0:
            row = event.GetRow()
            self.use(row, not self.is_used(row))
            self._fit_columns()
            self.changed()
        else:
            event.Skip()

    def _state(self) -> dict:
        """feature -> (used, cell texts)."""
        return {
            feature: (
                self.is_used(row),
                [
                    self.grid.GetCellValue(row, col + 2)
                    for col in range(len(self.columns))
                ],
            )
            for row, feature in enumerate(self.features)
        }

    def _show(self, features, state) -> None:
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.features = list(features) + [
            f for f in state if f not in features and state[f][0]
        ]
        self.grid.AppendRows(len(self.features))
        for row, feature in enumerate(self.features):
            used, texts = state.get(feature, (False, [""] * len(self.columns)))
            self.grid.SetCellValue(row, 0, "1" if used else "")
            self.grid.SetCellValue(row, 1, feature.replace("\n", " "))
            for col, text in enumerate(texts):
                self.grid.SetCellValue(row, col + 2, text)
        self._fit_columns()

        # --- Editor ---
        self._style_rows()

    def set_schema(self, schema):
        features = [] if schema is None else schema.by_role("feature")
        self._show(features, self._state())

    def set_data(self, tables):
        self.ranges = {}
        if tables:
            data = tables[0]
            for column in data.select_dtypes("number").columns:
                values = data[column].replace(
                    [float("inf"), float("-inf")], float("nan")
                )
                if values.notna().any():
                    self.ranges[column] = (float(values.min()), float(values.max()))

    def get(self):
        result = {}
        for feature, (used, texts) in self._state().items():
            if used:
                result[feature] = {
                    c.name: t.strip() for c, t in zip(self.columns, texts) if t.strip()
                }
        return result

    def set(self, value):
        state = {}
        for feature, settings in (value or {}).items():
            data = settings if isinstance(settings, dict) else settings.model_dump()
            state[feature] = (
                True,
                [_cell_text(data.get(c.name)) for c in self.columns],
            )
        self._show(self.features, state)  # the input's features, checked as configured


def find_feature_settings(data, names: list) -> Optional[dict]:
    """Per-feature settings in a loaded settings file: {feature: {name: value}}.

    ``names`` are the settings' names (e.g. min, max, bins). Reads the files written by
    "Save Feature Settings...", configs ({"features": {...}}) and the application's settings
    files (searched for such entries). Also reads two older forms: histogram
    "featuresettings" lists [min, max, bins, ...], and range filter lists of
    {"name", "rangelow", "rangehigh", "dropna"}.
    """
    allowed = set(names) | {"classname", "version"}

    def dict_settings(value) -> Optional[dict]:
        """{feature: {name: value}} with only these names."""
        if not isinstance(value, dict) or not value:
            return None
        if not all(
            isinstance(e, dict) and e and set(e) <= allowed for e in value.values()
        ):
            return None
        return {f: {k: v for k, v in e.items() if k in names} for f, e in value.items()}

    def histogram_lists(value) -> Optional[dict]:
        if names[:3] != ["min", "max", "bins"] or not isinstance(value, dict):
            return None
        rows = {}
        for feature, entry in value.items():
            if isinstance(entry, list) and len(entry) >= 3:
                rows[feature] = dict(zip(names, entry[:3]))
        return rows or None

    def range_filter_list(value) -> Optional[dict]:
        if not ({"low", "high"} <= set(names)) or not isinstance(value, list):
            return None
        from flim.configs.data import range_of_legacy

        rows = {
            e["name"]: {k: v for k, v in range_of_legacy(e).items() if k in names}
            for e in value
            if isinstance(e, dict)
            and "name" in e
            and ("rangelow" in e or "rangehigh" in e)
        }
        return rows or None

    def search(value) -> Optional[dict]:
        if isinstance(value, list):
            return range_filter_list(value)
        if not isinstance(value, dict):
            return None
        found = (
            dict_settings(value.get("features"))
            or dict_settings(value.get("range_filters"))
            or histogram_lists(value.get("featuresettings"))
            or dict_settings(value.get("featuresettings"))
            or dict_settings(value)
        )
        if found:
            return found
        for child in value.values():
            found = search(child)
            if found:
                return found
        return None

    return search(data)


def _cell_text(value) -> str:
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


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
    if spec.kind == "modelmap" and spec.role == "feature":
        return FeatureSettingsEditor
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


# small fields that need a row of their own (a text field and a button)
WIDE_KINDS = ("path",)


class FieldsPanel(wx.Panel):
    """Editors for the visible fields of a config class, with issue markers.

    Fields are shown in their order (flim.core.fields.field_order): small fields that
    follow each other share a grid of 2 or 3 columns (label, editor); lists and tables
    take the full width; nested configs are collapsible sections.
    """

    def __init__(self, parent, model: type, exclude=()):
        super().__init__(parent)
        self.model = model
        self.on_change: Optional[Callable[[], None]] = None
        self.editors: dict[str, Editor] = {}
        self.markers: dict[str, wx.StaticBitmap] = {}
        self.widgets: dict[str, list] = {}  # field -> its label and editor
        self.fixed: set = set()  # fields that allow only one value now (not shown)
        specs = [s for s in visible(describe(model)) if s.name not in exclude]
        large = {s.name: editor_for(model, s).expands for s in specs}
        specs = sorted(
            specs, key=lambda s: field_order(s, specs.index(s), large[s.name])
        )

        # in order: consecutive small fields share a grid (label, editor, marker);
        # lists, tables and nested sections take the full width between them
        sizer = wx.BoxSizer(wx.VERTICAL)
        small = []
        for spec in specs + [None]:  # None: the end
            if spec is not None and not large[spec.name]:
                if spec.kind in WIDE_KINDS:  # a row of its own
                    self._add_grid(sizer, small)
                    self._add_grid(sizer, [spec])
                    small = []
                else:
                    small.append(spec)
                continue
            self._add_grid(sizer, small)
            small = []
            if spec is None:
                break
            if spec.kind == "model":  # a collapsible section with its own title
                row = wx.BoxSizer(wx.HORIZONTAL)
                row.Add(self._editor(spec).control, 1, wx.EXPAND)
                row.Add(self._marker(spec), 0, wx.TOP, 4)
                sizer.Add(row, 0, wx.EXPAND | wx.ALL, 4)
                continue
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.Add(self._label(spec), 0, wx.RIGHT, 6)
            row.Add(self._marker(spec), 0)
            sizer.Add(row, 0, wx.LEFT | wx.TOP, 4)
            editor = self._editor(spec)
            sizer.Add(editor.control, 1 if editor.grows else 0, wx.EXPAND | wx.ALL, 4)
        self.SetSizer(sizer)

    def _add_grid(self, sizer, specs) -> None:
        """Small fields in a grid: 2 or 3 per row (one alone takes the row)."""
        if not specs:
            return
        n = len(specs)
        per_row = 1 if n == 1 else 2 if n in (2, 4) else 3
        grid = wx.FlexGridSizer(cols=3 * per_row, vgap=4, hgap=6)
        for i in range(per_row):
            grid.AddGrowableCol(3 * i + 1)
        for spec in specs:
            grid.Add(self._label(spec), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(self._editor(spec).control, 1, wx.EXPAND)
            grid.Add(self._marker(spec), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 4)

    def _label(self, spec):
        label = wx.StaticText(self, label=spec.title)
        if spec.description:
            label.SetToolTip(spec.description)
        self.widgets.setdefault(spec.name, []).append(label)
        return label

    def _editor(self, spec):
        editor = editor_for(self.model, spec)(self, spec)
        editor.on_change = self._on_editor_change
        self.editors[spec.name] = editor
        self.widgets.setdefault(spec.name, []).append(editor.control)
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
        """Lets editors that depend on other fields update (e.g. value choices), and
        hides the fields that allow only one value given the others."""
        for editor in self.editors.values():
            editor.refresh(self)
        allowed_values = getattr(self.model, "allowed_values", None)
        if allowed_values is None:
            return
        values = {name: self.value_of(name) for name in self.editors}
        allowed = allowed_values(values)
        for name, editor in self.editors.items():
            editor.set_allowed(allowed.get(name))
        fixed = {n for n, a in allowed.items() if len(a) == 1} & set(self.editors)
        if fixed == self.fixed:
            return
        self.fixed = fixed
        for name, widgets in self.widgets.items():
            for widget in widgets:
                widget.Show(name not in fixed)
            if name in fixed:
                self.markers[name].Hide()
        self.Layout()
        relayout(self)

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
        if severity is None or name in self.fixed:
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
