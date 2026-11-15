"""Autoencoder: Train: the architecture, with its description and layers."""

import logging
from typing import Any

import wx

from flim.configs.analysis import AETrainConfig
from flim.gui.editors import Editor, FieldsPanel, register_editor

logger = logging.getLogger(__name__)


def architecture_info(name: str, n_features: int) -> tuple[str, str]:
    """Return the description and the layers of an autoencoder architecture.

    Args:
        name: The architecture's name.
        n_features: The number of inputs (selected features); values below 1 are
            taken as 1.

    Returns:
        The model's description ("" if it has none) and its layers: the model's
        text without its first and last line (the class name and the closing
        parenthesis). Two empty strings if torch is not available or the model
        cannot be created.
    """
    try:
        import flim.analysis.ml.autoencoder as autoencoder
    except ImportError:
        return "", ""
    try:
        model_class = autoencoder.get_autoencoder_classes()[name]
        model = autoencoder.create_instance(model_class, nb_param=max(n_features, 1))
    except Exception as err:
        logger.debug(f"No information on {name}: {err}")
        return "", ""
    if model is None:
        return "", ""
    layers = "\n".join(str(model).split("\n")[1:-1])  # without the class line
    return model.get_description() or "", layers


@register_editor(AETrainConfig, "architecture")
class ArchitectureEditor(Editor):
    """Choice of the autoencoder architecture, with its description and layers.

    The layers are shown for the number of features selected in the `features`
    field.
    """

    expands = True
    grows = False

    def create(self, parent: wx.Window) -> wx.Window:
        """Create the panel of the choice, the description and the layers."""
        self.values = list(self.spec.choices)
        self.n_features = 0
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.choice = wx.Choice(panel, choices=[str(v) for v in self.values])
        self.choice.Bind(wx.EVT_CHOICE, self._on_choice)
        sizer.Add(self.choice, 0, wx.EXPAND)
        self.description = wx.StaticText(panel, label="")
        sizer.Add(self.description, 0, wx.EXPAND | wx.TOP, 4)
        self.layers = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP
        )
        size = self.layers.GetFont().GetPointSize()
        self.layers.SetFont(wx.Font(wx.FontInfo(size).Family(wx.FONTFAMILY_TELETYPE)))
        self.layers.SetMinSize((-1, 80))
        sizer.Add(self.layers, 0, wx.EXPAND | wx.TOP, 4)
        panel.SetSizer(sizer)
        return panel

    def _on_choice(self, event: wx.CommandEvent) -> None:
        """Show the selected architecture's information."""
        self._show_info()
        self.changed(event)

    def _show_info(self) -> None:
        """Show the description and layers of the selected architecture."""
        index = self.choice.GetSelection()
        if index == wx.NOT_FOUND:
            return
        description, layers = architecture_info(self.values[index], self.n_features)
        self.description.SetLabel(description)
        self.description.Wrap(460)
        self.layers.ChangeValue(layers)
        self.layers.Show(bool(layers))
        self.control.Layout()

    def refresh(self, panel: FieldsPanel) -> None:
        """Show the layers again if the number of selected features changed."""
        features = panel.value_of("features")
        n = len(features) if isinstance(features, list) else 0
        if n != self.n_features:
            self.n_features = n
            self._show_info()

    def get(self) -> Any:
        """Return the selected architecture.

        Raises:
            ValueError: If no architecture is selected.
        """
        index = self.choice.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Select an architecture")
        return self.values[index]

    def set(self, value: Any) -> None:
        """Select an architecture; a value not among the choices is ignored."""
        if value in self.values:
            self.choice.SetSelection(self.values.index(value))
        self._show_info()
