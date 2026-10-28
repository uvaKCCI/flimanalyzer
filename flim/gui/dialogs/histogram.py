"""Frequency Histogram: range and bins per feature."""

from flim.configs.plot import HistogramConfig
from flim.gui.dialogs.filter import numeric_ranges
from flim.gui.editors import ModelMapEditor, register_editor


@register_editor(HistogramConfig, "per_feature")
class HistogramRangesEditor(ModelMapEditor):
    """Rows of feature, min, max and bins; "Add Features" adds the selected features
    (or all numeric columns) with their range in the data."""

    def create(self, parent):
        self.tables = []
        self.features = []
        return super().create(parent)

    def extra_buttons(self):
        return [("Add Features", self._on_add_features)]

    def set_data(self, tables):
        self.tables = tables

    def refresh(self, panel):
        features = panel.value_of("features")
        self.features = features if isinstance(features, list) else []

    def _on_add_features(self, event=None):
        present = {key for key, _ in self.rows()}
        ranges = numeric_ranges(self.tables)
        for feature in self.features or list(ranges):
            if feature not in present and feature in ranges:
                low, high = ranges[feature]
                self.add_row({"min": low, "max": high, "bins": 30}, key=feature)
        self.grid.AutoSizeColumns()
        self.changed()
