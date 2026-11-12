"""The Output box of dialogs: the formats to save results in, a column per kind."""

from collections.abc import Callable, Iterable, Sequence
from typing import Any, Optional

import wx

from flim.core.saving import (
    SaveOptions,
    formats_from_values,
    formats_model,
    formats_values,
)
from flim.gui.editors import FieldErrors, FieldsPanel


class FormatsBox(wx.BoxSizer):
    """A row with a column of format fields per kind of output (e.g. tables, plots).

    Each column holds the kind's formats and options, generated from its save
    options, one under the other. Dialogs put the box in their Output section.

    Attributes:
        kinds: The kinds of output, in the order of the columns.
        model: The model of all columns' fields (`formats_model`).
        panels: The columns' panels, one per kind.
        editors: The fields' editors by field name (e.g. `plot_formats`).
        markers: The fields' issue markers by field name.
    """

    def __init__(
        self,
        parent: wx.Window,
        kinds: Iterable[str],
        formats: Sequence[SaveOptions] = (),
        on_change: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Create a column of fields per kind and show the formats.

        Args:
            parent: The dialog; the parent window of the columns' panels.
            kinds: The kinds of output, e.g. `["table", "plot"]`.
            formats: The formats to show (`AutosaveConfig.formats`). Kinds without a
                format in it show their default formats. Defaults to none.
            on_change: Called without arguments when a field changes.
        """
        super().__init__(wx.HORIZONTAL)
        self.kinds = list(kinds)
        self.model = formats_model(self.kinds)
        self.panels = []
        for kind in self.kinds:
            panel = FieldsPanel(parent, formats_model([kind]), stacked=True)
            panel.on_change = on_change
            self.Add(panel, 0, wx.ALL, 6)
            self.panels.append(panel)
        self.editors = {n: e for p in self.panels for n, e in p.editors.items()}
        self.markers = {n: m for p in self.panels for n, m in p.markers.items()}
        self.set(formats)

    def set(self, formats: Sequence[SaveOptions]) -> None:
        """Show formats (`AutosaveConfig.formats`); kinds not listed get defaults."""
        values = formats_values(self.model, list(formats), self.kinds)
        for panel in self.panels:
            panel.set_values(values)

    def formats(self) -> tuple[list[SaveOptions], dict[str, str]]:
        """Return the chosen formats and an error message per field name.

        Returns:
            The formats and an empty dict; or, if a field has text that is not a
            valid value or a kind has no format, an empty list and the errors.
        """
        values, errors = {}, {}
        for panel in self.panels:
            try:
                values.update(panel.values(panel.model()))
            except FieldErrors as err:
                errors.update(err.errors)
        if errors:
            return [], errors
        return formats_from_values(values, self.kinds)

    def Enable(self, enabled: bool = True) -> None:
        """Enable or disable the fields of all columns."""
        for panel in self.panels:
            panel.Enable(enabled)

    def show_issue(self, name: str, severity: Optional[str], message: str = "") -> None:
        """Show or clear the issue marker of a field.

        Args:
            name: The field name, e.g. `plot_formats`.
            severity: `error`, `warning` or `guessed`; None clears the marker.
            message: The marker's tooltip text.
        """
        for panel in self.panels:
            if name in panel.editors:
                panel.show_issue(name, severity, message)

    def show_errors(self, errors: dict[str, str], enabled: bool = True) -> None:
        """Mark the fields with errors and clear the other fields' markers.

        Args:
            errors: Error messages by field name, as returned by `formats`.
            enabled: False clears all markers. Defaults to True.
        """
        for name in self.editors:
            message = errors.get(name) if enabled else None
            self.show_issue(name, "error" if message else None, message or "")
