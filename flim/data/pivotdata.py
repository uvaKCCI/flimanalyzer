import logging
import flim
from flim.plugin import AbstractPlugin, ALL_FEATURES
import flim.tools.data as tools
from flim.plugin import plugin
from importlib_resources import files
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import pandas as pd


@plugin(plugintype="Data")
class Pivot(AbstractPlugin):
    def __init__(self, name="Pivot", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_icon(self):
        source = files(flim.resources).joinpath("pivot.png")
        return wx.Bitmap(str(source))

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

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]
        dlg = BasicAnalysisConfigDlg(
            parent,
            "Pivot Data",
            input=self.input,
            selectedgrouping=selgrouping,
            selectedfeatures=selfeatures,
            saveconfig=self.params["saveconfig"],
            config_file=self.params["config_file"],
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def execute(self):
        return self.run_tool(tools.Pivot, list(self.input.values())[0])
