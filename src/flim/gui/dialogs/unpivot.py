"""Unpivot: the level of the headers to move into a category column."""

from typing import Any, Optional, Union

import wx

from flim.configs.data import UnpivotConfig
from flim.core import headers
from flim.core.schema import TableSchema
from flim.gui.editors import Editor, FieldsPanel, register_editor

SHOWN_VALUES = 3  # example values per level in the drop-down


@register_editor(UnpivotConfig, "level")
class LevelEditor(Editor):
    """Drop-down of the lines (levels) of the selected columns' headers.

    Each line is shown with its name (recorded by the tool that made the columns,
    else its position) and example values, e.g. `Statistic: mean, std`. The last
    line is the default; its value is "".
    """

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the drop-down, empty until columns are selected."""
        self.schema = None
        self.levels: list[str] = []
        self.value = ""  # "": the last line
        control = wx.Choice(parent)
        control.Bind(wx.EVT_CHOICE, self._on_choice)
        return control

    def set_schema(self, schema: Optional[TableSchema]) -> None:
        """Store the input's columns; the lines are shown on `refresh`."""
        self.schema = schema

    def refresh(self, panel: FieldsPanel) -> None:
        """Show the lines of the columns selected in the `features` field."""
        self.show_levels(panel.value_of("features"))

    def show_levels(self, columns: Union[list[Any], str, None]) -> None:
        """Show the lines of the headers of columns in the drop-down.

        Args:
            columns: The column headers; `all` for all feature columns of the
                schema; None for none.
        """
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
        """Select the stored line; the last line if it is not among the lines."""
        if not self.levels:
            return
        try:
            index = headers.level_index(self.value, self.levels)
        except ValueError:  # e.g. saved for other columns: the last line
            index = len(self.levels) - 1
        self.control.SetSelection(index)

    def _on_choice(self, event: wx.CommandEvent) -> None:
        """Store the selected line; "" for the last line."""
        index = self.control.GetSelection()
        last = index == len(self.levels) - 1
        self.value = "" if last else self.levels[index]
        self.changed(event)

    def get(self) -> Any:
        """Return the name of the selected line; "" for the last line."""
        return self.value

    def set(self, value: Any) -> None:
        """Select a line by name or position; None or "" selects the last line."""
        self.value = value or ""
        self._select()
