"""Application settings: versioned, typed, and upgraded from older settings files.

A settings file stores ``schema_version``. Files of older versions are upgraded step by
step (``MIGRATIONS``: version n -> n+1) and then validated with :class:`AppSettings`;
settings are always saved in the newest version. Version 0 is the dict ``Config`` of
FLIMAnalyzer up to 0.5 (``{"root": {"import": ..., "plugins": ...}}``).

- :class:`ToolSettings`: the settings of each tool (its config, autosave and results
  folder), by tool name.
- :class:`AppSettings`: import, preprocessing, display, filters, the results folder and
  the tool settings.
"""

import copy
import json
import logging
import os
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

from flim.core.config import TaskConfig

SETTINGS_VERSION = 1


class _Settings(BaseModel):
    # keys of newer versions (or typos) are reported, not fatal: see load_settings
    model_config = ConfigDict(extra="allow")


class ParserSettings(_Settings):
    parser: str = Field(default="defaultparser", description="Filename parser class")
    patterns: list = []  # the regex parser's [{Use, Category, Regex}, ...]


class ImportSettings(_Settings):
    include_files: list[str] = []
    exclude_files: list[str] = []
    delimiter: str = "\t,"
    filename_parser: ParserSettings = Field(default_factory=ParserSettings)
    category_columns: list[str] = []
    fitting_columns: list[str] = []
    category_combinations: Optional[list] = None


class PreprocessSettings(_Settings):
    # new column -> [function name, [argument columns]]
    calculate: dict[str, list] = {}
    drop: list[str] = []  # column name parts to drop
    rename: dict[str, str] = {}  # column name part -> replacement


class FilterSettings(_Settings):
    use: bool = False
    show_dropped: bool = True
    range_filters: list[dict] = []  # flim.core.filter.RangeFilter parameters
    series_filters: list = []


class ToolEntry(_Settings):
    """A tool's settings: its config (JSON, with ``classname``), and where it saves."""

    config: Optional[dict] = None
    autosave: bool = False
    results_dir: Optional[str] = None
    legacy: Optional[dict] = None  # plugin parameters no config class was found for


class ToolSettings(BaseModel):
    """The settings of each tool, by tool name."""

    tools: dict[str, ToolEntry] = {}

    def entry(self, tool) -> Optional[ToolEntry]:
        """The tool's settings, also those saved under one of its former names."""
        for name in (tool.name, *getattr(tool, "former_names", ())):
            if name in self.tools:
                return self.tools[name]
        return None

    def config(self, tool) -> TaskConfig:
        """The tool's saved config; its defaults if none is saved or it is not valid."""
        entry = self.entry(tool)
        try:
            if entry is not None and entry.config is not None:
                return tool.config_class.model_validate(entry.config)
            if entry is not None and entry.legacy is not None:
                return tool.config_class.from_legacy_params(entry.legacy)
        except Exception as err:
            logging.warning(f"{tool.name}: settings not valid, using the defaults ({err})")
        return tool.config_class()

    def set(self, tool, config: TaskConfig, autosave=False, results_dir=None) -> None:
        self.tools[tool.name] = ToolEntry(
            config=config.model_dump(mode="json"),
            autosave=bool(autosave),
            results_dir=None if results_dir is None else str(results_dir),
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


class AppSettings(_Settings):
    schema_version: int = SETTINGS_VERSION
    working_dir: str = Field(
        default_factory=lambda: os.path.join(
            os.path.expanduser("~"), "FLIMAnalyzerResults"
        )
    )
    import_: ImportSettings = Field(default_factory=ImportSettings, alias="import")
    preprocess: PreprocessSettings = Field(default_factory=PreprocessSettings)
    display: list[dict] = []  # histogram ranges of the import dialog
    filters: FilterSettings = Field(default_factory=FilterSettings)
    tool_settings: ToolSettings = Field(default_factory=ToolSettings, alias="tools")

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @classmethod
    def default(cls) -> "AppSettings":
        """The defaults: those of the importer, preprocessor and filters."""
        from flim.core.importer import dataimporter
        from flim.core.preprocessor import defaultpreprocessor

        return cls(
            import_=dataimporter().settings(),
            preprocess=defaultpreprocessor().settings(),
            display=[
                {"name": name, "min": "auto", "max": "auto", "bins": 100}
                for name in ["trp t1", "trp t2", "trp tm"]
            ],
            filters=FilterSettings(
                range_filters=[f.get_params() for f in default_range_filters()]
            ),
        )

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)


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


def _v0_to_v1(data: dict, convert: bool = True) -> dict:
    """Version 0 (the dict ``Config``) to 1. ``convert``: also the plugin settings."""
    root = copy.deepcopy(data.get("root", data))
    settings = {"schema_version": 1}
    if "working_dir" in root:
        settings["working_dir"] = root.pop("working_dir")
    for key, (field, names) in _V0_SECTIONS.items():
        if isinstance(root.get(key), dict):
            settings[field] = _renamed(root.pop(key), names)
    parser = settings.get("import", {}).get("filename_parser")
    if isinstance(parser, dict):
        settings["import"]["filename_parser"] = _renamed(parser, _V0_PARSER)
    if "display" in root:
        settings["display"] = root.pop("display")
    plugins = root.pop("plugins", None)
    if convert and isinstance(plugins, dict):
        settings["tools"] = {"tools": _v0_tools(plugins)}
    for key in ("analysis", "workflow"):  # never used
        root.pop(key, None)
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
                logging.info(f"Settings of {name} kept as plugin parameters ({err})")
                entry["legacy"] = legacy
        entries[name] = entry
    return entries


# version n -> the settings of version n + 1
MIGRATIONS: dict[int, Callable[[dict], dict]] = {0: _v0_to_v1}


def version_of(data: dict) -> int:
    return int(data.get("schema_version", 0)) if isinstance(data, dict) else 0


def migrate(data: dict) -> dict:
    """``data`` of any version, upgraded to the current one."""
    version = version_of(data)
    if version > SETTINGS_VERSION:
        raise ValueError(
            f"Settings of version {version} are newer than this FLIMAnalyzer"
            f" (version {SETTINGS_VERSION}): update FLIMAnalyzer"
        )
    while version < SETTINGS_VERSION:
        data = MIGRATIONS[version](data)
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


def settings_from_data(data: dict) -> AppSettings:
    """Settings from loaded JSON of any version; unknown keys are logged."""
    settings = AppSettings.model_validate(migrate(data))
    unknown = _unknown_keys(settings)
    if unknown:
        logging.warning(f"Settings: ignoring unknown keys {', '.join(unknown)}")
    return settings


def load_settings(path) -> AppSettings:
    """Reads a settings file of any version."""
    with open(path) as f:
        return settings_from_data(json.load(f))


def save_settings(settings: AppSettings, path) -> None:
    """Writes settings in the current version."""
    with open(path, "w") as f:
        json.dump(settings.to_json(), f, indent=2, default=str)
