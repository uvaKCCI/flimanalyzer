"""Filter: category values to keep (the range filters use the generic table)."""

import wx

from flim.configs.data import FilterConfig
from flim.gui.editors import Editor, fit_rows, register_editor


@register_editor(FilterConfig, "category_filters")
class CategoryFiltersEditor(Editor):
    """Per category column, the values whose rows are kept (all are, by default)."""

    expands = True

    def create(self, parent):
        self.levels: dict = {}  # column -> values in the data
        self.kept: dict = {}  # column -> values kept (only columns that filter)
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.columns = wx.ListBox(panel, choices=[])
        self.columns.Bind(wx.EVT_LISTBOX, lambda e: self._show_values())
        sizer.Add(self.columns, 1, wx.EXPAND | wx.RIGHT, 6)
        self.values = wx.CheckListBox(panel, choices=[])
        self.values.Bind(wx.EVT_CHECKLISTBOX, self._on_check)
        self.values.SetToolTip("Rows with an unchecked value are dropped")
        sizer.Add(self.values, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel

    def column_names(self) -> list:
        return list(self.levels) + [c for c in self.kept if c not in self.levels]

    def selected_column(self):
        index = self.columns.GetSelection()
        if index == wx.NOT_FOUND:
            return None
        return self.columns.GetString(index).removesuffix(" *")  # " *": filters

    def values_of(self, column) -> list:
        levels = self.levels.get(column, [])
        return levels + [v for v in self.kept.get(column, []) if v not in levels]

    def _show_columns(self):
        names = self.column_names()
        selected = self.selected_column()
        labels = [f"{c} *" if c in self.kept else c for c in names]
        self.columns.Set(labels)
        if names:
            self.columns.SetSelection(names.index(selected) if selected in names else 0)
        fit_rows(self.columns, len(names), most=8)
        self._show_values()

    def _show_values(self):
        column = self.selected_column()
        values = self.values_of(column) if column else []
        kept = self.kept.get(column, values)
        self.values.Set([str(v) for v in values])
        self.values.SetCheckedItems([i for i, v in enumerate(values) if v in kept])
        fit_rows(self.values, len(values), most=8)

    def _on_check(self, event):
        column = self.selected_column()
        values = self.values_of(column)
        kept = [values[i] for i in self.values.GetCheckedItems()]
        if len(kept) == len(values):
            self.kept.pop(column, None)  # keeps all: no filter
        else:
            self.kept[column] = kept
        index = self.columns.GetSelection()
        self.columns.SetString(index, f"{column} *" if column in self.kept else column)
        self.changed(event)

    def set_schema(self, schema):
        self.levels = {}
        if schema is not None:
            for column in schema.columns:
                if column.role == "category" and column.levels is not None:
                    self.levels[column.name] = list(column.levels)
        self._show_columns()

    def get(self):
        return {column: list(values) for column, values in self.kept.items()}

    def set(self, value):
        self.kept = {column: list(values) for column, values in (value or {}).items()}
        self._show_columns()
