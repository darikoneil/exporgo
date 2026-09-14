# Getting started

This tutorial builds a small experiment end to end: you'll declare an identity coordinate system,
register the subjects and sessions the experiment should contain, point at raw files on disk,
store some behavioral data, and ask exporgo what's present and what's missing. By the end
you'll have a `experiment.json` you can reload, and a clear picture of how the pieces fit.

It assumes the base install (`uv add exporgo`) plus the datastore extra for the storage step:

```bash
uv add "exporgo[datastore]"
```

## Declare an experiment

A **experiment** is the top-level container. It needs a name, a root directory, and an *identity
coordinate system*: the one to three keys that name a single unit of data. Here the units are
a subject and a session, so the keys are `Subject` (a string) and `Session` (an integer):

```python
from pathlib import Path

from exporgo.experiment import IdentityKey, Experiment

experiment = Experiment(
    "mouse_experiment",
    Path.home() / "experiments" / "mouse_experiment",
    identity=["Subject", IdentityKey(name="Session", dtype="int")],
)
print(experiment)
```

```text
Experiment 'mouse_experiment' [Subject, Session]: 0 identities, 0 resources, 0 stores, 0 array stores, 0 dumps
```

A bare string like `"Subject"` becomes a string-typed key; wrap it in
{class}`~exporgo.experiment.IdentityKey` when you want a different dtype (`"str"`, `"int"`, or
`"bool"`). Give no `identity` at all and the experiment defaults to a single `Subject` key.

## Register the identities you expect

**Registering** an identity records that the experiment *should* contain it. It's a declared
expectation (it never touches the filesystem), and it's what later lets exporgo tell you when
expected data is missing.

```python
experiment.register(Subject="m01", Session=1)
experiment.register(Subject="m01", Session=2)
experiment.register(Subject="m02", Session=1)

print(experiment.entities)
```

```text
(Identity(Subject='m01', Session=1), Identity(Subject='m01', Session=2), Identity(Subject='m02', Session=1))
```

Each call returns a validated {class}`~exporgo.experiment.Identity`. Re-registering the same
identity is a no-op — identities are de-duplicated.

## Point at raw files with a resource

A **resource** is a file or folder the experiment expects at each identity, located by a path
*template* over the identity keys. Declare one for the raw acquisition file:

```python
experiment.declare_resource("raw", "{Subject}/{Session}/raw.tif")
```

`experiment.path(...)` resolves the template for a specific identity (whether or not the file
exists yet), so you always know where a thing belongs:

```python
path = experiment.path("raw", Subject="m01", Session=1)
print(path)
```

```text
/home/you/experiments/mouse_experiment/m01/1/raw.tif
```

Say you've collected `m01` but not yet `m02`. Create the two `m01` files, and exporgo can tell
real from expected:

```python
for subject, session in (("m01", 1), ("m01", 2)):
    p = experiment.path("raw", Subject=subject, Session=session)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"II*\x00")  # a stand-in for the real acquisition file

print(experiment.resource("raw").exists(Subject="m01", Session=1))
print(experiment.resource("raw").exists(Subject="m02", Session=1))
```

```text
True
False
```

## Store some data

exporgo *locates* a resource, but it *owns* a **store** — a schema-enforced, partitioned
Parquet dataset for bulk data. Declare a `behavior` store with a polars schema; its partition
keys default to the experiment's identity keys:

```python
import polars as pl

experiment.declare_store(
    "behavior",
    {"Subject": pl.String, "Session": pl.Int64, "trial": pl.Int64, "rt": pl.Float64},
    sort_column="trial",
)
```

Write a frame per session. `mode="unique"` refuses to write an identity the store already
contains, so a re-run can't silently duplicate data:

```python
frame = pl.DataFrame(
    {
        "Subject": ["m01", "m01", "m01"],
        "Session": [1, 1, 2],
        "trial": [2, 1, 1],
        "rt": [0.42, 0.51, 0.39],
    }
)
store = experiment.store("behavior")
store.write(frame.filter(pl.col("Session") == 1), mode="unique")
store.write(frame.filter(pl.col("Session") == 2), mode="unique")
```

Read it back with a lazy, partition-pruned scan. Filter on the partition keys *before*
collecting, and only the matching fragments are touched:

```python
print(
    store.scan()
    .filter(pl.col("Subject") == "m01")
    .sort("Session", "trial")
    .collect()
)
```

```text
shape: (3, 4)
┌─────────┬─────────┬───────┬──────┐
│ Subject ┆ Session ┆ trial ┆ rt   │
│ ---     ┆ ---     ┆ ---   ┆ ---  │
│ str     ┆ i64     ┆ i64   ┆ f64  │
╞═════════╪═════════╪═══════╪══════╡
│ m01     ┆ 1       ┆ 1     ┆ 0.51 │
│ m01     ┆ 1       ┆ 2     ┆ 0.42 │
│ m01     ┆ 2       ┆ 1     ┆ 0.39 │
└─────────┴─────────┴───────┴──────┘
```

## Ask what's present and what's missing

Two questions, two methods. {meth}`~exporgo.experiment.Experiment.validate` is a **liveness** check:
for every registered identity, does its resource file still exist?

```python
report = experiment.validate()
print(report.is_complete)
print(report.missing)
```

```text
False
((Identity(Subject='m02', Session=1), 'raw'),)
```

{meth}`~exporgo.experiment.Experiment.coverage` is the fuller picture: every registered identity
against every component (resources *and* stores), plus anything on disk that was never
registered.

```python
print(experiment.coverage())
```

```text
CoverageReport: 4 present, 2 missing, 0 unregistered (incomplete)
  missing:
    behavior: Subject=m02/Session=1
    raw: Subject=m02/Session=1
  present:
    behavior: Subject=m01/Session=1
    behavior: Subject=m01/Session=2
    raw: Subject=m01/Session=1
    raw: Subject=m01/Session=2
```

`m02/1` is registered but has neither a raw file nor stored behavior — exactly the gap you'd
want flagged. For a filterable view, {meth}`~exporgo.experiment.CoverageReport.to_polars` returns a
tidy long frame:

```python
print(experiment.coverage().to_polars())
```

```text
shape: (6, 4)
┌─────────┬─────────┬───────────┬─────────┐
│ Subject ┆ Session ┆ component ┆ status  │
│ ---     ┆ ---     ┆ ---       ┆ ---     │
│ str     ┆ i64     ┆ str       ┆ str     │
╞═════════╪═════════╪═══════════╪═════════╡
│ m01     ┆ 1       ┆ raw       ┆ present │
│ m01     ┆ 2       ┆ raw       ┆ present │
│ m01     ┆ 1       ┆ behavior  ┆ present │
│ m01     ┆ 2       ┆ behavior  ┆ present │
│ m02     ┆ 1       ┆ raw       ┆ missing │
│ m02     ┆ 1       ┆ behavior  ┆ missing │
└─────────┴─────────┴───────────┴─────────┘
```

## Save and reload

{meth}`~exporgo.experiment.Experiment.save` writes the experiment's *declaration* (its keys, resource
templates, and store specs) to `experiment.json`, with registered identities kept separately in
`entities.jsonl`. It also wires logging into the experiment root, so from here on a
`mouse_experiment.log` records what happens.

```python
experiment.save()
reloaded = Experiment.load(experiment.root)
print(reloaded)
```

```text
Experiment 'mouse_experiment' [Subject, Session]: 3 identities, 1 resources, 1 stores, 0 array stores, 0 dumps
```

The reload restores the declaration, not the data — data and status are always re-read from
the filesystem, because the filesystem is the source of truth.

## Where to go next

- Bootstrap a registry from data that already exists on disk:
  [Discover identities](../how-to/discover-identities).
- The full write model (append, overwrite, unique): [Write to a store](../how-to/write-to-a-store).
- Why `validate` and `coverage` differ:
  [Coverage and validation](../explanation/coverage-and-validation).
- The concepts underneath it all: [The identity model](../explanation/identity-model).
