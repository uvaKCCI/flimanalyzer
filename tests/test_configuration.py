import json

import flim.core.configuration as cfg
from flim.core.configuration import Config


def _default():
    config = Config()
    config.create_default()
    return config


def test_default_configuration_is_valid():
    config = _default()
    assert config.validate() == ([], [])
    assert config.is_valid()


def test_round_trip_through_json(tmp_path):
    config = _default()
    config.update({"working_dir": "/data/results"})
    path = tmp_path / "config.json"
    config.write_to_json(str(path))
    assert not config.is_modified() and config.filename == str(path)

    loaded = Config()
    assert loaded.read_from_json(str(path))
    assert loaded.get() == config.get()
    assert not loaded.is_modified()


def test_partial_file_can_be_fixed(tmp_path):
    # loading settings: missing keys are reported and fix() fills them in (the app
    # offers this), keeping the values from the file
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({cfg.CONFIG_ROOT: {cfg.CONFIG_IMPORT: {cfg.CONFIG_DELIMITER: ";"}}}))
    config = Config()
    assert config.read_from_json(str(path))
    missing, invalid = config.validate()
    assert missing and not config.is_valid()
    assert config.fix()
    assert config.is_valid()
    assert config.get([cfg.CONFIG_DELIMITER]) == ";"


def test_missing_file_falls_back_to_defaults(tmp_path):
    config = Config()
    assert not config.read_from_json(str(tmp_path / "missing.json"))
    assert config.is_valid() and config.filename is None

    config = Config()
    assert not config.read_from_json(str(tmp_path / "missing.json"), defaultonfail=False)
    assert config.get() == {}


def test_save_one_tools_settings(tmp_path):
    # "Save configuration" in a tool's dialog writes only that tool's settings
    config = _default()
    keys = [cfg.CONFIG_PLUGINS, "Summarize"]
    config.update(
        {"aggs": ["count", "mean"], "working_dir": "/data", "bins": [1, 2.5], "flag": True},
        keys,
    )
    path = tmp_path / "summarize.json"
    config.write_to_json(str(path), searchkey=keys)
    saved = json.loads(path.read_text())
    settings = saved["Summarize"]
    mine = {k: settings[k] for k in ("aggs", "working_dir", "bins", "flag")}
    assert mine == {"aggs": ["count", "mean"], "working_dir": "/data", "bins": [1, 2.5], "flag": True}


def test_values_json_cannot_represent_are_saved_as_text(tmp_path):
    config = _default()
    config.update({"path": tmp_path}, [cfg.CONFIG_PLUGINS, "Tool"])
    path = tmp_path / "tool.json"
    config.write_to_json(str(path), searchkey=[cfg.CONFIG_PLUGINS, "Tool"])
    assert json.loads(path.read_text()) == {"Tool": {"path": str(tmp_path)}}


def test_update_get_and_remove():
    config = Config()
    updated, notfound = config.update({"a": 1}, ["x", "y"])
    assert updated == {"a": 1} and notfound == {}
    assert config.get(["x", "y", "a"]) == 1
    assert config.get_parent(["x", "y", "a"]) == {"a": 1}
    assert config.is_modified()

    updated, notfound = config.update({"b": 2}, ["nope"], addmissing=False)
    assert updated == {} and notfound == {"b": 2}

    assert config.remove(["x", "y", "a"])
    assert config.get(["x", "y", "a"]) is None
    assert not config.remove(["does", "not", "exist"])


def test_keys():
    config = Config()
    config.update({"a": 1, "b": {"c": 2}}, ["root"])
    keys = config.get_keys()
    assert ["root"] in keys and ["root", "a"] in keys and ["root", "b", "c"] in keys
    assert ("root", "b") in config.get_nodekeys()


def test_fix_restores_missing_and_invalid_keys():
    config = _default()
    delimiter_key = (cfg.CONFIG_ROOT, cfg.CONFIG_IMPORT, cfg.CONFIG_DELIMITER)
    rangefilters_key = (cfg.CONFIG_ROOT, cfg.CONFIG_FILTERS, cfg.CONFIG_RANGEFILTERS)
    config.remove(list(delimiter_key))
    config.update({cfg.CONFIG_RANGEFILTERS: None}, list(rangefilters_key[:-1]))
    missing, invalid = config.validate()
    assert delimiter_key in missing and rangefilters_key in invalid
    assert not config.is_valid()

    assert config.fix()
    assert config.is_valid()
    assert config.get(list(delimiter_key)) == _default().get(list(delimiter_key))
