__version__ = "0.4.0"

import os
import flim.plugin
import prefect

#os.environ["PREFECT__FLOWS__CHECKPOINTING"] = "true"
prefect.config.flows.checkpointing = True
