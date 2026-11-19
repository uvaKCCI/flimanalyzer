"""Filter: the dialog with presets, and the editors of the three filter components.

The filter components are the feature filters (one per feature column; today range
filters), the category values to keep (one filter per category column) and the
other filters, each with its switch. The feature and category filter components
list only the input table's columns; their filters on other columns are not used and
are kept unchanged in the settings.
The presets are those saved in the user settings file (`presets` > `Filter`), also
by the table windows' `Filter Features...`.
"""

from typing import Any, Optional

import wx
from pydantic import BaseModel, TypeAdapter

from flim.configs.data import FILTER_COMPONENTS, FilterConfig, FilterEntry, RangeSettings
from flim.core.config import FeatureColumn, Issue
from flim.core.schema import TableSchema
from flim.core.fields import FieldSpec, describe_annotation
from flim.gui.configdialog import PresetsDialog, register_dialog
from flim.gui.editors import (
    Editor,
    FeatureSettingsEditor,
    FieldsPanel,
    VariantsEditor,
    fit_rows,
    register_editor,
)


@register_dialog(FilterConfig)
class FilterDialog(PresetsDialog):
    """The Filter dialog, with buttons for presets below the settings.

    The buttons are `Load Preset...`, `Save as Preset...` and `Remove Presets...`;
    a preset sets the switch of all filters (`enabled`) and the filter components it
    has. A preset saved in a table window's `Filter Features...` has only the
    feature filters (`features`) and their switch.
    """

    preset_fields = ("enabled",) + FILTER_COMPONENTS

    def preset_settings(self, settings: dict) -> dict:
        """Return the settings a stored preset sets, converted from earlier versions.

        A preset of an earlier version (`enabled` and a flat `filters` list) is
        converted by kind (see `flim.configs.data.split_filters`) and sets all
        three filter components.

        Args:
            settings: The preset's settings, as stored.

        Returns:
            The values of `preset_fields` that the preset sets.
        """
        if "filters" not in settings:
            return super().preset_settings(settings)
        keys = ("enabled", "filters") + FILTER_COMPONENTS
        config = FilterConfig.model_validate({k: v for k, v in settings.items() if k in keys})
        data = config.model_dump(mode="json")
        given = [k for k in self.preset_fields if k in settings or k in FILTER_COMPONENTS]
        return {k: data[k] for k in given}


class CategoryFiltersEditor(Editor):
    """Per category column, the values whose rows are kept (all are, by default).

    A column with unchecked values filters; it is marked with `*` in the list, and
    with `(off)` if its filter is switched off (`off`). Checking or unchecking a
    value of such a column uses its filter again. With an input table, only its
    category columns are listed: filters on other columns are not used, and are
    kept unchanged (`get` returns them).
    """

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the panel of the columns and their values."""
        self.levels: dict = {}  # column -> values in the data
        self.kept: dict = {}  # column -> values kept (only columns that filter)
        self.off: set = set()  # columns whose filter is switched off
        self.table_columns: Optional[set] = None  # the input's category columns; None: no input
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
        """Return the category columns of the data, then the other filtering columns shown.

        Without an input table, every filtering column is shown; with one, only
        those of its category columns whose values are unknown.
        """
        others = [c for c in self.kept if c not in self.levels]
        if self.table_columns is not None:
            others = [c for c in others if c in self.table_columns]
        return list(self.levels) + others

    def _label(self, column: str) -> str:
        """Return a column's label in the list: ` *` if it filters, ` (off)` if switched off."""
        if column not in self.kept:
            return column
        return f"{column} * (off)" if column in self.off else f"{column} *"

    def selected_column(self) -> Optional[str]:
        """Return the column selected in the list; None if none is selected."""
        index = self.columns.GetSelection()
        if index == wx.NOT_FOUND:
            return None
        return self.columns.GetString(index).removesuffix(" (off)").removesuffix(" *")

    def values_of(self, column: str) -> list[Any]:
        """Return a column's values in the data, then its kept values not in it."""
        levels = self.levels.get(column, [])
        return levels + [v for v in self.kept.get(column, []) if v not in levels]

    def show_columns(self) -> None:
        """List the columns, keep the selected one, and show its values."""
        names = self.column_names()
        selected = self.selected_column()
        self.columns.Set([self._label(c) for c in names])
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
        self.off.discard(column)  # an edit uses the column's filter again
        if len(kept) == len(values):
            self.kept.pop(column, None)  # keeps all: no filter
        else:
            self.kept[column] = kept
        index = self.columns.GetSelection()
        self.columns.SetString(index, self._label(column))
        self.changed(event)

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """List the input's category columns; hide filters on other columns."""
        self.levels = {}
        self.table_columns = None
        if schema is not None:
            if schema.complete:
                self.table_columns = {c.name for c in schema.columns if c.role == "category"}
            for column in schema.columns:
                if column.role == "category" and column.levels is not None:
                    self.levels[column.name] = list(column.levels)
        self.show_columns()

    def get(self) -> Any:
        """Return the kept values of each column that filters, shown or not."""
        return {column: list(values) for column, values in self.kept.items()}

    def set(self, value: Any) -> None:
        """Show the kept values (a dict of value lists by column; None for none)."""
        self.kept = {column: list(values) for column, values in (value or {}).items()}
        self.off = set()
        self.show_columns()


def _spec(name: str, title: str, annotation: Any, description: str = "") -> FieldSpec:
    """Return the field spec of a sub-editor, described from its annotation."""
    return FieldSpec(name=name, title=title, description=description, **describe_annotation(annotation))


class _ComponentEditor(Editor):
    """Editor of a filter component of the Filter settings: its switch above its filters.

    The view is greyed out while the component's switch or the switch of all filters
    (`Use filters`) is off. Subclasses create the view (`create_view`) and convert
    its value (`view_get`, `view_set`, `view_issues`).
    """

    expands = True

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the titled group with the switch and the view."""
        panel = wx.Panel(parent)
        box = wx.StaticBoxSizer(wx.VERTICAL, panel, self.spec.title)
        inner = box.GetStaticBox()
        switch = self.spec.model.model_fields["enabled"]
        self.switch = wx.CheckBox(inner, label=switch.title)
        self.switch.SetToolTip(switch.description)
        self.switch.Bind(wx.EVT_CHECKBOX, self._on_switch)
        box.Add(self.switch, 0, wx.ALL, 4)
        self.view = self.create_view(inner)
        self.view.on_change = lambda e: self.changed()
        box.Add(self.view.control, 1, wx.EXPAND | wx.ALL, 4)
        panel.SetSizer(box)
        self.all_on = True  # `Use filters`, see refresh
        return panel

    def create_view(self, parent: wx.Window) -> Editor:
        """Create and return the editor of the component's filters; implemented by subclasses."""
        raise NotImplementedError

    def _on_switch(self, event: wx.CommandEvent) -> None:
        """Grey out the view as the switch says, and report the change."""
        self.grey_out()
        self.changed(event)

    def grey_out(self) -> None:
        """Enable the view only while the component's switch and `Use filters` are on."""
        self.view.control.Enable(self.all_on and self.switch.GetValue())

    def get(self) -> Any:
        """Return the filter component: its switch and its filters, as a dict.

        Raises:
            ValueError: If text in the view is not a valid value.
        """
        return {"enabled": self.switch.GetValue(), "filters": self.view_get()}

    def set(self, value: Any) -> None:
        """Show a filter component (a model or a dict; None for an empty one that is on)."""
        if isinstance(value, BaseModel):
            enabled, filters = value.enabled, list(value.filters)
        else:
            enabled = (value or {}).get("enabled", True)
            filters = list((value or {}).get("filters") or [])
        self.switch.SetValue(bool(enabled))
        self.view_set([n if isinstance(n, BaseModel) else _node(n) for n in filters])
        self.grey_out()

    def view_get(self) -> list:
        """Return the filters of the view as dicts; implemented by subclasses."""
        raise NotImplementedError

    def view_set(self, nodes: list) -> None:
        """Show filter nodes in the view; implemented by subclasses."""
        raise NotImplementedError

    def view_issues(self, issues: list) -> None:
        """Show the issues at `<component>.filters[i]` in the view; none here."""

    def show_issues(self, issues: list) -> None:
        """Show the issues of the component's filters in the view."""
        self.view_issues(issues)

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Pass the schema to the view."""
        self.view.set_schema(schema)

    def set_data(self, tables: list) -> None:
        """Pass the input tables to the view."""
        self.view.set_data(tables)

    def refresh(self, panel: FieldsPanel) -> None:
        """Grey out the view if `Use filters` is off; refresh the view."""
        on = panel.value_of("enabled")
        self.all_on = on is None or bool(on)
        self.grey_out()
        self.view.refresh(panel)

    def _indexed(self, issues: list) -> list[tuple[int, str, Issue]]:
        """Return (index, rest of the path, issue) of the issues at the component's filters."""
        result = []
        prefix = f"{self.spec.name}.filters["
        for issue in issues:
            rest = (issue.field or "").removeprefix(prefix)
            if rest == (issue.field or ""):
                continue
            index, _, tail = rest.partition("]")
            if index.isdigit():
                result.append((int(index), tail, issue))
        return result


@register_editor(FilterConfig, "features")
class FeaturesComponentEditor(_ComponentEditor):
    """The feature filters: per feature of the input a range, used or not.

    Only the input's feature columns are listed; a feature filter of a column the
    input does not have is not used, and is kept unchanged. An
    unused range without values keeps the values it had.
    """

    def create_view(self, parent: wx.Window) -> Editor:
        """Create the table of the ranges."""
        self.unused: dict = {}  # column -> its unused range leaf
        self.used: dict = {}  # column -> its used range leaf
        self.views: list = []  # per filter of `view_get`: (view, column)
        return FeatureSettingsEditor(
            parent,
            _spec("range_filters", "Feature filters", dict[FeatureColumn, RangeSettings],
                  "Check the columns to filter: rows outside [low, high] are dropped (empty: no limit)."),
        )

    def view_set(self, nodes: list) -> None:
        """Show the range leaves, checked if enabled."""
        self.used = {n.column: n for n in nodes if n.enabled}
        self.unused = {n.column: n for n in nodes if not n.enabled}
        self.view.set_states(self.used, self.unused)

    def view_get(self) -> list:
        """Return the range leaves: the input's columns with a range, then the others."""
        nodes, self.views = [], []
        states = self.view.states()
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
        return nodes

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Pass the schema to the table; the ranges keep their states."""
        used = {c: v for c, (u, v) in self.view.states().items() if u}
        self.view.set_schema(schema)
        self.view.set_states(used, dict(self.unused))

    def view_issues(self, issues: list) -> None:
        """Show the issues of the ranges shown in their rows."""
        moved = []
        for index, tail, issue in self._indexed(issues):
            if index < len(self.views) and self.views[index][0] == "ranges":
                moved.append(_moved(issue, f"range_filters[{self.views[index][1]!r}]{tail}"))
        self.view.show_issues(moved)


@register_editor(FilterConfig, "categories")
class CategoriesComponentEditor(_ComponentEditor):
    """The category filters: per category column the values whose rows are kept."""

    def create_view(self, parent: wx.Window) -> Editor:
        """Create the lists of the columns and their values."""
        return CategoryFiltersEditor(
            parent, FieldSpec(name="category_filters", title="Category values to keep", kind="json",
                              description="For each category column, the values whose rows are kept.")
        )

    def view_set(self, nodes: list) -> None:
        """Show the category leaves; those not enabled are marked `(off)`."""
        self.view.set({n.column: list(n.keep) for n in nodes})
        self.view.off = {n.column for n in nodes if not n.enabled}
        self.view.show_columns()

    def view_get(self) -> list:
        """Return a category leaf per column that keeps some of its values."""
        return [
            {"kind": "category", "column": column, "keep": keep, "enabled": column not in self.view.off}
            for column, keep in self.view.get().items()
        ]


@register_editor(FilterConfig, "other")
class OtherComponentEditor(_ComponentEditor):
    """The other filters: expressions, groups and further filters, as a table."""

    def create_view(self, parent: wx.Window) -> Editor:
        """Create the table of the filters."""
        return VariantsEditor(
            parent,
            _spec("filters", "Other filters", list[FilterEntry],
                  "Conditions, groups and further filters; a row is kept if every filter keeps it."),
        )

    def view_set(self, nodes: list) -> None:
        """Show the filters, one per row."""
        self.view.set(nodes)

    def view_get(self) -> list:
        """Return the filters of the table."""
        return list(self.view.get())

    def view_issues(self, issues: list) -> None:
        """Show the issues of the filters in their rows."""
        self.view.show_issues([_moved(i, f"filters[{n}]{tail}") for n, tail, i in self._indexed(issues)])


def _node(values: dict) -> FilterEntry:
    """Return the filter node of a dict."""
    return TypeAdapter(FilterEntry).validate_python(values)


def _moved(issue: Issue, field: str) -> Issue:
    """Return a copy of an issue at another field path."""
    from dataclasses import replace

    return replace(issue, field=field)
