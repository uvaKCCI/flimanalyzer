"""Settings management: the SettingsManager service, which manages the settings of a
running FLIMAnalyzer (GUI or flimbatch), and the user settings file it writes changes
to."""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from filelock import FileLock

from flim.core.config import TaskConfig
from flim.core.settings import (
    SETTINGS_VERSION,
    AppSettings,
    merge_sections,
    migrate,
    save_settings,
    tool_settings,
    update_settings,
)

APP_NAME = "FLIMAnalyzer"
LOCK_TIMEOUT = 10  # seconds to wait for another instance writing the user settings file


def user_settings_path() -> Path:
    """Path of the user settings file: the value of FLIM_USER_SETTINGS if set, else
    settings.json in the platform's settings folder (macOS: ~/Library/Application
    Support/FLIMAnalyzer; Linux: $XDG_CONFIG_HOME/FLIMAnalyzer, by default
    ~/.config/FLIMAnalyzer; Windows: %LOCALAPPDATA%\\FLIMAnalyzer)."""
    if os.environ.get("FLIM_USER_SETTINGS"):
        return Path(os.environ["FLIM_USER_SETTINGS"]).expanduser()
    from platformdirs import user_config_dir

    return Path(user_config_dir(APP_NAME, appauthor=False)) / "settings.json"


class UserSettingsFile:
    """The settings the user changed, in the settings file format (read in any
    version, written in the current one). Several instances may write the file. Each
    change is merged into the file's current content and written atomically, under a
    lock file, so an instance overwrites only the sections it changes; changes by other
    instances to other sections are preserved. If two instances change the same section
    (e.g. the same tool), the instance that saves last takes precedence."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = FileLock(f"{self.path}.lock", timeout=LOCK_TIMEOUT)

    def read(self) -> dict:
        """The file's sections, migrated to the current version. Returns {} if the file
        does not exist, cannot be read or is not a settings file; in the latter two
        cases a warning is logged."""
        try:
            with open(self.path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("not a settings file")
            return migrate(data)
        except FileNotFoundError:
            return {}
        except Exception as err:
            logging.warning(f"User settings {self.path} not used: {err}")
            return {}

    def merge(self, changes: dict) -> None:
        """Writes ``changes`` (sections in the settings file format, any version) to
        the file: under the lock file, reads the file's current content, replaces only
        these sections (tools: each tool's section), writes the result to a temporary
        file in the same folder and replaces the file with it. Creates the folder if it
        does not exist. If writing fails, the file is left unchanged and the exception
        is raised (filelock.Timeout if the lock is not acquired within LOCK_TIMEOUT)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            data = merge_sections(self.read(), changes)
            data["schema_version"] = SETTINGS_VERSION
            fd, tmp = tempfile.mkstemp(
                dir=self.path.parent, prefix=".settings-", suffix=".json"
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                os.replace(tmp, self.path)  # atomic: readers get either the old or the new file
            except BaseException:
                os.unlink(tmp)
                raise


class SettingsManager:
    """Manages the settings of this instance (GUI or flimbatch). All
    changes are applied through it, one at a time: it validates and applies them,
    writes the changed sections to the user settings file and counts versions.
    ``settings`` returns a copy, so the settings cannot be modified except through the
    manager, and a run uses the settings in effect when it started."""

    def __init__(
        self,
        base: Optional[AppSettings] = None,
        user_file: Optional[UserSettingsFile] = None,
    ):
        """Args:
            base: the settings the user settings file is applied to (default: the
                built-in defaults).
            user_file: the UserSettingsFile changes are written to; None: changes are
                kept in memory only.
        """
        self._lock = threading.RLock()
        self._user_file = user_file
        settings = base if base is not None else AppSettings.default()
        if user_file is not None:
            settings = update_settings(settings, user_file.read())
        self._settings = settings
        self._version = 0

    @property
    def settings(self) -> AppSettings:
        """A copy of the current settings."""
        with self._lock:
            return self._settings.model_copy(deep=True)

    @property
    def version(self) -> int:
        """The number of changes applied since the manager was created."""
        return self._version

    def update(self, changes: dict, *, keep: bool = True) -> AppSettings:
        """Applies ``changes``: sections in the settings file format, in the current
        version unless they contain ``schema_version``; each replaces the current
        section, tools each tool's section. They are validated as when a file is
        loaded: unknown keys are logged and ignored; invalid values raise a validation
        error and leave the settings unchanged. ``keep``: also write them to the user
        settings file; if writing fails, a warning is logged and the change remains in
        effect. Returns a copy of the new settings."""
        changes = {"schema_version": SETTINGS_VERSION, **changes}
        with self._lock:
            self._settings = update_settings(self._settings, changes)
            self._version += 1
            if keep and self._user_file is not None:
                try:
                    self._user_file.merge(changes)
                except Exception as err:
                    logging.warning(f"Settings not saved to {self._user_file.path}: {err}")
            return self._settings.model_copy(deep=True)

    def set_tool(self, tool, config: TaskConfig, autosave=False, results_dir=None) -> AppSettings:
        """Sets a tool's config and run settings (autosave, results folder) under the
        tool's name and writes them to the user settings file. Settings stored under
        the tool's former names are removed. Returns a copy of the new settings."""
        entry = tool_settings(config, autosave, results_dir)
        return self.update({"tools": {tool.name: entry.model_dump(mode="json")}})

    def load(self, path) -> AppSettings:
        """Applies the sections of a settings file (any version) for this session; they
        are not written to the user settings file. Returns a copy of the new settings.
        Raises ValueError if the file does not hold a JSON object (and the errors of
        reading, migrating and validating it); the settings are then unchanged."""
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a settings file")
        return self.update(migrate(data), keep=False)

    def export(self, path) -> None:
        """Writes all current settings, in the current version, to a file."""
        save_settings(self.settings, path)
