import logging
import flim
from flim.plugin import AbstractPlugin, ALL_FEATURES
from flim.plugin import plugin
from importlib_resources import files
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import pandas as pd


class UnPivotConfigDlg(BasicAnalysisConfigDlg):
    def __init__(
        self,
        parent,
        title,
        input=None,
        selectedgrouping=["None"],
        selectedfeatures="All",
        category_name="",
        feature_name="",
        autosave=True,
        working_dir="",
    ):
        self.category_name = category_name
        self.feature_name = feature_name
        super().__init__(
            self,
            parent,
            title,
            input=input,
            enablegrouping=False,
            enablefeatures=True,
            selectedgrouping=selectedgrouping,
            selectedfeatures=selectedfeatures,
            optgridrows=2,
            optgridcols=1,
            autosave=autosave,
            working_dir=working_dir,
        )

    def get_option_panels(self):
        hsizer = wx.BoxSizer(wx.VERTICAL)
        self.category_field = wx.TextCtrl(
            self.panel, value=self.category_name, size=(500, -1)
        )
        hsizer.Add(
            wx.StaticText(self.panel, label="New Category Column"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        hsizer.Add(self.category_field, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        self.feature_field = wx.TextCtrl(
            self.panel, value=self.feature_name, size=(500, -1)
        )
        hsizer.Add(
            wx.StaticText(self.panel, label="New Feature Column"),
            0,
            wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            5,
        )
        hsizer.Add(self.feature_field, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        return [hsizer]

    def _get_selected(self):
        params = super()._get_selected()
        params["category_name"] = self.category_field.GetValue()
        params["feature_name"] = self.feature_field.GetValue()
        return params


@plugin(plugintype="Data")
class UnPivot(AbstractPlugin):
    def __init__(self, name="Unpivot", **kwargs):
        super().__init__(name=name, **kwargs)

    # def __repr__(self):
    #    return f"{'name': {self.name}}"

    def __str__(self):
        return self.name

    def get_icon(self):
        source = files(flim.resources).joinpath("unpivot.png")
        return wx.Bitmap(str(source))

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
                "category_name": "Category",
                "feature_name": "Feature",
            }
        )
        return params

    def output_definition(self):
        return {"Table: Unpivoted": pd.DataFrame}

    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params["grouping"]
        selfeatures = self.params["features"]
        category_name = self.params["category_name"]
        feature_name = self.params["feature_name"]
        dlg = UnPivotConfigDlg(
            parent,
            "Unpivot Data",
            input=self.input,
            selectedgrouping=selgrouping,
            selectedfeatures=selfeatures,
            category_name=category_name,
            feature_name=feature_name,
            autosave=self.params["autosave"],
            working_dir=self.params["working_dir"],
        )
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:
            return None

    def _create_unique_name(self, name, default="", existing=[]):
        i = 1
        if name == "":
            name = default
        while name == "" or name in existing:
            name = f'{name.split("_")[0]}_{i}'
        return name

    def execute(self):
        data = list(self.input.values())[0]
        cat_cols = list(data.select_dtypes("category").columns.values)
        sel_features = [c for c in self.params["features"]]
        new_cat_name = self._create_unique_name(
            self.params["category_name"], "Category", existing=cat_cols
        )
        new_value_name = self._create_unique_name(
            self.params["feature_name"], "Feature", existing=sel_features
        )
        unpivot_data = pd.melt(
            data,
            id_vars=cat_cols,
            value_vars=sel_features,
            var_name=new_cat_name,
            value_name=new_value_name,
        )
        unpivot_data[new_cat_name] = unpivot_data[new_cat_name].astype("category")
        results = {"Table: Unpivoted": unpivot_data}
        return results
