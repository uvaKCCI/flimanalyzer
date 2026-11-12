"""Filter: the editor of the filter tree, in three views.

The views are the category values to keep, the range filters (the top-level
leaves, one per column), and the other filters.
"""

from typing import Any, Optional

import wx
from pydantic import BaseModel

from flim.configs.data import FilterConfig, FilterEntry, RangeSettings
from flim.core.config import FeatureColumn, Issue
from flim.core.schema import TableSchema
from flim.core.fields import FieldSpec, describe_annotation
from flim.gui.editors import (
    Editor,
    FeatureSettingsEditor,
    FieldsPanel,
    VariantsEditor,
    fit_rows,
    register_editor,
)


class CategoryFiltersEditor(Editor):
    """Per category column, the values whose rows are kept (all are, by default).

    A column with unchecked values filters; it is marked with `*` in the list.
    """

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the panel of the columns and their values."""
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

    def column_names(self) -> list[str]:
        """Return the category columns of the data, then other filtering columns."""
        return list(self.levels) + [c for c in self.kept if c not in self.levels]

    def selected_column(self) -> Optional[str]:
        """Return the column selected in the list; None if none is selected."""
        index = self.columns.GetSelection()
        if index == wx.NOT_FOUND:
            return None
        return self.columns.GetString(index).removesuffix(" *")  # " *": filters

    def values_of(self, column: str) -> list[Any]:
        """Return a column's values in the data, then its kept values not in it."""
        levels = self.levels.get(column, [])
        return levels + [v for v in self.kept.get(column, []) if v not in levels]

    def _show_columns(self) -> None:
        """List the columns, keep the selected one, and show its values."""
        names = self.column_names()
        selected = self.selected_column()
        labels = [f"{c} *" if c in self.kept else c for c in names]
        self.columns.Set(labels)
        if names:
            self.columns.SetSelection(names.index(selected) if selected in names else 0)
        fit_rows(self.columns, len(names), most=8)
        self._show_values()

    def _show_values(self) -> None:
        """Show the selected column's values; the kept ones are checked."""
        column = self.selected_column()
        values = self.values_of(column) if column else []
        kept = self.kept.get(column, values)
        self.values.Set([str(v) for v in values])
        self.values.SetCheckedItems([i for i, v in enumerate(values) if v in kept])
        fit_rows(self.values, len(values), most=8)

    def _on_check(self, event: wx.CommandEvent) -> None:
        """Store the checked values; a column with all values checked keeps all."""
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

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """List the category columns with known values."""
        self.levels = {}
        if schema is not None:
            for column in schema.columns:
                if column.role == "category" and column.levels is not None:
                    self.levels[column.name] = list(column.levels)
        self._show_columns()

    def get(self) -> Any:
        """Return the kept values of each column that filters."""
        return {column: list(values) for column, values in self.kept.items()}

    def set(self, value: Any) -> None:
        """Show the kept values (a dict of value lists by column; None for none)."""
        self.kept = {column: list(values) for column, values in (value or {}).items()}
        self._show_columns()


def _spec(name: str, title: str, annotation: Any, description: str = "") -> FieldSpec:
    """Return the field spec of a sub-editor, described from its annotation."""
    return FieldSpec(name=name, title=title, description=description, **describe_annotation(annotation))


@register_editor(FilterConfig, "filters")
class FilterTreeEditor(Editor):
    """Editor of the filter list (a tree) in three views.

    The views are: per category column the values to keep (the first enabled
    top-level category leaf of the column), per feature a range (the first
    top-level range leaf of the column, used or not), and the other filters
    (expressions, groups, further leaves) as a table. On `get` the views are joined
    again: ranges, categories, then the others. Range leaves of columns that are
    not in the input are kept unchanged.
    """

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the panel of the three views."""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.categories = CategoryFiltersEditor(
            panel, FieldSpec(name="category_filters", title="Category values to keep", kind="json",
                             description="For each category column, the values whose rows are kept.")
        )
        self.ranges = FeatureSettingsEditor(
            panel,
            _spec("range_filters", "Range filters", dict[FeatureColumn, RangeSettings],
                  "Check the columns to filter: rows outside [low, high] are dropped (empty: no limit)."),
        )
        self.others = VariantsEditor(
            panel,
            _spec("filters", "Other filters", list[FilterEntry],
                  "Conditions, groups and further filters; a row is kept if every filter keeps it."),
        )
        for title, editor in (
            ("Category values to keep", self.categories),
            ("Range filters", self.ranges),
            ("Other filters", self.others),
        ):
            editor.on_change = lambda e: self.changed()
            sizer.Add(wx.StaticText(panel, label=title), 0, wx.TOP, 6)
            sizer.Add(editor.control, 1 if editor is not self.categories else 0, wx.EXPAND)
        panel.SetSizer(sizer)
        self.unused: dict = {}  # column -> its unused top-level range leaf
        self.used: dict = {}  # column -> its used top-level range leaf
        self.hidden: list = []  # range leaves not shown (column not in the input)
        self.views: list = []  # per filter of `get`: (view, key)
        return panel

    def set(self, value: Any) -> None:
        """Show filters (nodes or dicts; None for none) in the three views."""
        nodes = [n if isinstance(n, BaseModel) else _node(n) for n in value or []]
        categories, used, self.unused, others = {}, {}, {}, []
        for node in nodes:
            if node.kind == "category" and node.enabled and node.column not in categories:
                categories[node.column] = list(node.keep)
            elif node.kind == "range" and node.column not in used and node.column not in self.unused:
                (used if node.enabled else self.unused)[node.column] = node
            else:
                others.append(node)
        self.used = dict(used)  # kept also if the input doesn't have the column
        self.categories.set(categories)
        self.ranges.set_states(used, self.unused)
        self.others.set(others)

    def get(self) -> Any:
        """Return the filters of the three views as dicts, in the order of `views`.

        A range of a column without a filter is left out; an unused range without
        values keeps the values it had.
        """
        nodes, self.views = [], []
        states = self.ranges.states()
        for column, (used, values) in states.items():
            unused = self.unused.get(column)
            if not used and unused is None and not values:
                continue  # a column of the input without a filter
            if not used and unused is not None and not values:
                values = unused.model_dump(include={"low", "high", "dropna"}, exclude_none=True)
            nodes.append({"kind": "range", "column": column, "enabled": used, **values})
            self.views.append(("ranges", column))
        for column, node in {**self.used, **self.unused}.items():
            if column not in states:  # not in the input: kept as it was
                nodes.append(node.model_dump(mode="json"))
                self.views.append(("hidden", column))
        for column, keep in self.categories.get().items():
            nodes.append({"kind": "category", "column": column, "keep": keep})
            self.views.append(("categories", column))
        for j, node in enumerate(self.others.get()):
            nodes.append(node)
            self.views.append(("others", j))
        return nodes

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Pass the schema to the views; the ranges keep their states."""
        unused_states = {c: n for c, n in self.unused.items()}
        used = {c: v for c, (u, v) in self.ranges.states().items() if u}
        for editor in (self.categories, self.ranges, self.others):
            editor.set_schema(schema)
        self.ranges.set_states(used, unused_states)

    def set_data(self, tables: list) -> None:
        """Pass the input tables to the views."""
        for editor in (self.categories, self.ranges, self.others):
            editor.set_data(tables)

    def refresh(self, panel: FieldsPanel) -> None:
        """Refresh the views."""
        for editor in (self.categories, self.ranges, self.others):
            editor.refresh(panel)

    def show_issues(self, issues: list) -> None:
        """Show issues at `filters[i]` in the view that shows filter `i`.

        Issues of the category view and of hidden ranges are not shown here.
        """
        ranges, others = [], []
        for issue in issues:
            rest = (issue.field or "").removeprefix("filters[")
            index, _, tail = rest.partition("]")
            if not index.isdigit() or int(index) >= len(self.views):
                continue
            view, key = self.views[int(index)]
            if view == "ranges":
                ranges.append(_moved(issue, f"range_filters[{key!r}]{tail}"))
            elif view == "others":
                others.append(_moved(issue, f"filters[{key}]{tail}"))
        self.ranges.show_issues(ranges)
        self.others.show_issues(others)


def _node(values: dict) -> FilterEntry:
    """Return the filter node of a dict."""
    return FilterConfig.model_validate({"filters": [values]}).filters[0]


def _moved(issue: Issue, field: str) -> Issue:
    """Return a copy of an issue at another field path."""
    from dataclasses import replace

    return replace(issue, field=field)
