"""The config models against the current plugins' default parameters."""

import pytest

from flim.configs import LEGACY_TOOL_CONFIGS
from flim.core.config import LEGACY_IGNORED
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.plugin import PLUGINS, create_instance

PLUGIN_CLASSES = {
    name: cls for group in PLUGINS.values() for name, cls in group.items()
}

# legacy defaults the configs change on purpose
CHANGED_DEFAULTS = {
    "Merge": {"how": "inner"},  # "" fails in pandas
    "Frequency Histogram": {"featuresettings": {}},  # list entries were never read
}


def plugin_defaults(name):
    params = create_instance(PLUGIN_CLASSES[name]).get_default_parameters()
    return {k: v for k, v in params.items() if k not in LEGACY_IGNORED}


def test_every_plugin_has_a_config():
    assert set(PLUGIN_CLASSES) == set(LEGACY_TOOL_CONFIGS)


@pytest.mark.parametrize("name", sorted(LEGACY_TOOL_CONFIGS))
def test_defaults_match_the_plugin(name):
    config_class = LEGACY_TOOL_CONFIGS[name]
    expected = plugin_defaults(name)
    for key in config_class.legacy_dropped:
        expected.pop(key, None)
    expected.update(CHANGED_DEFAULTS.get(name, {}))
    assert config_class().to_legacy_params() == expected


@pytest.mark.parametrize("name", sorted(LEGACY_TOOL_CONFIGS))
def test_plugin_defaults_load(name):
    config_class = LEGACY_TOOL_CONFIGS[name]
    assert config_class.from_legacy_params(plugin_defaults(name)) == config_class()
