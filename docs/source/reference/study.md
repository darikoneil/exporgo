# Study &amp; Identity (`exporgo.study`)

The Study & Identity model: the identity coordinate system
({class}`~exporgo.study.IdentitySchema`, {class}`~exporgo.study.IdentityKey`,
{class}`~exporgo.study.Identity`), the resources a study expects, and the
{class}`~exporgo.study.Study` container that ties them together and validates them. Every name
below is exported from `exporgo.study.__all__`.

## Study container

The top-level object. A {class}`~exporgo.study.Study` declares an identity coordinate system,
the identities it should contain, and the components (resources, stores, array stores, dumps)
expected at each; it describes and validates but never runs your analysis. Declarations
persist to `study.json` via {meth}`~exporgo.study.Study.save` and reload with
{meth}`~exporgo.study.Study.load`.

```python
study = Study("mouse_study", "/data/mouse_study", identity=["Subject", "Session"])
study.register(Subject="m01", Session=1)
study.declare_resource("raw", "{Subject}/{Session}/raw.tif")
```

```{eval-rst}
.. autoclass:: exporgo.study.Study
   :members:
```

## Identity coordinate system

An identity names one addressable unit of data. An {class}`~exporgo.study.IdentitySchema` is the
ordered set of one to three {class}`~exporgo.study.IdentityKey` columns (each with a name and a
dtype: `"str"`, `"int"`, or `"bool"`); an {class}`~exporgo.study.Identity` is a concrete point
in that coordinate system, e.g. `Subject="m01", Session=1`. These keys become the datastore's
partition keys, so a store partition and an identity are the same thing.

```{eval-rst}
.. autopydantic_model:: exporgo.study.IdentitySchema
   :members:

.. autoclass:: exporgo.study.IdentityKey
   :members:

.. autoclass:: exporgo.study.Identity
   :members:
```

## Resources

A resource is a file or folder exporgo reads but doesn't own, located by a path template over the
identity keys. {class}`~exporgo.study.ResourceSpec` is the declaration (a name plus a template);
{class}`~exporgo.study.Resource` binds it to a study root so you can resolve concrete paths,
check existence, and reverse-resolve the template to discover identities on disk. Reach for one
when the data is a single nameable path — see [Choosing a component](../explanation/choosing-a-component).

```{eval-rst}
.. autopydantic_model:: exporgo.study.ResourceSpec
   :members:

.. autoclass:: exporgo.study.Resource
   :members:
```

## Dumps

A {class}`~exporgo.study.Dump` indexes many files under one study-global root, keyed by each
file's path relative to that root, so same-named files in different subfolders never collide. It
is for shared assets that belong to no single identity — an atlas, a README, a lookup table. It
copies nothing; the index persists to a `_dump.json` sidecar in the dump's own directory under
the study root, however far away the files themselves live.

```{eval-rst}
.. autoclass:: exporgo.study.Dump
   :members:
```

## Reports

Two frozen, handle-free snapshots. {class}`~exporgo.study.ValidationReport` is the outcome of
{meth}`~exporgo.study.Study.validate`: a closed-world, existence-only check of whether each
registered identity's resource files still exist.
{class}`~exporgo.study.CoverageReport` is the outcome of {meth}`~exporgo.study.Study.coverage`
and {meth}`~exporgo.study.Study.discover`: membership across stores and resources, plus an
open-world `unregistered` bucket for on-disk data that was never registered. See
[Coverage and validation](../explanation/coverage-and-validation).

```{eval-rst}
.. autoclass:: exporgo.study.ValidationReport
   :members:

.. autoclass:: exporgo.study.CoverageReport
   :members:
```
