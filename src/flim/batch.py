"""Deprecated: the flimbatch command is `flim.batchcmd`, its run logic `flim.core.batchrun`.

Deprecated in 0.7.0, removed in 0.8.0. The names of this module are imported from
their new modules.
"""

import warnings

from flim.batchcmd import main  # noqa: F401
from flim.core.batchrun import (  # noqa: F401
    BatchError,
    validate_run,
    file_run,
    ignored_settings,
    read_settings,
    resolve_run,
    run_on_tables,
    tool_workflow,
)

warnings.warn(
    "flim.batch is deprecated and is removed in 0.8.0; use flim.core.batchrun (the"
    " run functions) or flim.batchcmd (the flimbatch command)",
    DeprecationWarning,
    stacklevel=2,
)
