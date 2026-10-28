from flim.plugin import AbstractPlugin, ALL_FEATURES
import flim.tools.data as tools
from flim.plugin import plugin
import pandas as pd


@plugin(plugintype="Data")
class Pivot(AbstractPlugin):
    def __init__(self, name="Pivot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "grouping": ["Treatment"],
                "features": ALL_FEATURES,
            }
        )
        return params

    def output_definition(self):
        return {"Table: Pivoted": pd.DataFrame}

    def execute(self):
        return self.run_tool(tools.Pivot, list(self.input.values())[0])
