# Resources, stores, file maps, and dumps

A study holds four kinds of component — and because a store comes in two flavors, five in
practice: a **resource**, a **tabular store**, an **array store**, a **file map**, and a
**dump**. The difference between them is who owns the data and how its location is known. Picking
the right one is most of using exporgo well; when you know the shapes and just need to route a
particular dataset, jump to [Choosing a component](choosing-a-component) for the comparison table
and decision tree.

## The four components

**Resource**: a file or folder exporgo *reads* but doesn't own, located by a **template** over
the identity keys. You declare `"{Subject}/{Session}/raw.tif"` and exporgo *derives* one path
for any identity. Use a resource for a single non-tabular blob you can name with a pattern: a
raw image tensor, a zarr store, an HDF5. The bytes are yours to read in whatever format; exporgo
only tells you where the file is and whether it's there.

*Reach for it when* the data is a single file or folder you can name with a pattern and exporgo
doesn't produce it. *Not when* one identity has a whole directory of files that must be addressed
individually (that's a file map), or when exporgo should own and write the bytes (that's a store).
For example, each session's raw two-photon acquisition lands at
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
to locate (use a resource or file map). For example, a `behavior` store with a
`{Subject, Session, trial, rt}` schema holds every session's trial table; a single
partition-pruned {meth}`~exporgo.datastore.Store.scan` pulls one subject's reaction times without
touching the rest.

*Reach for an array store when* each identity has exactly one dense N-D array you want back as a
labelled {class}`xarray.DataArray`. *Not when* the identity has many independent files (a file
map) or tabular rows (a tabular store). For example, a `neural` array store holds each session's
calcium traces as a `[unit, time]` array with unit indices and frame timestamps as coordinates;
{meth}`~exporgo.datastore.ArrayStore.load` returns it aligned and ready for
`neural.sel(time=slice(0, 10))`.

**File map**: a per-identity index of many files, keyed by each file's path **relative to that
identity's root**. Where a resource derives one path, a file map holds a whole folder's worth:
suite2p's `plane0/F.npy`, `plane1/F.npy`, and the rest, side by side without collision. Its mode
is fixed at declaration — **templated** (a `root_template` derives each identity's root folder)
or **recorded** (you hand it the folder, or pin loose files). Use one for multi-file outputs and
for raw acquisitions that live anywhere. Paths are stored as-given; nothing is copied, and the
index persists to a `_filemap.json` sidecar.

*Reach for it when* one identity owns a directory of files you must address individually and no
single template names them. *Not when* the data is one nameable path (a resource) or a shared
study-wide asset with no identity (a dump). For example, suite2p writes `plane0/F.npy`,
`plane0/Fneu.npy`, `plane0/iscell.npy`, and the same again for `plane1` under each session's
output folder; a templated file map with `root_template="{Subject}/{Session}/suite2p"` indexes
the whole tree, and `s2p.path("*iscell*", ...)` finds a file anywhere in it.

**Dump**: a file map without the identity — one study-global root and its relative-path-keyed
files. Use it for assets that belong to the whole study rather than one subject: an atlas, a
README, a shared lookup table. Same indexing and the same `*`-dispatch retrieval as a file map,
minus the identity.

*Reach for it when* an asset belongs to the whole study rather than any one subject or session.
*Not when* the data varies per identity (a file map or resource). For example, a shared Allen CCF
atlas (the annotation volume, the reference template, the structure tree) is one set of files
every session's registration reads; a dump indexes them once, and `reference.path("*annotation*")`
resolves the volume wherever it sits. Because a dump has no identity, it is not swept by
{meth}`~exporgo.study.Study.validate` or {meth}`~exporgo.study.Study.coverage`; check it directly
with {meth}`~exporgo.study.Dump.exists`.

## Derive, own, index

The distinction to remember is how each component knows where its data is:

- A **resource** *derives* one path from a template. exporgo reads; you own the bytes.
- A **store** *owns* the data. exporgo writes and reads it — a tabular store as Parquet, an
  array store as `.npy` blobs (plus a Parquet coordinate catalog).
- A **file map** *indexes* files under a root, derived (templated) or given (recorded), keyed
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
