"""The Separate Categories dialog, with presets of its settings.

The presets are the built-in ones (the filename parsers of FLIMAnalyzer 0.6, see
`flim.core.categories.separate_presets`) and those saved in the user settings file
(`separate_presets`). `Remove Presets...` removes saved ones; the built-in ones
can't be removed.
"""

import logging
from typing import TYPE_CHECKING, Callable, Optional

import wx

from flim.configs.data import SeparateCategoriesConfig
from flim.core.categories import PRESET_FIELDS, separate_presets
from flim.gui.configdialog import ConfigDialog, register_dialog

if TYPE_CHECKING:
    from flim.core.settingsmgr import SettingsManager

logger = logging.getLogger(__name__)

_settings_manager: Optional["SettingsManager"] = None  # the session's (see bind)


def bind(settings_manager: "SettingsManager") -> None:
    """Use a session's settings for the saved presets.

    Args:
        settings_manager: The SettingsManager of the session.
    """
    global _settings_manager
    _settings_manager = settings_manager


def saved_presets() -> list[dict]:
    """Return the presets saved in the user settings file.

    Presets that are not valid are left out, with a warning in the log.

    Returns:
        One dict per preset: its `name` and its `settings`; empty if no settings
        manager is bound.
    """
    if _settings_manager is None:
        return []
    presets = []
    for data in _settings_manager.settings.separate_presets:
        try:
            SeparateCategoriesConfig.model_validate(data["settings"])
            presets.append({"name": str(data["name"]), "settings": dict(data["settings"])})
        except (KeyError, TypeError, ValueError) as err:
            logger.warning(f"Saved Separate Categories preset not valid, not offered: {err}")
    return presets


def save_presets(presets: list[dict]) -> None:
    """Replace the saved presets in the user settings file.

    Nothing is saved if no settings manager is bound (`bind`).

    Args:
        presets: One dict per preset: its `name` and its `settings`.
    """
    if _settings_manager is not None:
        _settings_manager.update({"separate_presets": presets})


@register_dialog(SeparateCategoriesConfig)
class SeparateDialog(ConfigDialog):
    """The Separate Categories dialog, with buttons for presets below the settings.

    The buttons are `Load Preset...`, `Save as Preset...` and `Remove Presets...`.
    """

    def settings_buttons(
        self,
    ) -> list[tuple[str, str, Callable[[wx.CommandEvent], None]]]:
        """Return the buttons of the base class and the buttons for presets."""
        return super().settings_buttons() + [
            ("Load Preset...", "Settings of a built-in or saved preset", self._on_load_preset),
            ("Save as Preset...", "Save how to separate, to load later", self._on_save_preset),
            ("Remove Presets...", "Remove saved presets", self._on_remove_presets),
        ]

    def _current(self) -> SeparateCategoriesConfig:
        """Return the edited config, or the dialog's config if it is not valid."""
        config, _ = self.current_config()
        return config if config is not None else self.config

    def apply_preset(self, preset: dict) -> None:
        """Show a preset's settings in the fields; the other fields are kept."""
        data = {**self._current().model_dump(), **preset["settings"]}
        self.set_values(SeparateCategoriesConfig.model_validate(data))
        self.validate()
        self.settings_message.SetLabel(f"Preset {preset['name']}")

    def _on_load_preset(self, event: wx.CommandEvent) -> None:
        """Ask for a built-in or saved preset and show its settings."""
        presets = separate_presets() + saved_presets()
        labels = [p["name"] for p in separate_presets()] + [
            f"{p['name']} (saved)" for p in saved_presets()
        ]
        with wx.SingleChoiceDialog(self, "Preset:", "Load Preset", labels) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            preset = presets[dialog.GetSelection()]
        self.apply_preset(preset)

    def _on_save_preset(self, event: wx.CommandEvent) -> None:
        """Ask for a name and save the values of `PRESET_FIELDS` as a preset.

        A saved preset of the same name is replaced; a built-in preset's name is
        refused with a message.
        """
        with wx.TextEntryDialog(self, "Name of the preset:", "Save as Preset") as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            name = dialog.GetValue().strip()
        if not name:
            return
        if name in [p["name"] for p in separate_presets()]:
            wx.MessageBox(f"'{name}' is a built-in preset; choose another name.", "Save as Preset")
            return
        data = self._current().model_dump(mode="json")
        settings = {name: data[name] for name in PRESET_FIELDS}
        presets = [p for p in saved_presets() if p["name"] != name]  # same name: replaced
        save_presets(presets + [{"name": name, "settings": settings}])
        self.settings_message.SetLabel(f"Saved as preset {name}")

    def _on_remove_presets(self, event: wx.CommandEvent) -> None:
        """Ask for saved presets and remove them."""
        saved = saved_presets()
        if not saved:
            wx.MessageBox("No saved presets.", "Remove Presets")
            return
        names = [p["name"] for p in saved]
        with wx.MultiChoiceDialog(self, "Saved presets to remove:", "Remove Presets", names) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            remove = {names[i] for i in dialog.GetSelections()}
        save_presets([p for p in saved if p["name"] not in remove])
