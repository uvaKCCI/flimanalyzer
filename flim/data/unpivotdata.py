from flim.plugin import AbstractPlugin, ALL_FEATURES
import flim.tools.data as tools
from flim.plugin import plugin
import pandas as pd


@plugin(plugintype="Data")
class UnPivot(AbstractPlugin):
    def __init__(self, name="Unpivot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "grouping": [],
                "features": ALL_FEATURES,
                "level": "",
                "category_name": "Category",
            }
        )
        return params

    def output_definition(self):
        return {"Table: Unpivoted": pd.DataFrame}

    def _create_unique_name(self, name, default="", existing=[]):
        i = 1
        if name == "":
            name = default
        while name == "" or name in existing:
            name = f'{name.split("_")[0]}_{i}'
        return name

    def execute(self):
        return self.run_tool(tools.Unpivot, list(self.input.values())[0])
