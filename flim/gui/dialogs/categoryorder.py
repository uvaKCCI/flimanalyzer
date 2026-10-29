"""Order Categories: the order of the values of category columns."""

import wx

from flim.configs.data import CategoryOrderConfig
from flim.gui.editors import Editor, fit_rows, register_editor


@register_editor(CategoryOrderConfig, "categories")
class CategoryOrderEditor(Editor):
    """Checked columns get the order of values shown when they are selected; values
    can be moved up and down, sorted, or reset to the order in the data."""

    expands = True

    def create(self, parent):
        self.levels: dict = {}  # column -> values in the data
        self.orders: dict = {}  # column -> configured order
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.columns = wx.CheckListBox(panel, choices=[])
        self.columns.Bind(wx.EVT_LISTBOX, self._on_column)
        self.columns.Bind(wx.EVT_CHECKLISTBOX, self.changed)
        self.columns.SetToolTip("Checked columns get the order on the right")
        sizer.Add(self.columns, 1, wx.EXPAND | wx.RIGHT, 6)
        self.values = wx.ListBox(panel, choices=[])
        sizer.Add(self.values, 1, wx.EXPAND | wx.RIGHT, 6)
        buttons = wx.BoxSizer(wx.VERTICAL)
        for label, handler in (
            ("Up", lambda e: self._move(-1)),
            ("Down", lambda e: self._move(1)),
            ("Sort", self._on_sort),
            ("Data Order", self._on_reset),
        ):
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            buttons.Add(button, 0, wx.EXPAND | wx.BOTTOM, 3)
        sizer.Add(buttons)
        panel.SetSizer(sizer)
        return panel

    # --- state ---

    def order(self, column) -> list:
        """The configured values first, then the others of the data."""
        configured = list(self.orders.get(column, []))
        return configured + [
            v for v in self.levels.get(column, []) if v not in configured
        ]

    def column_names(self) -> list:
        return list(self.levels) + [c for c in self.orders if c not in self.levels]

    def selected_column(self):
        index = self.columns.GetSelection()
        return None if index == wx.NOT_FOUND else self.columns.GetString(index)

    def _show_columns(self, checked):
        names = self.column_names()
        selected = self.selected_column()
        self.columns.Set(names)
        self.columns.SetCheckedItems([names.index(c) for c in checked if c in names])
        if names:
            self.columns.SetSelection(names.index(selected) if selected in names else 0)
        fit_rows(self.columns, len(names), most=8)
        self._show_values()

    def _show_values(self, select=None):
        column = self.selected_column()
        values = self.order(column) if column else []
        self.values.Set([str(v) for v in values])
        fit_rows(self.values, len(values), most=8)
        if select is not None:
            self.values.SetSelection(select)

    # --- events ---

    def _on_column(self, event):
        self._show_values()

    def _set_order(self, column, values):
        self.orders[column] = list(values)
        index = self.column_names().index(column)
        self.columns.Check(index, True)  # changing the order uses it
        self.changed()

    def _move(self, step):
        column, index = self.selected_column(), self.values.GetSelection()
        if column is None or index == wx.NOT_FOUND:
            return
        values = self.order(column)
        target = index + step
        if not 0 <= target < len(values):
            return
        values[index], values[target] = values[target], values[index]
        self._set_order(column, values)
        self._show_values(select=target)

    def _on_sort(self, event):
        column = self.selected_column()
        if column is not None:
            self._set_order(column, sorted(self.order(column), key=str))
            self._show_values()

    def _on_reset(self, event):
        column = self.selected_column()
        if column is not None:
            self._set_order(column, self.levels.get(column, []))
            self._show_values()

    # --- Editor ---

    def checked_columns(self) -> list:
        return [self.columns.GetString(i) for i in self.columns.GetCheckedItems()]

    def set_schema(self, schema):
        checked = self.checked_columns()
        self.levels = {}
        if schema is not None:
            for column in schema.columns:
                if column.role == "category" and column.levels is not None:
                    self.levels[column.name] = list(column.levels)
        self._show_columns(checked)

    def get(self):
        return {column: self.order(column) for column in self.checked_columns()}

    def set(self, value):
        self.orders = {column: list(values) for column, values in (value or {}).items()}
        self._show_columns(list(self.orders))
