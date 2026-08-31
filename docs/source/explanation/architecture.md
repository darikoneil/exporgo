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

**study**: also in the base install (it adds only `pydantic`). The Study & Identity model: the
coordinate system, the resources and file maps a study expects, and file-existence validation.
This is the shared foundation — the identity keys it defines become the datastore's partition
keys, and its validation seeds what a monitoring layer would report.

**datastore** (`exporgo[datastore]`): fast, schema-enforced polars/Parquet component stores
for bulk data, Hive-partitioned on the identity keys, with lazy, partition-pruned retrieval.
It adds the heavier analytical stack (`polars`, `pyarrow`, `numpy`), which is why it's an
opt-in extra rather than part of the base.

**monitoring** (`exporgo[monitor]`): progress *derived* from the filesystem and rendered into
an agent-readable map. Planned; not yet implemented.

## How the layers depend on each other

The dependency arrow points one way: study builds on logging, and datastore builds on study.
It doesn't point back — importing `exporgo.study` never pulls in the datastore layer. The study module refers to store types only under `TYPE_CHECKING` and imports the real
datastore classes lazily, inside the methods that need them. So the base install stays light,
and a study that never touches a store never imports polars.

The identity model is the seam that holds it together. Because the study layer and the
datastore layer both key everything by the same {class}`~exporgo.study.Identity`, and an
identity renders to exactly the partition path a store writes to, the layers line up on disk
without any coupling in code. Declare your keys once; the layers agree from there.

## Persistence

A study persists its **declaration** (keys, registered identities, resource templates, store
specs) to `study.toml`, and reloads with {meth}`~exporgo.study.Study.load`. It never persists
data or derived status: those are re-read from the filesystem on demand, because the filesystem
is the source of truth. A `study.toml` plus the tree it describes is enough to reconstruct the
whole picture, which also makes a study straightforward for an agent to read and reason about.
