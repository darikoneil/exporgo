# Record files with a file map

Some files don't fit a store and aren't a single templated blob: a suite2p output is five
`.npy` files across per-plane folders; raw acquisitions live anywhere on an external drive. A
**file map** indexes those, per identity, keyed by each file's path **relative to that
identity's root** — so `plane0/F.npy` and `plane1/F.npy` never collide. See [Resources, stores,
and file maps](../explanation/components) for how it differs from the other components, and
[Choosing a component](../explanation/choosing-a-component) to confirm a file map is the right
tool before you reach for one.

A file map has one mode, fixed when you declare it:

- **templated** — a `root_template` derives each identity's root folder.
- **recorded** — you hand it the folder (or pin loose files yourself).

These examples assume a `study` with `Subject` and `Session` keys.

## Templated: a derived root (suite2p)

When the layout is predictable, give the file map a `root_template` over the identity keys. It
resolves each identity's root, so `discover` needs no path:

```python
s2p = study.declare_filemap("suite2p", root_template="{Subject}/{Session}/suite2p")
s2p.discover(pattern="*.npy", Subject="m01", Session=1)
```

```text
{'plane0/F.npy': PosixPath('/data/study/m01/1/suite2p/plane0/F.npy'),
 'plane0/Fneu.npy': PosixPath('/data/study/m01/1/suite2p/plane0/Fneu.npy'),
 'plane0/iscell.npy': PosixPath('/data/study/m01/1/suite2p/plane0/iscell.npy'),
 'plane1/F.npy': PosixPath('/data/study/m01/1/suite2p/plane1/F.npy'),
 'plane1/Fneu.npy': PosixPath('/data/study/m01/1/suite2p/plane1/Fneu.npy')}
```

The keys are relative paths, so the two planes' `F.npy` sit side by side without collision.
`discover` **reconciles** on every call — re-run it and new files appear, deleted ones drop.

## Recorded: a root you supply

For files that follow no pattern, declare the file map without a template and hand `discover`
the folder — that folder becomes the identity's root:

```python
raw = study.declare_filemap("raw")
raw.discover("Z:/scope/2026-01-15/m01", Subject="m01", Session=1)
```

Or pin loose files one at a time with {meth}`~exporgo.study.FileMap.record` (the key defaults
to the file's name):

```python
raw.record("Z:/scope/2026-01-15/m01_run1.tif", Subject="m01", Session=1)  # key "m01_run1.tif"
raw.record("Z:/other/red.tif", name="red", Subject="m01", Session=1)      # key "red"
```

Paths are stored as-given (typically absolute, outside the study root); nothing is required to
exist yet, and nothing is copied. Records persist to a `_filemap.json` sidecar.

## Look files up: exact key or glob

Retrieval dispatches on `*`. A selector without one is an exact key; a selector with one is a
glob (an {mod}`fnmatch` pattern where `*` crosses `/`, so `*iscell*` finds the file anywhere in
the tree):

```python
s2p.path("plane0/F.npy", Subject="m01", Session=1)   # exact key -> one Path
s2p.path("*iscell*", Subject="m01", Session=1)        # glob -> the one iscell file
```

{meth}`~exporgo.study.FileMap.path` returns exactly one file: it raises `KeyError` if nothing
matches and a `ValueError` if a glob is ambiguous (`"*/F.npy"` matches both planes). For many
files at once, {meth}`~exporgo.study.FileMap.paths` returns a `{key: Path}` mapping — all of
them, or all matching a glob:

```python
s2p.paths(Subject="m01", Session=1)                  # every file
s2p.paths("*.npy", Subject="m01", Session=1)          # every .npy
s2p.paths("plane0/*", Subject="m01", Session=1)       # just plane0
```

## Existence and validation

{meth}`~exporgo.study.FileMap.exists` reports whether an identity has recorded files and *all*
of them are present — which is what {meth}`~exporgo.study.Study.validate` checks. So a file map
participates in validation and coverage exactly like a resource: it just indexes locations
instead of deriving a single one. {meth}`~exporgo.study.FileMap.identities` lists the identities
with at least one recorded file.

## Two file maps in one study: templated and recorded together

A study often needs both modes at once: predictable processing output *and* raw files that landed
wherever the scope wrote them. Declare one file map of each kind — the modes are independent, and
each identity is indexed separately in its own map.

```python
# Predictable: suite2p writes under {Subject}/{Session}/suite2p, so template the root.
s2p = study.declare_filemap("suite2p", root_template="{Subject}/{Session}/suite2p")

# Irregular: raw scope files live on an external drive under no fixed pattern.
raw = study.declare_filemap("raw")

for subject, session, scope_dir in [
    ("m01", 1, "Z:/scope/2026-01-15/m01"),
    ("m02", 1, "Z:/scope/2026-01-16/m02"),
]:
    raw.discover(scope_dir, pattern="*.tif", Subject=subject, Session=session)
    s2p.discover(pattern="*.npy", Subject=subject, Session=session)
```

Each map answers for its own files, and both feed the same validation:

```python
raw.path("*_run1*", Subject="m01", Session=1)      # a raw acquisition, by glob
s2p.path("plane0/F.npy", Subject="m01", Session=1)  # a suite2p trace, by exact key

report = study.validate()   # checks every registered identity across BOTH file maps
print(report.missing)       # (identity, "raw") or (identity, "suite2p") pairs, if any
```

A `(identity, "raw")` pair in `missing` means that session's raw files were never recorded or have
gone missing; a `(identity, "suite2p")` pair means suite2p hasn't run (or its output moved). The
component name in each pair tells you which map to look at.

## Re-discover when files are added or moved

`discover` **reconciles** — each call replaces an identity's recorded files with the folder's
current contents. That makes it the tool for keeping a file map honest as data changes, not just
for the first index.

A templated map re-derives its own root, so re-indexing is a bare re-run:

```python
# suite2p was re-run and now writes a third plane; pick it up.
s2p.discover(pattern="*.npy", Subject="m01", Session=1)
print("plane2/F.npy" in s2p.paths(Subject="m01", Session=1))   # True
```

A recorded map remembers each identity's root from the first `discover`, so re-indexing the *same*
folder also needs no path — but if the files **moved**, pass the new folder to repoint the root:

```python
# Same drive, new files dropped in: re-run with no directory to re-index the stored root.
raw.discover(Subject="m01", Session=1)

# Files were relocated to new storage: pass the new folder to update the root.
raw.discover("/archive/2026/m01", Subject="m01", Session=1)
```

To find what reconciliation should catch before you run it, {meth}`~exporgo.study.Study.validate`
flags any identity whose recorded files have since vanished:

```python
stale = [identity for identity, component in study.validate().missing if component == "raw"]
for identity in stale:
    raw.discover(Subject=identity["Subject"], Session=identity["Session"])
```

Because nothing is cached, the next `validate` reflects the reconciled state immediately — the
filesystem stays the source of truth. If a whole registry needs rebuilding from data already on
disk, see [Discover identities](discover-identities).

## Study-global files: a dump

A {class}`~exporgo.study.Dump` is a file map without the identity — one root for assets that
belong to the whole study (an atlas, a README, a shared lookup table). Same relative-path keys
and same `*`-dispatch retrieval, minus the `**identity` arguments:

```python
reference = study.declare_dump("reference")
reference.discover("Z:/atlases/allen_ccf")
reference.path("*annotation*")     # the annotation volume, wherever it sits in the tree
```
