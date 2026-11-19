"""FLIMAnalyzer settings: versioned, typed, and upgraded from older settings files.

A settings file stores `schema_version`. Files of older versions are upgraded step by
step (`MIGRATIONS`: version n -> n+1) and then validated with `AppSettings`;
settings are always saved in the newest version. Version 0 is the dict `Config` of
FLIMAnalyzer up to 0.5 (`{"root": {"import": ..., "plugins": ...}}`); version 1 is
the format of 0.6; version 2 the format of 0.7.

A settings file has a section per settings area, and one per tool::

    {"schema_version": 2,
     "results_dir": null, "execution": {"executor": "local", ...},
     "prefect_server": true, "server_timeout": 60, "log": {...},
     "presets": {...}, "favorites": [...], "filters": {...},
     "tools": {"Summarize": {"config": {...}, "output": {"save": true,
                             "results_dir": null, "formats": [...]}}, ...}}

A file may have only some of the sections: loading it changes only those
(`update_settings`). A tool file, which a tool dialog's `Save Settings...` writes,
holds one tool's settings without the folder: `{"schema_version": 2, "tool":
"Summarize", "config": {...}, "output": {"save": true, "formats": [...]}}`, the shape
of a workflow step; it is read as a settings file with that one tool's section.

- `ToolSettingsMap`: the settings of each tool (its config, and its `output`: whether
  it saves its results, the folder and the formats), by tool name.
- `AppSettings`: the results folder, the executor, the Prefect server and its
  timeout, the log, the GUI's settings (presets, favorites, window limits, search
  paths), the table windows' filter switches and the tool settings. The `import`
  section of 0.6 is dropped when a file is upgraded (`_v1_import`); the GUI offers
  to save it as a workflow file.
"""

import copy
import json
import logging
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializerFunctionWrapHandler,
    ValidationError,
    model_serializer,
    model_validator,
)

from flim import __version__
from flim.core.config import Processing, TaskConfig
from flim.core.paths import CharReplacements, without_unset_replacements
from flim.core.saving import AutosaveConfig, Formats
from flim.core.execution import ExecutorSettings, LocalExecutorSettings

if TYPE_CHECKING:
    from flim.core.filter import RangeFilter
    from flim.core.tool import Tool

logger = logging.getLogger(__name__)

SETTINGS_VERSION = 2
# settings read only from the user settings file (they belong to one user on one
# computer); in an app settings file they are reported as not used
USER_FILE_ONLY = ("appsettings_path", "workflow_paths", "default_app_settings", "last_run_url")

# the folder FLIMAnalyzer was started from: the default results folder. Recorded at
# import, because file dialogs can change the current folder later.
START_DIR = Path.cwd()


class _Settings(BaseModel):
    """The base of the settings models: unknown keys are kept, not refused."""

    # keys of newer versions (or typos) are logged, not fatal: see _validated
    model_config = ConfigDict(extra="allow")


class FilterSwitch(_Settings):
    """The switch of a group of filters of the table windows.

    Attributes:
        enabled: Whether the filters of the group are used.
    """

    enabled: bool = False


class FilterSettings(_Settings):
    """The table windows' filter switches; the filters are the Filter tool's settings.

    A `use` of earlier settings of this version (the switch of all filters) sets
    both switches.

    Attributes:
        features: `Filter Features`: whether new table windows use the range
            filters.
        categories: `Filter Categories`: whether new table windows use the category
            values hidden through a column header.
        show_dropped: Whether the table windows show the rows the filters dropped.
    """

    features: FilterSwitch = Field(default_factory=FilterSwitch)
    categories: FilterSwitch = Field(default_factory=FilterSwitch)
    show_dropped: bool = True

    @model_validator(mode="before")
    @classmethod
    def _from_use(cls, values: Any) -> Any:
        """Read `use`, the switch of all filters, as both switches."""
        if isinstance(values, dict) and "use" in values:
            values = dict(values)
            use = values.pop("use")  # validated as the switches
            for name in ("features", "categories"):
                values.setdefault(name, {"enabled": use})
        return values


class ToolOutput(_Settings):
    """A tool's `output` section: whether, where and in which formats it saves.

    The names of a workflow step's `output` (`save`, `formats`); the folder is a
    setting of this computer, so steps and tool files have none.

    Attributes:
        save: Whether a run of the tool saves its results.
        results_dir: The folder (GUI); None for the app's results folder.
        formats: The formats, per kind of output; a kind not listed is saved in its
            default format.
        char_replacements: The text replaced in the names of the files and folders
            the results are saved in, added to the defaults; None for the defaults.
    """

    save: bool = False
    results_dir: Optional[Path] = None
    formats: Formats = []
    char_replacements: Optional[CharReplacements] = None

    # no return annotation: with one, pydantic's serialization JSON schema of the
    # section would lose its fields (as for flim.core.config.BaseConfig)
    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler):
        """Serialize the section, leaving out `char_replacements` if it is not set."""
        return without_unset_replacements(handler(self))


class ToolSettings(_Settings):
    """A tool's settings: its config, its `output` and `processing` sections and
    legacy parameters.

    Attributes:
        config: The tool's config as JSON, with `classname`; None if none is saved.
        output: Whether, where and in which formats the tool saves its results.
        processing: How a run treats input that doesn't match the settings
            (`flim.core.config.Processing`); written only if set.
        legacy: The plugin parameters of a FLIMAnalyzer 0.5 settings file that no
            config class was found for; None otherwise. It is written only if set.
    """

    config: Optional[dict] = None
    output: ToolOutput = Field(default_factory=ToolOutput)
    processing: Processing = Field(default_factory=Processing)
    legacy: Optional[dict] = None  # plugin parameters no config class was found for

    @model_validator(mode="before")
    @classmethod
    def _strict(cls, data: Any) -> Any:
        """Move a workflow config's `strict` (FLIMAnalyzer 0.6) to `processing.strict`.

        `None` (automatic) is dropped: strict is the default. A `processing.strict`
        that is set takes precedence.
        """
        config = data.get("config") if isinstance(data, dict) else None
        if isinstance(config, dict) and "strict" in config:
            data = dict(data)
            config = dict(config)
            value = config.pop("strict")
            data["config"] = config
            processing = dict(data.get("processing") or {})
            if isinstance(value, bool) and processing.get("strict") is None:
                processing["strict"] = value
            if processing:
                data["processing"] = processing
        return data

    @model_validator(mode="before")
    @classmethod
    def _output(cls, data: Any) -> Any:
        """Accept the `autosave` section of earlier 0.7 development builds."""
        if isinstance(data, dict) and isinstance(data.get("autosave"), dict):
            data = dict(data)
            autosave = data.pop("autosave")
            output = {"save": autosave.get("enabled", False)}
            output.update({k: autosave[k] for k in ("results_dir", "formats") if k in autosave})
            data.setdefault("output", output)
        return data

    @property
    def autosave(self) -> AutosaveConfig:
        """Whether, where and in which formats the tool saves, as a run takes it."""
        output = self.output
        return AutosaveConfig(
            enabled=output.save,
            results_dir=output.results_dir,
            formats=output.formats,
            char_replacements=output.char_replacements,
        )

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Serialize the settings, leaving out `legacy` and `processing` if not set."""
        # `legacy` is written only if set: it is used only for 0.5 settings of tools
        # of other packages
        data = handler(self)
        if data.get("legacy") is None:
            data.pop("legacy", None)
        if self.processing.is_empty():
            data.pop("processing", None)
        elif isinstance(data.get("processing"), dict):  # only the fields set
            data["processing"] = {
                k: v for k, v in data["processing"].items() if v not in (None, {})
            }
        return data


class ToolSettingsMap(RootModel[dict[str, ToolSettings]]):
    """The settings of each tool, by tool name."""

    root: dict[str, ToolSettings] = {}

    @property
    def entries(self) -> dict[str, ToolSettings]:
        """The tools' settings by tool name."""
        return self.root

    def entry(self, tool: "type[Tool]") -> Optional[ToolSettings]:
        """Return the tool's settings, also those saved under one of its former names.

        Settings under a former name are deprecated (`warn_former_name`); writing
        the tool's settings saves them under its name.

        Args:
            tool: The tool class; its `name` is looked up first, then its
                `former_names` in order.

        Returns:
            The settings, or None if none are saved for the tool.
        """
        for name in (tool.name, *getattr(tool, "former_names", ())):
            if name in self.entries:
                if name != tool.name:
                    from flim.core.registry import warn_former_name

                    warn_former_name(tool, name)
                return self.entries[name]
        return None

    def config(self, tool: "type[Tool]") -> TaskConfig:
        """Return the tool's saved config.

        A saved config is validated with the tool's config class; legacy plugin
        parameters are converted with its `from_legacy_params`.

        Args:
            tool: The tool class.

        Returns:
            The saved config; the tool's default config if none is saved, or if the
            saved one is not valid (a warning is logged).
        """
        entry = self.entry(tool)
        try:
            if entry is not None and entry.config is not None:
                return tool.config_class.model_validate(entry.config)
            if entry is not None and entry.legacy is not None:
                return tool.config_class.from_legacy_params(entry.legacy)
        except Exception as err:
            logger.warning(f"{tool.name}: settings not valid, using the defaults ({err})")
        return tool.config_class()

    def set(
        self,
        tool: "type[Tool]",
        config: TaskConfig,
        autosave: Optional[AutosaveConfig] = None,
    ) -> None:
        """Save the tool's settings under its name, removing those under former names.

        Args:
            tool: The tool class.
            config: The tool's config.
            autosave: Whether, where and in which formats the tool saves its results;
                None for not saving. Defaults to None.
        """
        for name in getattr(tool, "former_names", ()):
            self.entries.pop(name, None)
        self.entries[tool.name] = tool_settings(config, autosave)


def tool_settings(
    config: TaskConfig,
    autosave: Optional[AutosaveConfig] = None,
    processing: Optional[Processing] = None,
) -> ToolSettings:
    """Return a tool's settings.

    Args:
        config: The tool's config.
        autosave: Whether, where and in which formats it saves its results; None for
            not saving. Defaults to None.
        processing: How a run treats input that doesn't match the config; None: not
            set. Defaults to None.

    Returns:
        The settings, with the config as JSON.
    """
    autosave = autosave or AutosaveConfig()
    return ToolSettings(
        config=config.model_dump(mode="json"),
        output=ToolOutput(
            save=autosave.enabled,
            results_dir=autosave.results_dir,
            formats=autosave.formats,
            char_replacements=autosave.char_replacements,
        ),
        processing=processing or Processing(),
    )


def default_range_filters() -> list["RangeFilter"]:
    """Return the default range filters of new settings."""
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
    """The app settings: folders, execution, log, filters and tool settings.

    Each field's `title` and `description` describe the setting; keys the model
    does not have are kept as extra and logged when a file is loaded.
    """

    schema_version: int = SETTINGS_VERSION
    description: Optional[str] = Field(
        default=None,
        title="Description",
        description="What the settings file is for, for example a course or an"
        " experiment; shown when the GUI asks which app settings file to start with.",
    )
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
    server_timeout: float = Field(
        default=60.0,
        gt=0,
        title="Server timeout",
        description="Seconds to wait for Prefect server responses (and Dask cluster"
        " responses, if used). Below 60, a local Prefect server"
        " that is started may not be ready in time.",
    )
    log: LogSettings = Field(
        default_factory=LogSettings,
        title="Log folder",
        description="Log folder and how long the GUI keeps its log files.",
    )
    appsettings_path: list[Path] = Field(
        default=[],
        description="Folders searched for app settings files, in order. Empty defaults to"
        " the folder appsettings in the platform's settings folder.",
    )
    max_windows: dict[str, int] = Field(
        default={"table": 10, "plot": 10, "image": 4},
        title="Most windows of a run",
        description="Per kind of result (table, plot, image), the most windows a GUI"
        " run opens; a run that would open more is refused. A kind not listed: no"
        " limit.",
    )
    presets: dict[str, list[dict]] = Field(
        default={},
        title="Presets",
        description="Named sets of a tool's settings, by tool name: each a `name` and"
        " the `settings` it sets, a part of the tool's config. Saved in a tool's dialog"
        " (Save as Preset...) and offered by its Load Preset... button.",
    )
    favorites: list[str] = Field(
        default=[],
        title="Favorites",
        description="Names of the tools and workflows the main window shows, in order,"
        " after the File group. Empty shows all tools. Set with File > Favorites....",
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
    last_run_url: Optional[str] = Field(
        default=None,
        title="Last run",
        description="The Prefect page of the last run the GUI started, also of a run"
        " that failed or was cancelled; opened by Monitor > Last Run. Read only from"
        " the user settings file.",
    )
    filters: FilterSettings = Field(default_factory=FilterSettings)
    tools: ToolSettingsMap = Field(default_factory=ToolSettingsMap)

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @classmethod
    def default(cls) -> "AppSettings":
        """Return the default settings.

        The Filter tool's settings hold the default feature filters (the range
        filters of the table windows of FLIMAnalyzer 0.6); the other tools have no
        saved settings, so their configs' defaults apply.
        """
        from flim.configs import FilterConfig
        from flim.core.filtering import default_ranges

        settings = cls()
        config = FilterConfig(features={"filters": default_ranges()})
        settings.tools.entries["Filter"] = ToolSettings(config=config.model_dump(mode="json"))
        return settings

    def to_json(self) -> dict:
        """Return the settings as JSON-compatible data, with field aliases as keys."""
        return self.model_dump(mode="json", by_alias=True)

    def tool_presets(self, tool: "type[Tool]") -> list[dict]:
        """Return a tool's saved presets, also those saved under a former name.

        Args:
            tool: The tool class; its `name` is looked up first, then its
                `former_names` in order.

        Returns:
            Copies of the presets, each a dict with `name` and `settings`; empty if
            none are saved.
        """
        for name in (tool.name, *getattr(tool, "former_names", ())):
            if name in self.presets:
                if name != tool.name:
                    from flim.core.registry import warn_former_name

                    warn_former_name(tool, name)
                return copy.deepcopy(self.presets[name])
        return []

    def resolved_results_dir(self) -> Path:
        """Return the results folder.

        Returns:
            `results_dir` with `~` expanded, or the folder FLIMAnalyzer was started
            from (`START_DIR`) if it is not set.
        """
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
    """Return `values` with the keys in `names` renamed; other keys kept."""
    return {names.get(k, k): v for k, v in values.items()}


def _v0_to_v1(
    data: dict, convert: bool = True, changes: Optional["Changes"] = None
) -> dict:
    """Upgrade version 0 (the dict `Config`) to 1.

    `convert` also converts the plugin parameters to tool settings; `changes`
    records the conversion.
    """
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
    """Return the plugin parameters of version 0 as tool settings."""
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


def _renamed_key(values: Any, old: str, new: str) -> bool:
    """Rename the key `old` of a dict to `new` in place; return whether it was there."""
    if isinstance(values, dict) and old in values:
        values[new] = values.pop(old)
        return True
    return False


def _v1_calculations(calculate: dict) -> list:
    """Return 0.6's `{column: [function, [argument columns]]}` as calculations.

    The calculations are in the order Import makes the default ones, then the others
    in file order.
    """
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
    """Drop 0.6's `import` section, keeping it in `changes.import_section`.

    The section (delimiter, filename parser and patterns, files left out, column
    combinations) has no place in version 2: what a run does with the files is set
    in a workflow file (e.g. the built-in `Import`).
    """
    section = data.pop("import", None)
    if not isinstance(section, dict):
        return
    changes.import_section = section
    parser = (section.get("filename_parser") or {}).get("parser", "defaultparser")
    changes.dropped.append(
        f"import (filename parser {parser}): use a workflow file, e.g. one of the"
        " built-in Import files"
    )


def _v1_filters(data: dict, changes: "Changes") -> None:
    """Move 0.6's range filters into the Filter tool's config, in place.

    The table windows' range filters become the Filter tool's feature filters
    (`enabled` = `selected`); the Filter tool's own 0.6 filters are added switched
    off. The filters are put into the filter components of the Filter tool's
    settings by kind (`flim.configs.data.split_filters`): a second filter on a column goes to the
    other filters. The windows' `use` (`Filter Data`, which switched the range
    filters only) becomes the `Filter Features` switch.
    """
    from flim.configs.data import _filters_of_v1, range_of_legacy, split_filters

    filters = data.get("filters")
    tools = data.setdefault("tools", {})
    if not isinstance(filters, dict) or not isinstance(tools, dict):
        return
    if "use" in filters:
        filters["features"] = {"enabled": bool(filters.pop("use"))}
        changes.converted.append("filters.use to filters.features.enabled (Filter Features)")
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
        flat = nodes + own + list(config.pop("filters", None) or [])
        config.update(split_filters(flat, config))
        entry["config"] = config


def _v1_to_v2(data: dict, changes: Optional["Changes"] = None) -> dict:
    """Upgrade version 1 (0.6) to 2 (0.7).

    `working_dir` becomes `results_dir`, and `display` (histogram ranges no longer
    used) is dropped. In the tool sections, `autosave` (whether) and `results_dir`
    (where) become the section `output` (`save`, `results_dir`; no formats: the
    defaults, as in 0.6), and the `rescale` field of the autoencoder training config,
    also inside the autoencoder workflows' `training` config, becomes
    `rescale_output`.

    Args:
        data: Settings of version 1.
        changes: Records the renamed and dropped keys; None for no record.

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
                entry["output"] = {
                    "save": bool(entry.pop("autosave", False)),
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
            f"autosave and results_dir of {moved} tool{'s' if moved != 1 else ''} to"
            f" {'their' if moved != 1 else 'its'} output section"
        )
    return data


# version n -> the settings of version n + 1
MIGRATIONS: dict[int, Callable[[dict], dict]] = {0: _v0_to_v1, 1: _v1_to_v2}


def version_of(data: Any) -> int:
    """Return the schema version of settings data; 0 if it has none or is not a dict."""
    return int(data.get("schema_version", 0)) if isinstance(data, dict) else 0


@dataclass
class Changes:
    """The keys a migration converted (renamed or restructured) and dropped.

    Attributes:
        converted: Descriptions of the converted keys.
        dropped: Descriptions of the dropped keys.
        import_section: The dropped `import` section of a version 1 file; None if
            there was none.
    """

    converted: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    # the `import` section of a file of FLIMAnalyzer 0.6 (version 1), dropped: it can
    # be saved as a workflow file (SettingsValidation.import_workflow)
    import_section: Optional[dict] = None


# keys of earlier 0.7.0 development builds that are not used any more
_DEVELOPMENT_KEYS = ("import_workflow",)
# the preset keys of earlier 0.7.0 development builds: key -> (tool, preset of an item)
_PRESET_KEYS: dict[str, tuple[str, Callable[[dict], dict]]] = {
    "separate_presets": ("Separate Categories", lambda item: item),
    "calculation_presets": (
        "Calculate",
        lambda item: {"name": item.get("name", ""), "settings": {"calculations": [item]}},
    ),
}


def _moved_presets(data: dict, changes: Changes) -> dict:
    """Return the data with the keys of earlier development builds moved or removed.

    `separate_presets` and `calculation_presets` (each calculation a preset) become
    `presets` > `Separate Categories` and `presets` > `Calculate`. The keys of
    `_DEVELOPMENT_KEYS` are removed without a record: no release wrote them. Data
    without these keys is returned as it is.
    """
    if not isinstance(data, dict):
        return data
    if any(key in data for key in _DEVELOPMENT_KEYS):
        data = {k: v for k, v in data.items() if k not in _DEVELOPMENT_KEYS}  # not released
    if not any(key in data for key in _PRESET_KEYS):
        return data
    data = copy.deepcopy(data)
    presets = data.setdefault("presets", {})
    for key, (tool, preset) in _PRESET_KEYS.items():
        if key in data:
            items = data.pop(key) or []
            presets.setdefault(tool, []).extend(preset(i) for i in items if isinstance(i, dict))
            changes.converted.append(f"{key} to presets.{tool}")
    return data


def migrate(data: dict, changes: Optional[Changes] = None) -> dict:
    """Upgrade settings data of any version to the current one.

    Args:
        data: The settings data; data of the current version is returned unchanged,
            apart from the preset keys of earlier development builds (`_moved_presets`).
        changes: Records the converted and dropped keys; None for no record.

    Returns:
        The settings data of version `SETTINGS_VERSION`.

    Raises:
        ValueError: If `data` is of a newer version than `SETTINGS_VERSION`.
    """
    data = tool_file_settings(data)
    version = version_of(data)
    if version > SETTINGS_VERSION:
        raise ValueError(
            f"settings file schema version {version} is not supported by the installed"
            f" FLIMAnalyzer {__version__} (up to schema version {SETTINGS_VERSION})."
            " Upgrade FLIMAnalyzer."
        )
    while version < SETTINGS_VERSION:
        data = MIGRATIONS[version](data, changes=changes)
        version += 1
        data["schema_version"] = version
    changes = changes if changes is not None else Changes()
    return _removed_settings(_moved_presets(data, changes), changes)


# the app settings that FLIMAnalyzer wrote and no longer has: key -> why it is dropped
_REMOVED_SETTINGS: dict[str, str] = {
    "strict": "now processing.strict of tool and workflow files",
    "cache": "never used",
    "char_replacements": "now output.char_replacements of tool and workflow files",
}


def _removed_settings(data: dict, changes: Changes) -> dict:
    """Drop the app settings that FLIMAnalyzer wrote and no longer has.

    `strict` (whether workflows guess missing columns) is a setting of tool and
    workflow files now (`processing.strict`), and so is `char_replacements` (the
    text replaced in the names of saved files, `output.char_replacements`). `cache` (a cache folder and its limits)
    was used by no code. Without this, an app settings file with one of them is
    refused for an unknown setting.

    Args:
        data: Settings data of the current version.
        changes: Records the dropped keys.

    Returns:
        The data without these settings.
    """
    for key, reason in _REMOVED_SETTINGS.items():
        if key in data:
            data = {k: v for k, v in data.items() if k != key}
            changes.dropped.append(f"{key} ({reason})")
    return data


def is_tool_file(data: Any) -> bool:
    """Return whether settings data is a tool file (one tool's settings, `tool`).

    Args:
        data: The data read from a file.

    Returns:
        True for a dict with `tool` and without `tools`.
    """
    return isinstance(data, dict) and "tool" in data and "tools" not in data


def settings_kind(data: object) -> Optional[str]:
    """Return the kind of a settings file's data: `tool`, `workflow`, `app` or None.

    The kinds are tested in this order, and the first match is returned (tool and
    workflow files also have `schema_version`):

    1. `tool`: a tool file (`schema_version` and `tool`, see `is_tool_file`).
    2. `workflow`: has `steps`.
    3. `app`: has `schema_version`, `tools` or a key of `AppSettings`; also an app
       settings file of an older version, which has other keys too.

    Args:
        data: The data read from the file.

    Returns:
        The kind, or None for other data (e.g. not a JSON object, or a config alone
        with `classname`).
    """
    if not isinstance(data, dict) or "classname" in data:  # a config alone is none
        return None
    if is_tool_file(data):
        return "tool"
    if "steps" in data:
        return "workflow"
    if set(data) & ({"schema_version", "tools"} | set(AppSettings.model_fields)):
        return "app"  # also of older versions, which have other sections too
    return None


def tool_file_settings(data: dict) -> dict:
    """Return a tool file's data as settings data with that one tool's section.

    Args:
        data: The data read from a file.

    Returns:
        For a tool file, settings data with the tool's section, as
        `{"schema_version": ..., "tools": {<tool>: {...}}}`, with the file's other
        keys (`config`, `output`, and any others, which are then reported as
        unknown) in the section; any other data unchanged.
    """
    if not is_tool_file(data):
        return data
    section = {k: v for k, v in data.items() if k not in ("schema_version", "tool")}
    return {
        "schema_version": data.get("schema_version", SETTINGS_VERSION),
        "tools": {str(data["tool"]): section},
    }


def _unknown_keys(model: BaseModel, path: str = "") -> list[str]:
    """Return the extra keys of a model and its nested models, with their paths."""
    keys = [f"{path}{k}" for k in (model.model_extra or {})]
    for name in type(model).model_fields:
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            keys += _unknown_keys(value, f"{path}{name}.")
    return keys


def known_data(model: BaseModel) -> dict:
    """Return a settings model as JSON data without its unknown keys.

    Unknown keys (`_unknown_keys`) are kept in the model but not used; this data has
    only the settings that are used, with field aliases as keys.

    Args:
        model: The settings, for example `AppSettings`.

    Returns:
        The JSON-compatible data.
    """
    data = model.model_dump(mode="json", by_alias=True)

    def strip(part: BaseModel, part_data: dict) -> None:
        for key in part.model_extra or {}:
            part_data.pop(key, None)
        for name, info in type(part).model_fields.items():
            value, key = getattr(part, name), info.alias or name
            if isinstance(value, BaseModel) and isinstance(part_data.get(key), dict):
                strip(value, part_data[key])

    strip(model, data)
    return data


def _validated(data: dict) -> AppSettings:
    """Validate settings data of the current version and log its unknown keys."""
    settings = AppSettings.model_validate(data)
    unknown = _unknown_keys(settings)
    if unknown:
        logger.warning(f"Settings: ignoring unknown keys {', '.join(unknown)}")
    return settings


def settings_from_data(data: dict) -> AppSettings:
    """Return the settings of loaded JSON of any version.

    Args:
        data: The settings data.

    Returns:
        The validated settings; unknown keys are logged.

    Raises:
        ValueError: If `data` is of a newer version than `SETTINGS_VERSION`.
        pydantic.ValidationError: If a value is not valid.
    """
    return _validated(migrate(data))


# how a later settings layer changes each section: "whole" replaces the section,
# "per key" replaces its entries one by one and keeps the others (`merge_sections`)
SECTION_MERGE: dict[str, str] = {
    "description": "whole",
    "results_dir": "whole",
    "execution": "whole",  # one executor with its options
    "prefect_server": "whole",
    "server_timeout": "whole",
    "log": "per key",
    "appsettings_path": "whole",
    "max_windows": "per key",  # a limit per kind of window
    "presets": "per key",  # per tool
    "favorites": "whole",
    "workflow_paths": "whole",
    "default_app_settings": "whole",
    "last_run_url": "whole",
    "filters": "whole",  # one filter set
    "tools": "per key",  # per tool; former names are removed
}


def merge_sections(base: dict, changes: dict) -> dict:
    """Return a copy of `base` with the sections of `changes` merged into it.

    Each section is merged by its rule in `SECTION_MERGE`: replaced whole, or entry
    by entry (`per key`), keeping the entries `changes` doesn't have; e.g. an app
    settings file with presets of Filter keeps the user's presets of Calculate. In
    `tools`, the sections under the former names of a registered tool are removed
    too. A section without a rule is replaced whole.

    Args:
        base: Settings sections in the current version.
        changes: Settings sections of any version; upgraded before merging.

    Returns:
        The merged sections, without `schema_version` from `changes`.

    Raises:
        ValueError: If `changes` is of a newer version than `SETTINGS_VERSION`.
    """
    merged = copy.deepcopy(base)
    for key, value in migrate(changes).items():
        if key == "schema_version":
            continue
        if key == "tools" and isinstance(value, dict):
            for name in value:
                tool = _registered(name)
                for former in getattr(tool, "former_names", ()):
                    merged.setdefault("tools", {}).pop(former, None)
        current = merged.get(key)
        if SECTION_MERGE.get(key) == "per key" and isinstance(value, dict) and isinstance(current, dict):
            merged[key] = {**current, **copy.deepcopy(value)}
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def update_settings(settings: AppSettings, data: dict) -> AppSettings:
    """Return `settings` with the sections in `data` merged into them.

    Each section is merged by its rule in `SECTION_MERGE` (see `merge_sections`):
    replaced whole, or entry by entry (`log`, `max_windows`, `presets` per tool);
    in `tools`, each tool's section is replaced separately.

    Args:
        settings: The current settings; not changed.
        data: Settings JSON of any version.

    Returns:
        New settings; unknown keys are logged.

    Raises:
        ValueError: If `data` is of a newer version than `SETTINGS_VERSION`.
        pydantic.ValidationError: If a value is not valid.
    """
    merged = merge_sections(settings.to_json(), data)
    merged["schema_version"] = SETTINGS_VERSION
    return _validated(merged)


def _current_tool_name(name: str) -> str:
    """Return a tool's current name for `name`, which may be a former name."""
    from flim.core.registry import tools

    return tools.current_name(name) or name


def _registered(name: str) -> "Optional[type[Tool]]":
    """Return the registered tool named `name`, or None."""
    from flim.core.registry import tools

    return tools.get(name) if name in tools else None


def load_settings(
    path: str | os.PathLike, settings: Optional[AppSettings] = None
) -> AppSettings:
    """Read a settings file of any version.

    Args:
        path: The settings file.
        settings: The sections the file does not have; None for the default settings
            (`AppSettings.default`). Defaults to None.

    Returns:
        The settings; unknown keys are logged.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not JSON (`json.JSONDecodeError`), does not hold a
            JSON object, or is of a newer version than `SETTINGS_VERSION`.
        pydantic.ValidationError: If a value is not valid.
    """
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a settings file")
    return update_settings(settings or AppSettings.default(), data)


# --- validating a settings file before it is used ---


@dataclass
class SettingsValidation:
    """The result of validating a settings file.

    It lists what the file's migration converted and dropped, which keys cannot be
    used, and the sections that can.

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
        not_validated: Tools whose settings cannot be validated because the tool is not
            installed; their settings are kept.
        user_only: Keys read only from the user settings file (`USER_FILE_ONLY`)
            that have a value; not used from this file, without stopping its use.
        sections: The sections that can be used, in the current version, without
            the unknown keys and the sections with invalid values.
        import_workflow: The content of a workflow file that imports data as the
            file's 0.6 `import` section did; None if the file has no such section.
            It is offered to be saved, never applied.
        import_read: How that `import` section read the data files: the Import
            Tables settings that differ from the defaults.
    """

    path: Path
    version: Optional[int] = None
    error: Optional[str] = None
    converted: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    not_validated: list[str] = field(default_factory=list)
    user_only: list[str] = field(default_factory=list)
    sections: dict = field(default_factory=dict)
    # a workflow file (its content) that imports as the file's 0.6 import settings
    # did; offered to be saved, never applied (see flim.core.workflowfile)
    import_workflow: Optional[dict] = None
    # how that file read the data files (Import Tables' settings that differ)
    import_read: dict = field(default_factory=dict)

    @property
    def problems(self) -> bool:
        """Whether some of the file's settings cannot be used."""
        return bool(self.error or self.unknown or self.invalid)

    def tool_problems(self, tool: "type[Tool]") -> bool:
        """Return whether some of a tool's settings, or the file, cannot be used.

        Args:
            tool: The tool class; its settings under former names are included.

        Returns:
            True if the file cannot be used at all, or if a key under the tool's
            settings is unknown or has an invalid value.
        """
        if self.error:
            return True
        names = (tool.name, *getattr(tool, "former_names", ()))
        prefixes = tuple(f"tools.{name}" for name in names)
        return any(key.startswith(prefixes) for key in self.unknown + self.invalid)

    def summary(self, limit: Optional[int] = None) -> str:
        """Return the result as text, one heading per kind of finding.

        Args:
            limit: The number of items listed per heading; None lists all. Defaults to
                None.

        Returns:
            The path and schema version, then each heading with its items; or one
            line with the error if the file cannot be used.
        """
        if self.error:
            return f"{self.path} cannot be used: {self.error}"
        lines = [f"{self.path}: schema version {self.version}"]
        for heading, items in (
            ("Settings that cannot be used (unknown)", self.unknown),
            ("Settings that cannot be used (invalid values)", self.invalid),
            ("Converted to the current version", self.converted),
            ("Removed by the conversion (no longer used)", self.dropped),
            ("Not validated (tool not installed)", self.not_validated),
            ("Not used (read only from the user settings file)", self.user_only),
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
    """Validate `data`, removing the sections with invalid values until it is valid.

    A tool's settings with an invalid value are removed, not the whole `tools`
    section.

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


def validate_settings_file(path: str | os.PathLike) -> SettingsValidation:
    """Validate a settings file of any version before it is used; the file is only read.

    The file is migrated to the current version and validated. Each tool's settings
    are validated with the tool's config class if the tool is installed. Errors of
    reading and upgrading the file are recorded in `error`, not raised.

    Args:
        path: The settings file.

    Returns:
        The result; `sections` holds what can be used.
    """
    path = Path(path)
    validation = SettingsValidation(path)
    changes = Changes()
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "classname" in data:
            raise ValueError("not a settings file")
        validation.version = version_of(data)
        data = migrate(data, changes)
    except (OSError, ValueError) as err:  # incl. json.JSONDecodeError
        validation.error = str(err)
        return validation
    validation.converted, validation.dropped = changes.converted, changes.dropped
    if changes.import_section is not None:
        from flim.core.workflowfile import import_read_settings, import_workflow_data

        validation.import_workflow = import_workflow_data(
            changes.import_section, data.get("tools") or {}, f"Import ({path.stem})"
        )
        validation.import_read = import_read_settings(changes.import_section)
    data.pop("schema_version", None)
    # an empty value (e.g. `[]` written by save_settings) carries nothing: not reported
    validation.user_only = [key for key in USER_FILE_ONLY if data.get(key) not in (None, [], "")]
    for key in USER_FILE_ONLY:
        data.pop(key, None)
    if "tools" in data and not isinstance(data["tools"], dict):
        validation.invalid.append("tools: not a mapping of tool names to settings")
        data.pop("tools")
    settings = _remove_invalid(data, validation.invalid)
    for name, entry in settings.tools.entries.items():
        tool = _registered(name)
        if tool is None:
            validation.not_validated.append(f"tools.{name}")
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
            validation.invalid.append(f"tools.{name}.config: {reason}")
            data["tools"].pop(name, None)
            continue
        # formats of kinds the tool doesn't make, as for tool and workflow files
        kinds = tool.output_kinds()
        for options in entry.output.formats:
            if options.kind not in kinds:
                validation.invalid.append(
                    f"tools.{name}.output.formats: a format of kind '{options.kind}',"
                    f" which {tool.name} doesn't make (it makes: {', '.join(kinds)})"
                )
                data["tools"].pop(name, None)  # as for an invalid value (_remove_invalid)
    settings = _remove_invalid(data, validation.invalid)
    validation.unknown = _extra_keys(settings) + [
        key
        for name, entry in settings.tools.entries.items()
        for key in _extra_keys(entry, f"tools.{name}.")
    ]
    known = settings.to_json()
    _drop_extra_keys(settings, known)
    for name, entry in settings.tools.entries.items():
        _drop_extra_keys(entry, known["tools"][name])
    validation.sections = {key: known[key] for key in data if key in known}
    return validation


def validate_app_settings(path: str | os.PathLike) -> SettingsValidation:
    """Validate an app settings file, as `validate_settings_file`; refuse tool and workflow files.

    A tool file or a workflow file holds the settings of a run, not app settings: it
    is given to `--run` (flimbatch) or loaded in a tool's dialog (GUI).

    Args:
        path: The file.

    Returns:
        The result; for a tool or workflow file, with `error` saying what it is.
    """
    validation = validate_settings_file(path)
    if validation.error is not None:
        return validation
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as err:
        validation.error = str(err)
        return validation
    if is_tool_file(data):
        validation.error = (
            f"a tool file (the settings of {data['tool']}), not an app settings file;"
            " flimbatch runs it with --run, the GUI loads it in the tool's dialog"
        )
    elif "steps" in data:
        validation.error = "a workflow file, not an app settings file; flimbatch runs it with --run"
    else:
        return validation
    validation.sections = {}
    return validation


def write_json(path: str | os.PathLike, data: Any, *, newline: bool = False) -> None:
    """Write data as JSON to a file in one step: readers get the old or the new file.

    The data is written to a temporary file in the same folder, which then replaces
    the file (`os.replace`). The new file keeps the permissions of the file it
    replaces. If writing fails, the file is left unchanged and the temporary file is
    removed.

    Args:
        path: The file; it is replaced if it exists. Its folder must exist.
        data: The data; values JSON doesn't know are written as texts.
        newline: End the file with a line break. Defaults to False.

    Raises:
        OSError: If the file can't be written.
    """
    import shutil
    import uuid

    path = Path(path)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "x") as f:  # permissions as for a new file (umask)
            json.dump(data, f, indent=2, default=str)
            if newline:
                f.write("\n")
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def with_current_names(sections: dict) -> dict:
    """Return settings sections with the tools' sections and presets under their names.

    A section or presets saved under a former name of a tool (`Tool.former_names`,
    deprecated) move to the tool's current name; if the current name has its own,
    those are kept and the former name's are dropped.

    Args:
        sections: Settings sections, e.g. `SettingsValidation.sections`.

    Returns:
        A copy, with `tools` and `presets` renamed.
    """
    from flim.core.registry import tools

    renamed = dict(sections)
    for key in ("tools", "presets"):
        entries = sections.get(key)
        if not isinstance(entries, dict):
            continue
        result: dict = {}
        for name, value in entries.items():
            current = tools.current_name(name)
            if current is None:
                result[name] = value
            elif current not in entries:
                result[current] = value
        renamed[key] = result
    return renamed


def save_sections(sections: dict, path: str | os.PathLike) -> None:
    """Write settings sections, in the current version, to a file.

    Args:
        sections: Sections in the current version, e.g. `SettingsValidation.sections`.
        path: The file; it is replaced if it exists, in one step (`write_json`).
    """
    write_json(path, {"schema_version": SETTINGS_VERSION, **sections})


def backup_path(path: str | os.PathLike, version: int) -> Path:
    """Return a free name for the copy of a settings file of an older version.

    Args:
        path: The file, e.g. `lab.json`.
        version: Its schema version.

    Returns:
        `lab.v1.json` in the same folder, or `lab.v1_2.json` and so on if taken.
    """
    path = Path(path)
    candidate, number = path.with_name(f"{path.stem}.v{version}{path.suffix}"), 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.v{version}_{number}{path.suffix}")
        number += 1
    return candidate


def update_settings_file(path: str | os.PathLike) -> Path:
    """Rewrite an app settings file or a tool file of an older version in the current one.

    The original is kept next to it (`backup_path`), so that the older FLIMAnalyzer
    version can still read it. A tool file stays a tool file. Tools named by a former
    name (deprecated) are saved under their current name (`with_current_names`).

    Args:
        path: The file.

    Returns:
        The copy of the original.

    Raises:
        ValueError: If the file can't be used, has settings that can't be used, or
            is of the current version; the message says which.
        OSError: If the file can't be copied or written.
    """
    import shutil

    path = Path(path)
    validation = validate_settings_file(path)
    if validation.problems:
        raise ValueError(validation.summary())
    if validation.version is None or validation.version >= SETTINGS_VERSION:
        raise ValueError(f"{path}: already in the current format (schema version {SETTINGS_VERSION})")
    data = json.loads(path.read_text())
    backup = backup_path(path, validation.version)
    shutil.copy2(path, backup)
    if is_tool_file(data):
        name = str(data["tool"])
        section = validation.sections.get("tools", {}).get(name, {})
        current = _current_tool_name(name)  # a former name: the tool's name now
        content = {"schema_version": SETTINGS_VERSION, "tool": current, **section}
        write_json(path, content, newline=True)
    else:
        save_sections(with_current_names(validation.sections), path)
    return backup


def save_settings(settings: AppSettings, path: str | os.PathLike) -> None:
    """Write settings, in the current version, to a file.

    Args:
        settings: The settings.
        path: The file; it is replaced if it exists, in one step (`write_json`).
    """
    write_json(path, settings.to_json())


# --- the settings of one tool (in a FLIMAnalyzer settings file, or alone) ---


def read_tool_settings(
    path: str | os.PathLike, tool: "type[Tool]"
) -> Optional[ToolSettings]:
    """Read a tool's settings from a tool file or a tool's section of a settings file.

    The file may be of an older version, and the section may be under one of the
    tool's former names; a tool file of another tool has no settings of `tool`. A
    file with only a config (with `classname`) is returned as the config, without
    validating that it is a config of `tool`.

    Args:
        path: The settings file, or a config file.
        tool: The tool class.

    Returns:
        The tool's settings, or None if the file has no settings of the tool.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not JSON (`json.JSONDecodeError`), does not hold a
            JSON object, or is of a newer version than `SETTINGS_VERSION`.
        pydantic.ValidationError: If the file's tool settings are not valid.
    """
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


def tool_file_data(tool: "type[Tool]", entry: ToolSettings) -> dict:
    """Return a tool's settings as the content of a tool file.

    Args:
        tool: The tool class.
        entry: The tool's settings.

    Returns:
        The keys `schema_version`, `tool`, `config`, `output` (`save`, `formats`)
        and `processing` if set, the shape of a workflow step; without
        `output.results_dir`, a setting of the computer.
    """
    section = entry.model_dump(mode="json")
    section["output"].pop("results_dir", None)
    data = {"schema_version": SETTINGS_VERSION, "tool": tool.name}
    data.update({k: section[k] for k in ("config", "output") if k in section})
    if "processing" in section:
        data["processing"] = section["processing"]
    return data


def write_tool_settings(
    path: str | os.PathLike, tool: "type[Tool]", entry: ToolSettings
) -> None:
    """Write a tool's settings: a tool file, or the tool's section of a settings file.

    A new file, or an existing tool file, is written as a tool file (`{"schema_version",
    "tool", "config", "output": {"save", "formats"}}`, the shape of a workflow step;
    no folder).
    In an existing settings file, the tool's section is replaced and the other
    sections are kept; the file is saved in the current version, and the tool's
    sections under its former names are removed.

    Args:
        path: The file; created if it does not exist, else replaced in one step
            (`write_json`).
        tool: The tool class.
        entry: The tool's settings.

    Raises:
        OSError: If the file cannot be read or written.
        ValueError: If an existing file is not JSON, is not a settings or tool file
            (or holds a config alone), or is of a newer version than
            `SETTINGS_VERSION`.
    """
    existing = None
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
        if not isinstance(existing, dict) or "classname" in existing:
            raise ValueError(f"{path} is not a settings file")
    if existing is None or is_tool_file(existing):
        data = tool_file_data(tool, entry)
    else:
        data = migrate(existing)
        tools = data.setdefault("tools", {})
        for name in getattr(tool, "former_names", ()):
            tools.pop(name, None)
        tools[tool.name] = entry.model_dump(mode="json")
    write_json(path, data)  # in one step: an existing file's other sections are kept
