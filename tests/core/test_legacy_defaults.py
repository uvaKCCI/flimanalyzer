"""The config models against the default parameters of the 0.5 plugins.

data/legacy_defaults.json holds those defaults, taken from the plugin classes
before they were removed (Phase 8); 0.5 settings files store them in this form.
"""

import json
from pathlib import Path

import pytest

import flim.workflow  # noqa: F401  (registers the workflows)
from flim.configs import LEGACY_TOOL_CONFIGS
from flim.core.registry import tools

PLUGIN_DEFAULTS = json.loads(
    (Path(__file__).parent / "data" / "legacy_defaults.json").read_text()
)

# legacy defaults the configs change on purpose
CHANGED_DEFAULTS = {
    "Merge": {"how": "inner"},  # "" fails in pandas
    "Frequency Histogram": {"featuresettings": {}},  # list entries were never read
}


def test_every_plugin_and_workflow_has_a_config():
    workflows = {cls.name for cls in tools.by_category()["Workflow"]}
    assert set(PLUGIN_DEFAULTS) | workflows == set(LEGACY_TOOL_CONFIGS)


# the workflows are no plugins any more (test_tool_configs.py loads their old settings)
@pytest.mark.parametrize("name", sorted(PLUGIN_DEFAULTS))
def test_defaults_match_the_plugin(name):
    config_class = LEGACY_TOOL_CONFIGS[name]
    expected = dict(PLUGIN_DEFAULTS[name])
    for key in config_class.legacy_dropped:
        expected.pop(key, None)
    expected.update(CHANGED_DEFAULTS.get(name, {}))
    assert json.loads(json.dumps(config_class().to_legacy_params())) == expected


@pytest.mark.parametrize("name", sorted(PLUGIN_DEFAULTS))
def test_plugin_defaults_load(name):
    config_class = LEGACY_TOOL_CONFIGS[name]
    assert config_class.from_legacy_params(PLUGIN_DEFAULTS[name]) == config_class()
