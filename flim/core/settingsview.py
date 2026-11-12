"""The app settings of a session as rows for the Settings viewer."""

import logging
from dataclasses import dataclass
from typing import Optional

from flim.core.settings import START_DIR, AppSettings
from flim.core.settingsmgr import ENV_NAMES, OPTION_NAMES, SettingsManager

# the app settings the viewer shows, in this order (the cache settings are not shown)
VIEWED = ("results_dir", "execution", "prefect_server", "log", "strict")


@dataclass
class SettingRow:
    """One app setting as the viewer shows it.

    Attributes:
        name: The field name in `AppSettings`.
        title: The field's title.
        description: The field's description.
        value: The value as text.
        origin: The layer that set the value, e.g. `command line (-o)`.
        change: The command-line option and environment variable that set it.
    """

    name: str
    title: str
    description: str
    value: str
    origin: str
    change: str


def _executor(settings: AppSettings) -> str:
    """Return the execution settings as text, e.g. `local, workers: automatic`."""
    execution = settings.execution.model_dump(mode="json")
    parts = [execution.pop("executor")]
    workers = execution.pop("workers", None)
    if "workers" in type(settings.execution).model_fields:
        parts.append(f"{workers} workers" if workers else "workers: automatic")
    for key, value in execution.items():
        if key == "kwargs":
            parts += [f"{k}={v}" for k, v in value.items()]
        else:
            parts.append(f"{key}: {value}")
    return ", ".join(parts)


def _prefect_profile() -> Optional[str]:
    """Return the name of the active Prefect profile, or None if it is not known."""
    try:
        from prefect.context import get_settings_context

        return get_settings_context().profile.name
    except Exception:
        return None


def _value(name: str, settings: AppSettings) -> str:
    """Return the value of the app setting `name` as the viewer shows it."""
    value = getattr(settings, name)
    if name == "results_dir":
        return str(value) if value else f"start folder ({START_DIR})"
    if name == "execution":
        return _executor(settings)
    if name == "prefect_server":
        if not value:
            return "no: a temporary server for each run"
        profile = _prefect_profile()
        return f"yes (Prefect profile: {profile})" if profile else "yes"
    if name == "log":
        from flim.core.logs import default_log_dir

        folder = str(value.dir) if value.dir else f"default ({default_log_dir()})"
        return f"{folder}; logs kept {value.max_age_days} days"
    if name == "strict":
        if value is None:
            return "default: the closest match, shown before the run"
        return "errors" if value else "the closest match"
    return str(value)


def _change(name: str) -> str:
    """Return the command-line option and environment variable of a setting."""
    env = ENV_NAMES[name]
    if name == "execution":
        env = f"{env}__*"  # FLIM_EXECUTION__EXECUTOR, ...; or FLIM_EXECUTION as JSON
    return f"{OPTION_NAMES[name]}, {env}"


def overview(manager: SettingsManager) -> list[SettingRow]:
    """Return the app settings of a session as rows for the Settings viewer.

    Args:
        manager: The settings manager of the session.

    Returns:
        One row per setting in `VIEWED`, with its value, the layer that set it, and
        the command-line option and environment variable that set it.
    """
    settings = manager.settings
    fields = AppSettings.model_fields
    return [
        SettingRow(
            name=name,
            title=fields[name].title or name,
            description=fields[name].description or "",
            value=_value(name, settings),
            origin=manager.origins.get(name, "built-in default"),
            change=_change(name),
        )
        for name in VIEWED
    ]


def log_files() -> list[str]:
    """Return the files the log is written to in this process."""
    return [
        handler.baseFilename
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.FileHandler)
    ]
