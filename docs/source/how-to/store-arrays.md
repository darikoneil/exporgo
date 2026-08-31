# Store arrays with coordinates

An **array store** holds one dense N-D array per identity — a calcium trace `[unit, time]`, an
imaging tensor — as a NumPy `.npy` blob paired with a coordinate catalog, and hands it back as an
{class}`xarray.DataArray`. It is the datastore's second store kind, for the bulk arrays that don't
belong in a tabular store. It needs the datastore extra:

```bash
uv add "exporgo[datastore]"
```

## Declare the array store

Give it a name, the ordered dimensions, and the array's element dtype. Each dimension maps to the
polars dtype of its coordinate vector — the values you'll attach along that axis (frame
timestamps, unit indices) — or `None` for a positional axis with no coordinate. Partition keys
default to the study's identity keys, so a partition is an identity:

```python
import numpy as np
import polars as pl

study.declare_array_store(
    "neural",
    dims={"unit": pl.Int64, "time": pl.Float64},
    dtype=np.float32,
)
store = study.array_store("neural")
```

The dimension order is the array's axis order: `neural` expects a 2-D array indexed `[unit,
time]`. A `.npy` file records its own shape and element dtype, so the coordinate catalog stores
only the coordinate vectors — nothing scalar.

## Write an identity's array

{meth}`~exporgo.datastore.ArrayStore.write` takes the array, its coordinates, and the identity.
The array is cast to the declared element dtype; every labelled dimension needs a coordinate whose
length matches that axis:

```python
store.write(
    np.random.default_rng(0).standard_normal((120, 9000)),  # cast to float32
    coords={"unit": np.arange(120), "time": np.arange(9000) / 30.0},
    Subject="m01",
    Session=1,
)
```

An array store holds a single array per identity, so there is no `append`. The two modes are about
an identity that already has an array:

```python
store.write(array, coords=coords, Subject="m01", Session=1)                   # mode="unique"
store.write(array, coords=coords, mode="overwrite", Subject="m01", Session=1)  # replace it
```

- **`unique`** (the default) refuses the write, raising a `ValueError`, if the identity already
  has an array — a re-run won't silently clobber.
- **`overwrite`** replaces it: the prior `.npy` is tombstoned and the coordinate row is rewritten.

A wrong rank, a value that can't be cast to the element dtype, a missing or mis-sized coordinate,
or the wrong identity keys each raise a `ValueError` before anything is written.

## Load it as an xarray DataArray

{meth}`~exporgo.datastore.ArrayStore.load` pairs the blob and its coordinates back into a labelled
array:

```python
neural = store.load(Subject="m01", Session=1)

print(neural.dims)               # ('unit', 'time')
print(neural.shape)              # (120, 9000)
print(neural.coords["time"][:3]) # the frame timestamps you wrote
```

The result is a genuine {class}`xarray.DataArray` named after the store, so labelled indexing,
alignment, and reductions are all available — for example `neural.sel(time=slice(0, 10)).mean("unit")`.

## Query the coordinate catalog

The coordinates live in a nested tabular store, one row per identity with a list-valued column per
labelled dimension. {meth}`~exporgo.datastore.ArrayStore.scan_coords` exposes it as a lazy
{class}`polars.LazyFrame` for cross-identity questions — how many frames each session has, say —
without loading a single array:

```python
print(
    store.scan_coords()
    .select("Subject", "Session", pl.col("time").list.len().alias("n_frames"))
    .collect()
)
```

## Report membership

An array store reports its identities the same way a tabular store does.
{meth}`study.identities(array_store="neural") <exporgo.study.Study.identities>` returns the
identities it holds (open-world, from the manifest), and {meth}`~exporgo.study.Study.coverage`
folds the array store into the full present/missing/unregistered report alongside every other
component.
