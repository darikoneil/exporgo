# Experiment &amp; Identity (`exporgo.experiment`)

The Experiment & Identity model: the identity coordinate system
({class}`~exporgo.experiment.IdentitySchema`, {class}`~exporgo.experiment.IdentityKey`,
{class}`~exporgo.experiment.Identity`), the resources an experiment expects, and the
{class}`~exporgo.experiment.Experiment` container that ties them together and validates them. Every name
below is exported from `exporgo.experiment.__all__`.

## Experiment container

The top-level object. A {class}`~exporgo.experiment.Experiment` declares an identity coordinate system,
the identities it should contain, and the components (resources, stores, array stores, dumps)
expected at each; it describes and validates but never runs your analysis. Declarations
persist to `experiment.json` via {meth}`~exporgo.experiment.Experiment.save` and reload with
{meth}`~exporgo.experiment.Experiment.load`.

```python
experiment = Experiment("mouse_experiment", "/data/mouse_experiment", identity=["Subject", "Session"])
experiment.register(Subject="m01", Session=1)
experiment.declare_resource("raw", "{Subject}/{Session}/raw.tif")
```

```{eval-rst}
.. autoclass:: exporgo.experiment.Experiment
   :members:
```

### The `experiment.json` manifest

{meth}`~exporgo.experiment.Experiment.save` writes these top-level keys, in this order:

| Key | Value |
| --- | --- |
| `format` | The layout version this exporgo writes: `1`. |
| `name` | The experiment name. |
| `identity` | One `{"name": ..., "dtype": ...}` object per identity key, in schema order. |
| `resources` | `{resource name: path template}`. |
| `stores` | Per store: `partition_keys`, `max_rows_per_file`, `max_rows_per_group`, and `sort_column` when one is declared. Columns are not here; each store's schema is persisted as a 0-row Parquet anchor in the store's own directory. |
| `array_stores` | Per array store: `dtype`, `partition_keys`, `dims` (axis order), `max_rows_per_file`, `max_rows_per_group`. |
| `dumps` | The declared dump names. |

Registered identities are **not** in this file; they go one JSON object per line to
`entities.jsonl` beside it, so the manifest's size and parse cost stay independent of how many
identities are registered.

{meth}`~exporgo.experiment.Experiment.load` reads `format` and enforces three rules:

- **Absent.** A manifest written before the field existed. Treated as legacy and accepted.
- **Greater than `1`.** A `ValueError`, naming both versions and telling you to upgrade exporgo.
- **Unknown top-level keys.** A loguru `WARNING` naming them; they are ignored and the next
  `save()` drops them.

See [Persistence](../explanation/architecture.md#persistence) for the reasoning, and
[Installation](../installation.md) if you are upgrading from a 2.x `study.json`.

`save()` defaults to `init_logging=True`, which calls
{meth}`~exporgo.experiment.Experiment.init_logging` and so resets **every** loguru sink in the
process. Pass `save(init_logging=False)` to write the manifest without touching the global
logger. See
[Configure logging](../how-to/configure-logging.md#save-without-touching-the-global-logger).

## Identity coordinate system

An identity names one addressable unit of data. An {class}`~exporgo.experiment.IdentitySchema` is the
ordered set of one to three {class}`~exporgo.experiment.IdentityKey` columns (each with a name and a
dtype: `"str"`, `"int"`, or `"bool"`); an {class}`~exporgo.experiment.Identity` is a concrete point
in that coordinate system, e.g. `Subject="m01", Session=1`. These keys become the datastore's
partition keys, so a store partition and an identity are the same thing.

```{eval-rst}
.. autopydantic_model:: exporgo.experiment.IdentitySchema
   :members:

.. autoclass:: exporgo.experiment.IdentityKey
   :members:

.. autoclass:: exporgo.experiment.Identity
   :members:
```

## Resources

A resource is a file or folder exporgo reads but doesn't own, located by a path template over the
identity keys. {class}`~exporgo.experiment.ResourceSpec` is the declaration (a name plus a template);
{class}`~exporgo.experiment.Resource` binds it to an experiment root so you can resolve concrete paths,
check existence, and reverse-resolve the template to discover identities on disk. Reach for one
when the data is a single nameable path. See
[Choosing a component](../explanation/choosing-a-component).

```{eval-rst}
.. autopydantic_model:: exporgo.experiment.ResourceSpec
   :members:

.. autoclass:: exporgo.experiment.Resource
   :members:
```

## Dumps

A {class}`~exporgo.experiment.Dump` indexes many files under one experiment-global root, keyed by each
file's path relative to that root, so same-named files in different subfolders never collide. It
is for shared assets that belong to no single identity: an atlas, a README, a lookup table. It
copies nothing; the index persists to a `_dump.json` sidecar in the dump's own directory under
the experiment root, however far away the files themselves live.

```{eval-rst}
.. autoclass:: exporgo.experiment.Dump
   :members:
```

## Reports

Two frozen, handle-free snapshots. {class}`~exporgo.experiment.ValidationReport` is the outcome of
{meth}`~exporgo.experiment.Experiment.validate`: a closed-world, existence-only check of whether each
registered identity's resource files still exist.
{class}`~exporgo.experiment.CoverageReport` is the outcome of {meth}`~exporgo.experiment.Experiment.coverage`
and {meth}`~exporgo.experiment.Experiment.discover`: membership across stores and resources, plus an
open-world `unregistered` bucket for on-disk data that was never registered. See
[Coverage and validation](../explanation/coverage-and-validation).

```{eval-rst}
.. autoclass:: exporgo.experiment.ValidationReport
   :members:

.. autoclass:: exporgo.experiment.CoverageReport
   :members:
```
