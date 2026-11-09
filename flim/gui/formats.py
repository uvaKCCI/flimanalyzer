"""The Output box of dialogs: the formats to save results in, a column per kind."""

import wx

from flim.core.saving import formats_from_values, formats_model, formats_values
from flim.gui.editors import FieldErrors, FieldsPanel


class FormatsBox(wx.StaticBoxSizer):
    """A box titled "Output" with a column per kind of output (e.g. Tables, Plots); each
    column holds the kind's formats and options, generated from its save options, one
    under the other.

    Attributes:
        editors: The fields' editors by field name (e.g. `plot_formats`).
        markers: The fields' issue markers by field name.
    """

    def __init__(self, parent, kinds, formats=(), on_change=None):
        """
        Args:
            parent: The dialog.
            kinds: The kinds of output, e.g. `["table", "plot"]`.
            formats: The formats to show (`AutosaveConfig.formats`); defaults per kind.
            on_change: Called when a field changes.
        """
        super().__init__(wx.HORIZONTAL, parent, "Output")
        self.kinds = list(kinds)
        self.model = formats_model(self.kinds)
        self.panels = []
        for kind in self.kinds:
            panel = FieldsPanel(self.GetStaticBox(), formats_model([kind]), stacked=True)
            panel.on_change = on_change
            self.Add(panel, 0, wx.ALL, 6)
            self.panels.append(panel)
        self.editors = {n: e for p in self.panels for n, e in p.editors.items()}
        self.markers = {n: m for p in self.panels for n, m in p.markers.items()}
        self.set(formats)

    def set(self, formats) -> None:
        """Show formats (`AutosaveConfig.formats`); kinds not listed get defaults."""
        values = formats_values(self.model, list(formats), self.kinds)
        for panel in self.panels:
            panel.set_values(values)

    def formats(self) -> tuple[list, dict]:
        """Return the chosen formats, and an error per field (e.g. no format)."""
        values, errors = {}, {}
        for panel in self.panels:
            try:
                values.update(panel.values(panel.model()))
            except FieldErrors as err:
                errors.update(err.errors)
        if errors:
            return [], errors
        return formats_from_values(values, self.kinds)

    def Enable(self, enabled=True) -> None:
        for panel in self.panels:
            panel.Enable(enabled)

    def show_issue(self, name, severity, message="") -> None:
        for panel in self.panels:
            if name in panel.editors:
                panel.show_issue(name, severity, message)

    def show_errors(self, errors: dict, enabled: bool = True) -> None:
        """Mark the fields with errors; none while `enabled` is False."""
        for name in self.editors:
            message = errors.get(name) if enabled else None
            self.show_issue(name, "error" if message else None, message or "")
