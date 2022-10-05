<<<<<<< HEAD
__version__ = "0.3.0"
=======
__version__ = "0.4.1"

import os
import flim.plugin
import prefect

# os.environ["PREFECT__FLOWS__CHECKPOINTING"] = "true"
prefect.config.flows.checkpointing = True
>>>>>>> prefect
