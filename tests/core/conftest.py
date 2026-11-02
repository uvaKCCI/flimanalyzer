# Register the built-in tools before the test modules create configs: a config names
# its tool (classname) when it is created, as in the application, which imports the
# tools at startup.
import flim.tools  # noqa: F401
