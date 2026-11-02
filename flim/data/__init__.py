# The tool modules here import flim.plugin, which imports all tool modules to register
# them. Loading flim.plugin first means no tool module is imported half-initialized.
import flim.plugin  # noqa: F401
