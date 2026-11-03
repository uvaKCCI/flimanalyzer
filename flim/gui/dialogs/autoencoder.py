"""Autoencoder: Train: the architecture, with its description and layers."""

import logging

import wx

from flim.configs.analysis import AETrainConfig
from flim.gui.editors import Editor, register_editor


def architecture_info(name: str, n_features: int) -> tuple[str, str]:
    """(description, layers) of an architecture for ``n_features`` inputs; empty if
    torch is not available."""
    try:
        import flim.analysis.ml.autoencoder as autoencoder
    except ImportError:
        return "", ""
    try:
        model_class = autoencoder.get_autoencoder_classes()[name]
        model = autoencoder.create_instance(model_class, nb_param=max(n_features, 1))
    except Exception as err:
        logging.debug(f"No information on {name}: {err}")
        return "", ""
    if model is None:
        return "", ""
    layers = "\n".join(str(model).split("\n")[1:-1])  # without the class line
    return model.get_description() or "", layers


@register_editor(AETrainConfig, "architecture")
class ArchitectureEditor(Editor):
    """The architecture choice, with the description and layers of the selected one
    (for the number of selected features)."""

    expands = True
    grows = False

    def create(self, parent):
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

    def _on_choice(self, event):
        self._show_info()
        self.changed(event)

    def _show_info(self):
        index = self.choice.GetSelection()
        if index == wx.NOT_FOUND:
            return
        description, layers = architecture_info(self.values[index], self.n_features)
        self.description.SetLabel(description)
        self.description.Wrap(460)
        self.layers.ChangeValue(layers)
        self.layers.Show(bool(layers))
        self.control.Layout()

    def refresh(self, panel):
        features = panel.value_of("features")
        n = len(features) if isinstance(features, list) else 0
        if n != self.n_features:
            self.n_features = n
            self._show_info()

    def get(self):
        index = self.choice.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError("Select an architecture")
        return self.values[index]

    def set(self, value):
        if value in self.values:
            self.choice.SetSelection(self.values.index(value))
        self._show_info()
