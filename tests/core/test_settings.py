"""Versioned application settings (flim.core.settings)."""

import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from flim.core.saving import AutosaveConfig

import flim.workflow  # noqa: F401  (registers the workflows)
from flim.configs import ConcatConfig, KMeansConfig, SummaryConfig
from flim.configs.workflow import BasicFLIRRConfig
from flim.core.registry import tools
from flim.core.execution import LocalExecutorSettings
from flim.core.settings import (
    SETTINGS_VERSION,
    START_DIR,
    AppSettings,
    Changes,
    ToolSettings,
    load_settings,
    migrate,
    read_tool_settings,
    save_settings,
    settings_from_data,
    tool_settings,
    update_settings,
    write_tool_settings,
)

# saved by FLIMAnalyzer 0.5 (the dict Config, version 0), with some changed settings
V0_FILE = Path(__file__).parent / "data" / "settings_v0.json"
# version 1: the format of 0.6
V1_FILE = Path(__file__).parent / "data" / "settings_v1.json"


def test_defaults():
    settings = AppSettings.default()
    assert settings.schema_version == SETTINGS_VERSION
    assert "import" not in settings.to_json()  # reading: a workflow file's
    # the windows' range filters of 0.6, now the Filter tool's range filters
    config = settings.tools.config(tools.get("Filter"))
    filters = config.features.filters
    assert len(filters) == 38 and sum(f.enabled for f in filters) == 3  # one per column
    assert len({f.column for f in filters}) == 38
    assert filters[0].column == "trp t1" and (filters[0].low, filters[0].high) == (0, 2500)
    assert config.categories.filters == [] and config.other.filters == []
    assert settings.results_dir is None and settings.resolved_results_dir() == START_DIR
    assert settings.execution == LocalExecutorSettings() and settings.prefect_server
    assert settings.log.dir is None and settings.log.max_age_days == 30
    assert "cache" not in settings.to_json()
    assert "preprocess" not in settings.to_json()  # the Rename, Drop, Calculate tools'
    assert settings.filters.model_dump() == {
        "features": {"enabled": False}, "categories": {"enabled": False}, "show_dropped": True,
    }  # fmt: skip
    assert list(settings.tools.entries) == ["Filter"]  # the others: their configs'


def test_settings_of_version_0(caplog):
    with caplog.at_level(logging.WARNING):
        settings = load_settings(V0_FILE)
    assert not caplog.records  # every key known
    assert settings.schema_version == SETTINGS_VERSION
    assert settings.results_dir == Path("/data/results")
    assert "import" not in settings.to_json()  # dropped: a workflow file's
    assert settings.filters.features.enabled is False and settings.filters.show_dropped is True
    assert settings.filters.categories.enabled is False
    store = settings.tools
    summary = store.config(tools.get("Summarize"))
    assert isinstance(summary, SummaryConfig)
    assert (summary.aggs, summary.grouping) == (["mean", "sem"], ["Treatment"])
    assert store.config(tools.get("K-Means")).n_clusters == 4
    # saved under the plugin's name, read by the renamed tool
    assert store.config(tools.get("Concatenate")).mode == "horizontal"
    assert isinstance(store.config(tools.get("Basic FLIRR Analysis")), BasicFLIRRConfig)
    assert all(e.legacy is None for e in store.entries.values())  # all converted


def test_saved_in_the_current_version_and_read_back(tmp_path):
    settings = load_settings(V0_FILE)
    settings.tools.set(
        tools.get("K-Means"),
        KMeansConfig(n_clusters=7),
        AutosaveConfig(enabled=True, results_dir="/r", formats=[{"kind": "plot", "format": "svg"}]),
    )
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    data = json.loads(path.read_text())
    assert data["schema_version"] == SETTINGS_VERSION and "root" not in data
    again = load_settings(path)
    assert again == settings
    entry = again.tools.entry(tools.get("K-Means"))
    assert (entry.autosave.enabled, entry.autosave.results_dir) == (True, Path("/r"))
    assert [(f.kind, f.format) for f in entry.autosave.formats] == [("plot", "svg")]
    assert again.tools.config(tools.get("K-Means")).n_clusters == 7


def test_unknown_keys_are_reported_not_fatal(caplog):
    data = {"schema_version": SETTINGS_VERSION, "colour": "red", "filters": {"x": 1}}
    with caplog.at_level(logging.WARNING):
        settings = settings_from_data(data)
    assert "colour" in caplog.text and "filters.x" in caplog.text
    assert settings.filters.features.enabled is False


def test_newer_versions_are_refused():
    with pytest.raises(ValueError, match="is not supported by the installed FLIMAnalyzer .* Upgrade FLIMAnalyzer"):
        migrate({"schema_version": SETTINGS_VERSION + 1})


def test_invalid_tool_settings_give_the_defaults(caplog):
    settings = AppSettings()
    settings.tools.entries["Concatenate"] = ToolSettings(config={"mode": "diagonal"})
    settings = AppSettings.model_validate(settings.to_json())
    with caplog.at_level(logging.WARNING):
        assert settings.tools.config(tools.get("Concatenate")) == ConcatConfig()
    assert "not valid" in caplog.text


def test_settings_of_version_1():
    settings = load_settings(V1_FILE)
    entry = settings.tools.entry(tools.get("Summarize"))
    # 0.6's autosave and results_dir: the autosave section, default formats
    assert (entry.autosave.enabled, entry.autosave.results_dir) == (True, Path("results"))
    assert entry.autosave.formats == []
    assert settings.tools.config(tools.get("K-Means")).n_clusters == 7
    # by tool; 0.6's preprocess: the Rename Columns, Drop Columns and Calculate tools
    assert set(settings.to_json()["tools"]) == {
        "Summarize", "K-Means", "Rename Columns", "Drop Columns", "Calculate", "Filter",
    }
    # version 2: working_dir is results_dir, display is gone
    assert settings.results_dir == Path("/Users/khs3z/FLIMAnalyzerResults")
    assert "display" not in settings.to_json() and "working_dir" not in settings.to_json()


def test_version_1_autoencoder_rescale_becomes_rescale_output():
    training = {"classname": "flim.tools.autoencoder.AETraining", "rescale": True}
    tune = {"classname": "flim.workflow.aetune.AETune", "training": dict(training)}
    data = {
        "schema_version": 1,
        "tools": {
            "Autoencoder: Train": {"config": training},
            "FLIM Data Augmentation Tuning": {"config": tune},
        },
    }
    migrated = migrate(data)
    assert migrated["schema_version"] == SETTINGS_VERSION
    tools_v2 = migrated["tools"]
    assert tools_v2["Autoencoder: Train"]["config"] == {
        "classname": "flim.tools.autoencoder.AETraining",
        "rescale_output": True,
    }
    assert tools_v2["FLIM Data Augmentation Tuning"]["config"]["training"][
        "rescale_output"
    ] is True
    assert data["tools"]["Autoencoder: Train"]["config"]["rescale"] is True  # unchanged


def test_a_file_with_some_sections_changes_only_those():
    settings = AppSettings.default()
    settings.tools.set(tools.get("K-Means"), KMeansConfig(n_clusters=3))
    data = {
        "schema_version": SETTINGS_VERSION,
        "filters": {"use": True},
        "tools": {"Summarize": {"config": SummaryConfig(aggs=["max"]).model_dump()}},
    }
    updated = update_settings(settings, data)
    # replaced; `use` of development builds: both switches
    assert updated.filters.features.enabled and updated.filters.categories.enabled
    assert updated.filters.show_dropped  # default
    assert updated.tools.config(tools.get("K-Means")).n_clusters == 3
    assert updated.tools.config(tools.get("Summarize")).aggs == ["max"]


def test_a_tool_section_in_a_settings_file(tmp_path):
    kmeans = tools.get("K-Means")
    path = tmp_path / "settings.json"
    write_tool_settings(
        path,
        kmeans,
        tool_settings(KMeansConfig(n_clusters=5), AutosaveConfig(enabled=True, results_dir="/r")),
    )
    # a new file: a tool file, the shape of a workflow step, without the folder
    data = json.loads(path.read_text())
    assert set(data) == {"schema_version", "tool", "config", "output"}
    assert data["schema_version"] == SETTINGS_VERSION and data["tool"] == "K-Means"
    assert data["config"]["classname"] == f"{kmeans.__module__}.{kmeans.__qualname__}"
    assert "version" not in data["config"]  # the run records the runtime's version
    assert data["output"] == {"save": True, "formats": []}
    entry = read_tool_settings(path, kmeans)
    assert entry.output.save and entry.output.results_dir is None
    assert entry.config["n_clusters"] == 5
    assert read_tool_settings(path, tools.get("Summarize")) is None  # another tool's file

    # in an application settings file (of an older version): the rest is kept, and
    # the tool's section has its folder
    path = tmp_path / "app.json"
    path.write_text(V0_FILE.read_text())
    write_tool_settings(path, kmeans, tool_settings(
        KMeansConfig(n_clusters=9), AutosaveConfig(enabled=True, results_dir="/r")
    ))  # fmt: skip
    assert json.loads(path.read_text())["tools"]["K-Means"]["output"]["results_dir"] == "/r"
    settings = load_settings(path)
    assert settings.tools.config(kmeans).n_clusters == 9
    assert "import" not in settings.to_json()  # version 0's import: dropped
    summary = settings.tools.config(tools.get("Summarize"))
    assert summary.aggs == ["mean", "sem"]
    # saved under a former name: replaced, read by the renamed tool
    concat = tools.get("Concatenate")
    assert read_tool_settings(V0_FILE, concat).config["mode"] == "horizontal"
    write_tool_settings(path, concat, tool_settings(ConcatConfig()))
    names = json.loads(path.read_text())["tools"]
    assert "Concatenate" in names and not set(concat.former_names) & set(names)

    # a config alone
    path = tmp_path / "config.json"
    path.write_text(json.dumps(KMeansConfig(n_clusters=4).model_dump(mode="json")))
    assert read_tool_settings(path, kmeans).config["n_clusters"] == 4
    with pytest.raises(ValueError, match="not a settings file"):
        write_tool_settings(path, kmeans, tool_settings(KMeansConfig()))


def test_a_tool_file_is_read_as_a_settings_file_with_one_tool(tmp_path):
    from flim.core.settings import validate_settings_file

    path = tmp_path / "summarize.json"
    path.write_text(json.dumps({
        "schema_version": 2, "tool": "Summarize", "config": {"aggs": ["mean"]},
        "output": {"save": True, "formats": [{"kind": "table", "format": "csv"}]},
    }))  # fmt: skip
    validation = validate_settings_file(path)
    assert validation.error is None and not validation.invalid and not validation.unknown
    section = validation.sections["tools"]["Summarize"]
    assert section["config"]["aggs"] == ["mean"] and section["output"]["save"] is True


def test_keys_of_the_user_settings_file_only_are_not_used(tmp_path):
    from flim.core.settings import USER_FILE_ONLY, validate_settings_file

    path = tmp_path / "app.json"
    data = {"schema_version": 2, "results_dir": "res", "workflow_paths": ["/wf"],
            "last_run_url": "http://x", "default_app_settings": "/a.json",
            "appsettings_path": ["/as"]}  # fmt: skip
    path.write_text(json.dumps(data))
    validation = validate_settings_file(path)
    assert validation.user_only == list(USER_FILE_ONLY) and not validation.problems
    assert set(validation.sections) == {"results_dir"}
    assert "Not used (read only from the user settings file):" in validation.summary()


def test_char_replacements_add_to_the_defaults_and_refuse_other_characters():
    from pydantic import ValidationError

    settings = AppSettings.model_validate({"char_replacements": {"%": "pct", "°": "deg"}})
    assert settings.char_replacements == {"%": "pct", "τ": "tau", "µ": "u", "μ": "u", "°": "deg"}
    assert AppSettings().char_replacements["%"] == "pcent"
    with pytest.raises(ValidationError, match="only ASCII letters, digits"):
        AppSettings.model_validate({"char_replacements": {"%": "/"}})


def test_the_autosave_section_of_development_builds_is_read():
    from flim.core.settings import ToolSettings

    entry = ToolSettings.model_validate(
        {"config": {}, "autosave": {"enabled": True, "results_dir": "/r", "formats": []}}
    )
    assert entry.output.save and entry.output.results_dir == Path("/r")
    assert "autosave" not in entry.model_dump(mode="json")


def test_rename_and_drop_of_version_1_become_tool_settings():
    from flim.tools.data import DropColumns, RenameColumns

    data = json.loads(V1_FILE.read_text())
    data["preprocess"]["drop"] = ["Exc1_", "Exc4_"]
    changes = Changes()
    migrated = migrate(data, changes)
    assert "preprocess" not in migrated
    assert "preprocess.rename to the Rename Columns tool" in changes.converted
    assert "preprocess.drop to the Drop Columns tool" in changes.converted
    settings = AppSettings.model_validate(migrated)
    rename = settings.tools.config(RenameColumns)
    assert [(r.part, r.new) for r in rename.replacements][2] == ("Exc2_-Ch3-_", "FAD ")
    drop = settings.tools.config(DropColumns)
    assert [(r.text, r.match) for r in drop.drop] == [
        ("Exc1_", "contains"), ("Exc4_", "contains")
    ]


def test_calculate_of_version_1_becomes_function_calculations():
    from flim.tools.data import Calculate

    data = json.loads(V1_FILE.read_text())
    data["preprocess"]["calculate"] = {
        "NADPH/NADH": ["ratio", ["NADPH %", "NADH %"]],
        "mine": ["ratio", ["a", "b"]],
        "NADH %": ["nadh_perc", ["NADPH %"]],
    }
    changes = Changes()
    settings = AppSettings.model_validate(migrate(data, changes))
    assert "preprocess.calculate to the Calculate tool" in changes.converted
    calculations = settings.tools.config(Calculate).calculations
    # Import's order first (NADH % before NADPH/NADH), then the others
    assert [c.name for c in calculations] == ["NADH %", "NADPH/NADH", "mine"]
    assert (calculations[2].kind, calculations[2].function, calculations[2].args) == (
        "function", "ratio", ["a", "b"]
    )


def test_filters_of_version_1_become_the_filter_tools():
    from flim.configs.data import RangeFilterNode

    data = json.loads(V1_FILE.read_text())
    data["filters"]["range_filters"] = [
        {"name": "t1", "rangelow": -5, "rangehigh": float("inf"), "allowedmin": 0, "selected": True},
        {"name": "t2", "rangelow": 0, "rangehigh": 10, "selected": False, "dropna": False},
    ]
    data["filters"]["series_filters"] = [{"x": 1}]
    data["filters"]["use"] = True
    data["tools"]["Filter"] = {
        "config": {
            "range_filters": {"t3": {"high": 2}, "t1": {"high": 9}},
            "category_filters": {"FOV": ["1"]},
        }
    }
    changes = Changes()
    migrated = migrate(data, changes)
    config = migrated["tools"]["Filter"]["config"]
    assert "filters" not in config and set(config) >= {"features", "categories", "other"}
    settings = AppSettings.model_validate(migrated)
    # 0.6's Filter Data switched the range filters only
    assert settings.filters.features.enabled and not settings.filters.categories.enabled
    assert "use" not in settings.filters.model_dump()
    filter_config = settings.tools.config(tools.get("Filter"))
    assert filter_config.features.filters == [
        RangeFilterNode(column="t1", low=0),  # clipped by allowedmin, as 0.6 did
        RangeFilterNode(column="t2", low=0, high=10, dropna=False, enabled=False),
        RangeFilterNode(column="t3", high=2, enabled=False),  # the tool's own: off
    ]
    # a second range on t1: kept, in the other filters
    assert filter_config.other.filters == [RangeFilterNode(column="t1", high=9, enabled=False)]
    (category,) = filter_config.categories.filters
    assert (category.column, category.keep, category.enabled) == ("FOV", ["1"], False)
    assert "the Filter tool's own 3 filter(s): added switched off" in changes.converted
    assert "filters.use to filters.features.enabled (Filter Features)" in changes.converted
    assert "filters.series_filters (never used)" in changes.dropped


def test_import_of_version_1_is_dropped_for_a_workflow_file():
    data = json.loads(V1_FILE.read_text())
    data["import"]["filename_parser"] = {"parser": "fov_treatment_cell_parser"}
    changes = Changes()
    settings = AppSettings.model_validate(migrate(data, changes))
    assert "import" not in settings.to_json() and "Import" not in settings.to_json()["tools"]
    (dropped,) = [d for d in changes.dropped if d.startswith("import")]
    assert "fov_treatment_cell_parser" in dropped and "workflow file" in dropped


def test_order_category_values_keeps_its_former_name(tmp_path):
    from flim.configs import CategoryOrderConfig
    from flim.core.settings import AppSettings, load_settings, save_settings
    from flim.core.workflowfile import validate_workflow_file

    tool = tools.get("Order Categories")  # e.g. flimbatch --run "Order Categories"
    assert tool is tools.get("Order Category Values")
    # settings saved under the former name are read by the renamed tool
    path = tmp_path / "app.json"
    data = AppSettings.default().to_json()
    data["tools"]["Order Categories"] = tool_settings(
        CategoryOrderConfig(categories={"Treatment": ["b", "a"]})
    ).model_dump(mode="json")
    path.write_text(json.dumps(data))
    assert load_settings(path).tools.config(tool).categories == {"Treatment": ["b", "a"]}
    # a workflow file step that names the former name
    wf = tmp_path / "wf.json"
    wf.write_text(json.dumps({"schema_version": 1, "name": "old", "steps": [{"id": "1", "tool": "Order Categories"}]}))
    result = validate_workflow_file(wf)
    assert result.errors == [] and result.definition.steps[0].tool in ("Order Categories", "Order Category Values")


def test_presets_by_tool_and_the_preset_keys_of_development_builds():
    from flim.core.settings import Changes, migrate

    calc = {"kind": "expression", "name": "t2", "expression": "t1 * 2"}
    separate = {"name": "Mine", "settings": {"column": "Source"}}
    data = {"schema_version": 2, "calculation_presets": [calc], "separate_presets": [separate]}
    changes = Changes()
    settings = AppSettings.model_validate(migrate(data, changes))
    assert settings.presets == {
        "Separate Categories": [separate],
        "Calculate": [{"name": "t2", "settings": {"calculations": [calc]}}],
    }
    assert "calculation_presets to presets.Calculate" in changes.converted
    assert "separate_presets to presets.Separate Categories" in changes.converted
    # read under a former name too (Order Categories is now Order Category Values)
    settings = AppSettings.model_validate({"schema_version": 2, "presets": {"Order Categories": [separate]}})
    assert settings.tool_presets(tools.get("Order Category Values")) == [separate]
    assert settings.tool_presets(tools.get("Sort")) == []


def test_export_leaves_out_unknown_keys_and_migration_drops_development_keys(tmp_path):
    import json

    from flim.core.settings import Changes, migrate, settings_from_data
    from flim.core.settingsmgr import SettingsManager

    data = {"schema_version": 2, "import_workflow": "Import", "newer_setting": 1,
            "filters": {"use": True, "newer_switch": 2}}
    changes = Changes()
    migrated = migrate(data, changes)
    assert "import_workflow" not in migrated and "newer_setting" in migrated
    assert changes.converted == [] and changes.dropped == []  # never released: no record
    manager = SettingsManager(base=settings_from_data(migrated))
    path = tmp_path / "exported.json"
    manager.export(path)
    exported = json.loads(path.read_text())
    assert "newer_setting" not in exported and "newer_switch" not in exported["filters"]
    # `use` of a development build: written as both switches
    assert "use" not in exported["filters"]
    assert exported["filters"]["features"] == {"enabled": True}
    assert exported["filters"]["categories"] == {"enabled": True}


def test_validate_app_settings_refuses_tool_and_workflow_files(tmp_path):
    from flim.core.settings import validate_app_settings

    tool_file = tmp_path / "tool.json"
    tool_file.write_text(json.dumps({"schema_version": 2, "tool": "Summarize", "config": {}}))
    validation = validate_app_settings(tool_file)
    assert validation.error.startswith("a tool file (the settings of Summarize), not an app settings")
    assert validation.sections == {}
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({"name": "w", "steps": [{"id": "1", "tool": "Sort"}]}))
    assert validate_app_settings(workflow).error.startswith("a workflow file, not an app settings")
    app = tmp_path / "app.json"
    app.write_text(json.dumps({"schema_version": 2, "strict": True}))
    assert validate_app_settings(app).error is None


def test_the_removed_app_setting_strict_is_dropped_not_unknown(tmp_path):
    """0.7 development builds wrote `strict` into app settings files."""
    from flim.core.settings import validate_settings_file

    path = tmp_path / "lab.json"
    path.write_text('{"schema_version": 2, "strict": true}')
    validation = validate_settings_file(path)
    assert not validation.problems and "strict" not in validation.sections
    assert validation.dropped == ["strict (now processing.strict of tool and workflow files)"]


def test_the_removed_app_setting_cache_is_dropped_not_unknown(tmp_path):
    """0.7 development builds wrote `cache` into app and user settings files."""
    from flim.core.settings import validate_settings_file

    section = {"dir": None, "max_size_mb": 2048, "max_age_days": 7}
    path = tmp_path / "lab.json"
    path.write_text(json.dumps({"schema_version": 2, "cache": section, "results_dir": "/out"}))
    validation = validate_settings_file(path)
    assert not validation.problems and not validation.unknown
    assert "cache" not in validation.sections and validation.sections["results_dir"] == "/out"
    assert validation.dropped == ["cache (never used)"]


def test_update_settings_file_keeps_the_original(tmp_path):
    import shutil
    from pathlib import Path

    from flim.core.settings import SETTINGS_VERSION, update_settings_file, validate_settings_file

    data = Path(__file__).parent / "data" / "settings_v1.json"
    path = tmp_path / "lab.json"
    shutil.copy(data, path)
    backup = update_settings_file(path)
    assert backup == tmp_path / "lab.v1.json" and backup.read_text() == data.read_text()
    updated = validate_settings_file(path)
    assert updated.version == SETTINGS_VERSION and not updated.problems
    with pytest.raises(ValueError, match="already in the current format"):
        update_settings_file(path)
    shutil.copy(data, path)
    assert update_settings_file(path) == tmp_path / "lab.v1_2.json"  # the first copy is kept
    mixed = tmp_path / "mixed.json"
    mixed.write_text(json.dumps({"schema_version": 1, "bogus": 1}))
    with pytest.raises(ValueError, match="bogus"):
        update_settings_file(mixed)  # settings that can't be used: not rewritten


def test_update_keeps_a_tool_file_a_tool_file(tmp_path):
    from flim.core.settings import update_settings_file

    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"schema_version": 1, "tool": "Summarize", "config": {"aggs": ["mean"]}}))
    update_settings_file(path)
    data = json.loads(path.read_text())
    assert data["tool"] == "Summarize" and data["schema_version"] == 2 and "tools" not in data


def test_every_app_settings_section_has_a_merge_rule():
    """A new section must state how a later layer changes it (presets were hidden
    by an app settings file's presets while all sections but tools were replaced)."""
    from flim.core.settings import SECTION_MERGE, AppSettings

    assert set(SECTION_MERGE) == set(AppSettings.model_fields) - {"schema_version"}
    assert set(SECTION_MERGE.values()) == {"whole", "per key"}


def test_sections_merge_whole_or_per_key():
    from flim.core.settings import merge_sections

    base = {
        "log": {"dir": "logs", "max_age_days": 10},
        "max_windows": {"table": 50, "plot": 20},
        "presets": {"Calculate": [{"name": "mine"}]},
        "execution": {"executor": "dask-local", "workers": 8},
        "char_replacements": {"/": "_", ":": "-"},
    }
    changes = {
        "schema_version": 2,
        "log": {"dir": "lab"},
        "max_windows": {"plot": 5},
        "presets": {"Filter": [{"name": "lab"}]},
        "execution": {"executor": "local"},
        "char_replacements": {"/": "-"},
    }
    merged = merge_sections(base, changes)
    assert merged["log"] == {"dir": "lab", "max_age_days": 10}  # per field
    assert merged["max_windows"] == {"table": 50, "plot": 5}  # per kind
    assert set(merged["presets"]) == {"Calculate", "Filter"}  # per tool
    assert merged["execution"] == {"executor": "local"}  # whole: one executor
    assert merged["char_replacements"] == {"/": "-"}  # whole: one table


@pytest.mark.parametrize("writer", ["save_settings", "save_sections", "export", "write_tool_settings"])
def test_a_settings_file_is_replaced_in_one_step(tmp_path, monkeypatch, writer):
    """If writing fails, the file is left as it was, and no temporary file is left."""
    import flim.core.settings as settings_module
    from flim.core.settings import save_sections, write_tool_settings
    from flim.core.settingsmgr import SettingsManager

    path = tmp_path / "lab.json"
    original = json.dumps({"schema_version": 2, "server_timeout": 9})
    path.write_text(original)
    path.chmod(0o640)

    def failing_dump(data, f, **kwargs):
        f.write('{"schema_version": ')  # a part, then the failure
        raise OSError("disk full")

    real_dump = json.dump
    monkeypatch.setattr(settings_module.json, "dump", failing_dump)
    calls = {
        "save_settings": lambda: save_settings(AppSettings.default(), path),
        "save_sections": lambda: save_sections({"server_timeout": 5}, path),
        "export": lambda: SettingsManager().export(path),
        "write_tool_settings": lambda: write_tool_settings(
            path, tools.get("Summarize"), tool_settings(SummaryConfig())
        ),
    }
    with pytest.raises(OSError, match="disk full"):
        calls[writer]()
    assert path.read_text() == original
    assert [p.name for p in tmp_path.iterdir()] == ["lab.json"]
    monkeypatch.setattr(settings_module.json, "dump", real_dump)
    calls[writer]()  # written, with the permissions of the file it replaces
    assert json.loads(path.read_text())["schema_version"] == 2
    assert path.stat().st_mode & 0o777 == 0o640
