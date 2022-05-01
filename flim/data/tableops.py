import logging
import flim
from flim.plugin import AbstractPlugin, ALL_FEATURES
from flim.plugin import plugin
from importlib_resources import files
from flim.gui.dialogs import BasicAnalysisConfigDlg
import wx
import pandas as pd

@plugin(plugintype="Data")
class Pivot(AbstractPlugin):

    def __init__(self, name="Pivot", **kwargs):
        super().__init__(name=name, **kwargs)
    
    #def __repr__(self):
    #    return f"{'name': {self.name}}"
    
    def __str__(self):
        return self.name
    
    def get_icon(self):
        source = files(flim.resources).joinpath('pivot.png')
        return wx.Bitmap(str(source))
        
    def get_required_categories(self):
        return []
    
    def get_required_features(self):
        return ['any']
        
    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update({
            'grouping': ['Treatment'],
            'features': ALL_FEATURES,
        })
        return params
                
    def output_definition(self):
        return {'Table: Pivoted': pd.DataFrame}
        
    def run_configuration_dialog(self, parent, data_choices={}):
        selgrouping = self.params['grouping']
        selfeatures = self.params['features']
        dlg = BasicAnalysisConfigDlg(parent, 'Pivot Data', 
            input=self.input, 
            selectedgrouping=selgrouping, 
            selectedfeatures=selfeatures)
        if dlg.ShowModal() == wx.ID_OK:
            results = dlg.get_selected()
            self.params.update(results)
            return self.params
        else:	
            return None

    def execute(self):
        data = list(self.input.values())[0]
        selfeatures = [c for c in self.params['features']]
        selgroups = self.params['grouping']
        groups = list(data.select_dtypes('category').columns.values)
        selfeatures.extend(groups)
        data = data[selfeatures]
        results = {}
        indexgroups = [g for g in data.columns.values if g in groups and g not in selgroups]
        logging.debug (f'index groups: {indexgroups}')
        logging.debug (f'pivoting {selgroups} in {groups}')
        data = data.reset_index()
        pivot_data = pd.pivot_table(data[selfeatures], index=indexgroups, columns=selgroups)
        # flatten multiindex in column headers
        pivot_data.columns = ['\n'.join(col).strip() for col in pivot_data.columns.values]    
        
        pivot_data = pivot_data.reset_index()
        results = {'Table: Pivoted': pivot_data}
        return results