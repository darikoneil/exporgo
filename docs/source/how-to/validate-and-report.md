# Validate and report on an experiment

Once an experiment is registered and has data, you'll want to ask what's there and what's missing.
exporgo gives you a quick liveness check and a fuller report. This guide shows both and how to
filter the result. For the concepts behind the two, see [Coverage and
validation](../explanation/coverage-and-validation).

## Quick liveness check

{meth}`~exporgo.experiment.Experiment.validate` checks that every registered identity's *indicated* files
(its resources) still exist on disk:

```python
report = experiment.validate()
print(report.is_complete)
print(report.missing)
```

```text
False
((Identity(Subject='m02', Session=1), 'raw'),)
```

`report.present` and `report.missing` are lists of `(identity, component)` pairs;
`report.is_complete` is `True` exactly when nothing is missing. It's existence-only: file
contents are never read. Stores are out of scope (use `coverage` for those).

## The full report

{meth}`~exporgo.experiment.Experiment.coverage` reports every registered identity against every
identity-bearing component (resources, stores, and array stores; dumps have no identity and are
excluded) and adds anything on disk that was never registered:

```python
print(experiment.coverage())
```

```text
CoverageReport: 4 present, 2 missing, 0 unregistered (incomplete)
  missing:
    behavior: Subject=m02/Session=1
    raw: Subject=m02/Session=1
  present:
    behavior: Subject=m01/Session=1
    behavior: Subject=m01/Session=2
    raw: Subject=m01/Session=1
    raw: Subject=m01/Session=2
```

The report object carries helpers for drilling in:

```python
coverage = experiment.coverage()
print(coverage.identities("behavior"))          # identities present in one component
print(coverage.components(some_identity))         # components that contain one identity
```

## Filter it as a DataFrame

For anything beyond eyeballing, {meth}`~exporgo.experiment.CoverageReport.to_polars` reshapes the
report into a tidy long frame — one row per `(identity, component)`, the identity keys exploded
into their own columns, plus `component` and `status`:

```python
import polars as pl

frame = experiment.coverage().to_polars()
print(frame.filter(pl.col("status") == "missing"))
```

```text
shape: (2, 4)
┌─────────┬─────────┬───────────┬─────────┐
│ Subject ┆ Session ┆ component ┆ status  │
│ ---     ┆ ---     ┆ ---       ┆ ---     │
│ str     ┆ i64     ┆ str       ┆ str     │
╞═════════╪═════════╪═══════════╪═════════╡
│ m02     ┆ 1       ┆ raw       ┆ missing │
│ m02     ┆ 1       ┆ behavior  ┆ missing │
└─────────┴─────────┴───────────┴─────────┘
```

From here it's ordinary polars — group by `component` to count gaps, pivot `status` into a
matrix, or join against another table. `to_polars` needs the datastore extra (it's where polars
lives); without it you get a clear `ImportError` pointing you to `exporgo[datastore]`.

## Inventory a single component

To ask which identities one component contains, {meth}`~exporgo.experiment.Experiment.identities` takes
exactly one target:

```python
experiment.identities(store="behavior")          # open-world: the store's manifest partitions
experiment.identities(array_store="traces")      # open-world: the array store's partitions
experiment.identities(resource="raw")            # closed-world: registered identities whose file exists
```

A store and an array store report **open-world** (whatever's on disk, including unregistered
identities); a resource reports **closed-world** (registered identities whose file exists). To
find unregistered *resource* data, use {meth}`~exporgo.experiment.Experiment.discover` (see [Discover
identities](discover-identities)).
