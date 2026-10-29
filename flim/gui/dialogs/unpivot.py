"""Unpivot: the level of the headers to move into a category column."""

from typing import Optional

import wx

from flim.configs.data import UnpivotConfig
from flim.core import headers
from flim.gui.editors import Editor, register_editor

SHOWN_VALUES = 3  # example values per level in the drop-down


@register_editor(UnpivotConfig, "level")
class LevelEditor(Editor):
    """A drop-down of the lines of the selected columns' headers, each with its name
    (recorded by the tool that made them, else its position) and example values,
    e.g. "Statistic: mean, std"; the last line is the default."""

    def create(self, parent):
        self.schema = None
        self.levels: list[str] = []
        self.value = ""  # "": the last line
        control = wx.Choice(parent)
        control.Bind(wx.EVT_CHOICE, self._on_choice)
        return control

    def set_schema(self, schema):
        self.schema = schema

    def refresh(self, panel):
        self.show_levels(panel.value_of("features"))

    def show_levels(self, columns) -> None:
        columns = columns or []
        if self.schema is not None and columns == "all":
            columns = self.schema.by_role("feature")
        recorded = [] if self.schema is None else self.schema.header_levels
        levels = headers.names_for(headers.depth(columns), recorded)
        labels = []
        for i, name in enumerate(levels):
            values = headers.level_values(columns, i)
            shown = ", ".join(values[:SHOWN_VALUES])
            more = ", ..." if len(values) > SHOWN_VALUES else ""
            labels.append(f"{name}: {shown}{more}")
        if labels == self.control.GetStrings():
            return
        self.levels = levels
        self.control.Set(labels)
        self._select()

    def _select(self) -> None:
        if not self.levels:
            return
        try:
            index = headers.level_index(self.value, self.levels)
        except ValueError:  # e.g. saved for other columns: the last line
            index = len(self.levels) - 1
        self.control.SetSelection(index)

    def _on_choice(self, event):
        index = self.control.GetSelection()
        last = index == len(self.levels) - 1
        self.value = "" if last else self.levels[index]
        self.changed(event)

    def get(self) -> str:
        return self.value

    def set(self, value: Optional[str]):
        self.value = value or ""
        self._select()
