"""Settings management: the SettingsManager service, which manages the settings of a
running FLIMAnalyzer (GUI or flimbatch), and the user settings file it writes changes
to."""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional, Sequence

from filelock import FileLock
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from flim.core.config import TaskConfig
from flim.core.execution import ExecutorSettings
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
APP_SETTINGS_PATH_VAR = "FLIM_APP_SETTINGS_PATH"


def user_settings_path() -> Path:
    """Path of the user settings file: the value of FLIM_USER_SETTINGS if set, else
    usersettings.json in the platform's settings folder (macOS: ~/Library/Application
    Support/FLIMAnalyzer; Linux: $XDG_CONFIG_HOME/FLIMAnalyzer, by default
    ~/.config/FLIMAnalyzer; Windows: %LOCALAPPDATA%\\FLIMAnalyzer)."""
    if os.environ.get("FLIM_USER_SETTINGS"):
        return Path(os.environ["FLIM_USER_SETTINGS"]).expanduser()
    from platformdirs import user_config_dir

    return Path(user_config_dir(APP_NAME, appauthor=False)) / "usersettings.json"


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
        self.source: Optional[Path] = None  # the app settings file of this session

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


# --- app settings files and their search path ---


def default_app_settings_dir() -> Path:
    """Return the default folder of app settings files.

    Returns:
        The folder `appsettings` in the platform's settings folder, e.g.
        `~/Library/Application Support/FLIMAnalyzer/appsettings` on macOS.
    """
    from platformdirs import user_config_dir

    return Path(user_config_dir(APP_NAME, appauthor=False)) / "appsettings"


def app_settings_path(user_path: Sequence[Path] = ()) -> list[Path]:
    """Return the folders searched for app settings files, in search order.

    Args:
        user_path: The `appsettings_path` of the user settings file.

    Returns:
        The folders of `FLIM_APP_SETTINGS_PATH` if it is set (separated by
        `os.pathsep`), otherwise `user_path` if it is not empty, otherwise the default
        folder. `~` is expanded; empty entries are ignored.
    """
    value = os.environ.get(APP_SETTINGS_PATH_VAR)
    if value:
        folders = [Path(p) for p in value.split(os.pathsep) if p]
    else:
        folders = [Path(p) for p in user_path] or [default_app_settings_dir()]
    return [f.expanduser() for f in folders]


def find_app_settings(name: str | os.PathLike, search_path: Sequence[Path]) -> Path:
    """Resolve the argument of `-s` to one app settings file.

    A path that exists as given (relative to the current folder, or absolute) is
    used. Otherwise the file name is looked up in each folder of `search_path`, as
    given and with `.json` appended.

    Args:
        name: The file name or path given with `-s`.
        search_path: The folders to search, from `app_settings_path`.

    Returns:
        The path of the app settings file.

    Raises:
        FileNotFoundError: If no file matches; the message names the folders searched.
        ValueError: If files in several folders match; the message names them.
    """
    given = Path(name).expanduser()
    if given.is_file():
        return given
    names = [given.name] if given.suffix == ".json" else [given.name, given.name + ".json"]
    matches = [f / n for f in search_path for n in names if (f / n).is_file()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        searched = ", ".join(str(f) for f in search_path) or "no folders"
        raise FileNotFoundError(f"No app settings file '{name}' here or in {searched}")
    found = ", ".join(str(m) for m in matches)
    raise ValueError(f"App settings file '{name}' is ambiguous: {found}")


def list_app_settings(search_path: Sequence[Path]) -> list[Path]:
    """Return the app settings files in the folders of a search path.

    Args:
        search_path: The folders to list, from `app_settings_path`.

    Returns:
        The `.json` files of each existing folder, sorted by name within a folder, in
        the order of the folders.
    """
    return [p for f in search_path if f.is_dir() for p in sorted(f.glob("*.json"))]


# --- the environment ---


class EnvSettings(BaseSettings):
    """App settings from environment variables with the prefix `FLIM_`.

    Only these app-level fields can be set this way; nested fields of the executor use
    `__`, e.g. `FLIM_EXECUTION__EXECUTOR=dask-local`, or `FLIM_EXECUTION` holds them as
    JSON. `FLIM_CACHE_DIR` sets `cache.dir`.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLIM_", env_nested_delimiter="__", extra="ignore"
    )
    results_dir: Optional[Path] = None
    execution: Optional[ExecutorSettings] = None
    prefect_server: Optional[bool] = None
    log_dir: Optional[Path] = None
    cache_dir: Optional[Path] = None
    strict: Optional[bool] = None


def environment_changes() -> dict:
    """Return the settings set by environment variables, as sections to apply.

    Returns:
        The sections set by the environment; empty if none is set. `FLIM_CACHE_DIR`
        gives the partial section `{"cache": {"dir": ...}}`.

    Raises:
        ValueError: If a variable has an invalid value; the message names it.
    """
    try:
        env = EnvSettings()
    except ValidationError as err:
        names = sorted(
            {"FLIM_" + "__".join(str(p) for p in e["loc"][:2]).upper() for e in err.errors()}
        )
        raise ValueError(f"Invalid environment variable: {', '.join(names)}") from None
    values = env.model_dump(mode="json", exclude_none=True)
    changes = {
        key: values[key]
        for key in ("results_dir", "execution", "prefect_server", "log_dir", "strict")
        if key in values
    }
    if "cache_dir" in values:
        changes["cache"] = {"dir": values["cache_dir"]}
    return changes


def _completed(changes: dict, current: AppSettings) -> dict:
    """Return `changes` with a partial `cache` section completed from `current`."""
    if "cache" not in changes:
        return changes
    cache = {**current.cache.model_dump(mode="json"), **changes["cache"]}
    return {**changes, "cache": cache}


# --- the settings of a session ---


def session_settings(
    settings_file: Optional[str] = None,
    command_line: Optional[dict] = None,
    *,
    user_file: Optional[UserSettingsFile] = None,
    base: Optional[AppSettings] = None,
) -> SettingsManager:
    """Create the settings manager of a session from all settings layers.

    Layers, lowest first: `base`, the user settings file, the app settings file
    `settings_file`, the environment, the command line. Only changes made later during
    the session are written to the user settings file.

    Args:
        settings_file: The argument of `-s`: a path, or a name in the app settings
            folders (see `find_app_settings`). None: no app settings file.
        command_line: The sections set on the command line (`flim.core.cli`); a
            `cache` section may be partial.
        user_file: The user settings file; None in flimbatch, whose runs do not depend
            on settings changed in the GUI.
        base: The lowest layer. Defaults to the built-in defaults.

    Returns:
        The settings manager. Its `source` is the path of the app settings file, or
        None.

    Raises:
        FileNotFoundError: If `settings_file` matches no file.
        ValueError: If `settings_file` is ambiguous or not a settings file, or if an
            environment variable or a command-line value is invalid.
    """
    manager = SettingsManager(base, user_file)
    if settings_file:
        search_path = app_settings_path(manager.settings.appsettings_path)
        path = find_app_settings(settings_file, search_path)
        manager.load(path)
        manager.source = path
    for changes in (environment_changes(), command_line or {}):
        if changes:
            manager.update(_completed(changes, manager.settings), keep=False)
    return manager


# settings file read at startup in the start folder (deprecated: the user settings file
# replaces it)
DEFAULTS_FILE = "defaults.json"


def start_folder_defaults() -> AppSettings:
    """Return the settings of `defaults.json` in the start folder, if it exists.

    Returns:
        The built-in defaults with the file's sections applied; the built-in defaults
        if there is no such file, or if it cannot be read (the error is logged).
    """
    from flim.core.settings import load_settings

    if os.path.isfile(DEFAULTS_FILE):
        try:
            return load_settings(DEFAULTS_FILE)
        except Exception:
            logging.exception(f"Settings in {DEFAULTS_FILE} could not be read")
    return AppSettings.default()

