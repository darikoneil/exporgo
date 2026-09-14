# Configure logging

exporgo's logging layer is the base install: a {mod}`loguru`-based framework any project can
drive, whether or not you use the experiment or datastore layers. This guide covers turning it on,
the logging an experiment gets for free, and the call-logging decorators.

## Turn logging on

exporgo disables its own logging on import, so using it as a library emits nothing until you ask.
{func}`~exporgo.log.init_logger` turns it on:

```python
from pathlib import Path

from exporgo.log import LogLevel, init_logger

init_logger(
    name="my_project",
    base_directory=Path("logs"),
    log_level_console=LogLevel.DEBUG,
)
```

That attaches a colorized console sink and, because `base_directory` is set, two rotating file
sinks — one for `INFO`/`WARNING` records and one for exceptions (with backtraces). The file stem
defaults to `name`; override it with `file_stem=...`. Pass `name=None` to enable *every* logger
namespace, not just your project's.

Each writer logs into its **own** directory, `logs/.logs/<host>_<user>_<pid>/`, rather than a
shared file: `my_project.log` (INFO/WARNING) and `my_project.exception.log`. So two processes —
or two people on a lab server — never write the same file, and there's no interleaving, rotation
race, or permission clash. {func}`~exporgo.log.read_log` merges them back into one timeline (see
[Storage and concurrency](../explanation/storage-and-concurrency)).

`init_logger` clears existing sinks first, so it's safe to call more than once — each call
reconfigures logging cleanly.

```{note}
Passing `log_level_custom` without a `base_directory` has nowhere to write, so it issues a
`UserWarning` and adds no sink. Give it a `base_directory` to get the extra threshold file.
```

## Levels

{class}`~exporgo.log.LogLevel` is an `IntEnum` whose values line up with the standard library's
where they overlap, plus loguru's `TRACE` (5) and `SUCCESS` (25):

```text
NOTSET=0  TRACE=5  DEBUG=10  INFO=20  SUCCESS=25  WARNING=30  ERROR=40  CRITICAL=50
```

Because the members are integers, they compare directly against the numeric levels used by both
{mod}`logging` and {mod}`loguru`.

## An experiment logs for free

You rarely call `init_logger` yourself when working with an experiment.
{meth}`~exporgo.experiment.Experiment.save` wires logging into the experiment automatically, so a saved experiment
gets a per-writer log under `<root>/.logs/`: the first save records a "created" line, later saves
a "saved" line. To start logging into an experiment *before* the first save (for instance after
{meth}`~exporgo.experiment.Experiment.load`, which is deliberately silent), call
{meth}`~exporgo.experiment.Experiment.init_logging` yourself:

```python
experiment = Experiment.load(root)
experiment.init_logging()   # resume logging into this experiment
```

## Read an experiment's log

Because each writer keeps its own file, read the log through
{meth}`~exporgo.experiment.Experiment.read_log`, which merges every writer's records into one chronological
string:

```python
print(experiment.read_log())                # the merged INFO/WARNING timeline
print(experiment.read_log(exceptions=True))  # merged exceptions instead
```

Records sort by a fixed-width UTC timestamp, so logs written on different machines in different
timezones still interleave correctly.

## Log function calls

Three decorators record what your code does. {func}`~exporgo.log.log_function_call` logs a
function's arguments and return value at a single level:

```python
from exporgo.log import log_function_call

@log_function_call()
def add(left, right):
    return left + right
```

{func}`~exporgo.log.log_major_function_call` additionally records wall-clock duration, meant for
pipeline-level entry points, where the call and its timing are worth a more visible level than
the (often verbose) arguments:

```python
from exporgo.log import log_major_function_call

@log_major_function_call()
def run_stage(config):
    ...
```

And {func}`~exporgo.log.log_class` logs an object's class name and string form — handy for
recording a resolved config or parameters object at the start of a stage. All three attribute
their records to the caller and preserve the wrapped function's signature and metadata.

```{tip}
For progress bars and logs to coexist, {func}`~exporgo.log.reset_tqdm` adds a `tqdm`-compatible
sink. It needs the optional `tqdm` dependency and raises a clear `ImportError` without it.
```
