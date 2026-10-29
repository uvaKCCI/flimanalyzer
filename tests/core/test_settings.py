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
    load_settings,
    migrate,
    save_settings,
    settings_from_data,
)

# saved by FLIMAnalyzer 0.5 (the dict Config, version 0), with some changed settings
V0_FILE = Path(__file__).parent / "data" / "settings_v0.json"


def test_defaults():
    settings = AppSettings.default()
    assert settings.schema_version == SETTINGS_VERSION
    assert settings.import_.delimiter == "\t,"
    assert settings.import_.filename_parser.parser == "defaultparser"
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
    settings.tool_settings.tools["Concatenate"] = {"config": {"mode": "diagonal"}}
    settings = AppSettings.model_validate(settings.to_json())
    with caplog.at_level(logging.WARNING):
        assert settings.tool_settings.config(tools.get("Concatenate")) == ConcatConfig()
    assert "not valid" in caplog.text


def test_settings_from_the_importer_and_preprocessor(tmp_path):
    from flim.core.importer import dataimporter
    from flim.core.preprocessor import defaultpreprocessor
    from flim.core.settings import import_settings, preprocess_settings

    importer = dataimporter()
    importer.set_delimiter(";")
    data_file = tmp_path / "a.txt"
    data_file.write_text("x\n1\n")
    importer.set_files([str(data_file)])
    imported = import_settings(importer.get_config())
    assert (imported.delimiter, imported.include_files) == (";", [str(data_file)])
    assert imported.filename_parser.parser == "defaultparser"
    preprocessor = defaultpreprocessor()
    preprocessor.set_dropcolumns(["x"])
    assert preprocess_settings(preprocessor.get_config()).drop == ["x"]
