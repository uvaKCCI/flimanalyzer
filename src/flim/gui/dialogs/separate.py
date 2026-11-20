"""The Separate Categories dialog, with presets of its settings.

The presets are the built-in ones (the filename parsers of FLIMAnalyzer 0.6, see
`flim.core.categories.separate_presets`) and those saved in the user settings file
(`presets` > `Separate Categories`). `Remove Presets...` removes saved ones; the built-in ones
cannot be removed.
"""

from flim.configs.data import SeparateCategoriesConfig
from flim.core.categories import PRESET_FIELDS, separate_presets
from flim.gui.configdialog import PresetsDialog, register_dialog


@register_dialog(SeparateCategoriesConfig)
class SeparateDialog(PresetsDialog):
    """The Separate Categories dialog, with buttons for presets below the settings.

    The buttons are `Load Preset...`, `Save as Preset...` and `Remove Presets...`;
    a preset sets the fields of `PRESET_FIELDS`.
    """

    preset_fields = tuple(PRESET_FIELDS)

    def built_in_presets(self) -> list[dict]:
        """Return the presets of the 0.6 filename parsers."""
        return separate_presets()
