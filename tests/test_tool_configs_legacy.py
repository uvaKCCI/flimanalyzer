"""The config models against the current plugins' default parameters."""

import pytest

from flim.configs import LEGACY_TOOL_CONFIGS
from flim.core.config import LEGACY_IGNORED
import flim.workflow  # noqa: F401  (registers the workflows)
from flim.core.registry import tools
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


def test_every_plugin_and_workflow_has_a_config():
    workflows = {cls.name for cls in tools.by_category()["Workflow"]}
    assert set(PLUGIN_CLASSES) | workflows == set(LEGACY_TOOL_CONFIGS)


# the workflows are no plugins any more (tests/core/test_tool_configs.py loads their
# old settings)
@pytest.mark.parametrize("name", sorted(PLUGIN_CLASSES))
def test_defaults_match_the_plugin(name):
    config_class = LEGACY_TOOL_CONFIGS[name]
    expected = plugin_defaults(name)
    for key in config_class.legacy_dropped:
        expected.pop(key, None)
    expected.update(CHANGED_DEFAULTS.get(name, {}))
    assert config_class().to_legacy_params() == expected


@pytest.mark.parametrize("name", sorted(PLUGIN_CLASSES))
def test_plugin_defaults_load(name):
    config_class = LEGACY_TOOL_CONFIGS[name]
    assert config_class.from_legacy_params(plugin_defaults(name)) == config_class()
