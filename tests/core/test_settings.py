"""Versioned application settings (flim.core.settings)."""

import json
import logging
from pathlib import Path

import pytest

import flim.workflow  # noqa: F401  (registers the workflows)
from flim.configs import ConcatConfig, KMeansConfig, SummaryConfig
from flim.configs.workflow import BasicFLIRRConfig
from flim.core.registry import tools
from flim.core.settings import (
    SETTINGS_VERSION,
    AppSettings,
    ToolEntry,
    load_settings,
    migrate,
    read_tool_entry,
    save_settings,
    settings_from_data,
    tool_entry,
    update_settings,
    write_tool_entry,
)

# saved by FLIMAnalyzer 0.5 (the dict Config, version 0), with some changed settings
V0_FILE = Path(__file__).parent / "data" / "settings_v0.json"
# version 1: the tools under {"tools": {"tools": {...}}}
V1_FILE = Path(__file__).parent / "data" / "settings_v1.json"


def test_defaults():
    settings = AppSettings.default()
    assert settings.schema_version == SETTINGS_VERSION
    assert settings.import_.delimiter == "\t,"
    assert settings.import_.filename_parser.parser == "defaultparser"
    assert len(settings.filters.range_filters) == 39 and settings.display
    assert settings.preprocess.rename["Exc2_-Ch3-_"] == "FAD "
    assert settings.filters.range_filters[0]["name"] == "trp t1"
    assert settings.tool_settings.tools == {}  # the tools' defaults: their configs'


def test_settings_of_version_0(caplog):
    with caplog.at_level(logging.WARNING):
        settings = load_settings(V0_FILE)
    assert not caplog.records  # every key known
    assert settings.schema_version == SETTINGS_VERSION
    assert settings.working_dir == "/data/results"
    assert settings.import_.delimiter == "\t"
    assert settings.filters.use is False and settings.filters.show_dropped is True
    store = settings.tool_settings
    summary = store.config(tools.get("Summarize"))
    assert isinstance(summary, SummaryConfig)
    assert (summary.aggs, summary.grouping) == (["mean", "sem"], ["Treatment"])
    assert store.config(tools.get("K-Means")).n_clusters == 4
    # saved under the plugin's name, read by the renamed tool
    assert store.config(tools.get("Concatenate")).mode == "horizontal"
    assert isinstance(store.config(tools.get("Basic FLIRR Analysis")), BasicFLIRRConfig)
    assert all(e.legacy is None for e in store.tools.values())  # all converted


def test_saved_in_the_current_version_and_read_back(tmp_path):
    settings = load_settings(V0_FILE)
    settings.tool_settings.set(
        tools.get("K-Means"), KMeansConfig(n_clusters=7), True, "/r"
    )
    path = tmp_path / "settings.json"
    save_settings(settings, path)
    data = json.loads(path.read_text())
    assert data["schema_version"] == SETTINGS_VERSION and "root" not in data
    again = load_settings(path)
    assert again == settings
    entry = again.tool_settings.entry(tools.get("K-Means"))
    assert (entry.autosave, entry.results_dir) == (True, "/r")
    assert again.tool_settings.config(tools.get("K-Means")).n_clusters == 7


def test_unknown_keys_are_reported_not_fatal(caplog):
    data = {"schema_version": SETTINGS_VERSION, "colour": "red", "import": {"x": 1}}
    with caplog.at_level(logging.WARNING):
        settings = settings_from_data(data)
    assert "colour" in caplog.text and "import_.x" in caplog.text
    assert settings.import_.delimiter == "\t,"


def test_newer_versions_are_refused():
    with pytest.raises(ValueError, match="newer than this FLIMAnalyzer"):
        migrate({"schema_version": SETTINGS_VERSION + 1})


def test_invalid_tool_settings_give_the_defaults(caplog):
    settings = AppSettings()
    settings.tool_settings.tools["Concatenate"] = ToolEntry(config={"mode": "diagonal"})
    settings = AppSettings.model_validate(settings.to_json())
    with caplog.at_level(logging.WARNING):
        assert settings.tool_settings.config(tools.get("Concatenate")) == ConcatConfig()
    assert "not valid" in caplog.text


def test_settings_from_the_importer_and_preprocessor(tmp_path):
    from flim.core.importer import dataimporter
    from flim.core.parser import treatment_fov_cell_parser
    from flim.core.preprocessor import defaultpreprocessor

    importer = dataimporter()
    importer.set_delimiter(";")
    importer.set_parser(treatment_fov_cell_parser())
    data_file = tmp_path / "a.txt"
    data_file.write_text("x\n1\n")
    importer.set_files([str(data_file)])
    imported = importer.settings()
    assert (imported.delimiter, imported.include_files) == (";", [str(data_file)])
    # the parser's own name (was "defaultparser" for every parser)
    assert imported.filename_parser.parser == "treatment_fov_cell_parser"
    assert imported.filename_parser.patterns[0]["Category"] == "Treatment"
    preprocessor = defaultpreprocessor()
    preprocessor.set_dropcolumns(["x"])
    assert preprocessor.settings().drop == ["x"]


def test_settings_of_version_1():
    settings = load_settings(V1_FILE)
    entry = settings.tool_settings.entry(tools.get("Summarize"))
    assert (entry.autosave, entry.results_dir) == (True, "results")
    assert settings.tool_settings.config(tools.get("K-Means")).n_clusters == 7
    assert set(settings.to_json()["tools"]) == {"Summarize", "K-Means"}  # by tool


def test_a_file_with_some_sections_changes_only_those():
    settings = AppSettings.default()
    settings.tool_settings.set(tools.get("K-Means"), KMeansConfig(n_clusters=3))
    data = {
        "schema_version": SETTINGS_VERSION,
        "filters": {"use": True},
        "tools": {"Summarize": {"config": SummaryConfig(aggs=["max"]).model_dump()}},
    }
    updated = update_settings(settings, data)
    assert updated.filters.use and updated.filters.range_filters == []  # replaced
    assert updated.import_ == settings.import_  # not in the file: kept
    assert updated.tool_settings.config(tools.get("K-Means")).n_clusters == 3
    assert updated.tool_settings.config(tools.get("Summarize")).aggs == ["max"]


def test_a_tool_section_in_a_settings_file(tmp_path):
    kmeans = tools.get("K-Means")
    path = tmp_path / "settings.json"
    write_tool_entry(path, kmeans, tool_entry(KMeansConfig(n_clusters=5), True, "/r"))
    data = json.loads(path.read_text())
    assert data["schema_version"] == SETTINGS_VERSION
    assert list(data["tools"]) == ["K-Means"]  # only the tool's section
    assert read_tool_entry(path, kmeans).results_dir == "/r"
    assert read_tool_entry(path, tools.get("Summarize")) is None

    # in an application settings file (of an older version): the rest is kept
    path = tmp_path / "app.json"
    path.write_text(V0_FILE.read_text())
    write_tool_entry(path, kmeans, tool_entry(KMeansConfig(n_clusters=9)))
    settings = load_settings(path)
    assert settings.tool_settings.config(kmeans).n_clusters == 9
    assert settings.import_.delimiter == "\t"  # from the version 0 file
    summary = settings.tool_settings.config(tools.get("Summarize"))
    assert summary.aggs == ["mean", "sem"]
    # saved under a former name: replaced, read by the renamed tool
    concat = tools.get("Concatenate")
    assert read_tool_entry(V0_FILE, concat).config["mode"] == "horizontal"
    write_tool_entry(path, concat, tool_entry(ConcatConfig()))
    names = json.loads(path.read_text())["tools"]
    assert "Concatenate" in names and not set(concat.former_names) & set(names)

    # a config alone
    path = tmp_path / "config.json"
    path.write_text(json.dumps(KMeansConfig(n_clusters=4).model_dump(mode="json")))
    assert read_tool_entry(path, kmeans).config["n_clusters"] == 4
    with pytest.raises(ValueError, match="not a settings file"):
        write_tool_entry(path, kmeans, tool_entry(KMeansConfig()))
