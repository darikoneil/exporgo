# Discover identities from an existing dataset

You already have data on disk and want an experiment registry that matches it — without typing out
every `register(...)` call by hand. exporgo can reverse-resolve your resource templates to find
what's there and seed the registry from it.

## See what's on disk

Declare the resource whose template matches your existing layout, then call
{meth}`~exporgo.experiment.Experiment.discover`. It reverse-resolves the template against the experiment root
and reports every identity it finds. With an empty registry, everything on disk shows up as
`unregistered` drift:

```python
from exporgo.experiment import IdentityKey, Experiment

experiment = Experiment("mouse_experiment", root, identity=["Subject", IdentityKey(name="Session", dtype="int")])
experiment.declare_resource("raw", "{Subject}/{Session}/raw.tif")

print(experiment.discover())
```

```text
CoverageReport: 0 present, 0 missing, 3 unregistered (complete)
  unregistered:
    raw: Subject=m01/Session=1
    raw: Subject=m01/Session=2
    raw: Subject=m03/Session=1
```

```{note}
The report says `(complete)` even with drift present. Completeness reflects only the `missing`
bucket (every *registered* identity is accounted for), so an empty registry is trivially
complete. The three `unregistered` entries are what there is to act on.
```

## Seed the registry

{meth}`~exporgo.experiment.Experiment.sync_registry` is the one-call bootstrap. It sweeps every declared
component: resources (reverse-resolved) and stores and array stores (their manifests). It
registers each full-key identity that isn't registered yet, returning the ones it added in path
order:

```python
print(experiment.sync_registry())
```

```text
(Identity(Subject='m01', Session=1), Identity(Subject='m01', Session=2), Identity(Subject='m03', Session=1))
```

Discover again and the drift is gone — the same identities are now `present`:

```python
print(experiment.discover())
```

```text
CoverageReport: 3 present, 0 missing, 0 unregistered (complete)
  present:
    raw: Subject=m01/Session=1
    raw: Subject=m01/Session=2
    raw: Subject=m03/Session=1
```

`sync_registry` is idempotent: running it again registers nothing and returns an empty tuple.

## discover(register=True) versus sync_registry

Both bootstrap the registry; they differ in scope.

- {meth}`Experiment.discover(register=True) <exporgo.experiment.Experiment.discover>` is
  **resource-only**. It builds the drift report, then registers the discovered full-key
  identities. Reach for it when you want the report *and* the bootstrap in one call, from
  resource templates.
- {meth}`~exporgo.experiment.Experiment.sync_registry` sweeps **every identity-bearing component**:
  resources, stores, and array stores together (dumps have no identity, so they're never
  swept). Reach for it to seed a registry from everything on disk at once.

Either way, only **full-key** identities are registered: a subset-key store or template yields a
partial identity that can't form a complete address, so it's reported as drift but never
auto-registered. And the report `discover` returns always reflects the state *before*
bootstrapping, so the drift it resolved stays visible in it.
