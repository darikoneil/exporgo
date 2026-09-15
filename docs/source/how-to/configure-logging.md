# Configure logging

exporgo's logging layer is the base install: a `loguru`-based framework any project can
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
sinks: one for `INFO`/`WARNING` records and one for exceptions (with backtraces). The file stem
defaults to `name`; override it with `file_stem=...`. Pass `name=None` to enable *every* logger
namespace, not just your project's.

Each writer logs into its **own** directory, `logs/.logs/<host>_<user>_<pid>/`, rather than a
shared file: `my_project.log` (INFO/WARNING) and `my_project.exception.log`. So two processes, or
two people on a lab server, never write the same file, and there's no interleaving, rotation
race, or permission clash. {func}`~exporgo.log.read_log` merges them back into one timeline (see
[Read an experiment's log](#read-an-experiments-log)).

`init_logger` clears existing sinks first, so it's safe to call more than once: each call
reconfigures logging cleanly.

Passing `log_level_custom` without a `base_directory` has nowhere to write, so it issues a
`UserWarning` and adds no sink. Give it a `base_directory` to get the extra threshold file.

## Levels

{class}`~exporgo.log.LogLevel` is an `IntEnum` whose values line up with the standard library's
where they overlap, plus loguru's `TRACE` (5) and `SUCCESS` (25):

```text
NOTSET=0  TRACE=5  DEBUG=10  INFO=20  SUCCESS=25  WARNING=30  ERROR=40  CRITICAL=50
```

Because the members are integers, they compare directly against the numeric levels used by both
{mod}`logging` and `loguru`.

## An experiment logs for free

You rarely call `init_logger` yourself when working with an experiment.
{meth}`~exporgo.experiment.Experiment.save` wires logging into the experiment automatically, so a saved experiment
gets a per-writer log under `<root>/.logs/`: the first save records a "created" line, later saves
a "saved" line. That convenience reconfigures the process-global logger, which is worth reading
about before you embed exporgo in a larger application. See
[Save without touching the global logger](#save-without-touching-the-global-logger) below.

To start logging into an experiment *before* the first save (for instance after
{meth}`~exporgo.experiment.Experiment.load`, which is deliberately silent), call
{meth}`~exporgo.experiment.Experiment.init_logging` yourself:

```python
experiment = Experiment.load("D:/data/mouse_experiment")
experiment.init_logging()   # resume logging into this experiment
```

## Save without touching the global logger

The convenience above has a cost. Wiring logging into the experiment means calling
{meth}`~exporgo.experiment.Experiment.init_logging`, which drives
{func}`~exporgo.log.init_logger`, which begins with loguru's `logger.remove()`. loguru's `logger`
is **process-global**, so that call removes *every* sink in the process, including sinks your
application, your notebook, or an unrelated library added. A plain `experiment.save()` therefore
reconfigures logging for everything running alongside it.

That is the right default for a script or a session driven by exporgo. It is the wrong one when
exporgo is embedded in a host application that owns its own logging. Pass `init_logging=False`
and the save touches nothing but the files it writes:

```python
experiment.save(init_logging=False)   # write experiment.json; leave all loguru sinks alone
```

Everything else about the save is identical: `experiment.json`, `entities.jsonl`, and each store's
schema anchor are written either way, and the "created"/"saved" record is still emitted. It just
goes to whatever sinks are already attached, and nothing is written under `<root>/.logs/`.

To keep the host's sinks *and* get a log in the experiment root, save with `init_logging=False`
and add your own sink pointing at the experiment. Only {func}`~exporgo.log.init_logger` and
{meth}`~exporgo.experiment.Experiment.init_logging` clear existing sinks; `logger.add(...)` on its
own is additive.

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

Two decorators and one helper record what your code does. {func}`~exporgo.log.log_function_call`
logs a function's arguments and return value at a single level — `TRACE` by default, which the
default sinks filter out (the console shows `INFO` and up; the primary file keeps exactly `INFO`
and `WARNING`). Raise the level, or lower the console's, to see the records:

```python
from exporgo.log import LogLevel, log_function_call

@log_function_call(level=LogLevel.INFO)
def add(left, right):
    return left + right
```

{func}`~exporgo.log.log_major_function_call` additionally records wall-clock duration, meant for
pipeline-level entry points: the call and its timing land at `INFO`, the (often verbose)
arguments and return value at `DEBUG`:

```python
from exporgo.log import log_major_function_call

@log_major_function_call()
def run_stage(config):
    ...
```

Both decorators attribute their records to the caller and preserve the wrapped function's
signature and metadata. The helper, {func}`~exporgo.log.log_class`, is not a decorator: call it
directly with an object to log its class name and string form — handy for recording a resolved
config or parameters object at the start of a stage:

```python
from exporgo.log import log_class

log_class(config)   # logs "Config:\n<its __str__>" at DEBUG
```

For progress bars and logs to coexist, {func}`~exporgo.log.reset_tqdm` adds a `tqdm`-compatible
sink. It needs the optional `tqdm` dependency and raises a clear `ImportError` without it.
