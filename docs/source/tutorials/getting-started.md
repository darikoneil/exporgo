# Getting started

This tutorial builds a small study end to end: you'll declare an identity coordinate system,
register the subjects and sessions the study should contain, point at raw files on disk,
store some behavioral data, and ask exporgo what's present and what's missing. By the end
you'll have a `study.json` you can reload, and a clear picture of how the pieces fit.

It assumes the base install (`uv add exporgo`) plus the datastore extra for the storage step:

```bash
uv add "exporgo[datastore]"
```

## Declare a study

A **study** is the top-level container. It needs a name, a root directory, and an *identity
coordinate system*: the one to three keys that name a single unit of data. Here the units are
a subject and a session, so the keys are `Subject` (a string) and `Session` (an integer):

```python
from pathlib import Path

from exporgo.study import IdentityKey, Study

study = Study(
    "mouse_study",
    Path.home() / "studies" / "mouse_study",
    identity=["Subject", IdentityKey(name="Session", dtype="int")],
)
print(study)
```

```text
Study 'mouse_study' [Subject, Session]: 0 identities, 0 resources, 0 stores, 0 array stores, 0 dumps
```

A bare string like `"Subject"` becomes a string-typed key; wrap it in
{class}`~exporgo.study.IdentityKey` when you want a different dtype (`"str"`, `"int"`, or
`"bool"`). Give no `identity` at all and the study defaults to a single `Subject` key.

## Register the identities you expect

**Registering** an identity records that the study *should* contain it. It's a declared
expectation (it never touches the filesystem), and it's what later lets exporgo tell you when
expected data is missing.

```python
study.register(Subject="m01", Session=1)
study.register(Subject="m01", Session=2)
study.register(Subject="m02", Session=1)

print(study.entities)
```

```text
(Identity(Subject='m01', Session=1), Identity(Subject='m01', Session=2), Identity(Subject='m02', Session=1))
```

Each call returns a validated {class}`~exporgo.study.Identity`. Re-registering the same
identity is a no-op — identities are de-duplicated.

## Point at raw files with a resource

A **resource** is a file or folder the study expects at each identity, located by a path
*template* over the identity keys. Declare one for the raw acquisition file:

```python
study.declare_resource("raw", "{Subject}/{Session}/raw.tif")
```

`study.path(...)` resolves the template for a specific identity (whether or not the file
exists yet), so you always know where a thing belongs:

```python
path = study.path("raw", Subject="m01", Session=1)
print(path)
```

```text
/home/you/studies/mouse_study/m01/1/raw.tif
```

Say you've collected `m01` but not yet `m02`. Create the two `m01` files, and exporgo can tell
real from expected:

```python
for subject, session in (("m01", 1), ("m01", 2)):
    p = study.path("raw", Subject=subject, Session=session)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"II*\x00")  # a stand-in for the real acquisition file

print(study.resource("raw").exists(Subject="m01", Session=1))
print(study.resource("raw").exists(Subject="m02", Session=1))
```

```text
True
False
```

## Store some data

exporgo *locates* a resource, but it *owns* a **store** — a schema-enforced, partitioned
Parquet dataset for bulk data. Declare a `behavior` store with a polars schema; its partition
keys default to the study's identity keys:

```python
import polars as pl

study.declare_store(
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
store = study.store("behavior")
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

Two questions, two methods. {meth}`~exporgo.study.Study.validate` is a **liveness** check:
for every registered identity, does its resource file still exist?

```python
report = study.validate()
print(report.is_complete)
print(report.missing)
```

```text
False
((Identity(Subject='m02', Session=1), 'raw'),)
```

{meth}`~exporgo.study.Study.coverage` is the fuller picture: every registered identity
against every component (resources *and* stores), plus anything on disk that was never
registered.

```python
print(study.coverage())
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
want flagged. For a filterable view, {meth}`~exporgo.study.CoverageReport.to_polars` returns a
tidy long frame:

```python
print(study.coverage().to_polars())
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

{meth}`~exporgo.study.Study.save` writes the study's *declaration* (its keys, resource
templates, and store specs) to `study.json`, with registered identities kept separately in
`entities.jsonl`. It also wires logging into the study root, so from here on a
`mouse_study.log` records what happens.

```python
study.save()
reloaded = Study.load(study.root)
print(reloaded)
```

```text
Study 'mouse_study' [Subject, Session]: 3 identities, 1 resources, 1 stores, 0 array stores, 0 dumps
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
