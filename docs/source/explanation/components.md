# Resources, stores, file maps, and dumps

A study holds four kinds of component, and the difference between them is who owns the data and
how its location is known. Picking the right one is most of using exporgo well.

## The four components

**Resource**: a file or folder exporgo *reads* but doesn't own, located by a **template** over
the identity keys. You declare `"{Subject}/{Session}/raw.tif"` and exporgo *derives* one path
for any identity. Use a resource for a single non-tabular blob you can name with a pattern: a
raw image tensor, a zarr store, an HDF5. The bytes are yours to read in whatever format; exporgo
only tells you where the file is and whether it's there.

**Store**: a schema-enforced dataset exporgo *owns and writes*, in one of two flavors. A
**tabular store** ({meth}`~exporgo.study.Study.declare_store`) is a partitioned Parquet dataset:
you declare a polars schema and partition keys, and query it fast across identities as a lazy
`LazyFrame` — trial-by-trial behavior, extracted features. An **array store**
({meth}`~exporgo.study.Study.declare_array_store`) holds one dense N-D array per identity — a
calcium trace `[unit, time]`, an imaging tensor — as a NumPy `.npy` blob paired with a coordinate
catalog, and hands it back as an {class}`xarray.DataArray`. Both own and dictate their layout and
keep a manifest of what's been written; they differ only in whether a component's data is a table
or an array. Arrays get their own store so tabular stores stay blob-free.

**File map**: a per-identity index of many files, keyed by each file's path **relative to that
identity's root**. Where a resource derives one path, a file map holds a whole folder's worth:
suite2p's `plane0/F.npy`, `plane1/F.npy`, and the rest, side by side without collision. Its mode
is fixed at declaration — **templated** (a `root_template` derives each identity's root folder)
or **recorded** (you hand it the folder, or pin loose files). Use one for multi-file outputs and
for raw acquisitions that live anywhere. Paths are stored as-given; nothing is copied, and the
index persists to a `_filemap.json` sidecar.

**Dump**: a file map without the identity — one study-global root and its relative-path-keyed
files. Use it for assets that belong to the whole study rather than one subject: an atlas, a
README, a shared lookup table. Same indexing and the same `*`-dispatch retrieval as a file map,
minus the identity.

## Derive, own, index

The distinction to remember is how each component knows where its data is:

- A **resource** *derives* one path from a template. exporgo reads; you own the bytes.
- A **store** *owns* the data. exporgo writes and reads it — a tabular store as Parquet, an
  array store as `.npy` blobs (plus a Parquet coordinate catalog).
- A **file map** *indexes* files under a root — derived (templated) or given (recorded) — keyed
  by relative path. exporgo remembers; you own the bytes.
- A **dump** is a file map with no identity: one study-global root.

Resource and store are deliberately symmetric. Each splits into a declaration and a root-bound
handle ({class}`~exporgo.study.ResourceSpec` + {class}`~exporgo.study.Resource` mirror
{class}`~exporgo.datastore.StoreSpec` + {class}`~exporgo.datastore.Store`), reached the same
way: `study.declare_resource(...)` / `study.resource(name)` alongside `study.declare_store(...)`
/ `study.store(name)`. File maps and dumps have no separate spec (the declaration is the name,
plus a file map's optional `root_template`), so `study.declare_filemap(name)` /
`study.filemap(name)` and `study.declare_dump(name)` / `study.dump(name)` each hand back the
handle directly.

## Where the data lives

A resource path is wherever its template resolves: exporgo doesn't impose a layout on data it
only reads. A store, by contrast, lives under `<root>/<name>/` and is partitioned on its keys,
so `behavior` data for `Subject=m01, Session=1` lands in
`<root>/behavior/Subject=m01/Session=1/`. Because a store's default partition keys *are* the
study's identity keys, a store partition and an identity are the same thing, which is what lets
a store report its own membership (see [Coverage and validation](coverage-and-validation)).

A raw resource feeds your processing, which writes multi-file output a file map indexes and
tabular results a store owns — exporgo brackets the ends and stays out of the middle. It
describes, validates, and reports; it never runs the analysis between.
