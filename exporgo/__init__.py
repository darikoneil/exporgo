"""exporgo — experiment organization, logging, and analysis monitoring.

The successor to the original ``exporgo``. This version is layered:

- **logging** (base install): a reusable :mod:`loguru`-based logging framework.
- **organization / monitoring** (``exporgo[monitor]``): a study/subject model,
  file-existence self-validation, and derived progress tracking rendered into an
  agent-readable map (added in later steps).

Only the logging layer is present so far. Logging is disabled on import so that using
``exporgo`` (or a project built on it) as a library emits nothing until
:func:`exporgo.log.init_logger` is called.
"""

from loguru import logger

# Silent by default: importing exporgo as a library should not emit log records into a
# host application. Call exporgo.log.init_logger to enable and configure logging.
logger.disable("exporgo")

__version__ = "2.0.0"
