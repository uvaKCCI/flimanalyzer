"""Settings management: the SettingsManager service, which manages the settings of a
running FLIMAnalyzer (GUI or flimbatch), and the user settings file it writes changes
to."""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

from filelock import FileLock
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from flim.core.config import TaskConfig
from flim.core.execution import ExecutorSettings
from flim.core.settings import (
    SETTINGS_VERSION,
    AppSettings,
    SettingsCheck,
    check_settings_file,
    merge_sections,
    migrate,
    tool_settings,
    update_settings,
)

APP_NAME = "FLIMAnalyzer"
LOCK_TIMEOUT = 10  # seconds to wait for another instance writing the user settings file
APP_SETTINGS_PATH_VAR = "FLIM_APP_SETTINGS_PATH"
# the environment variables and command-line options of the app settings
ENV_NAMES = {
    "results_dir": "FLIM_RESULTS_DIR",
    "execution": "FLIM_EXECUTION",
    "prefect_server": "FLIM_PREFECT_SERVER",
    "log_dir": "FLIM_LOG_DIR",
    "cache": "FLIM_CACHE_DIR",
    "strict": "FLIM_STRICT",
}
OPTION_NAMES = {
    "results_dir": "-o",
    "execution": "-e",
    "prefect_server": "--no-prefect-server",
    "log_dir": "--log-dir",
    "cache": "--cache-dir",
    "strict": "--strict, --no-strict",
}


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
        # an unreadable file renamed by `read`: (new path or None, the reason)
        self.set_aside: Optional[tuple[Optional[Path], str]] = None

    def read(self) -> dict:
        """Return the file's sections, migrated to the current version.

        A file that cannot be read (not JSON, not a settings file, or of a newer
        version) is renamed to `<name>.unreadable.json` (`-2`, `-3`, ... if that
        exists), so that writing the next change does not replace it; `set_aside`
        records this and a warning is logged. If it cannot be renamed, changes are
        not written to it (`merge` raises OSError).

        Returns:
            The sections; {} if the file does not exist or cannot be read.
        """
        try:
            with open(self.path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("not a settings file")
            return migrate(data)
        except FileNotFoundError:
            return {}
        except Exception as err:
            self._set_aside(str(err))
            return {}

    def _set_aside(self, reason: str) -> None:
        """Rename the unreadable file to a free `<name>.unreadable[-N].json`."""
        stem, suffix = self.path.stem, self.path.suffix
        target = self.path.with_name(f"{stem}.unreadable{suffix}")
        number = 2
        while target.exists():
            target = self.path.with_name(f"{stem}.unreadable-{number}{suffix}")
            number += 1
        try:
            os.rename(self.path, target)
        except FileNotFoundError:  # renamed by another instance
            return
        except OSError as err:
            logging.warning(f"User settings {self.path} cannot be read ({reason}) or renamed ({err})")
            self.set_aside = (None, reason)
            return
        logging.warning(f"User settings {self.path} cannot be read ({reason}); renamed to {target}")
        self.set_aside = (target, reason)

    def merge(self, changes: dict) -> None:
        """Writes ``changes`` (sections in the settings file format, any version) to
        the file: under the lock file, reads the file's current content, replaces only
        these sections (tools: each tool's section), writes the result to a temporary
        file in the same folder and replaces the file with it. Creates the folder if it
        does not exist. If writing fails, the file is left unchanged and the exception
        is raised (filelock.Timeout if the lock is not acquired within LOCK_TIMEOUT)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            current = self.read()
            if self.set_aside and self.set_aside[0] is None:
                raise OSError(f"{self.path} cannot be read or renamed: {self.set_aside[1]}")
            data = merge_sections(current, changes)
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


def _sections(data: dict) -> list[str]:
    """Return the section names of settings data, without `schema_version`."""
    return [key for key in data if key != "schema_version"]


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
        # setting -> the layer that set it, e.g. "user settings file"; settings not
        # listed have their built-in defaults
        self.origins: dict[str, str] = {}
        if user_file is not None:
            data = user_file.read()
            settings = update_settings(settings, data)
            self.origins.update(dict.fromkeys(_sections(data), "user settings file"))
        self._settings = settings
        self._version = 0
        self.source: Optional[Path] = None  # the app settings file of this session
        self.check: Optional[SettingsCheck] = None  # the check of that file
        # messages for the user about the settings files, e.g. a renamed user file
        self.notices: list[str] = []
        if user_file is not None and user_file.set_aside:
            target, reason = user_file.set_aside
            if target is None:
                self.notices.append(
                    f"The user settings file {user_file.path} cannot be read ({reason})"
                    " and cannot be renamed. Changes to the settings are kept until"
                    " FLIMAnalyzer closes, and not saved."
                )
            else:
                self.notices.append(
                    f"The user settings file {user_file.path} cannot be read ({reason})."
                    f" It was renamed to {target}, and a new user settings file is"
                    " started. If it is from a newer FLIMAnalyzer, rename it back"
                    " before using that version again."
                )

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
            if keep:
                self.origins.update(dict.fromkeys(_sections(changes), "user settings file"))
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
        Raises ValueError if the file cannot be used or has invalid values (see
        `strict_choice`); the settings are then unchanged."""
        return self.apply(strict_choice(check_settings_file(path)))

    def apply(self, check: SettingsCheck) -> AppSettings:
        """Applies the usable sections of a checked settings file for this session;
        they are not written to the user settings file. The check is logged.

        Args:
            check: The result of `check_settings_file`.

        Returns:
            A copy of the new settings.
        """
        logging.info(check.summary())
        settings = self.update(check.sections, keep=False)
        self.source = check.path
        self.check = check
        self.origins.update(dict.fromkeys(_sections(check.sections), "app settings file"))
        return settings

    def record(self) -> list[str]:
        """Return the settings files of this session, for the run summary.

        Returns:
            Lines naming the user settings file and the app settings file, with the
            app settings file's schema version and the keys its check converted,
            removed and did not use.
        """
        user = self._user_file.path if self._user_file is not None else "not read"
        lines = [f"User settings file: {user}"]
        check = self.check
        if check is None:
            return lines + ["App settings file: none"]
        lines.append(f"App settings file: {check.path} (schema version {check.version})")
        for label, items in (
            ("converted", check.converted),
            ("removed by the conversion", check.dropped),
            ("not used (unknown)", check.unknown),
            ("not used (invalid)", check.invalid),
            ("not checked (tool not installed)", check.not_checked),
        ):
            if items:
                lines.append(f"  {label}: {'; '.join(items)}")
        return lines

    def export(self, path) -> None:
        """Write all current settings, in the current version, to an app settings file.

        Every installed tool's settings are written, its defaults if none are set, so
        that the file does not depend on the defaults of the version that reads it.
        Defaults that do not pass validation are not written: they could not be used
        when the file is read.
        `appsettings_path` is left out: it is read only from the user settings file.

        Args:
            path: The file; it is replaced if it exists.
        """
        from flim.core.registry import tools as registry

        settings = self.settings
        for group in registry.by_category().values():
            for tool in group:
                if settings.tools.entry(tool) is not None:
                    continue
                config = tool.config_class()
                try:
                    tool.config_class.model_validate(config.model_dump(mode="json"))
                except ValidationError:
                    continue
                settings.tools.set(tool, config)
        data = settings.to_json()
        data.pop("appsettings_path", None)
        data["tools"] = dict(sorted(data["tools"].items()))
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)


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


def strict_choice(check: SettingsCheck, *, complete: bool = False) -> SettingsCheck:
    """Accept a checked settings file only if all its values can be used.

    Unknown keys are logged and not used, unless `complete`.

    Args:
        check: The result of `check_settings_file`.
        complete: Also refuse unknown keys and settings of tools that are not
            installed (flimbatch: the run must not depend on settings that are
            ignored or on which tools are installed).

    Returns:
        `check`.

    Raises:
        ValueError: If the file cannot be used or has invalid values, or with
            `complete` unknown keys or settings of tools that are not installed; the
            message lists them.
    """
    if check.error or check.invalid:
        raise ValueError(check.summary())
    if complete and (check.unknown or check.not_checked):
        raise ValueError(
            check.summary() + "\nOnly a settings file whose settings can all be used"
            " and checked is accepted."
        )
    if check.unknown:
        logging.warning(f"{check.path}: ignoring unknown keys {', '.join(check.unknown)}")
    return check


# decides which checked settings file to use: the check given, another file's
# check, or None for none
Choice = Callable[[SettingsCheck], Optional[SettingsCheck]]


def session_settings(
    settings_file: Optional[str] = None,
    command_line: Optional[dict] = None,
    *,
    user_file: Optional[UserSettingsFile] = None,
    base: Optional[AppSettings] = None,
    choose: Optional[Choice] = None,
    complete: bool = False,
    pick: Optional[Callable[[list[Path]], Optional[Path]]] = None,
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
        choose: Called if some settings of the app settings file cannot be used;
            returns the check whose sections to use, or None to use no file. Without
            it, such a file is refused (`strict_choice`).
        complete: Refuse an app settings file unless all its settings can be used
            and checked (see `strict_choice`); for flimbatch.
        pick: Called without `settings_file` if the app settings search path has
            files (`list_app_settings`); returns the file to use, or None for none.

    Returns:
        The settings manager. Its `source` is the path of the app settings file, or
        None.

    Raises:
        FileNotFoundError: If `settings_file` matches no file.
        ValueError: If `settings_file` is ambiguous, or without `choose` cannot be
            used or has invalid values, or if an environment variable or a
            command-line value is invalid.
    """
    manager = SettingsManager(base, user_file)
    search_path = app_settings_path(manager.settings.appsettings_path)
    if not settings_file and pick is not None:
        files = list_app_settings(search_path)
        settings_file = pick(files) if files else None
    if settings_file:
        check = check_settings_file(find_app_settings(settings_file, search_path))
        if choose and check.problems:
            chosen = choose(check)
        else:
            chosen = strict_choice(check, complete=complete)
        if chosen is not None:
            manager.apply(chosen)
    for changes, names, layer in (
        (environment_changes(), ENV_NAMES, "environment"),
        (command_line or {}, OPTION_NAMES, "command line"),
    ):
        if changes:
            manager.update(_completed(changes, manager.settings), keep=False)
            manager.origins.update(
                {key: f"{layer} ({names.get(key, key)})" for key in _sections(changes)}
            )
    return manager


# settings file in the start folder that the GUI read before 0.7.0 when started
# without -c (deprecated: an app settings file given with -s replaces it)
DEFAULTS_FILE = "defaults.json"


def start_folder_settings() -> tuple[Optional[Path], Optional[str]]:
    """Return `defaults.json` in the start folder, if there is one.

    The GUI started without `-s` uses this file as if it were given with `-s`.

    Returns:
        The file's path and the deprecation message to show; (None, None) if there
        is no such file.
    """
    path = Path(DEFAULTS_FILE).resolve()
    if not path.is_file():
        return None, None
    return path, (
        f"reading {DEFAULTS_FILE} from the start folder is deprecated: move {path} to"
        f" an app settings folder (e.g. {default_app_settings_dir()}), give it a name,"
        " and start with -s NAME"
    )
