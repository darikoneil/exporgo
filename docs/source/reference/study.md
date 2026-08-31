# Study &amp; Identity (`exporgo.study`)

The Study & Identity model: the identity coordinate system
({class}`~exporgo.study.IdentitySchema`, {class}`~exporgo.study.IdentityKey`,
{class}`~exporgo.study.Identity`), the resources and file maps a study expects, and the
{class}`~exporgo.study.Study` container that ties them together and validates them. Every name
below is exported from `exporgo.study.__all__`.

## Study container

The top-level object. A {class}`~exporgo.study.Study` declares an identity coordinate system,
the identities it should contain, and the components (resources, stores, array stores, file maps,
dumps) expected at each; it describes and validates but never runs your analysis. Declarations
persist to `study.toml` via {meth}`~exporgo.study.Study.save` and reload with
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

## File maps and dumps

A {class}`~exporgo.study.FileMap` indexes many files per identity, keyed by each file's path
relative to that identity's root, so same-named files in different subfolders never collide. Its
mode is fixed at declaration — *templated* (a `root_template` derives each identity's root) or
*recorded* (you supply the folder, or pin loose files). A {class}`~exporgo.study.Dump` is the
same index without the identity dimension: one study-global root for shared assets. Neither copies
data; both persist to a JSON sidecar.

```{eval-rst}
.. autoclass:: exporgo.study.FileMap
   :members:

.. autoclass:: exporgo.study.Dump
   :members:
```

## Reports

Two frozen, handle-free snapshots. {class}`~exporgo.study.ValidationReport` is the outcome of
{meth}`~exporgo.study.Study.validate`: a closed-world, existence-only check of whether each
registered identity's resource and file-map files still exist.
{class}`~exporgo.study.CoverageReport` is the outcome of {meth}`~exporgo.study.Study.coverage`
and {meth}`~exporgo.study.Study.discover`: membership across stores, resources, and file maps,
plus an open-world `unregistered` bucket for on-disk data that was never registered. See
[Coverage and validation](../explanation/coverage-and-validation).

```{eval-rst}
.. autoclass:: exporgo.study.ValidationReport
   :members:

.. autoclass:: exporgo.study.CoverageReport
   :members:
```
