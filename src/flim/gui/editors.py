"""Editors for config fields: one wx control per field kind (`flim.core.fields`).

An editor shows a value (`set`), reads it back (`get`, raising `ValueError` for text
that is not a valid value) and calls `on_change` when the user edits it. Column
editors offer the columns of the input tables (`set_schema`).
"""

import json
import math
import os
import typing
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
import wx
import wx.grid
from pydantic import BaseModel

from flim.core.paths import with_extension
from flim.core.fields import FieldSpec, describe, field_order, title_of, visible
from flim.core.schema import TableSchema
from flim.core.validation import guess_column

NONE_LABEL = "(none)"


class Editor:
    """Base class of the field editors: one wx control that edits one config field.

    Subclasses implement `create`, `get` and `set`; the other methods do nothing
    unless a subclass overrides them.
    """

    expands = False  # takes the full width of the dialog (lists, tables)
    grows = True  # if it expands: also gets taller when the dialog does

    def __init__(self, parent: wx.Window, spec: FieldSpec) -> None:
        """Create the editor's control in `parent`.

        The field's description becomes the control's tooltip.

        Args:
            parent: The window that holds the control.
            spec: The field that the editor edits.
        """
        self.spec = spec
        self.on_change: Optional[Callable[["Editor"], None]] = None
        self.control = self.create(parent)
        if spec.description:
            self.control.SetToolTip(spec.description)

    def create(self, parent: wx.Window) -> wx.Window:
        """Create and return the editor's control; implemented by subclasses.

        Args:
            parent: The window that holds the control.

        Returns:
            The control, stored as `control`.
        """
        raise NotImplementedError

    def get(self) -> Any:
        """Return the edited value; implemented by subclasses.

        Raises:
            ValueError: If the edited text is not a valid value.
        """
        raise NotImplementedError

    def set(self, value: Any) -> None:
        """Show `value` in the control, without calling `on_change`.

        Implemented by subclasses.
        """
        raise NotImplementedError

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Take the schema of the input tables, e.g. to offer their columns.

        Args:
            schema: The input's columns; None if they are unknown.
        """

    def set_data(self, tables: list) -> None:
        """Take the selected input tables, e.g. for the ranges of their values.

        Args:
            tables: The selected input tables (DataFrames).
        """

    def show_issues(self, issues: list) -> None:
        """Show the issues of this field, e.g. by marking the table rows they are about.

        The dialog marks the field itself.

        Args:
            issues: The field's issues (`flim.core.config.Issue`), with paths into
                the field such as `features['FLIRR']`.
        """

    def refresh(self, panel: "FieldsPanel") -> None:
        """Update the editor after any field of the panel changed.

        For fields that depend on other fields, e.g. the values of a column named by
        another field.

        Args:
            panel: The panel that holds the editor.
        """

    def set_allowed(self, allowed: Optional[tuple]) -> None:
        """Offer only the values allowed now (see `BaseConfig.allowed_values`).

        Args:
            allowed: The allowed values; None if all values are allowed.
        """

    def changed(self, event: Optional[wx.Event] = None) -> None:
        """Call `on_change` after an edit; the event, if any, is skipped."""
        if self.on_change is not None:
            self.on_change(self)
        if event is not None:
            event.Skip()


class BoolEditor(Editor):
    """A bool that is not optional: a check box."""

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the check box."""
        control = wx.CheckBox(parent, label="")
        control.Bind(wx.EVT_CHECKBOX, self.changed)
        return control

    def get(self) -> Any:
        """Return whether the box is checked."""
        return self.control.GetValue()

    def set(self, value: Any) -> None:
        """Check the box if `value` is true."""
        self.control.SetValue(bool(value))


class ChoiceEditor(Editor):
    """A choice of one value: a `Literal`, or an optional bool (Automatic, Yes, No).

    An optional `Literal` also offers None, shown as `(none)`.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create a drop-down list of the field's values."""
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

    def _label(self, value: Any) -> str:
        """Return the label shown for a value."""
        if value is None:
            return NONE_LABEL
        return str(self.spec.labels.get(value, value))

    def get(self) -> Any:
        """Return the selected value.

        Raises:
            ValueError: If no value is selected.
        """
        index = self.control.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Select a value")
        return self.values[index]

    def set(self, value: Any) -> None:
        """Select `value`; a value that is not offered is ignored."""
        if value in self.values:
            self.control.SetSelection(self.values.index(value))

    def set_allowed(self, allowed: Optional[tuple]) -> None:
        """Offer only the allowed values (None: all of the field's values).

        The selected value stays selected if it is allowed; otherwise the first
        allowed value is selected.
        """
        values = [v for v in self.all_values if allowed is None or v in allowed]
        if values == self.values:
            return
        current = self.values[self.control.GetSelection()] if self.values else None
        self.values = values
        self.control.Set([self._label(v) for v in values])
        # keep the value if still allowed, else the first allowed
        self.control.SetSelection(values.index(current) if current in values else 0)


class TextEditor(Editor):
    """Text, numbers typed as text, and lists typed as one line of text.

    Used for the kinds text, int (optional), float, number, mixed (a combo box of
    the choices, or a number) and numbers, and for fields with `words`, `escapes` or
    `chars`.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create a text field; for the kind mixed, a combo box of the choices."""
        if self.spec.kind == "mixed":
            control = wx.ComboBox(parent, choices=[str(c) for c in self.spec.choices])
        else:
            control = wx.TextCtrl(parent)
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def get(self) -> Any:
        """Return the value of the text.

        - `chars`: the distinct characters of the text (after `unescape`); a text
          that starts with `[` is read as a JSON list.
        - `escapes`: the text after `unescape`; spaces are kept.
        - Otherwise the text is stripped. `words`: the entries separated by commas,
          each stripped; empty entries are kept, an empty text gives an empty list.
        - An empty text of an optional field is None.
        - text: the text. numbers: the numbers separated by commas or semicolons,
          of the field's item type. mixed: the choice with this text, else a number.
          int, float: a number of that type. Other kinds: an int if the text is
          written as an int, else a float.

        Raises:
            ValueError: If a `chars` text that starts with `[` is not a JSON list, or
                a text is not a number.
        """
        if self.spec.chars:  # each character one entry; JSON for longer entries
            text = self.control.GetValue()
            if text.strip().startswith("["):
                try:
                    return json.loads(text)
                except ValueError:
                    raise ValueError("not a valid list, e.g. [\"::\", \"-\"]") from None
            return list(dict.fromkeys(unescape(text)))
        if self.spec.escapes:  # spaces may be part of the value, tabs are typed as \t
            return unescape(self.control.GetValue())
        text = self.control.GetValue().strip()
        kind = self.spec.kind
        if self.spec.words:  # empty entries are kept: "a, , b" has three
            return [t.strip() for t in text.split(",")] if text else []
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
    def _number(text: str, kind: Optional[type] = None) -> float:
        """Return `text` as an int or float (`kind`; None: as written); else raise."""
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

    def set(self, value: Any) -> None:
        """Show `value` as text.

        None is an empty text. `chars`: the characters as one text (with `escape`),
        or a JSON list if an entry is longer than one character. Other lists: the
        entries separated by commas. `escapes`: the text with `escape`.
        """
        if value is None:
            text = ""
        elif self.spec.chars:
            values = [str(v) for v in value]
            text = escape("".join(values)) if all(len(v) == 1 for v in values) else json.dumps(values)
        elif isinstance(value, (list, tuple)):
            text = ", ".join(str(v) for v in value)
        elif self.spec.escapes:
            text = escape(str(value))
        else:
            text = str(value)
        self.control.ChangeValue(text)


def escape(text: str) -> str:
    r"""Return `text` with its backslashes as `\\` and its tabs as `\t`.

    Args:
        text: The text.

    Returns:
        The text as it is typed in an editor.
    """
    return text.replace("\\", "\\\\").replace("\t", "\\t")


def unescape(text: str) -> str:
    r"""Return `text` with `\t` as a tab and `\\` as a backslash.

    The reverse of `escape`. Other backslashes are kept.

    Args:
        text: The text as typed in an editor.

    Returns:
        The text.
    """
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in "t\\":
            out.append("\t" if text[i + 1] == "t" else "\\")
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


class IntEditor(Editor):
    """An int that is not optional: a spin control within the field's bounds.

    Without bounds, the limits are -10**9 and 10**9.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the spin control, limited to the field's bounds."""
        bounds = self.spec.bounds
        low = bounds.get("ge", bounds["gt"] + 1 if "gt" in bounds else -(10**9))
        high = bounds.get("le", bounds["lt"] - 1 if "lt" in bounds else 10**9)
        control = wx.SpinCtrl(parent, min=int(low), max=int(high))
        control.Bind(wx.EVT_SPINCTRL, self.changed)
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def get(self) -> Any:
        """Return the number."""
        return self.control.GetValue()

    def set(self, value: Any) -> None:
        """Show the number `value`."""
        self.control.SetValue(int(value))


def set_combo_items(combo: wx.ComboBox, items: list) -> None:
    """Replace the items of a combo box.

    The items are deleted one by one: `Set` appends to them on macOS, and `Clear`
    only clears the text.

    Args:
        combo: The combo box.
        items: The new items (texts).
    """
    for index in reversed(range(combo.GetCount())):
        combo.Delete(index)
    if items:
        combo.Append(items)


def fit_rows(
    control: wx.Window, rows: int, fewest: int = 3, most: int = 10, fixed: bool = False
) -> None:
    """Make a list control tall enough for `rows` items.

    The number of rows is limited to `fewest` .. `most`. The control's parent is laid
    out again.

    Args:
        control: The list control.
        rows: The number of items.
        fewest: The smallest number of rows. Defaults to 3.
        most: The largest number of rows. Defaults to 10.
        fixed: Whether the height is also the maximum height, for lists that do not
            grow with the dialog. Defaults to False.
    """
    height = control.GetCharHeight() + 6  # about one row of a list
    size = (-1, max(fewest, min(rows, most)) * height + 6)
    control.SetMinSize(size)
    if fixed:
        control.SetMaxSize(size)
        control.SetInitialSize(size)
    control.GetParent().Layout()


class ColumnEditor(Editor):
    """One column of the input: a combo box of the input's columns of the field's role.

    Any name can be typed.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the combo box; `set_schema` offers the columns."""
        control = wx.ComboBox(parent, choices=[])
        control.Bind(wx.EVT_COMBOBOX, self.changed)
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Offer the input's columns of the field's role; the text is kept.

        An optional field also offers an empty entry, first.
        """
        value = self.control.GetValue()
        names = [] if schema is None else schema.by_role(self.spec.role)
        set_combo_items(self.control, ([""] if self.spec.optional else []) + names)
        self.control.ChangeValue(value)

    def get(self) -> Any:
        """Return the column name, stripped; None if empty and the field is optional.

        Raises:
            ValueError: If the text is empty and the field is not optional.
        """
        value = self.control.GetValue().strip()
        if value == "":
            if self.spec.optional:
                return None
            raise ValueError("Select a column")
        return value

    def set(self, value: Any) -> None:
        """Show the column name; None as an empty text."""
        self.control.ChangeValue("" if value is None else str(value))

    def set_allowed(self, allowed: Optional[tuple]) -> None:
        """Offer only the allowed columns, e.g. the selected features.

        With None or fewer than two allowed values, the offered columns stay as they
        are. The text is kept if it is allowed, else the first allowed column is
        shown.
        """
        if allowed is None or len(allowed) < 2:
            return
        names = [str(a) for a in allowed if a is not None]
        if names == self.control.GetItems():
            return
        value = self.control.GetValue()
        set_combo_items(self.control, names)
        self.control.ChangeValue(value if value in names else names[0])


class ValueEditor(Editor):
    """A value of the category column named by another field (`column_field`)."""

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the combo box; `refresh` offers the column's values."""
        control = wx.ComboBox(parent, choices=[])
        control.Bind(wx.EVT_COMBOBOX, self.changed)
        control.Bind(wx.EVT_TEXT, self.changed)
        self.schema = None
        return control

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Keep the input's schema, which lists the values of category columns."""
        self.schema = schema

    def refresh(self, panel: "FieldsPanel") -> None:
        """Offer the values of the column named by the `column_field` field.

        If that field is a list of columns (e.g. grouping), its first column is used.
        """
        column = panel.value_of(self.spec.column_field)
        if isinstance(column, list):  # e.g. grouping: its first column
            column = column[0] if column else None
        self.update_choices(column)

    def update_choices(self, column: Optional[str]) -> None:
        """Offer the values (levels) of `column` that the input's schema lists.

        Without a schema, a column, or listed values, no values are offered. The text
        is kept.

        Args:
            column: The column name; None for none.
        """
        info = None if self.schema is None or not column else self.schema.column(column)
        levels = (
            [] if info is None or info.levels is None else [str(v) for v in info.levels]
        )
        value = self.control.GetValue()
        if levels != self.control.GetItems():
            set_combo_items(self.control, levels)
            self.control.ChangeValue(value)

    def get(self) -> Any:
        """Return the text, stripped; None if empty and the field is optional."""
        value = self.control.GetValue().strip()
        if value == "" and self.spec.optional:
            return None
        return value

    def set(self, value: Any) -> None:
        """Show the value; None as an empty text."""
        self.control.ChangeValue("" if value is None else str(value))


class _CheckList(Editor):
    """Checked items of a list, in list order, with Select All and Deselect All."""

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the check list, its buttons, and the `extra_controls` above it."""
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

    def extra_controls(self, panel: wx.Panel, sizer: wx.BoxSizer) -> None:
        """Add controls above the list; none in this class.

        Args:
            panel: The editor's panel, the parent of the controls.
            sizer: The panel's sizer, to add the controls to.
        """
        pass

    def set_items(self, items: Sequence[Any], checked: Sequence[Any]) -> None:
        """List `items` and check the items in `checked`.

        Checked items that are not in `items` are listed after them. Line breaks in
        items are shown as spaces. The list is made tall enough for up to 10 items.

        Args:
            items: The items to list.
            checked: The items to check.
        """
        self.items = list(items) + [c for c in checked if c not in items]
        self.list.Set([str(i).replace("\n", " ") for i in self.items])
        self.list.SetCheckedItems([self.items.index(c) for c in checked])
        fit_rows(self.list, len(self.items), most=10)

    def checked(self) -> list:
        """Return the checked items, in list order."""
        return [self.items[i] for i in self.list.GetCheckedItems()]

    def check_all(self, checked: bool) -> None:
        """Check all items, or uncheck all, and call `on_change`.

        Args:
            checked: Whether to check the items.
        """
        self.list.SetCheckedItems(list(range(len(self.items))) if checked else [])
        self.changed()


class MultiChoiceEditor(_CheckList):
    """Several of the field's choices: a check list of them."""

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the check list of the field's choices."""
        panel = super().create(parent)
        self.set_items(self.spec.choices, [])
        return panel

    def get(self) -> Any:
        """Return the checked choices, in the order of the choices."""
        return self.checked()

    def set(self, value: Any) -> None:
        """Check the choices that are in `value`."""
        self.set_items(self.spec.choices, [v for v in self.spec.choices if v in value])


class FewChoicesEditor(Editor):
    """A few choices to check (up to `FEW_CHOICES`): one check box each.

    The check boxes are shown one under the other, without a list box.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create a check box for each of the field's choices."""
        self.panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.boxes = {}
        for choice in self.spec.choices:
            box = wx.CheckBox(self.panel, label=str(choice))
            box.Bind(wx.EVT_CHECKBOX, self.changed)
            sizer.Add(box, 0, wx.BOTTOM, 2)
            self.boxes[choice] = box
        self.panel.SetSizer(sizer)
        return self.panel

    def get(self) -> Any:
        """Return the checked choices, in the order of the choices."""
        return [c for c in self.spec.choices if self.boxes[c].GetValue()]

    def set(self, value: Any) -> None:
        """Check the choices that are in `value` (None: none)."""
        for choice, box in self.boxes.items():
            box.SetValue(choice in (value or []))


FEW_CHOICES = 4  # multi-choice fields with up to this many choices: FewChoicesEditor


def _one_line(name: Any) -> str:
    """Return `name` as text, with line breaks as spaces."""
    return str(name).replace("\n", " ")


class FeaturesEditor(_CheckList):
    """Feature columns, or `all` (if the field allows it): a check list.

    The input's features are listed. The features of the settings (the wanted ones)
    are checked as `_shown` describes.
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the check list; checking an item calls `_on_check`."""
        panel = super().create(parent)
        self.list.Unbind(wx.EVT_CHECKLISTBOX)
        self.list.Bind(wx.EVT_CHECKLISTBOX, self._on_check)
        return panel

    def extra_controls(self, panel: wx.Panel, sizer: wx.BoxSizer) -> None:
        """Add the note of guessed features and, if allowed, the All features box.

        Args:
            panel: The editor's panel, the parent of the controls.
            sizer: The panel's sizer, to add the controls to.
        """
        self.all = None
        self.selection: list = []  # the selection before "All features" was checked
        self.wanted: list = []  # the features to check
        self.features: list = []  # the input's features
        self.known = False  # all of the input's features are known
        self.note = wx.StaticText(panel, label="")  # the features guessed
        self.note.SetForegroundColour(wx.Colour(120, 120, 120))
        self.note.Hide()
        sizer.Add(self.note, 0, wx.BOTTOM, 3)
        if self.spec.allow_all:
            self.all = wx.CheckBox(panel, label="All features")
            self.all.Bind(wx.EVT_CHECKBOX, self._on_all)
            sizer.Add(self.all, 0, wx.BOTTOM, 3)

    def is_all(self) -> bool:
        """Return whether All features is checked."""
        return self.all is not None and self.all.GetValue()

    def _show_all(self, is_all: bool) -> None:
        """All features: all shown checked, the list and its buttons disabled."""
        if is_all:
            self.list.SetCheckedItems(list(range(len(self.items))))
        for control in [self.list] + self.buttons:
            control.Enable(not is_all)

    def _on_all(self, event: wx.CommandEvent) -> None:
        """Check or uncheck All features; unchecking restores the earlier checks."""
        if self.is_all():
            self.selection = self.checked()
        elif self.selection:  # back to the selection made before; else all stay checked
            self.list.SetCheckedItems(
                [self.items.index(f) for f in self.selection if f in self.items]
            )
        self._show_all(self.is_all())
        self.changed(event)

    def _remember(self) -> None:
        """Keep the checked features as the wanted ones."""
        self.wanted = self.checked()

    def _on_check(self, event: wx.CommandEvent) -> None:
        """Keep the checked features and call `on_change`."""
        self._remember()
        self.changed(event)

    def check_all(self, checked: bool) -> None:
        """Check all features, or uncheck all, keep them and call `on_change`.

        Args:
            checked: Whether to check the features.
        """
        self.list.SetCheckedItems(list(range(len(self.items))) if checked else [])
        self._remember()
        self.changed()

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """List the input's features of the field's role, the wanted ones checked."""
        if not self.is_all():
            self._remember()
        self.known = schema is not None and schema.complete
        self.features = [] if schema is None else schema.by_role(self.spec.role)
        self.set_items(self.features, [] if self.is_all() else self._shown())
        self._show_all(self.is_all())

    def _shown(self) -> list:
        """Return the wanted features to show checked.

        If all of the input's features are known: those the input has; a wanted
        feature the input lacks is replaced by the closest of its features (a guess,
        named in a note) if there is one, else ignored. Otherwise all wanted features
        (they may be in the input).
        """
        if not self.known:
            self._show_note([])
            return list(self.wanted)
        shown, notes = [], []
        for f in self.wanted:
            if f in self.features:
                shown.append(f)
                continue
            guess, _ = guess_column(f, self.features)
            if guess is not None and guess not in self.wanted:
                shown.append(guess)
                notes.append(f"{_one_line(f)} → {_one_line(guess)}")
        self._show_note(["Guessed: " + ", ".join(notes)] if notes else [])
        return list(dict.fromkeys(shown))

    def _show_note(self, lines: list[str]) -> None:
        """Show the note with these lines; hide it if there are none."""
        if lines:
            self.note.SetLabel("\n".join(lines))
            self.note.SetToolTip(self.note.GetLabel())
        if bool(lines) != self.note.IsShown():
            self.note.Show(bool(lines))
            self.panel.Layout()

    def get(self) -> Any:
        """Return `all` if All features is checked, else the checked features."""
        if self.is_all():
            return "all"
        return self.checked()

    def set(self, value: Any) -> None:
        """Check the features in `value`, or All features for `all` (see `_shown`)."""
        is_all = value == "all"
        if self.all is not None:
            self.all.SetValue(is_all)
        self.selection = []
        self.wanted = [] if is_all or value is None else list(value)
        self.set_items(self.features, self._shown())
        self._show_all(is_all)


class CategoriesEditor(Editor):
    """Category columns in a chosen order (grouping): check them and move them.

    The input's category columns are listed; those of the settings are checked if
    the input has them, the others are ignored.
    """

    expands = True
    grows = False  # as tall as its columns

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the list of columns with its move buttons.

        An optional field also gets an Automatic check box (None: the tool chooses).
        """
        self.panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.automatic = None
        if self.spec.optional:  # None: chosen by the tool
            self.automatic = wx.CheckBox(self.panel, label="Automatic")
            self.automatic.Bind(wx.EVT_CHECKBOX, self._on_automatic)
            sizer.Add(self.automatic, 0, wx.BOTTOM, 3)
        self.items: list = []  # the columns listed
        self.columns: list = []  # the input's category columns
        self.known = False  # all of the input's columns are known
        self.wanted: list = []  # the columns to check, in their order
        self.rearrange = wx.RearrangeCtrl(self.panel, order=[], items=[])
        self.rearrange.GetList().Bind(wx.EVT_CHECKLISTBOX, self._on_check)
        for button in self.rearrange.GetChildren():
            if isinstance(button, wx.Button):
                button.Bind(wx.EVT_BUTTON, self._on_move)
        sizer.Add(self.rearrange, 1, wx.EXPAND)
        self.panel.SetSizer(sizer)
        return self.panel

    def _on_check(self, event: wx.CommandEvent) -> None:
        """Keep the checked columns and call `on_change`."""
        self._remember()
        self.changed(event)

    def _on_move(self, event: wx.CommandEvent) -> None:
        """After a move button, keep the new order once the list has moved the item."""
        event.Skip()
        wx.CallAfter(self._moved)

    def _moved(self) -> None:
        """Keep the checked columns in their new order and call `on_change`."""
        self._remember()
        self.changed()

    def _on_automatic(self, event: wx.CommandEvent) -> None:
        """Disable the list while Automatic is checked, and call `on_change`."""
        self.rearrange.Enable(not self.automatic.GetValue())
        self.changed(event)

    def _remember(self) -> None:
        """Keep the checked columns, in their order, as the wanted ones."""
        self.wanted = self.checked()

    def _show(self) -> None:
        """List the input's columns, the wanted ones checked and first, in their order.

        If the input's columns are not all known (e.g. a workflow step's input before
        the run), the wanted ones are listed too.
        """
        if self.known:
            items = list(self.columns)
            checked = [w for w in self.wanted if w in items]
        else:
            items = list(self.columns) + [w for w in self.wanted if w not in self.columns]
            checked = list(self.wanted)
        self.items = items
        order = [items.index(c) for c in checked] + [
            ~i for i, item in enumerate(items) if item not in checked
        ]
        labels = [items[i if i >= 0 else ~i] for i in order]
        rearrange_list = self.rearrange.GetList()
        rearrange_list.Set(labels)
        for position, i in enumerate(order):
            rearrange_list.Check(position, i >= 0)
        fit_rows(rearrange_list, len(labels), fewest=2, most=8, fixed=True)

    def checked(self) -> list:
        """Return the checked columns, in their order in the list."""
        rearrange_list = self.rearrange.GetList()
        return [
            rearrange_list.GetString(i)
            for i in range(rearrange_list.GetCount())
            if rearrange_list.IsChecked(i)
        ]

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """List the input's columns of the field's role, the wanted ones checked."""
        self._remember()
        self.known = schema is not None and schema.complete
        self.columns = [] if schema is None else schema.by_role(self.spec.role)
        self._show()

    def get(self) -> Any:
        """Return the checked columns in their order; None if Automatic is checked."""
        if self.automatic is not None and self.automatic.GetValue():
            return None
        return self.checked()

    def set(self, value: Any) -> None:
        """Check the columns in `value`, in its order; None checks Automatic."""
        if self.automatic is not None:
            self.automatic.SetValue(value is None)
            self.rearrange.Enable(value is not None)
        self.wanted = [] if value is None else list(value)
        self._show()


class PathEditor(Editor):
    """A path: a file picker with a text field."""

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the file picker."""
        control = wx.FilePickerCtrl(parent, style=wx.FLP_USE_TEXTCTRL | wx.FLP_OPEN)
        control.Bind(wx.EVT_FILEPICKER_CHANGED, self.changed)
        return control

    def get(self) -> Any:
        """Return the path; None if it is empty and the field is optional."""
        path = self.control.GetPath()
        if not path and self.spec.optional:
            return None
        return Path(path)

    def set(self, value: Any) -> None:
        """Show the path; None as an empty text."""
        self.control.SetPath("" if value is None else str(value))


class PathsEditor(Editor):
    """A list of paths: a list box with Add... and Remove buttons."""

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the list box and its buttons."""
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

    def _on_add(self, event: wx.CommandEvent) -> None:
        """Add the files selected in a file dialog."""
        with wx.FileDialog(
            self.control, "Select files", style=wx.FD_OPEN | wx.FD_MULTIPLE
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.set(self.get() + [Path(p) for p in dialog.GetPaths()])
                self.changed()

    def _on_remove(self, event: wx.CommandEvent) -> None:
        """Remove the selected paths."""
        for index in sorted(self.list.GetSelections(), reverse=True):
            self.list.Delete(index)
        self.changed()

    def get(self) -> Any:
        """Return the listed paths."""
        return [Path(p) for p in self.list.GetItems()]

    def set(self, value: Any) -> None:
        """List the paths in `value` (None: none)."""
        self.list.Set([str(p) for p in value or []])


def relayout(window: wx.Window) -> None:
    """Fit the dialog of `window` to fields that appeared or disappeared.

    Calls the top-level window's `fit_contents` if it has one, else its `Layout`.

    Args:
        window: A window in the dialog.
    """
    top = wx.GetTopLevelParent(window)
    if hasattr(top, "fit_contents"):
        top.fit_contents()
    elif top is not None:
        top.Layout()


class ModelEditor(Editor):
    """A nested config: its fields in a titled group, or in a collapsed section.

    The collapsed section is for an advanced field
    (`Field(json_schema_extra={"advanced": True})`, or a class with `advanced = True`,
    such as `Resources`).
    """

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create a `FieldsPanel` of the nested config in a group or a section."""
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

    def get(self) -> Any:
        """Return the values of the config last set, with the edited ones, as a dict.

        Raises:
            ValueError: If text in the nested fields is not valid; the message names
                each such field.
        """
        try:
            return self.fields.values(self.value)
        except FieldErrors as err:
            raise ValueError(
                "; ".join(f"{k}: {v}" for k, v in err.errors.items())
            ) from None

    def set(self, value: Any) -> None:
        """Show the fields of the nested config `value`."""
        self.value = value
        self.fields.set_values(value)

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Pass the input's schema to the nested fields."""
        self.fields.set_schema(schema)

    def set_data(self, tables: list) -> None:
        """Pass the input tables to the nested fields."""
        self.fields.set_data(tables)


class _RowIssues:
    """Marks the rows of a grid editor that issues are about (`_row_of`).

    A row with issues gets a marker, drawn by `_MarkedTextRenderer`, and the issues'
    messages as its tooltip.
    """

    def _init_row_issues(self) -> wx.grid.GridCellAttr:
        """Set up the marks; return a cell attribute that draws them."""
        self.marks: dict = {}  # row -> severity of its issues
        self.row_messages: dict = {}  # row -> its issues' messages
        attr = wx.grid.GridCellAttr()
        attr.SetRenderer(_MarkedTextRenderer(self.marks))
        return attr

    def show_issues(self, issues: list) -> None:
        """Mark the rows that the issues are about with their most severe issue.

        Issues about no row are ignored.

        Args:
            issues: The field's issues (`flim.core.config.Issue`).
        """
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

    def _on_motion(self, event: wx.MouseEvent) -> None:
        """Show the issues' messages of the row under the mouse as the tooltip."""
        x, y = self.grid.CalcUnscrolledPosition(event.GetPosition())
        messages = self.row_messages.get(self.grid.YToRow(y))
        window = self.grid.GetGridWindow()
        text = "\n".join(messages) if messages else ""
        if window.GetToolTipText() != text:
            window.SetToolTip(text)
        event.Skip()


SEVERITIES = ("error", "guessed", "skipped", "warning")  # first: most severe


class ModelsEditor(_RowIssues, Editor):
    """A list of nested configs (with simple fields) as an editable table.

    Subclasses may add buttons (`extra_buttons`) and a first column for dict keys
    (`key_title`: the value is then a dict key -> config).
    """

    expands = True
    key_title = None

    def extra_buttons(self) -> list:
        """Return (label, handler) of further buttons below the table; none here."""
        return []

    def _columns(self) -> list:
        """The fields shown as columns."""
        return [
            s
            for s in visible(describe(self.spec.model))
            if s.kind not in ("model", "models", "variants")
        ]

    def _column_choices(self) -> dict:
        """The values offered per column (name -> values); bool fields: yes, no."""
        choices = {c.name: c.choices for c in self.columns if c.choices}
        choices.update({c.name: ("yes", "no") for c in self.columns if c.kind == "bool"})
        return choices

    def _cell_text(self, column: FieldSpec, value: Any) -> str:
        """The text of a cell: lists comma separated, dicts as `key=value`."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            return ", ".join(f"{k}={v}" for k, v in value.items())
        if getattr(column, "escapes", False):
            return escape(str(value))
        return str(value)

    def _cell_value(self, column: FieldSpec, text: str) -> Any:
        """The value of a cell's text, as the config's validation takes it."""
        container = self.containers.get(column.name)
        if container is list:
            return [t.strip() for t in text.split(",") if t.strip()]
        if container is dict:
            pairs = [t.split("=", 1) for t in text.split(",") if t.strip()]
            if any(len(p) != 2 for p in pairs):
                raise ValueError(f"{column.title}: write key=value, e.g. const=3100")
            return {k.strip(): v.strip() for k, v in pairs}
        return text

    def _containers(self) -> dict:
        """List and dict fields by name (their cells are converted)."""
        models = self.spec.variants or (self.spec.model,)
        containers = {}
        for model in models:
            for name, info in model.model_fields.items():
                origin = typing.get_origin(info.annotation)
                if origin in (list, dict):
                    containers[name] = origin
        return containers

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the table and its Add, Remove and further buttons.

        The table has a column per field (`_columns`), after the key column if there
        is one.
        """
        self.columns = self._columns()
        self.containers = self._containers()
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
        self._set_choices(self._column_choices())
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
        """Return what a row is, for the buttons: "Rules" → "Rule"; else "Row"."""
        title = self.spec.title
        return title[:-1] if title.endswith("s") and len(title) > 1 else "Row"

    def _set_choices(self, choices: dict) -> None:
        """Edit the cells of the columns in `choices` with a drop-down of the values.

        `choices` maps a field name to its values; other columns are edited as text.
        The first column marks rows with issues.
        """
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

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Offer the input's columns of the role in the cells of column fields.

        Without a schema, the cells stay as they are.
        """
        # column cells: a drop-down of the input's columns of the role (unknown: text)
        if schema is None:
            return
        choices = self._column_choices()
        for column in self.columns:
            if column.kind == "column":
                choices[column.name] = schema.by_role(column.role)
        self._set_choices(choices)

    def _row_of(self, path: Optional[str]) -> Optional[int]:
        """Return the row a path into this field is about; None if none.

        Paths are like `rules[1].min` (a list) or `ranges['FLIRR']` (a dict with its
        keys in the first column).
        """
        rest = (path or "")[len(self.spec.name) :].lstrip(".")
        if self.key_title:
            rest = rest.removeprefix("['")
            keys = [key for key, _ in self.rows()]
            matches = [i for i, k in enumerate(keys) if k and rest.startswith(k)]
            return max(matches, key=lambda i: len(keys[i])) if matches else None
        number = rest.removeprefix("[").split("]")[0].split(".")[0]
        return int(number) if number.isdigit() else None

    def _on_add(self, event: wx.CommandEvent) -> None:
        """Add an empty row."""
        self.grid.AppendRows(1)
        self.changed()

    def _on_remove(self, event: wx.CommandEvent) -> None:
        """Remove the selected rows and the row of the cursor."""
        rows = sorted(
            set(self.grid.GetSelectedRows()) | {self.grid.GetGridCursorRow()},
            reverse=True,
        )
        for row in rows:
            if 0 <= row < self.grid.GetNumberRows():
                self.grid.DeleteRows(row)
        self.changed()

    def rows(self) -> list[tuple[str, dict]]:
        """Return (key, values) of each row.

        Empty cells are left out. The texts of `escapes` fields are unescaped and keep
        their spaces; other texts are stripped, and those of list and dict fields
        converted; the config's validation converts the rest. The key is empty
        without a key column.

        Raises:
            ValueError: If the text of a dict field is not written as `key=value`.
        """
        rows = []
        for row in range(self.grid.GetNumberRows()):
            values = {}
            for col, column in enumerate(self.columns):
                text = self.grid.GetCellValue(row, col + self.offset)
                if getattr(column, "escapes", False):  # spaces are part of the value
                    if text != "":
                        values[column.name] = unescape(text)
                    continue
                text = text.strip()
                if text != "":
                    values[column.name] = self._cell_value(column, text)
            key = self.grid.GetCellValue(row, 0).strip() if self.key_title else ""
            rows.append((key, values))
        return rows

    def add_row(self, values: dict, key: str = "") -> None:
        """Add a row with the values of a config.

        Args:
            values: The config's values by field name; fields not shown are ignored.
            key: The text of the key column, if there is one. Defaults to "".
        """
        row = self.grid.GetNumberRows()
        self.grid.AppendRows(1)
        if self.key_title:
            self.grid.SetCellValue(row, 0, key)
        for col, column in enumerate(self.columns):
            self.grid.SetCellValue(
                row, col + self.offset, self._cell_text(column, values.get(column.name))
            )

    def get(self) -> Any:
        """Return the values of the rows as dicts.

        Returns:
            A list of the rows' values; with a key column, a dict key -> values,
            without the rows that have no key.

        Raises:
            ValueError: If the text of a dict field is not written as `key=value`.
        """
        if self.key_title:
            return {key: values for key, values in self.rows() if key}
        return [values for _, values in self.rows()]

    def set(self, value: Any) -> None:
        """Show a row per config of `value`, a list or a dict by key (None: none)."""
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


class VariantsEditor(ModelsEditor):
    """A list of configs of several kinds as one table.

    For example Calculate's expressions and functions: a column for the kind, then
    the fields of all kinds. Cells of fields that a row's kind does not have are
    greyed out and not editable.

    Kinds with nested lists (e.g. filter groups) are shown, with their simple fields
    editable, but cannot be chosen for a row; their nested values are kept as they are.
    """

    INACTIVE = wx.Colour(225, 225, 225)

    def _columns(self) -> list:
        """Return the kind and the simple fields of all kinds; set the kinds' fields."""
        disc = self.spec.discriminator
        per_kind, self.nested = {}, set()
        for variant in self.spec.variants:
            specs = describe(variant)
            simple = [
                s
                for s in visible(specs)
                if s.kind not in ("model", "models", "variants") and s.name != disc
            ]
            nested = any(s.kind in ("models", "variants") for s in specs)
            for kind in typing.get_args(variant.model_fields[disc].annotation):
                per_kind[kind] = simple
                if nested:
                    self.nested.add(kind)
        self.kind_fields = {k: {s.name for s in v} for k, v in per_kind.items()}
        shared_names = set.intersection(*self.kind_fields.values())
        order = list(self.spec.variants[0].model_fields)
        shared = [s for s in next(iter(per_kind.values())) if s.name in shared_names]
        before = [s for s in shared if order.index(s.name) < order.index(disc)]
        after = [s for s in shared if s not in before]
        own, seen = [], set()
        for specs in per_kind.values():
            for s in specs:
                if s.name not in shared_names and s.name not in seen:
                    own.append(s)
                    seen.add(s.name)
        info = self.spec.variants[0].model_fields[disc]
        kind = FieldSpec(
            name=disc,
            title=info.title or title_of(disc),
            kind="choice",
            description=info.description or "",
            choices=tuple(k for k in per_kind if k not in self.nested),
        )
        return before + [kind] + own + after

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the table; `originals` keeps the values each row was set with."""
        self.originals: list[dict] = []  # per row: the values it was set with
        return super().create(parent)

    def _kind_column(self) -> int:
        """Return the grid column of the kind."""
        names = [c.name for c in self.columns]
        return names.index(self.spec.discriminator) + self.offset

    def _apply_kind(self, row: int) -> None:
        """Grey out and clear the cells of fields the row's kind does not have.

        The kind of a row with nested values cannot be changed.
        """
        kind = self.grid.GetCellValue(row, self._kind_column()).strip()
        fields = self.kind_fields.get(kind)
        for col, column in enumerate(self.columns):
            col += self.offset
            is_kind = column.name == self.spec.discriminator
            active = fields is None or column.name in fields or is_kind
            self.grid.SetReadOnly(row, col, not active or (is_kind and kind in self.nested))
            if active and not (is_kind and kind in self.nested):
                self.grid.SetCellBackgroundColour(row, col, self.grid.GetDefaultCellBackgroundColour())
            else:
                if not active:
                    self.grid.SetCellValue(row, col, "")
                self.grid.SetCellBackgroundColour(row, col, self.INACTIVE)

    def changed(self, event: Optional[wx.Event] = None) -> None:
        """Apply the kind of an edited row, then call `on_change`."""
        if isinstance(event, wx.grid.GridEvent) and event.GetRow() >= 0:
            self._apply_kind(event.GetRow())
            self.grid.ForceRefresh()
        super().changed(event)

    def _on_add(self, event: wx.CommandEvent) -> None:
        """Add a row of the first kind that can be chosen, with its defaults."""
        kind = self.columns[self._kind_column() - self.offset].choices[0]
        variant = next(
            v
            for v in self.spec.variants
            if kind in typing.get_args(v.model_fields[self.spec.discriminator].annotation)
        )
        self.add_row(variant(**{self.spec.discriminator: kind}).model_dump())
        self.changed()

    def _on_remove(self, event: wx.CommandEvent) -> None:
        """Remove the selected rows and the row of the cursor, with their originals."""
        rows = sorted(
            set(self.grid.GetSelectedRows()) | {self.grid.GetGridCursorRow()},
            reverse=True,
        )
        for row in rows:
            if 0 <= row < self.grid.GetNumberRows():
                self.grid.DeleteRows(row)
                del self.originals[row]
        self.changed()

    def add_row(self, values: dict, key: str = "") -> None:
        """Add a row with the values of a config, and keep the values.

        The kept values supply the values the table does not show (see `rows`).

        Args:
            values: The config's values by field name.
            key: The text of the key column, if there is one. Defaults to "".
        """
        super().add_row(values, key)
        self.originals.append(dict(values))
        self._apply_kind(self.grid.GetNumberRows() - 1)

    def set(self, value: Any) -> None:
        """Show a row per config of `value`."""
        self.originals = []
        super().set(value)

    def rows(self) -> list[tuple[str, dict]]:
        """Return (key, values) of each row.

        Fields that the row's kind does not have are left out. While a row keeps the
        kind it was set with, its values that the table does not show (e.g. a group's
        filters) are taken from the values it was set with.

        Raises:
            ValueError: If the text of a dict field is not written as `key=value`.
        """
        rows = []
        shown = {c.name for c in self.columns}
        disc = self.spec.discriminator
        for (key, values), original in zip(super().rows(), self.originals):
            fields = self.kind_fields.get(values.get(disc))
            if fields is not None:
                values = {k: v for k, v in values.items() if k in fields or k == disc}
            if original.get(disc) == values.get(disc):
                # values not shown (e.g. a group's filters) stay as they were
                values = {
                    **{k: v for k, v in original.items() if k not in shown and v is not None},
                    **values,
                }
            rows.append((key, values))
        return rows


class ModelMapEditor(ModelsEditor):
    """A dict of nested configs by key (e.g. per feature): the key is the first column."""

    @property
    def key_title(self) -> str:
        """Return the key column's title by role: Feature, Column or Key."""
        return {"feature": "Feature", "category": "Column"}.get(self.spec.role, "Key")


class _MarkedTextRenderer(wx.grid.GridCellStringRenderer):
    """Draws a cell's text and, in rows with issues, the issue marker at its right."""

    def __init__(self, marks: dict) -> None:
        """Create the renderer.

        Args:
            marks: The severity of the issues by row, shared with the editor.
        """
        super().__init__()
        self.marks = marks  # row -> severity

    def Draw(
        self,
        grid: wx.grid.Grid,
        attr: wx.grid.GridCellAttr,
        dc: wx.DC,
        rect: wx.Rect,
        row: int,
        col: int,
        isSelected: bool,
    ) -> None:
        """Draw the cell's text and the marker of the row's issues, if any."""
        super().Draw(grid, attr, dc, rect, row, col, isSelected)
        severity = self.marks.get(row)
        if severity:
            bitmap = _marker_bitmap(severity)
            x = rect.x + rect.width - bitmap.GetWidth() - 2
            y = rect.y + (rect.height - bitmap.GetHeight()) // 2
            dc.DrawBitmap(bitmap, x, y, True)

    def GetBestSize(
        self,
        grid: wx.grid.Grid,
        attr: wx.grid.GridCellAttr,
        dc: wx.DC,
        row: int,
        col: int,
    ) -> wx.Size:
        """Return the size of the text, 20 pixels wider for the marker."""
        size = super().GetBestSize(grid, attr, dc, row, col)
        return wx.Size(size.width + 20, size.height)  # room for the marker

    def Clone(self) -> "_MarkedTextRenderer":
        """Return a renderer that shares the marks."""
        return _MarkedTextRenderer(self.marks)


class FeatureSettingsEditor(_RowIssues, Editor):
    """Features with settings (a dict of configs by feature, e.g. ranges) as a table.

    One row for each feature of the input and, while the input's features are not
    all known, for each checked feature the input lacks; "Use" selects it, and its
    settings are edited in the same row. Checking a feature fills empty settings that
    have a default with the default, and an empty min and max (or low and high) with
    the feature's range in the first input table; not for a constant column or while
    those settings are disabled.
    """

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the table (Use, Feature, the settings), its buttons and a message."""
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

    def _on_load(self, event: wx.CommandEvent) -> None:
        """Load the settings of a JSON file chosen in a file dialog."""
        with wx.FileDialog(
            self.control,
            "Load feature settings",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.load_settings(dialog.GetPath())

    def _on_save(self, event: wx.CommandEvent) -> None:
        """Save the settings to a JSON file chosen in a file dialog."""
        with wx.FileDialog(
            self.control,
            "Save feature settings",
            wildcard="JSON files (*.json)|*.json|All files|*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            dialog.SetFilterIndex(0)  # JSON selected: with All files, the macOS panel adds .txt to a name without one
            if dialog.ShowModal() == wx.ID_OK:
                self.save_settings(with_extension(dialog.GetPath(), ".json"))

    def load_settings(self, path: str | os.PathLike) -> tuple[list, list]:
        """Apply the settings in a file to the matching features.

        The features stay checked or unchecked. The config flags that keep settings
        the same in all rows or disable them are turned off, since the loaded
        settings are per feature. The message below the table reports the result.

        Args:
            path: The file, in one of the forms that `find_feature_settings` reads.

        Returns:
            The applied features and the skipped ones (not in the table); `([], [])`,
            with a message, if the file cannot be read or has no feature settings.
        """
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
        # the loaded settings are per feature and all used: turn off the flags that
        # keep settings the same in all rows or disable them
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

    def save_settings(self, path: str | os.PathLike) -> None:
        """Write the settings of the checked features to a JSON file.

        The file holds {feature: {setting: value}}; features whose settings are not
        valid are left out. The message below the table reports the result, also
        when the file cannot be written.

        Args:
            path: The file.
        """
        settings = {}
        for feature, values in self.get().items():
            try:
                model = self.spec.model.model_validate(values)
            except ValueError:
                continue
            settings[feature] = model.model_dump(exclude={"classname", "version"})
        try:
            with open(path, "w") as f:
                json.dump(settings, f, indent=2)
        except OSError as err:
            self.message.SetLabel(f"Could not save {Path(path).name}: {err}")
            return
        self.message.SetLabel(f"Saved the settings of {len(settings)} features")

    # --- rows ---

    def is_used(self, row: int) -> bool:
        """Return whether the row's feature is checked (Use)."""
        return self.grid.GetCellValue(row, 0) == "1"

    def use(self, row: int, used: bool = True) -> None:
        """Check or uncheck the row's feature.

        Checking it fills in: the settings kept the same in all rows, from another
        checked row; empty settings that have a default, with the default; empty
        limits (min and max, or low and high), with the feature's range in the data,
        unless the feature has one value or a limit is disabled.

        Args:
            row: The row.
            used: Whether to check the feature. Defaults to True.
        """
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
            # a constant column (one value) has no range: the limits stay empty
            constant = feature in self.ranges and len(set(self.ranges[feature])) == 1
            fill = limits and not set(limits) & self.disabled and not constant
            if feature in self.ranges and fill:
                for name, value in zip(limits, self.ranges[feature]):
                    col = names.index(name) + 2
                    if self.grid.GetCellValue(row, col) == "":
                        self.grid.SetCellValue(row, col, f"{value:g}")
        self._style_row(row)
        self.grid.ForceRefresh()

    def _take_synced(self, row: int) -> None:
        """Give a newly checked row the settings kept the same in all rows."""
        for name in self.synced:
            col = self._column(name)
            others = [
                r for r in range(len(self.features)) if r != row and self.is_used(r)
            ]
            if col is not None and others:
                self.grid.SetCellValue(row, col, self.grid.GetCellValue(others[0], col))

    def use_all(self, used: bool) -> None:
        """Check or uncheck all features (see `use`) and call `on_change`.

        Args:
            used: Whether to check the features.
        """
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
        """Return the settings that a config flag keeps the same in all rows.

        Returns:
            Setting name -> name of the flag field, from the config class's
            `synced_settings`; empty while the editor has no panel.
        """
        model = getattr(self.panel, "model", None)
        return dict(getattr(model, "synced_settings", {}))

    def _column(self, name: str) -> Optional[int]:
        """Return the grid column of a setting; None if it is not shown."""
        names = [c.name for c in self.columns]
        return names.index(name) + 2 if name in names else None

    def sync_column(self, name: str, value: Optional[str] = None) -> None:
        """Set the setting `name` of all rows to the same text.

        Args:
            name: The setting.
            value: The text. Defaults to None: the text of the row edited last, else
                of the first checked row, or of the first row.
        """
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

    def _row_of(self, path: Optional[str]) -> Optional[int]:
        """The row a path into this field is about, e.g. "features['FAD t1'].min"."""
        rest = (path or "")[len(self.spec.name) :].lstrip(".").removeprefix("['")
        matches = [i for i, f in enumerate(self.features) if rest.startswith(f)]
        return max(matches, key=lambda i: len(self.features[i])) if matches else None

    def disabled_settings(self) -> dict:
        """Return the settings that a config flag makes unused (greyed out).

        Returns:
            Setting name -> name of the flag field, from the config class's
            `disabled_settings`; empty while the editor has no panel.
        """
        model = getattr(self.panel, "model", None)
        return dict(getattr(model, "disabled_settings", {}))

    def _set_disabled(self, disabled: set) -> None:
        """Grey out the columns of unused settings (read-only); values are kept."""
        if disabled == self.disabled:
            return
        self.disabled = disabled
        self._style_rows()

    def _style_row(self, row: int) -> None:
        """Grey out (read-only) an unchecked row, and the disabled settings of a row."""
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
        """Style all rows (see `_style_row`)."""
        for row in range(len(self.features)):
            self._style_row(row)
        self.grid.ForceRefresh()

    def refresh(self, panel: "FieldsPanel") -> None:
        """Apply the panel's flags that keep settings the same or disable them.

        Settings whose flag is turned on are set to the same text in all rows (see
        `sync_column`); settings whose disabling flag is on are greyed out.
        """
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

    def _on_cell_changed(self, event: wx.grid.GridEvent) -> None:
        """Remember the edited row; copy a synced setting to all rows."""
        col = event.GetCol()
        name = self.columns[col - 2].name if col >= 2 else None
        if name is not None:
            self.last_edited[name] = self.features[event.GetRow()]
        if name in self.synced:
            self.sync_column(name, self.grid.GetCellValue(event.GetRow(), col))
        self.changed(event)

    def _on_tab(self, event: wx.grid.GridEvent) -> None:
        """Move to the next editable cell on Tab (Shift+Tab: the previous one).

        The move continues in the next row and wraps around; the focus stays in the
        table. Without this handler, Tab moves the focus to the check boxes above the
        table (e.g. Same bins for all), where a key toggles them.
        """
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

    def _on_click(self, event: wx.grid.GridEvent) -> None:
        """Toggle Use on a click in its column; other clicks are handled as usual."""
        if event.GetCol() == 0:
            row = event.GetRow()
            self.use(row, not self.is_used(row))
            self._fit_columns()
            self.changed()
        else:
            event.Skip()

    def _state(self) -> dict:
        """Return feature -> (used, cell texts of the settings) of the rows shown."""
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

    def _show(self, features: list[str], state: dict) -> None:
        """Show a row per feature, checked and filled in as in `state`."""
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        # used features the input lacks: listed only while the input's features are
        # not all known, otherwise ignored
        lacking = [f for f in state if f not in features and state[f][0]]
        self.features = list(features) + ([] if getattr(self, "known", False) else lacking)
        self.grid.AppendRows(len(self.features))
        for row, feature in enumerate(self.features):
            used, texts = state.get(feature, (False, [""] * len(self.columns)))
            self.grid.SetCellValue(row, 0, "1" if used else "")
            self.grid.SetCellValue(row, 1, feature.replace("\n", " "))
            for col, text in enumerate(texts):
                self.grid.SetCellValue(row, col + 2, text)
        self._fit_columns()
        self._style_rows()

    # --- Editor ---

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """List the input's features; the checks and settings shown or set are kept."""
        state = {**getattr(self, "wanted", {}), **self._state()}
        self.known = schema is not None and schema.complete
        features = [] if schema is None else schema.by_role("feature")
        self._show(features, state)
        self.wanted = {}  # the settings applied: from now on the rows shown count

    def set_data(self, tables: list) -> None:
        """Keep the range (min, max) of each numeric column of the first table.

        Infinite values are ignored; columns without finite values have no range.
        """
        self.ranges = {}
        if tables:
            data = tables[0]
            for column in data.select_dtypes("number").columns:
                values = data[column].replace(
                    [float("inf"), float("-inf")], float("nan")
                )
                if values.notna().any():
                    self.ranges[column] = (float(values.min()), float(values.max()))

    def states(self) -> dict:
        """Return feature -> (used, {setting: text}) of the rows shown, used or not.

        Empty texts are left out.
        """
        return {
            feature: (used, {c.name: t.strip() for c, t in zip(self.columns, texts) if t.strip()})
            for feature, (used, texts) in self._state().items()
        }

    def set_states(self, used: dict, unused: dict) -> None:
        """Show the settings of used features (checked) and of unused ones (unchecked).

        A feature that is in both is checked. Unused features are shown only if the
        input has them.

        Args:
            used: Configs or dicts of settings by feature, checked; None for none.
            unused: Configs or dicts of settings by feature, unchecked; None for none.
        """
        state = {}
        for checked, value in ((False, unused), (True, used)):
            for feature, settings in (value or {}).items():
                data = settings if isinstance(settings, dict) else settings.model_dump()
                state[feature] = (checked, [_cell_text(data.get(c.name)) for c in self.columns])
        self.wanted = state
        self._show(self.features, state)

    def get(self) -> Any:
        """Return {feature: {setting: text}} of the checked features.

        Empty settings are left out; the config's validation converts the texts.
        """
        result = {}
        for feature, (used, texts) in self._state().items():
            if used:
                result[feature] = {
                    c.name: t.strip() for c, t in zip(self.columns, texts) if t.strip()
                }
        return result

    def set(self, value: Any) -> None:
        """Check the features of `value` (settings by feature), with settings."""
        state = {}
        for feature, settings in (value or {}).items():
            data = settings if isinstance(settings, dict) else settings.model_dump()
            state[feature] = (
                True,
                [_cell_text(data.get(c.name)) for c in self.columns],
            )
        self.wanted = state
        self._show(self.features, state)  # the input's features, checked as configured


def find_feature_settings(data: Any, names: list[str]) -> Optional[dict]:
    """Return the per-feature settings in a loaded settings file.

    Reads the files written by "Save Feature Settings...", configs
    (`{"features": {...}}`) and FLIMAnalyzer settings files (searched for such
    entries). Also reads two older forms: histogram `featuresettings` lists
    `[min, max, bins, ...]`, and range filter lists of
    `{"name", "rangelow", "rangehigh", "dropna"}`.

    Args:
        data: The file's content, as read by `json.load`.
        names: The settings' names, e.g. min, max, bins.

    Returns:
        {feature: {name: value}} with only the settings in `names`; None if no such
        settings are found.
    """
    allowed = set(names) | {"classname", "version"}

    def dict_settings(value: Any) -> Optional[dict]:
        """{feature: {name: value}} with only these names."""
        if not isinstance(value, dict) or not value:
            return None
        if not all(
            isinstance(e, dict) and e and set(e) <= allowed for e in value.values()
        ):
            return None
        return {f: {k: v for k, v in e.items() if k in names} for f, e in value.items()}

    def histogram_lists(value: Any) -> Optional[dict]:
        if names[:3] != ["min", "max", "bins"] or not isinstance(value, dict):
            return None
        rows = {}
        for feature, entry in value.items():
            if isinstance(entry, list) and len(entry) >= 3:
                rows[feature] = dict(zip(names, entry[:3]))
        return rows or None

    def range_filter_list(value: Any) -> Optional[dict]:
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

    def search(value: Any) -> Optional[dict]:
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


def _cell_text(value: Any) -> str:
    """Return a setting's cell text: floats in `g` format, None as empty."""
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, float) else str(value)


class JsonEditor(Editor):
    """Anything else, as JSON text."""

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create a multi-line text field."""
        control = wx.TextCtrl(parent, style=wx.TE_MULTILINE)
        control.SetMinSize((-1, 60))
        control.Bind(wx.EVT_TEXT, self.changed)
        return control

    def get(self) -> Any:
        """Return the value of the JSON text; an empty text is None.

        Raises:
            ValueError: If the text is not valid JSON.
        """
        try:
            return json.loads(self.control.GetValue() or "null")
        except json.JSONDecodeError as err:
            raise ValueError(f"Not valid JSON: {err.msg}") from None

    def set(self, value: Any) -> None:
        """Show `value` as JSON text."""
        self.control.ChangeValue(json.dumps(_jsonable(value)))


def _jsonable(value: Any) -> Any:
    """Return `value` with configs, paths, tuples, sets and dict keys as JSON types."""
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
    """Return the editor class for a field, by its kind and options.

    Args:
        spec: The field.

    Returns:
        The editor class; `TextEditor` for kinds without an editor of their own.
    """
    if spec.words or spec.escapes or spec.chars:
        return TextEditor
    if spec.kind == "bool":
        return ChoiceEditor if spec.optional else BoolEditor
    if spec.kind == "int" and not spec.optional:
        return IntEditor
    if spec.kind == "columns":
        return FeaturesEditor if spec.role == "feature" else CategoriesEditor
    if spec.kind == "modelmap" and spec.role == "feature":
        return FeatureSettingsEditor
    if spec.kind == "multichoice" and len(spec.choices) <= FEW_CHOICES:
        return FewChoicesEditor
    return {
        "choice": ChoiceEditor,
        "multichoice": MultiChoiceEditor,
        "column": ColumnEditor,
        "value": ValueEditor,
        "path": PathEditor,
        "paths": PathsEditor,
        "model": ModelEditor,
        "models": ModelsEditor,
        "variants": VariantsEditor,
        "modelmap": ModelMapEditor,
        "json": JsonEditor,
    }.get(spec.kind, TextEditor)


# (config class, field name) -> editor class, for fields that need their own widget
_FIELD_EDITORS: dict = {}


def register_editor(
    config_class: type[BaseModel], field_name: str
) -> Callable[[type[Editor]], type[Editor]]:
    """Return a class decorator that registers the editor of one field.

    The editor is used for the field of the config class and of its subclasses (see
    `editor_for`).

    Args:
        config_class: The config class.
        field_name: The field's name.

    Returns:
        The decorator; it returns the editor class unchanged.
    """

    def register(editor: type[Editor]) -> type[Editor]:
        _FIELD_EDITORS[(config_class, field_name)] = editor
        return editor

    return register


def editor_for(model: type[BaseModel], spec: FieldSpec) -> type[Editor]:
    """Return the editor class for a field of a config class.

    Args:
        model: The config class.
        spec: The field.

    Returns:
        The editor registered for the field of the class or of its nearest base
        class (`register_editor`), else the editor of the field's kind
        (`editor_class`).
    """
    for base in model.__mro__:
        if (base, spec.name) in _FIELD_EDITORS:
            return _FIELD_EDITORS[(base, spec.name)]
    return editor_class(spec)


# small fields that need a row of their own (a text field and a button)
WIDE_KINDS = ("path",)


class FieldsPanel(wx.Panel):
    """Editors for the visible fields of a config class, with issue markers.

    Fields are shown in their order (`flim.core.fields.field_order`): small fields
    that follow each other share a grid of 1 to 3 fields per row (label, editor,
    marker); path fields take a row of their own; lists and tables take the full
    width; nested configs are titled groups, or collapsible sections if advanced.
    With `stacked`, the fields are shown one under the other, each label above its
    editor, in the model's order (e.g. a column of a few fields).
    """

    def __init__(
        self,
        parent: wx.Window,
        model: type[BaseModel],
        exclude: Collection[str] = (),
        stacked: bool = False,
    ) -> None:
        """Create the editors of the config class's visible fields.

        Args:
            parent: The parent window.
            model: The config class.
            exclude: The names of fields not to show. Defaults to none.
            stacked: Whether to show the fields one under the other, in the model's
                order. Defaults to False.
        """
        super().__init__(parent)
        self.model = model
        self.on_change: Optional[Callable[[], None]] = None
        self.editors: dict[str, Editor] = {}
        self.markers: dict[str, wx.StaticBitmap] = {}
        self.widgets: dict[str, list] = {}  # field -> its label and editor
        self.fixed: set = set()  # fields that allow only one value now (not shown)
        self.hidden: set = set()  # fields not shown now: fixed, or `shown_when` not met
        self.inapplicable: set = set()  # fields that do not apply to the input tables
        specs = [s for s in visible(describe(model)) if s.name not in exclude]
        if stacked:
            self._stack(specs)
            return
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
                if spec.kind in WIDE_KINDS or spec.wide:  # a row of its own
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
            if spec.kind == "model":  # a group or collapsible section with its title
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

    def _stack(self, specs: list[FieldSpec]) -> None:
        """Each field under the previous one: its label and marker, then its editor."""
        sizer = wx.BoxSizer(wx.VERTICAL)
        for spec in specs:
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.Add(self._label(spec), 0, wx.RIGHT, 6)
            row.Add(self._marker(spec), 0)
            sizer.Add(row, 0, wx.TOP, 4)
            sizer.Add(self._editor(spec).control, 0, wx.EXPAND | wx.TOP, 2)
        self.SetSizer(sizer)

    def _add_grid(self, sizer: wx.BoxSizer, specs: list[FieldSpec]) -> None:
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

    def _label(self, spec: FieldSpec) -> wx.StaticText:
        """Create the field's label, with its description as the tooltip."""
        label = wx.StaticText(self, label=spec.title)
        if spec.description:
            label.SetToolTip(spec.description)
        self.widgets.setdefault(spec.name, []).append(label)
        return label

    def _editor(self, spec: FieldSpec) -> Editor:
        """Create the field's editor."""
        editor = editor_for(self.model, spec)(self, spec)
        editor.on_change = self._on_editor_change
        self.editors[spec.name] = editor
        self.widgets.setdefault(spec.name, []).append(editor.control)
        return editor

    def _marker(self, spec: FieldSpec) -> wx.StaticBitmap:
        """Create the field's issue marker, hidden."""
        marker = wx.StaticBitmap(self, bitmap=_marker_bitmap("error"))
        marker.Hide()
        self.markers[spec.name] = marker
        return marker

    def set_values(self, config: BaseModel) -> None:
        """Show the values of `config` in the editors, then `refresh`.

        Args:
            config: A config of the panel's config class.
        """
        for name, editor in self.editors.items():
            editor.set(getattr(config, name))
        self.refresh()

    def values(self, config: BaseModel) -> dict[str, Any]:
        """Return the values of `config`, with the edited ones.

        Args:
            config: The config whose values the fields without an editor keep.

        Returns:
            The values of all of the config's fields, by name.

        Raises:
            FieldErrors: If text in editors is not a valid value; it holds the
                message of each such field.
        """
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

    def _on_editor_change(self, editor: Editor) -> None:
        """Refresh the fields and call `on_change` after an edit."""
        self.refresh()
        if self.on_change:
            self.on_change()

    def value_of(self, name: str) -> Any:
        """Return the edited value of a field.

        Args:
            name: The field's name.

        Returns:
            The value; None if the panel has no editor for the field or its text is
            not valid.
        """
        editor = self.editors.get(name)
        try:
            return editor.get() if editor else None
        except ValueError:
            return None

    def refresh(self) -> None:
        """Update the editors that depend on other fields, and hide fields.

        Lets each editor update (e.g. value choices) and offer only the values the
        config class allows given the other fields (`allowed_values`). Hides the
        fields that allow only one value, those that do not apply to the input tables,
        and those whose `shown_when` is not met (e.g. the settings of another mode).
        """
        for editor in self.editors.values():
            editor.refresh(self)
        allowed_values = getattr(self.model, "allowed_values", None)
        if allowed_values is not None:
            values = {name: self.value_of(name) for name in self.editors}
            allowed = allowed_values(values)
            for name, editor in self.editors.items():
                editor.set_allowed(allowed.get(name))
            self.fixed = {n for n, a in allowed.items() if len(a) == 1} & set(self.editors)
        hidden = self.fixed | (self.inapplicable & set(self.editors)) | {
            name for name, editor in self.editors.items() if not self._shown(editor.spec)
        }
        if hidden == self.hidden:
            return
        self.hidden = hidden
        for name, widgets in self.widgets.items():
            for widget in widgets:
                widget.Show(name not in hidden)
            if name in hidden:
                self.markers[name].Hide()
        self.Layout()
        relayout(self)

    def set_inapplicable(self, names: Iterable[str]) -> None:
        """Hide the fields that do not apply to the input tables.

        Args:
            names: The fields' names (see `Tool.inapplicable_fields`).
        """
        names = set(names)
        if names != self.inapplicable:
            self.inapplicable = names
            self.refresh()

    def _shown(self, spec: FieldSpec) -> bool:
        """Whether the other fields have the values a field's `shown_when` asks for."""
        for other, wanted in spec.shown_when.items():
            wanted = wanted if isinstance(wanted, (list, tuple)) else [wanted]
            if other in self.editors and self.value_of(other) not in wanted:
                return False
        return True

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Pass the input's schema to the editors, then `refresh`.

        Args:
            schema: The input's columns; None if they are unknown.
        """
        for editor in self.editors.values():
            editor.set_schema(schema)
        self.refresh()

    def set_data(self, tables: list) -> None:
        """Pass the selected input tables to the editors.

        Args:
            tables: The selected input tables (DataFrames).
        """
        for editor in self.editors.values():
            editor.set_data(tables)

    def show_issue(self, name: str, severity: Optional[str], message: str = "") -> None:
        """Show or hide the issue marker of a field.

        The marker of a hidden field stays hidden.

        Args:
            name: The field's name; a field without a marker is ignored.
            severity: `error`, `warning` or `guessed`; None hides the marker.
            message: The marker's tooltip. Defaults to "".
        """
        marker = self.markers.get(name)
        if marker is None:
            return
        if severity is None or name in self.hidden:
            marker.Hide()
        else:
            marker.SetBitmap(_marker_bitmap(severity))
            marker.SetToolTip(message)
            marker.Show()
        self.Layout()


class FieldErrors(Exception):
    """Text in editors that is not a valid value: field name -> message."""

    def __init__(self, errors: dict) -> None:
        """Create the exception.

        Args:
            errors: The message of each field whose text is not valid, by name.
        """
        super().__init__(errors)
        self.errors = errors


_ART = {"error": wx.ART_ERROR, "warning": wx.ART_WARNING, "guessed": wx.ART_WARNING, "skipped": wx.ART_WARNING}


def _marker_bitmap(severity: str) -> wx.Bitmap:
    """Return the 16-pixel marker icon of a severity."""
    return wx.ArtProvider.GetBitmap(_ART[severity], wx.ART_MENU, (16, 16))


class ExampleView(wx.Panel):
    """What a tool does with the input, below its settings (`Tool.example`).

    A table (a `pd.DataFrame` from `flim.core.tool.example_table`) is shown under
    `Example:` and its caption, as a read-only list with a column per table column
    (the columns the tool makes are marked `→`); a line is shown as `Example: ...`.
    """

    def __init__(self, parent: wx.Window) -> None:
        """Create the view, hidden until it shows an example.

        Args:
            parent: The parent window.
        """
        super().__init__(parent)
        self.label = wx.StaticText(self, label="")
        self.table = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.label, 0, wx.BOTTOM, 2)
        sizer.Add(self.table, 0, wx.EXPAND)
        self.SetSizer(sizer)
        self.Hide()

    def show(self, example: Any) -> bool:
        """Show an example table or line; hide the view for None or an empty line.

        Args:
            example: A `pd.DataFrame`, a line, or None.

        Returns:
            Whether the view's height changed (the dialog then fits its contents).
        """
        before = self.GetBestSize().height if self.IsShown() else 0
        if isinstance(example, pd.DataFrame):
            caption = example.attrs.get("caption", "")
            self.label.SetLabel(f"Example ({caption}):" if caption else "Example:")
            self._fill(example)
            self.table.Show()
            self.Show()
        elif example:
            self.label.SetLabel(f"Example: {example}")
            self.table.Hide()
            self.Show()
        else:
            self.Hide()
        self.Layout()
        return (self.GetBestSize().height if self.IsShown() else 0) != before

    def rows(self) -> list[list[str]]:
        """Return the shown table's cells as text, row by row (the header first)."""
        count = self.table.GetColumnCount()
        header = [self.table.GetColumn(c).GetText() for c in range(count)]
        cells = [
            [self.table.GetItemText(r, c) for c in range(count)]
            for r in range(self.table.GetItemCount())
        ]
        return [header] + cells

    def _fill(self, table: pd.DataFrame) -> None:
        """Fill the list with the table: its columns, its rows, as high as its rows."""
        self.table.ClearAll()
        for index, name in enumerate(table.columns):
            self.table.InsertColumn(index, str(name))
        for values in table.itertuples(index=False):
            row = self.table.InsertItem(self.table.GetItemCount(), _cell(values[0]))
            for column, value in enumerate(values[1:], 1):
                self.table.SetItem(row, column, _cell(value))
        for index in range(len(table.columns)):
            self.table.SetColumnWidth(index, wx.LIST_AUTOSIZE_USEHEADER)
        line = self.table.GetCharHeight() + 8
        self.table.SetMinSize((-1, line * (len(table) + 1) + 6))


def _cell(value: Any) -> str:
    """Return a value of an example table as text: floats with 4 significant digits."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)
