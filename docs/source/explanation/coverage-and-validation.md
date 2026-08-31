# Coverage and validation

exporgo answers two different questions about your data, and it's worth knowing which is which.
{meth}`~exporgo.study.Study.validate` asks *is what I registered still there?*
{meth}`~exporgo.study.Study.coverage` asks *which identities does each component actually
contain, registered or not?* One is a liveness check; the other is a membership-and-drift
report.

## Closed world versus open world

The distinction underneath both is **closed-world** versus **open-world** reporting.

A **closed-world** view starts from the registry (the identities you declared the study should
contain) and checks each one. It can tell you an expected identity is *missing*, but it can
never surface data you never registered, because it never looks beyond the registry.

An **open-world** view starts from the disk. It reads what's physically present (a store's
manifest, a file map's records, a resource template reverse-resolved against the tree), and so
it *can* surface identities that exist on disk but were never registered. That surplus is
**drift**.

## `validate`: liveness, closed-world

{meth}`~exporgo.study.Study.validate` walks every registered identity and checks that the files
it *points at* still exist: each declared resource (does its resolved path exist?) and each
declared file map (are its recorded files present?). Every `(identity, component)` pair lands
in `present` or `missing`. It's existence-only: file contents are never read.

It's closed-world by design. `validate` catches data that was expected, or once recorded, and
has since been deleted or moved — the thing you want to know before a pipeline run. Stores are
out of scope here: they hold exporgo-owned data, not files the study merely points at, so their
membership is a coverage concern. The report holds no live handles, so it's safe to store or
diff across runs.

## `coverage`: membership plus drift

{meth}`~exporgo.study.Study.coverage` generalizes `validate` across resources, stores, *and*
file maps, and adds the open-world piece. It classifies every `(registered identity,
component)` pair as `present` or `missing`, and it collects a third bucket, `unregistered`:
identities physically present in a store or file map that were never registered.

```text
CoverageReport: 4 present, 2 missing, 0 unregistered (incomplete)
  missing:
    behavior: Subject=m02/Session=1
    raw: Subject=m02/Session=1
  present:
    behavior: Subject=m01/Session=1
    ...
```

The three buckets answer three questions: `missing` is *expected but absent*, `unregistered`
is *present but unexpected*, and `present` is *as it should be*. For a filterable view,
{meth}`~exporgo.study.CoverageReport.to_polars` reshapes the report into a tidy long frame: one
row per `(identity, component)`, the identity keys exploded into columns, plus `component` and
`status`.

## `discover`: the open-world view of resources

A store and a file map are already open-world in `coverage`, because each keeps its own record
of what it contains. A resource has no such record — it only derives paths. That's what
{meth}`~exporgo.study.Study.discover` is for: it reverse-resolves each resource template to
find which identities physically match, so on-disk-but-unregistered resource data surfaces as
`unregistered` drift too. Pass `register=True` and the discovered full-key identities are
folded into the registry, bootstrapping a study from data that already exists. See
[Discover identities](../how-to/discover-identities).

## The filesystem is the source of truth

None of these reports cache. `validate`, `coverage`, and `discover` all read the tree (and the
store manifests) at call time, every time, and a loaded study re-derives status rather than
trusting a stored ledger. Status is *derived*, never recorded — so it can't drift out of sync
with reality, and a report is always a snapshot of the tree as it is right now.
