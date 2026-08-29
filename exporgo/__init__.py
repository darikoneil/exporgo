"""exporgo — experiment organization, logging, and analysis monitoring.

The successor to the original ``exporgo``. This version is layered:

- **logging** (base install): a reusable :mod:`loguru`-based logging framework.
- **study** (base install): the Study & Identity model — a study's identity
  coordinate system (1-3 keys, default ``Subject``), the resources it expects at each
  identity, and file-existence self-validation.
- **datastore** (``exporgo[datastore]``): fast, schema-enforced polars/Parquet
  component stores for a study's bulk data, Hive-partitioned on the identity keys.
- **monitoring** (``exporgo[monitor]``): progress *derived* from the filesystem,
  rendered into an agent-readable map (planned).

Logging is disabled on import so that using ``exporgo`` (or a project built on it) as a
library emits nothing until :func:`exporgo.log.init_logger` is called.
"""

import importlib.metadata

from loguru import logger

# Silent by default: importing exporgo as a library should not emit log records into a
# host application. Call exporgo.log.init_logger to enable and configure logging.
logger.disable("exporgo")

# Source the version from the installed distribution metadata (pyproject.toml), so it
# cannot drift from the packaged version.
__version__ = importlib.metadata.version("exporgo")
