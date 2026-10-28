# The workflow modules import flim.plugin, which imports the tool plugin modules.
# Loading flim.plugin first means no module is imported half-initialized; importing
# the workflow modules registers the workflows.
import flim.plugin  # noqa: F401
from flim.plugin import discover_plugin_classes

discover_plugin_classes(["workflow"])
