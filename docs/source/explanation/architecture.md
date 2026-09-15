# Architecture

exporgo is built in layers, and you install only the ones you use. This page explains the
layers, the principle that shapes them, and how they depend on each other.

## Describe, validate, report — never execute

One principle runs through the whole framework: **exporgo describes, validates, and reports; it
never executes your analysis.** It tells you what data should exist, checks whether it does, and
reports the gaps. Running the processing between a raw file and a stored result is your code's
job, or an agent's. exporgo brackets the ends and stays out of the middle.

This is why status is always *derived* from the filesystem rather than kept in a mutable
ledger. There's no "mark this step done" to fall out of sync with reality: progress is read
from the existence of declared outputs, every time it's asked for.

## The layers

**logging**: the base layer, depending only on `loguru`. A reusable logging framework any
project can drive through {func}`~exporgo.log.init_logger`: a colorized console sink, rotating
file and exception sinks, and decorators that record calls, arguments, return values, and
timing. It's the foundation the other layers log through, and it's useful on its own.

**experiment**: also in the base install (it adds only `pydantic`). The Experiment & Identity model: the
coordinate system, the resources an experiment expects, and file-existence validation.
This is the shared foundation: the identity keys it defines become the datastore's partition
keys, and its validation seeds what a monitoring layer would report.

**datastore** (`exporgo[datastore]`): fast, schema-enforced polars/Parquet component stores
for bulk data, Hive-partitioned on the identity keys, with lazy, partition-pruned retrieval.
It adds the heavier analytical stack (`polars`, `pyarrow`, `numpy`, `xarray`), which is why
it's an opt-in extra rather than part of the base.

**monitoring** (`exporgo[monitor]`): progress *derived* from the filesystem and rendered into
an agent-readable map. Planned; not yet implemented.

## How the layers depend on each other

The dependency arrow points one way: experiment builds on logging, and datastore builds on experiment.
It doesn't point back — importing `exporgo.experiment` never pulls in the datastore layer. The
experiment module refers to store types only under `TYPE_CHECKING` and imports the real
datastore classes lazily, inside the methods that need them. So the base install stays light,
and an experiment that never touches a store never imports polars. Loading a manifest that
declares one is the main place the boundary shows (see [Installation](../installation.md) for
the full list of calls that need an extra).

The identity model is the seam that holds it together. Because the experiment layer and the
datastore layer both key everything by the same {class}`~exporgo.experiment.Identity`, and an
identity renders to exactly the partition path a store writes to, the layers line up on disk
without any coupling in code. Declare your keys once; the layers agree from there.

## Persistence

An experiment persists its **declaration** (keys, resource templates, store specs) to `experiment.json`,
with registered identities kept separately in `entities.jsonl` so a large registry doesn't bloat
the config file. {meth}`~exporgo.experiment.Experiment.load` reloads both. It never persists data or
derived status: those are re-read from the filesystem on demand, because the filesystem is the
source of truth. Those two files plus the tree they describe are enough to reconstruct the whole
picture, which also makes an experiment straightforward for an agent to read and reason about.

### The manifest's format field

`experiment.json` declares the version of its own layout, as a top-level integer. Here are a
manifest's first three keys:

```json
{
  "format": 1,
  "name": "mouse_experiment",
  "identity": [{"name": "Subject", "dtype": "str"}]
}
```

That one field buys a forward-compatibility contract, and the loader's three rules spell it out:

- **No `"format"` at all** means a file written before the field existed. It is read as a legacy
  manifest and accepted: an older experiment keeps loading, and the next
  {meth}`~exporgo.experiment.Experiment.save` stamps the current version into it.
- **A format newer than this exporgo understands** is refused with a `ValueError` that names both
  versions and tells you to upgrade exporgo. A future release may add fields this one would
  silently ignore, and a data root is shared: better a clear stop than a quiet partial read.
- **Unknown top-level keys** are ignored, but they raise a loguru `WARNING` naming them first,
  because the next `save()` will drop them. Nothing disappears without having said so.

The asymmetry is deliberate. Old files must keep opening (data outlives code), while a file from
the future must not be half-interpreted. Between those, an unrecognized key is a warning rather
than an error, so a hand-edited manifest or a field from a newer sibling install is survivable.

## The workspace CLI and the data root

exporgo has a second half, and knowing where the seam falls makes both halves easier to use. The
repository ships a **Rust command-line tool** (`exporgo new`, `check`, `update`, `sync`,
`exporgo experiment new`) that stamps and maintains *project workspaces* from a template embedded
in the binary. Installing it is downloading one file from GitHub Releases; after that, stamping
and updating need no network and no toolchain on a lab machine.

The two halves divide by **what each side owns**:

- The **Python package** owns the data. An {class}`~exporgo.experiment.Experiment` is the
  data-side unit and it lives *at* the data root, typically on the lab server: one root, one
  identity schema of one to three keys, one catalog of stores, and the `experiment.json` manifest
  that records them.
- The **workspace** owns the prose. A project workspace is documentation (context, protocols,
  analyses, and plans) and holds no code and no raw data. Within it, `experiments/<name>/` is a
  folder of Markdown about one experiment, and its `resources.md` records the canonical location
  of that experiment's raw data root.

So the workspace folder *points at* the data root; the experiment *is* the data root. Convention
keeps them in step, not a live link. `exporgo experiment new "<name>"` derives the pointer it
writes into `resources.md` as `<project data_root>/<slug>`, taking the project's `data_root` from
the workspace manifest and the slug from the experiment name (lowercased, with runs of
non-alphanumerics collapsed to hyphens). Pass the data root explicitly and that wins instead.
Nothing in the Python package reads a workspace, and nothing in the workspace reads
`experiment.json`. A reader follows the recorded path, opens the root with
{meth}`~exporgo.experiment.Experiment.load`, and the identity schema takes over from there.

For the CLI's commands, flags, and installation, see the
[repository README](https://github.com/darikoneil/exporgo#workspace-cli-rust).
