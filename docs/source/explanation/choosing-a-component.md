# Choosing a component

A study has four kinds of component, and most of using exporgo well is reaching for the right
one. This page routes you there. Read [Resources, stores, and dumps](./components.md) first
for what each component *is*; this page is the decision layer on top.

The question that separates them is always the same: **who owns the bytes, and how is their
location known?** exporgo either *reads* data it doesn't own (resources, dumps) or *owns and
writes* it (tabular stores, array stores). Within each half the next question is shape: for data
you own, a table or a single array; for data you don't, per-identity or study-global.

## At a glance

| Component | Who owns the bytes | How the location is known | Cardinality | On-disk layout | Retrieval → type | Reporting |
| --- | --- | --- | --- | --- | --- | --- |
| **Resource** | exporgo reads; you own | `{Key}` **template** over identity keys | one path per identity (file *or* folder) | wherever the template resolves; no imposed layout | {meth}`~exporgo.study.Resource.path` → {class}`~pathlib.Path` | `validate` + `coverage` |
| **Tabular Store** | exporgo owns & writes | owned Hive-partitioned layout | a table of many rows; partition = identity | `<root>/<name>/` Parquet fragments + `_manifest/` | {meth}`~exporgo.datastore.Store.scan` → {class}`polars.LazyFrame` | `coverage` |
| **Array Store** | exporgo owns & writes | owned Hive-partitioned layout | exactly one N-D array per identity | `<root>/<name>/` `.npy` blobs + `_coords/` + `_manifest/` | {meth}`~exporgo.datastore.ArrayStore.load` → {class}`xarray.DataArray` | `coverage` |
| **Dump** | exporgo indexes; you own | **recorded index**, one study-global root | a folder of many files, no identity | files stay put; index in `<root>/<name>/_dump.json` | {meth}`~exporgo.study.Dump.path` / {meth}`~exporgo.study.Dump.paths` → {class}`~pathlib.Path` / `{key: Path}` | neither |

Two things in that last column are easy to miss. A **tabular store** and an **array store** never
appear in {meth}`~exporgo.study.Study.validate` — validation is existence-only over files the
study merely points at, and a store owns its data, so its membership is a
{meth}`~exporgo.study.Study.coverage` question instead. A **dump** appears in neither report: it
has no identity to check against the registry, so it is swept by neither validate nor coverage
(query it directly with {meth}`~exporgo.study.Dump.exists`). See
[Coverage and validation](coverage-and-validation) for the full split.

## A decision tree

Ask yourself, in order:

1. **Does exporgo write the bytes, or do you?** If the data is produced elsewhere and exporgo
   only needs to find it and read it, you want a **resource** or a **dump** — skip to question 3.
   If exporgo should *own* the data and write it under a strict schema, continue.
2. **Is it a table or a single array?** Rows and columns queried across identities → a
   **tabular store** ({meth}`~exporgo.study.Study.declare_store`). Exactly one dense N-D array
   per identity, loaded as an {class}`xarray.DataArray` → an **array store**
   ({meth}`~exporgo.study.Study.declare_array_store`). *Done.*
3. **Is the data per-identity, or study-global?** One shared asset for the whole study, with no
   subject or session → a **dump** ({meth}`~exporgo.study.Study.declare_dump`). *Done.* Otherwise
   (one per identity), continue.
4. **Otherwise, it's a resource** ({meth}`~exporgo.study.Study.declare_resource`), named by a
   `{Key}` pattern. A pattern may name a folder as readily as a file.

## Rules of thumb

- **One blob you can name with a pattern → resource.** A raw `.tif`, a zarr store, an HDF5.
  exporgo derives the path; you read the bytes in whatever format.
- **Rows you want to query across identities → tabular store.** Trial-by-trial behavior,
  extracted features, per-cell statistics.
- **One dense array per identity → array store.** Calcium traces `[unit, time]`, a deconvolved
  spike matrix, an imaging tensor.
- **A shared asset that isn't per-subject → dump.** An atlas, a README, a shared lookup table.

When two fit, prefer the one that matches ownership: if exporgo doesn't produce the bytes, keep
them in a resource or dump rather than copying them into a store.
