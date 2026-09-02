# Resources, stores, and dumps

A study holds four kinds of component: a **resource**, a **tabular store**, an **array store**,
and a **dump**. The difference between them is who owns the data and how its location is known.
Picking the right one is most of using exporgo well; when you know the shapes and just need to
route a particular dataset, jump to [Choosing a component](choosing-a-component) for the
comparison table and decision tree.

## The components

**Resource**: a file or folder exporgo *reads* but doesn't own, located by a **template** over
the identity keys. You declare `"{Subject}/{Session}/raw.tif"` and exporgo *derives* one path
for any identity. Use a resource for a single non-tabular blob you can name with a pattern: a
raw image tensor, a zarr store, an HDF5. The bytes are yours to read in whatever format; exporgo
only tells you where the file is and whether it's there.

*Reach for it when* the data is a single file or folder you can name with a pattern and exporgo
doesn't produce it — a folder counts, so a whole acquisition directory is a resource pointing at
the directory. *Not when* exporgo should own and write the bytes (that's a store). For example,
each session's raw two-photon acquisition lands at
`{Subject}/{Session}/raw.tif`; declare it as a resource and exporgo can resolve the path for any
identity and tell you which sessions have been collected.

**Store**: a schema-enforced dataset exporgo *owns and writes*, in one of two flavors. A
**tabular store** ({meth}`~exporgo.study.Study.declare_store`) is a partitioned Parquet dataset:
you declare a polars schema and partition keys, and query it fast across identities as a lazy
`LazyFrame` (trial-by-trial behavior, extracted features). An **array store**
({meth}`~exporgo.study.Study.declare_array_store`) holds one dense N-D array per identity (a
calcium trace `[unit, time]`, an imaging tensor) as a NumPy `.npy` blob paired with a coordinate
catalog, and hands it back as an {class}`xarray.DataArray`. Both own and dictate their layout and
keep a manifest of what's been written; they differ only in whether a component's data is a table
or an array. Arrays get their own store so tabular stores stay blob-free.

*Reach for a tabular store when* you want to query rows across identities (trial-by-trial
behavior, extracted features, per-cell statistics) and let exporgo enforce the schema and
partitioning. *Not when* the payload is a dense array (use an array store) or a file you only want
to locate (use a resource). For example, a `behavior` store with a
`{Subject, Session, trial, rt}` schema holds every session's trial table; a single
partition-pruned {meth}`~exporgo.datastore.Store.scan` pulls one subject's reaction times without
touching the rest.

*Reach for an array store when* each identity has exactly one dense N-D array you want back as a
labelled {class}`xarray.DataArray`. *Not when* the data is tabular rows (a tabular store) or a
file you only need to locate (a resource). For example, a `neural` array store holds each
session's
calcium traces as a `[unit, time]` array with unit indices and frame timestamps as coordinates;
{meth}`~exporgo.datastore.ArrayStore.load` returns it aligned and ready for
`neural.sel(time=slice(0, 10))`. The declaration fixes the coordinate *structure* (the dimension
names, the axis order, and which axes are labelled), so every array in the store shares it. The
coordinate *values* are per-identity: each write brings its own vectors, and each array its own
shape, so one session can be `[300 unit, 9000 time]` and the next `[512 unit, 12000 time]`, each
with its own unit indices and timestamps.

**Dump**: an index of many files under one study-global root, keyed by each file's path
**relative to that root**. Where a resource derives one path per identity, a dump *records* a
whole folder's worth of paths that belong to no identity at all. Use it for assets that belong to
the study rather than one subject: an atlas, a README, a shared lookup table. Paths are stored
as-given; nothing is copied, and the index persists to a `_dump.json` sidecar. Retrieval
dispatches on `*` — a selector without one is an exact relative-path key, a selector with one is
an {mod}`fnmatch` glob that crosses `/`.

*Reach for it when* an asset belongs to the whole study rather than any one subject or session.
*Not when* the data varies per identity (a resource). For example, a shared Allen CCF atlas (the
annotation volume, the reference template, the structure tree) is one set of files
every session's registration reads; a dump indexes them once, and `reference.path("*annotation*")`
resolves the volume wherever it sits. Because a dump has no identity, it is not swept by
{meth}`~exporgo.study.Study.validate` or {meth}`~exporgo.study.Study.coverage`; check it directly
with {meth}`~exporgo.study.Dump.exists`.

## Derive, own, index

The distinction to remember is how each component knows where its data is:

- A **resource** *derives* one path from a template. exporgo reads; you own the bytes.
- A **store** *owns* the data. exporgo writes and reads it — a tabular store as Parquet, an
  array store as `.npy` blobs (plus a Parquet coordinate catalog).
- A **dump** *indexes* many files under one study-global root, keyed by relative path. exporgo
  remembers; you own the bytes.

Resource and store are deliberately symmetric. Each splits into a declaration and a root-bound
handle ({class}`~exporgo.study.ResourceSpec` + {class}`~exporgo.study.Resource` mirror
{class}`~exporgo.datastore.StoreSpec` + {class}`~exporgo.datastore.Store`), reached the same
way: `study.declare_resource(...)` / `study.resource(name)` alongside `study.declare_store(...)`
/ `study.store(name)`. A dump has no separate spec — its declaration is just its name — so
`study.declare_dump(name)` / `study.dump(name)` hands back the handle directly.

## Where the data lives

A resource path is wherever its template resolves: exporgo doesn't impose a layout on data it
only reads. A store, by contrast, lives under `<root>/<name>/` and is partitioned on its keys,
so `behavior` data for `Subject=m01, Session=1` lands in
`<root>/behavior/Subject=m01/Session=1/`. Because a store's default partition keys *are* the
study's identity keys, a store partition and an identity are the same thing, which is what lets
a store report its own membership (see [Coverage and validation](coverage-and-validation)).

A raw resource feeds your processing, which writes tabular results a store owns — exporgo
brackets the ends and stays out of the middle. It describes, validates, and reports; it never
runs the analysis between.
