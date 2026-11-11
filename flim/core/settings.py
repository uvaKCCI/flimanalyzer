"""FLIMAnalyzer settings: versioned, typed, and upgraded from older settings files.

A settings file stores ``schema_version``. Files of older versions are upgraded step by
step (``MIGRATIONS``: version n -> n+1) and then validated with :class:`AppSettings`;
settings are always saved in the newest version. Version 0 is the dict ``Config`` of
FLIMAnalyzer up to 0.5 (``{"root": {"import": ..., "plugins": ...}}``); version 1 is
the format of 0.6; version 2 the format of 0.7.

A settings file has a section per settings area, and one per tool::

    {"schema_version": 2,
     "results_dir": null, "execution": {"executor": "local", ...},
     "prefect_server": true, "log": {...}, "cache": {...},
     "import": {...}, "filters": {...},
     "tools": {"Summarize": {"config": {...}, "autosave": {...}}, ...}}

A file may have only some of the sections (e.g. only one tool's, saved from its
dialog): loading it changes only those (:func:`update_settings`).

- :class:`ToolSettingsMap`: the settings of each tool (its config, autosave and results
  folder), by tool name.
- :class:`AppSettings`: the results folder, the executor, the Prefect server, the log and
  cache folders, import, filters and the tool settings (Import's renaming, dropping
  and calculating: the Rename Columns, Drop Columns and Calculate tools' settings).
"""

import copy
import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    model_serializer,
)

from flim.core.config import TaskConfig
from flim.core.saving import AutosaveConfig
from flim.core.execution import ExecutorSettings, LocalExecutorSettings

logger = logging.getLogger(__name__)

SETTINGS_VERSION = 2

# the folder FLIMAnalyzer was started from: the default results folder. Recorded at
# import, because file dialogs can change the current folder later.
START_DIR = Path.cwd()


class _Settings(BaseModel):
    # keys of newer versions (or typos) are logged, not fatal: see _validated
    model_config = ConfigDict(extra="allow")


class FilterSettings(_Settings):
    """The table windows' filter switches; the filters are the Filter tool's settings
    (version 2). `use` also decides whether `flimbatch` filters after Import."""

    use: bool = False
    show_dropped: bool = True


class ToolSettings(_Settings):
    """A tool's settings: its config (JSON, with ``classname``), whether, where and in
    which formats it saves its results (``autosave``), and the plugin parameters
    (``legacy``) that no config class was found for."""

    config: Optional[dict] = None
    autosave: AutosaveConfig = Field(default_factory=AutosaveConfig)
    legacy: Optional[dict] = None  # plugin parameters no config class was found for

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        # `legacy` is written only if set: it is used only for 0.5 settings of tools
        # of other packages
        data = handler(self)
        if data.get("legacy") is None:
            data.pop("legacy", None)
        return data


class ToolSettingsMap(RootModel[dict[str, ToolSettings]]):
    """The settings of each tool, by tool name."""

    root: dict[str, ToolSettings] = {}

    @property
    def entries(self) -> dict[str, ToolSettings]:
        """The tools' settings by tool name."""
        return self.root

    def entry(self, tool) -> Optional[ToolSettings]:
        """The tool's settings, also those saved under one of its former names."""
        for name in (tool.name, *getattr(tool, "former_names", ())):
            if name in self.entries:
                return self.entries[name]
        return None

    def config(self, tool) -> TaskConfig:
        """The tool's saved config; its defaults if none is saved or it is not valid
        (a warning is logged)."""
        entry = self.entry(tool)
        try:
            if entry is not None and entry.config is not None:
                return tool.config_class.model_validate(entry.config)
            if entry is not None and entry.legacy is not None:
                return tool.config_class.from_legacy_params(entry.legacy)
        except Exception as err:
            logger.warning(f"{tool.name}: settings not valid, using the defaults ({err})")
        return tool.config_class()

    def set(self, tool, config: TaskConfig, autosave: Optional[AutosaveConfig] = None) -> None:
        for name in getattr(tool, "former_names", ()):
            self.entries.pop(name, None)
        self.entries[tool.name] = tool_settings(config, autosave)


def tool_settings(config: TaskConfig, autosave: Optional[AutosaveConfig] = None) -> ToolSettings:
    """Return a tool's settings.

    Args:
        config: The tool's config.
        autosave: Whether, where and in which formats it saves its results; defaults
            to not saving.
    """
    return ToolSettings(
        config=config.model_dump(mode="json"), autosave=autosave or AutosaveConfig()
    )


def default_range_filters() -> list:
    """The range filters of new settings (flim.core.filter.RangeFilter)."""
    from flim.core.filter import RangeFilter

    return [
    RangeFilter("trp t1", 0, 2500),
    RangeFilter("trp t2", 0, 8000),
    RangeFilter("trp tm", 0, 4000, selected=False),
    RangeFilter("trp a1[%]", 0, 100),
    RangeFilter("trp a2[%]", 0, 100),
    RangeFilter("trp a1[%]/a2[%]", 0, 2),
    RangeFilter("trp E%1", 0, 100),
    RangeFilter("trp E%2", 0, 100),
    RangeFilter("trp E%3", 0, 100),
    RangeFilter("trp r1", 0, 15),
    RangeFilter("trp r2", 0, 3),
    RangeFilter("trp r3", 0, 3),
    RangeFilter("trp chi", 0, 4.7, selected=True),
    RangeFilter("trp photons", 0, 160),
    RangeFilter("NAD(P)H a1", 0, 1000),
    RangeFilter("NAD(P)H a1[%]", 0, 100),
    RangeFilter("NAD(P)H a2", 5, 300),
    RangeFilter("NAD(P)H a2[%]", 0, 100),
    RangeFilter("NAD(P)H t1", 10, 1000),
    RangeFilter("NAD(P)H t2", 2000, 7000),
    RangeFilter("NAD(P)H tm", 0, 2000),
    RangeFilter("NAD(P)H photons", 10, 2000),
    RangeFilter("NAD(P)H a2[%]", 0, 100),
    RangeFilter("NADPH %", 0, 99),
    RangeFilter("NADH %", 0, 100),
    RangeFilter("NADPH/NADH", 0, 3),
    RangeFilter("NAD(P)H chi", 0.7, 4.7, selected=True),
    RangeFilter("FAD t1", 10, 1500),
    RangeFilter("FAD t2", 1000, 6000),
    RangeFilter("FAD tm", 0, 2500),
    RangeFilter("FAD a1", 10, 500),
    RangeFilter("FAD a1[%]", 0, 100),
    RangeFilter("FAD a2", 10, 300),
    RangeFilter("FAD a2[%]", 0, 100),
    RangeFilter("FAD a1[%]/a2[%]", 0, 16),
    RangeFilter("FLIRR", 0, 2.4),
    RangeFilter("FAD chi", 0.7, 4.7, selected=True),
    RangeFilter("FAD photons", 10, 1000),
    RangeFilter("FAD photons/NAD(P)H photons", 0, 2),
    ]


class CacheSettings(_Settings):
    """Where closed items are kept, and the limits of that cache."""

    dir: Optional[Path] = Field(
        default=None,
        description="Cache folder. None defaults to FLIM_CACHE_DIR, else the platform's"
        " cache folder.",
    )
    max_size_mb: int = Field(default=2048, ge=0, description="Maximum cache size (MB).")
    max_age_days: int = Field(
        default=7, ge=0, description="Items older than this are removed (days)."
    )


class LogSettings(_Settings):
    """Where the log files are written, and how long the GUI keeps them."""

    dir: Optional[Path] = Field(
        default=None,
        title="Log folder",
        description="Log folder. None: the platform's log folder for the GUI, the"
        " output folder for flimbatch.",
    )
    max_age_days: int = Field(
        default=30,
        ge=1,
        description="The GUI removes its log files older than this at startup (days).",
    )


class AppSettings(_Settings):
    schema_version: int = SETTINGS_VERSION
    results_dir: Optional[Path] = Field(
        default=None,
        title="Results folder",
        description="Results folder. None defaults to the folder FLIMAnalyzer was"
        " started from.",
    )
    execution: ExecutorSettings = Field(
        default_factory=LocalExecutorSettings,
        title="Executor",
        description="Where and how the tasks of a run are executed.",
    )
    prefect_server: bool = Field(
        default=True,
        title="Prefect server",
        description="Use or start a local Prefect server for the runs.",
    )
    log: LogSettings = Field(
        default_factory=LogSettings,
        title="Log folder",
        description="Log folder and how long the GUI keeps its log files.",
    )
    cache: CacheSettings = Field(default_factory=CacheSettings)
    strict: Optional[bool] = Field(
        default=None,
        title="Workflows: missing columns",
        description="Workflows: columns not in the data are errors (True) or replaced by"
        " the closest match (False). A workflow's own setting takes precedence. None"
        " defaults to strict in flimbatch and to guessing, shown before the run, in the"
        " GUI.",
    )
    appsettings_path: list[Path] = Field(
        default=[],
        description="Folders searched for app settings files, in order. Empty defaults to"
        " the folder appsettings in the platform's settings folder.",
    )
    workflow_paths: list[Path] = Field(
        default=[],
        description="Folders searched for workflow files, in order. Empty defaults to"
        " the folder workflows in the platform's settings folder.",
    )
    default_app_settings: Optional[Path] = Field(
        default=None,
        title="Default app settings file",
        description="The app settings file preselected when the GUI starts without -s."
        " Read only from the user settings file.",
    )
    filters: FilterSettings = Field(default_factory=FilterSettings)
    tools: ToolSettingsMap = Field(default_factory=ToolSettingsMap)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @classmethod
    def default(cls) -> "AppSettings":
        """The default settings: the Filter tool's default range filters (those of
        the table windows up to 0.6); the other tools' defaults are their configs'."""
        from flim.configs import FilterConfig
        from flim.core.filtering import default_ranges

        settings = cls()
        settings.tools.entries["Filter"] = ToolSettings(
            config=FilterConfig(filters=default_ranges()).model_dump(mode="json")
        )
        return settings

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)

    def resolved_results_dir(self) -> Path:
        """The results folder: `results_dir` with `~` expanded, or the folder
        FLIMAnalyzer was started from if it is not set."""
        return self.results_dir.expanduser() if self.results_dir else START_DIR


# --- versions ---

# version 0 keys (the dict Config of 0.5) -> AppSettings fields
_V0_SECTIONS = {
    "import": (
        "import",
        {
            "include files": "include_files",
            "exclude files": "exclude_files",
            "delimiter": "delimiter",
            "fname parser": "filename_parser",
            "category cols": "category_columns",
            "fitting columns": "fitting_columns",
            "category combos": "category_combinations",
        },
    ),
    "preprocess": (
        "preprocess",
        {"calculate": "calculate", "drop": "drop", "rename": "rename"},
    ),
    "filters": (
        "filters",
        {
            "Use": "use",
            "show dropped": "show_dropped",
            "range filters": "range_filters",
            "series filters": "series_filters",
        },
    ),
}
_V0_PARSER = {"Class": "parser", "Patterns": "patterns"}
_V0_TOOL_KEYS = {"_config", "autosave", "working_dir"}


def _renamed(values: dict, names: dict) -> dict:
    """``values`` with the keys in ``names`` renamed; other keys kept."""
    return {names.get(k, k): v for k, v in values.items()}


def _v0_to_v1(data: dict, convert: bool = True, changes: Optional["Changes"] = None) -> dict:
    """Version 0 (the dict ``Config``) to 1. ``convert``: also the plugin settings.
    ``changes``: records the conversion."""
    changes = changes if changes is not None else Changes()
    changes.converted.append("FLIMAnalyzer 0.5 keys to the names of 0.6")
    root = copy.deepcopy(data.get("root", data))
    settings = {"schema_version": 1}
    if "working_dir" in root:
        settings["working_dir"] = root.pop("working_dir")
    for key, (section, names) in _V0_SECTIONS.items():
        if isinstance(root.get(key), dict):
            settings[section] = _renamed(root.pop(key), names)
    parser = settings.get("import", {}).get("filename_parser")
    if isinstance(parser, dict):
        settings["import"]["filename_parser"] = _renamed(parser, _V0_PARSER)
    if "display" in root:
        settings["display"] = root.pop("display")
    plugins = root.pop("plugins", None)
    if convert and isinstance(plugins, dict):
        settings["tools"] = _v0_tools(plugins)
        changes.converted.append("plugin parameters of 0.5 to tool settings")
    for key in ("analysis", "workflow"):  # never used
        if root.pop(key, None) is not None:
            changes.dropped.append(key)
    settings.update(root)  # unknown keys: reported when loaded
    return settings


def _v0_tools(plugins: dict) -> dict:
    """The plugin parameters of version 0 as tool settings."""
    from flim.configs import LEGACY_TOOL_CONFIGS
    from flim.core.registry import tools as registry

    entries = {}
    for name, params in plugins.items():
        if not isinstance(params, dict):
            continue
        entry = {
            "autosave": bool(params.get("autosave")),
            "results_dir": params.get("working_dir") or None,
        }
        if isinstance(params.get("_config"), dict):  # saved by 0.5 with the tools
            entry["config"] = params["_config"]
        else:
            tool = registry.get(name) if name in registry else None
            config_class = tool.config_class if tool else LEGACY_TOOL_CONFIGS.get(name)
            legacy = {k: v for k, v in params.items() if k not in _V0_TOOL_KEYS}
            try:
                if config_class is None:
                    raise KeyError(name)
                config = config_class.from_legacy_params(legacy)
                entry["config"] = config.model_dump(mode="json")
            except Exception as err:  # e.g. a plugin of another package
                logger.info(f"Settings of {name} kept as plugin parameters ({err})")
                entry["legacy"] = legacy
        entries[name] = entry
    return entries


def _renamed_key(values: dict, old: str, new: str) -> bool:
    if isinstance(values, dict) and old in values:
        values[new] = values.pop(old)
        return True
    return False


def _v1_calculations(calculate: dict) -> list:
    """0.6's `{column: [function, [argument columns]]}` as Calculate's calculations:
    in the order Import makes the default ones, then the others in file order."""
    from flim.core.preprocessor import DEFAULT_CALCULATIONS

    order = {name: i for i, (name, _, _) in enumerate(DEFAULT_CALCULATIONS)}
    names = sorted(calculate, key=lambda n: order.get(n, len(order)))
    calculations = []
    for name in names:
        entry = calculate[name]
        function, args = (list(entry) + [None, []])[:2]
        calculations.append(
            {"kind": "function", "name": name, "function": function, "args": args}
        )
    return calculations


def _v1_import(data: dict, changes: "Changes") -> None:
    """0.6's `import` section (delimiter, filename parser and patterns, files left
    out, column combinations) is dropped: what a run does with the files is a
    workflow file's (e.g. the built-in `Import: FOV, Treatment, Cell`)."""
    section = data.pop("import", None)
    if not isinstance(section, dict):
        return
    parser = (section.get("filename_parser") or {}).get("parser", "defaultparser")
    changes.dropped.append(
        f"import (filename parser {parser}): use a workflow file, e.g. one of the"
        " built-in Import files"
    )


def _v1_filters(data: dict, changes: "Changes") -> None:
    """0.6's windows' range filters become the Filter tool's filters (`enabled` =
    `selected`); the Filter tool's own 0.6 filters are added switched off."""
    from flim.configs.data import _filters_of_v1, range_of_legacy

    filters = data.get("filters")
    tools = data.setdefault("tools", {})
    if not isinstance(filters, dict) or not isinstance(tools, dict):
        return
    nodes = []
    if "range_filters" in filters:
        for spec in filters.pop("range_filters") or []:
            low = spec.get("rangelow")
            allowed = spec.get("allowedmin")
            if low is not None and allowed is not None and low < allowed:
                spec = {**spec, "rangelow": allowed}  # as 0.6 clipped it
            nodes.append(
                {
                    "kind": "range",
                    "column": spec.get("name", ""),
                    "enabled": bool(spec.get("selected", True)),
                    **range_of_legacy(spec),
                }
            )
        changes.converted.append("filters.range_filters to the Filter tool's filters")
    if filters.pop("series_filters", None):
        changes.dropped.append("filters.series_filters (never used)")
    entry = tools.get("Filter")
    config = entry.get("config") if isinstance(entry, dict) else None
    own = []
    if isinstance(config, dict) and ("range_filters" in config or "category_filters" in config):
        own = _filters_of_v1(config, enabled=False)
        for key in ("range_filters", "category_filters"):
            config.pop(key, None)
        if own:
            changes.converted.append(
                f"the Filter tool's own {len(own)} filter(s): added switched off"
            )
    if nodes or own:
        entry = tools.setdefault("Filter", {})
        config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
        config["filters"] = nodes + own + list(config.get("filters") or [])
        entry["config"] = config


def _v1_to_v2(data: dict, changes: Optional["Changes"] = None) -> dict:
    """Upgrade version 1 (0.6) to 2 (0.7).

    `working_dir` becomes `results_dir`, and `display` (histogram ranges no longer
    used) is dropped. In the tool sections, `autosave` (whether) and `results_dir`
    (where) become the section `autosave` (`enabled`, `results_dir`; no formats: the
    defaults, as in 0.6), and the `rescale` field of the autoencoder training config,
    also inside the autoencoder workflows' `training` config, becomes
    `rescale_output`.

    Args:
        data: Settings of version 1.
        changes: Records the renamed and dropped keys.

    Returns:
        A new dict with the settings of version 2.
    """
    changes = changes if changes is not None else Changes()
    data = copy.deepcopy(data)
    if _renamed_key(data, "working_dir", "results_dir"):
        changes.converted.append("working_dir to results_dir")
    if data.pop("display", None) is not None:
        changes.dropped.append("display (histogram ranges)")
    # Import's rename and drop: the Rename Columns and Drop Columns tools' settings
    preprocess = data.get("preprocess")
    if isinstance(preprocess, dict) and isinstance(data.setdefault("tools", {}), dict):
        if "rename" in preprocess:
            rename = preprocess.pop("rename") or {}
            data["tools"].setdefault("Rename Columns", {})["config"] = {
                "replacements": [{"part": p, "new": n} for p, n in rename.items()]
            }
            changes.converted.append("preprocess.rename to the Rename Columns tool")
        if "drop" in preprocess:
            drop = preprocess.pop("drop") or []
            data["tools"].setdefault("Drop Columns", {})["config"] = {
                "drop": [{"text": t, "match": "contains"} for t in drop]
            }
            changes.converted.append("preprocess.drop to the Drop Columns tool")
        if "calculate" in preprocess:
            data["tools"].setdefault("Calculate", {})["config"] = {
                "calculations": _v1_calculations(preprocess.pop("calculate") or {})
            }
            changes.converted.append("preprocess.calculate to the Calculate tool")
        if not preprocess:
            data.pop("preprocess")
    _v1_filters(data, changes)
    _v1_import(data, changes)
    moved = 0
    for name, entry in (data.get("tools") or {}).items():
        if isinstance(entry, dict) and not isinstance(entry.get("autosave"), dict):
            if "autosave" in entry or "results_dir" in entry:
                entry["autosave"] = {
                    "enabled": bool(entry.pop("autosave", False)),
                    "results_dir": entry.pop("results_dir", None),
                }
                moved += 1
        config = (entry or {}).get("config") if isinstance(entry, dict) else None
        if not isinstance(config, dict):
            continue
        if _renamed_key(config, "rescale", "rescale_output"):
            changes.converted.append(f"tools.{name}.config.rescale to rescale_output")
        if _renamed_key(config.get("training"), "rescale", "rescale_output"):
            changes.converted.append(
                f"tools.{name}.config.training.rescale to rescale_output"
            )
    if moved:
        changes.converted.append(
            f"autosave and results_dir of {moved} tools to their autosave section"
        )
    return data


# version n -> the settings of version n + 1
MIGRATIONS: dict[int, Callable[[dict], dict]] = {0: _v0_to_v1, 1: _v1_to_v2}


def version_of(data: dict) -> int:
    return int(data.get("schema_version", 0)) if isinstance(data, dict) else 0


@dataclass
class Changes:
    """The keys a migration converted (renamed or restructured) and dropped."""

    converted: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def migrate(data: dict, changes: Optional[Changes] = None) -> dict:
    """``data`` of any version, upgraded to the current one. Raises ValueError if
    ``data`` is of a newer version than SETTINGS_VERSION. ``changes``: records the
    converted and dropped keys."""
    version = version_of(data)
    if version > SETTINGS_VERSION:
        raise ValueError(
            f"Settings of version {version} are newer than this FLIMAnalyzer"
            f" (version {SETTINGS_VERSION}): update FLIMAnalyzer"
        )
    while version < SETTINGS_VERSION:
        data = MIGRATIONS[version](data, changes=changes)
        version += 1
        data["schema_version"] = version
    return data


def _unknown_keys(model: BaseModel, path: str = "") -> list[str]:
    keys = [f"{path}{k}" for k in (model.model_extra or {})]
    for name in type(model).model_fields:
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            keys += _unknown_keys(value, f"{path}{name}.")
    return keys


def _validated(data: dict) -> AppSettings:
    settings = AppSettings.model_validate(data)
    unknown = _unknown_keys(settings)
    if unknown:
        logger.warning(f"Settings: ignoring unknown keys {', '.join(unknown)}")
    return settings


def settings_from_data(data: dict) -> AppSettings:
    """Settings from loaded JSON of any version; unknown keys are logged."""
    return _validated(migrate(data))


def merge_sections(base: dict, changes: dict) -> dict:
    """A copy of ``base`` (sections in the current version) with the sections of
    ``changes`` (any version): each replaces the section in ``base``; tools each tool's
    section, which also removes that tool's sections under its former names."""
    merged = copy.deepcopy(base)
    for key, value in migrate(changes).items():
        if key == "tools" and isinstance(value, dict):
            tools = merged.setdefault("tools", {})
            for name in value:
                tool = _registered(name)
                for former in getattr(tool, "former_names", ()):
                    tools.pop(former, None)
            tools.update(value)
        elif key != "schema_version":
            merged[key] = value
    return merged


def update_settings(settings: AppSettings, data: dict) -> AppSettings:
    """``settings`` with the sections in ``data`` (JSON of any version): each section
    replaces the one in ``settings``; tools each tool's section. Unknown keys are
    logged; invalid values raise pydantic.ValidationError."""
    merged = merge_sections(settings.to_json(), data)
    merged["schema_version"] = SETTINGS_VERSION
    return _validated(merged)


def _registered(name):
    from flim.core.registry import tools

    return tools.get(name) if name in tools else None


def load_settings(path, settings: Optional[AppSettings] = None) -> AppSettings:
    """Reads a settings file of any version. Sections the file does not have are
    those of ``settings`` (default: the defaults). Raises ValueError if the file does
    not hold a JSON object, and the errors of reading and validating it."""
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a settings file")
    return update_settings(settings or AppSettings.default(), data)


# --- checking a settings file before it is used ---


@dataclass
class SettingsCheck:
    """The result of checking a settings file: what its migration converted and
    dropped, which keys cannot be used, and the sections that can.

    Attributes:
        path: The settings file.
        version: The file's schema version; None if the file cannot be read.
        error: Why the file cannot be used at all (not readable, not JSON, not a
            settings file, or of a newer version); None if it can be used.
        converted: Keys the migration renamed or restructured.
        dropped: Keys the migration removed on purpose (no longer used).
        unknown: Keys the current version does not have.
        invalid: Invalid values, as `key: reason`; the section (or the tool's
            settings) holding one is not used.
        not_checked: Tools whose settings cannot be checked because the tool is not
            installed; their settings are kept.
        sections: The sections that can be used, in the current version, without
            the unknown keys and the sections with invalid values.
    """

    path: Path
    version: Optional[int] = None
    error: Optional[str] = None
    converted: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    not_checked: list[str] = field(default_factory=list)
    sections: dict = field(default_factory=dict)

    @property
    def problems(self) -> bool:
        """Whether some of the file's settings cannot be used."""
        return bool(self.error or self.unknown or self.invalid)

    def tool_problems(self, tool) -> bool:
        """Whether some of the settings of `tool` (also under a former name) cannot
        be used, or the file cannot be used at all."""
        if self.error:
            return True
        names = (tool.name, *getattr(tool, "former_names", ()))
        prefixes = tuple(f"tools.{name}" for name in names)
        return any(key.startswith(prefixes) for key in self.unknown + self.invalid)

    def summary(self, limit: Optional[int] = None) -> str:
        """Return the result as text, one heading per kind of finding.

        Args:
            limit: The number of items listed per heading; None lists all.
        """
        if self.error:
            return f"{self.path} cannot be used: {self.error}"
        lines = [f"{self.path}: schema version {self.version}"]
        for heading, items in (
            ("Settings that cannot be used (unknown)", self.unknown),
            ("Settings that cannot be used (invalid values)", self.invalid),
            ("Converted to the current version", self.converted),
            ("Removed by the conversion (no longer used)", self.dropped),
            ("Not checked (tool not installed)", self.not_checked),
        ):
            if not items:
                continue
            lines.append(f"{heading}:")
            shown = items if limit is None else items[:limit]
            lines += [f"  {item}" for item in shown]
            if len(items) > len(shown):
                lines.append(f"  and {len(items) - len(shown)} more")
        return "\n".join(lines)


def _extra_keys(model: BaseModel, path: str = "") -> list[str]:
    """Return the keys a model kept as extra, with their paths in the file."""
    keys = [f"{path}{k}" for k in (model.model_extra or {})]
    for name, info in type(model).model_fields.items():
        value = getattr(model, name)
        if isinstance(value, BaseModel) and not isinstance(value, RootModel):
            keys += _extra_keys(value, f"{path}{info.alias or name}.")
    return keys


def _drop_extra_keys(model: BaseModel, data: dict) -> None:
    """Remove the keys a model kept as extra from its JSON `data`, in place."""
    for key in model.model_extra or {}:
        data.pop(key, None)
    for name, info in type(model).model_fields.items():
        value, key = getattr(model, name), info.alias or name
        if isinstance(value, BaseModel) and isinstance(data.get(key), dict):
            _drop_extra_keys(value, data[key])


def _remove_invalid(data: dict, invalid: list[str]) -> AppSettings:
    """Validate `data`, removing each section (or tool's settings) with an invalid
    value until the rest is valid.

    Args:
        data: Sections in the current version; changed in place.
        invalid: Receives the invalid values, as `key: reason`.

    Returns:
        The validated settings of the remaining sections.
    """
    while True:
        try:
            return AppSettings.model_validate({**data, "schema_version": SETTINGS_VERSION})
        except ValidationError as err:
            for error in err.errors():
                loc = error["loc"]
                invalid.append(f"{'.'.join(str(p) for p in loc)}: {error['msg']}")
                if loc[0] == "tools" and len(loc) > 1 and isinstance(data.get("tools"), dict):
                    data["tools"].pop(loc[1], None)
                else:
                    data.pop(loc[0], None)


def check_settings_file(path: str | os.PathLike) -> SettingsCheck:
    """Check a settings file of any version before it is used; the file is only read.

    The file is migrated to the current version and validated. Each tool's settings
    are validated with the tool's config class if the tool is installed.

    Args:
        path: The settings file.

    Returns:
        The result; `sections` holds what can be used.
    """
    path = Path(path)
    check = SettingsCheck(path)
    changes = Changes()
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "classname" in data:
            raise ValueError("not a settings file")
        check.version = version_of(data)
        data = migrate(data, changes)
    except (OSError, ValueError) as err:  # incl. json.JSONDecodeError
        check.error = str(err)
        return check
    check.converted, check.dropped = changes.converted, changes.dropped
    data.pop("schema_version", None)
    if "tools" in data and not isinstance(data["tools"], dict):
        check.invalid.append("tools: not a mapping of tool names to settings")
        data.pop("tools")
    settings = _remove_invalid(data, check.invalid)
    for name, entry in settings.tools.entries.items():
        tool = _registered(name)
        if tool is None:
            check.not_checked.append(f"tools.{name}")
            continue
        try:
            if entry.config is not None:
                tool.config_class.model_validate(entry.config)
            elif entry.legacy is not None:
                tool.config_class.from_legacy_params(entry.legacy)
        except Exception as err:
            reason = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
            ) if isinstance(err, ValidationError) else str(err)
            check.invalid.append(f"tools.{name}.config: {reason}")
            data["tools"].pop(name, None)
    settings = _remove_invalid(data, check.invalid)
    check.unknown = _extra_keys(settings) + [
        key
        for name, entry in settings.tools.entries.items()
        for key in _extra_keys(entry, f"tools.{name}.")
    ]
    known = settings.to_json()
    _drop_extra_keys(settings, known)
    for name, entry in settings.tools.entries.items():
        _drop_extra_keys(entry, known["tools"][name])
    check.sections = {key: known[key] for key in data if key in known}
    return check


def save_sections(sections: dict, path: str | os.PathLike) -> None:
    """Write settings sections, in the current version, to a file.

    Args:
        sections: Sections in the current version, e.g. `SettingsCheck.sections`.
        path: The file; it is replaced if it exists.
    """
    with open(path, "w") as f:
        json.dump({"schema_version": SETTINGS_VERSION, **sections}, f, indent=2, default=str)


def save_settings(settings: AppSettings, path) -> None:
    """Writes settings in the current version."""
    with open(path, "w") as f:
        json.dump(settings.to_json(), f, indent=2, default=str)


# --- the settings of one tool (in a FLIMAnalyzer settings file, or alone) ---


def read_tool_settings(path, tool) -> Optional[ToolSettings]:
    """The tool's section of a settings file (also of an older version, or under one
    of its former names); a file with only a config (with ``classname``) is the
    config. None if the file has no settings of the tool. Raises ValueError if the
    file does not hold a JSON object."""
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a settings file")
    if "classname" in data:  # a config alone
        return ToolSettings(config=data)
    tools = migrate(data).get("tools")
    if not isinstance(tools, dict):
        return None
    return ToolSettingsMap.model_validate(tools).entry(tool)


def write_tool_settings(path, tool, entry: ToolSettings) -> None:
    """Puts the tool's section into a settings file: the other sections of an
    existing file are kept (the file is saved in the current version). Raises
    ValueError if an existing file is not a settings file (or holds a config alone)."""
    data = {"schema_version": SETTINGS_VERSION}
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
        if not isinstance(existing, dict) or "classname" in existing:
            raise ValueError(f"{path} is not a settings file")
        data = migrate(existing)
    tools = data.setdefault("tools", {})
    for name in getattr(tool, "former_names", ()):
        tools.pop(name, None)
    tools[tool.name] = entry.model_dump(mode="json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
