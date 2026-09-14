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
when the data is a single nameable path — see [Choosing a component](../explanation/choosing-a-component).

```{eval-rst}
.. autopydantic_model:: exporgo.experiment.ResourceSpec
   :members:

.. autoclass:: exporgo.experiment.Resource
   :members:
```

## Dumps

A {class}`~exporgo.experiment.Dump` indexes many files under one experiment-global root, keyed by each
file's path relative to that root, so same-named files in different subfolders never collide. It
is for shared assets that belong to no single identity — an atlas, a README, a lookup table. It
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
