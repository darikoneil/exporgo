# exporgo — Study & Identity model Design

*Design record, 2026-08-23. Shaped through discussion; the shared foundation both the
monitoring and datastore layers build on. **Built & verified 2026-08-24** (TDD;
ruff/pyrefly clean). `discover()` is the one deferred piece — flagged inline below.*

## Context

Every exporgo study needs a common way to (a) name the things it's about (subjects,
sessions), (b) say where their data lives on disk, and (c) check that it's actually there —
Darik's original ask: *"organize subjects/filepaths, self-validate file existence,
pre-register subjects."* This model is that foundation. It **describes and validates; it
never executes.** Its identity keys become the datastore's partition keys, and its
`validate()` output seeds monitoring's derived status — so both higher layers stand on it,
and it must exist first.

## Core objects

**`IdentityKey` — the name of an axis the study is organized by.** A labeled, typed field:
`Subject` (str), `Session` (int), `Group` (str). A study declares an ordered **1–3** of
them; omitted → default `["Subject"]`.

**`Identity` — one concrete address in that coordinate system.** An immutable, validated
mapping over the keys, e.g. `Identity(Subject="m01", Session=1)`. Hashable (indexes
things), validates against the schema, and renders to the path fragment `Subject=m01/…` —
the *same* fragment the datastore partitions on. It is the addressable unit you register,
query for, and attach data to.

**`ResourceSpec` — a named file/folder the study expects at each identity.** e.g. `"raw"`,
`"suite2p"`, `"behavior"`. Each carries a **per-resource path template** over the identity
keys (a template may use any subset — a per-subject genotype file uses only `{Subject}`).
This is the resource *declaration*; combined with an `Identity` it resolves to a concrete
path whose existence can be checked. `ResourceSpec` is to a resource what `StoreSpec` is to
a store.

**`Resource` — a `ResourceSpec` bound to the study root + identity schema.** The root-bound
*handle* returned by `study.resource(name)`: call `.path(**identity)` to resolve a location
or `.exists(**identity)` to check it. It is the resource counterpart of a datastore `Store`
(the live handle), so the two component surfaces are symmetric (see below).

**`Study` — the container.** `name`, `root`, the ordered identity keys, the set of
**registered `Identity`s**, and the declared **`ResourceSpec`s**. Later it also carries the
datastore catalog and the monitoring steps — which consume this same identity + layout.

## Resource vs. datastore (the access boundary)

A `resource` gives you a **location**; a `store` gives you **data**. They sit at opposite
ends of a pipeline, and exporgo brackets the ends without running the middle:

| | **Resource** (`study.resource` / `study.path`) | **Datastore** (`study.store`) |
|---|---|---|
| exporgo's job | locate + validate existence | own format/schema/partitioning + do the IO/query |
| You get back | a `Path` | a polars `LazyFrame`/`DataFrame` |
| Who reads bytes | you (`np.load`, `pl.read_csv`, …) | exporgo (Parquet) |
| Format | anything (tiff, npy, csv, mat, …) | Parquet (exporgo-owned) |
| Role | raw inputs + step outputs (external, arbitrary) | curated data dumped for fast retrieval |

```
raw resource            your processing code             datastore
study.path(...) ──►  read, compute, transform  ──►  study.store("neural").write(df)
 (locate + validate)   (exporgo does NOT run this)      (dump) ─► .scan() fast queries
```

Both are addressed by the **same `Identity`**, so resource paths and store partitions line
up. Rule of thumb: external/arbitrary/raw → **resource** (get a path, load it yourself);
curated/queryable/exporgo-owned → **datastore** (get polars back).

### Symmetric accessor surface

The three component surfaces mirror each other — a `ResourceSpec`/`Resource` pair, the
datastore's `StoreSpec`/`Store`, and the `FileMap` (which has no separate spec):

| | declaration | declare verb | collection | handle getter | handle |
|---|---|---|---|---|---|
| **Resource** | `ResourceSpec` | `declare_resource` | `resources` | `resource(name)` | `Resource` |
| **Store** | `StoreSpec` | `declare_store` | `stores` | `store(name)` | `Store` |
| **FileMap** | *(none — name only)* | `declare_filemap` | `filemaps` | `filemap(name)` | `FileMap` |

`study.path(name, **identity)` is kept as terse sugar for
`study.resource(name).path(**identity)`; there is no store/filemap equivalent because a
`Store`/`FileMap` is already the usable handle.

**FileMap (built 2026-08-27) — recorded locations.** Where a `Resource` *derives* a path
from a template and a `Store` *owns* the data, a `FileMap` *records* the concrete
location(s) of particular files per identity — typically raw acquisition files that live
anywhere on disk (an external drive) and follow no naming pattern. Each identity maps to a
`{name -> path}` set (name defaults to the file stem); paths are stored as-given (absolute,
outside the root, never copied/created). Records persist to a sidecar
`<root>/<name>/_filemap.json`. `record(path, **identity)` adds one; `discover(directory,
**identity)` indexes a directory (like v1's `FileSet.index()`); `path`/`paths`/`exists`
retrieve and validate; `identities()` lists which identities have records — so
`study.identities(filemap=…)` and `study.coverage()` extend to it (open-world, like a
store).

## Declaring a study

```python
from exporgo.study import Study

study = Study(
    name="fomo",
    root=Path("D:/data/fomo"),
    identity=["Subject", "Session"],   # 1–3 keys; omit → defaults to ["Subject"]
)

# Pre-register what SHOULD exist (declared expectation):
study.register(Subject="m01", Session=1)
study.register(Subject="m01", Session=2)
study.register(Subject="m02", Session=1)

# Declare where each resource lives (per-resource templates over the identity keys):
study.declare_resource("raw",      "{Subject}/{Session}/raw")
study.declare_resource("suite2p",  "{Subject}/{Session}/suite2p/plane0/F.npy")
study.declare_resource("behavior", "{Subject}/{Session}/behavior.csv")

study.path(Subject="m01", Session=1, resource="suite2p")
#   -> D:/data/fomo/m01/1/suite2p/plane0/F.npy
```

## Registration vs. discovery (both, distinct roles)

- **`register(...)`** is the **canonical expectation** — what the study *should* contain.
  This is what lets validation detect **missing** data.
- **`discover()`** *(deferred — not yet implemented)* scans the tree to (a) **bootstrap**
  a registry from an existing dataset and (b) report **drift** in both directions:
  registered-but-missing, and on-disk-but-unregistered.

Registration is the declared truth; discovery only reconciles it against reality — keeping
the "describe + validate" philosophy intact.

## Validation — the "self-validate" foundation

```python
report = study.validate()
report.missing   # [(Identity(Subject='m02', Session=1), resource='suite2p'), ...]
report.present   # ...
```

`validate()` reads the filesystem (the source of truth) and compares it against *registered
identities × declared resources*. This is the file-existence self-check, and it's exactly
what the monitoring layer later turns into **derived** per-step status.

### Which identities a component contains (built 2026-08-27)

Two related accessors report component membership, both derived on demand:

- **`study.identities(store=…)` / `study.identities(resource=…)`** — the per-component
  primitive, returning a `set[Identity]`. A **store** is answered **open-world** from its
  manifest (the partitions physically present — which may include identities never
  registered); a **resource** is answered **closed-world** (the registered identities whose
  file exists — there is no scan for unregistered files; that is `discover()`'s future job).
- **`study.coverage()`** — a study-wide `CoverageReport` layered on the primitive: every
  `(registered identity, component)` pair classified `present`/`missing` across both stores
  and resources, plus `unregistered` — store identities present on disk but not registered
  (the open-world drift a registered-only matrix would miss). It generalizes `validate()`
  (which stays resource-only).

The write-time counterpart lives in the datastore: `store.write(frame, mode="unique")`
refuses to write an identity the store already contains (see the datastore design doc).

## Layout: per-resource templates, default by ownership

There is **no single forced tree**. Each resource declares its own path template, and the
default shape depends on who owns the data:

- **Resources exporgo only *reads*** (raw acquisition, upstream step outputs) → **flexible
  template that matches whatever layout already exists** (often identity-first, e.g.
  `{Subject}/{Session}/raw`). exporgo locates data; it never forces a reorganization.
- **Data exporgo *writes/manages*** (the datastore, and any derived products it owns) →
  **resource/store-first + identity-partitioned** (`{store}/subject=…/session=…`) — the
  query-optimal Hive layout that makes "all subjects in group X" fast (see the datastore
  design doc). Identity-first here would scatter a kind across subject folders and kill
  partition pruning.

## On disk

```
D:/data/fomo/
  study.toml                # declared study: identity keys, registered identities, resources, store specs (steps later)
  m01/1/raw/…  m01/1/suite2p/…  m01/1/behavior.csv          # resources exporgo only reads (your layout)
  m01/2/…   m02/1/…
  neural/  _schema.parquet  _manifest.json  Subject=m01/Session=1/part-*.parquet   # a datastore component (exporgo-owned)
```

The study is fully declarable in `study.toml` and reloadable via `Study.load(root)`, so a
fresh session — **or an LLM agent** — can reconstruct the whole picture.

## Persistence

```python
study.save()               # writes root/study.toml + each store's _schema.parquet anchor
study = Study.load(root)    # points at the root dir, finds study.toml, reconstructs
```

**Auto-logging:** `save()` also wires up logging into the study root via
`study.init_logging()` (which drives the base `init_logger` with `base_directory=root`,
`file_stem=name`), so every saved study automatically gets a `<root>/<name>.log` (plus a
`.logs/.<name>_exception.log` and a console sink) that the logger writes to — a primary
reason the logging layer exists. `load()` is deliberately side-effect-free and does *not*
reconfigure logging; call `study.init_logging()` explicitly to resume logging into a
loaded study.

**What persists is the *declaration*** — identity keys, registered identities, resource
templates, and (later) store/step specs. **What does *not* persist is the data or the
derived status:** data lives in the datastore/resources on disk, and status is recomputed
by `validate()` on demand (filesystem = truth). So `Study.load(root)` restores the declared
structure, then `validate()`/`store()` re-read current reality. Mutating methods
(`register`, `declare_resource`, …) mark the study dirty; `save()` flushes (auto-save on
mutation is an option to decide at build).

## How the higher layers plug in (not built here)

- **Datastore:** a store's partition keys **default to the study's identity keys**;
  `study.store("behavior")` writes/queries keyed by the same `Identity`, and
  `Identity.as_path()` *is* the partition path — so cross-component joins line up.
- **Monitoring:** for each registered identity × declared step, status is **derived** from
  `validate()` (do the step's declared output resources exist / are they fresh?) → the
  status matrix and the agent-readable map.

## Proposed module layout

```
exporgo/study/
  __init__.py       # public API
  identity.py       # IdentityKey, IdentitySchema, Identity
  study.py          # Study: register / declare_resource / resource / path / declare_store / store / validate
  resources.py      # ResourceSpec (declaration) + Resource (root-bound handle)
```

## Packaging & dependencies

`exporgo.study` is the shared foundation and needs **pydantic** (models + config), so it's
an extra — `exporgo[study]` — that both `[monitor]` and `[datastore]` depend on. The **base
install stays loguru-only.** No domain libraries (no pynapple/suite2p/regions) — the model
is generic; identity keys, resources, and templates are all supplied by the study.

## Principles honored

- Describe + validate, never execute.
- Filesystem = truth (registry = declared expectation; `validate()`/`discover()` = reality).
- Strict, declared pydantic models; identity 1–3 keys, default `Subject`.
- Config-declarable and agent-reconstructable.

## Open / spec-level items (resolve when building)

- Path-template syntax and edge cases (globs, optional segments, resources keyed on a
  subset of identity keys, multiple files per resource).
- `study.toml` schema and `Study.from_config` / round-trip.
- Freshness semantics for `validate()` (existence only vs. mtime-vs-inputs), which the
  monitoring layer will lean on.
- Exact `discover()` reconciliation rules and drift reporting.

## Verification (when built)

TDD as with `exporgo/log`: unit-test identity validation (key/dtype conformance, 1–3
bound, default `Subject`), path resolution for full and subset-key resources,
register/discover/validate behavior (present/missing/drift), and `study.toml` round-trip;
an end-to-end smoke test over a small temp tree. Must pass `ruff`/`pyrefly` and hold
coverage ≥ 75%.
