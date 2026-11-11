"""Calculate: the table of calculations, with presets to add, save and remove.

The table starts empty (Calculate.dialog_config); `Add Calculations...` adds presets
that apply to the input table: the built-in calculations and those saved with `Save
as Presets` (the user settings' `calculation_presets`). `Remove Presets...` removes
saved ones; the built-in ones can't be removed.
"""

import logging

import wx

from flim.configs.data import CalculateConfig
from flim.gui.editors import VariantsEditor, register_editor

logger = logging.getLogger(__name__)

_settings_manager = None  # the session's SettingsManager (see bind)


def bind(settings_manager) -> None:
    """Use a session's settings for the saved presets.

    Args:
        settings_manager: The SettingsManager of the session.
    """
    global _settings_manager
    _settings_manager = settings_manager


def built_in_presets() -> list:
    """The built-in calculations: those of the import (FLIRR, NAD(P)H tm, ...)."""
    return list(CalculateConfig().calculations)


def saved_presets() -> list:
    """The calculations saved as presets; those that are not valid are left out."""
    if _settings_manager is None:
        return []
    presets = []
    for data in _settings_manager.settings.calculation_presets:
        try:
            presets.extend(CalculateConfig(calculations=[data]).calculations)
        except ValueError as err:
            logger.warning(f"Saved calculation not valid, not offered: {err}")
    return presets


def save_presets(presets) -> None:
    """Replace the saved presets (written to the user settings file)."""
    if _settings_manager is not None:
        _settings_manager.update(
            {"calculation_presets": [p.model_dump(mode="json") for p in presets]}
        )


def describe(calculation) -> str:
    """One line for a calculation, e.g. `FLIRR = ratio(NAD(P)H a2[%], FAD a1[%])`."""
    if calculation.kind == "expression":
        return f"{calculation.name} = {calculation.expression}"
    return f"{calculation.name} = {calculation.function}({', '.join(map(str, calculation.args))})"


@register_editor(CalculateConfig, "calculations")
class CalculationsEditor(VariantsEditor):
    """The calculations table, with buttons for presets."""

    def create(self, parent):
        self.columns_of_input: list = []
        return super().create(parent)

    def extra_buttons(self) -> list:
        return [
            ("Add Calculations...", self._on_add_presets),
            ("Save as Presets", self._on_save_presets),
            ("Remove Presets...", self._on_remove_presets),
        ]

    def set_schema(self, schema):
        super().set_schema(schema)
        self.columns_of_input = [] if schema is None else schema.names

    def _table_columns(self) -> list:
        """The input's columns and the columns of the rows already in the table."""
        names = [row.get("name") for _, row in self.rows() if row.get("name")]
        return list(self.columns_of_input) + names

    def _on_add_presets(self, event):
        from flim.core.calculate import applicable, with_prerequisites

        columns = self._table_columns()
        saved = saved_presets()
        offered = applicable(saved + built_in_presets(), columns)
        if not offered:
            wx.MessageBox(
                "No preset applies to this table: their columns are missing, or the"
                " table has their results already.",
                "Add Calculations",
                wx.OK,
            )
            return
        saved_names = {p.name for p in saved}
        labels = [describe(p) + ("  (saved)" if p.name in saved_names else "") for p in offered]
        with wx.MultiChoiceDialog(
            self.control, "Calculations that apply to the table:", "Add Calculations", labels
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            chosen = [offered[i] for i in dialog.GetSelections()]
        for preset in with_prerequisites(chosen, offered, columns):
            self.add_row(preset.model_dump())
        self.grid.AutoSizeColumns()
        self.changed()

    def _selected_rows(self) -> list:
        rows = set(self.grid.GetSelectedRows()) | {self.grid.GetGridCursorRow()}
        return sorted(r for r in rows if 0 <= r < self.grid.GetNumberRows())

    def _on_save_presets(self, event):
        values = [self.rows()[r][1] for r in self._selected_rows()]
        try:
            new = CalculateConfig(calculations=values).calculations
        except ValueError as err:
            wx.MessageBox(f"Not saved: {err}", "Save as Presets", wx.OK | wx.ICON_WARNING)
            return
        if not new:
            wx.MessageBox("Select the rows to save.", "Save as Presets", wx.OK)
            return
        names = {p.name for p in new}
        save_presets([p for p in saved_presets() if p.name not in names] + new)
        wx.MessageBox(
            f"Saved {len(new)} calculation(s); Add Calculations... offers them.",
            "Save as Presets",
            wx.OK,
        )

    def _on_remove_presets(self, event):
        saved = saved_presets()
        if not saved:
            wx.MessageBox(
                "There are no saved calculations (built-in ones can't be removed).",
                "Remove Presets",
                wx.OK,
            )
            return
        with wx.MultiChoiceDialog(
            self.control, "Saved calculations to remove:", "Remove Presets",
            [describe(p) for p in saved],
        ) as dialog:  # fmt: skip
            if dialog.ShowModal() != wx.ID_OK:
                return
            removed = set(dialog.GetSelections())
        save_presets([p for i, p in enumerate(saved) if i not in removed])
