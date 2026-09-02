# exporgo — Removing file maps

*Design record, 2026-09-01. A deletion, not a feature. **Done & verified 2026-09-01**
(ruff/pyrefly clean; 193 tests pass). Supersedes the `FileMap` sections of
[the Study & Identity design](2026-08-23-study-identity-design.md).*

## What was removed

`FileMap` — the per-identity index of many files keyed by relative path, in templated and
recorded modes, with its `_filemap.json` sidecar. With it went `Study.declare_filemap`,
`Study.filemap`, `Study.filemaps`, the `filemap=` argument to `Study.identities`, and the
file-map arms of `validate`, `coverage`, `sync_registry`, `save`, and `load`.

A depth-and-fingerprint feature built on top of `FileMap` the same day — folder-granularity
recording, two-tier content fingerprints, and a `Study.drift()` report answering "have these
files changed since I recorded them?" — was removed with it, before it was ever committed.

`Dump` survives unchanged and moved into `resources.py`, since it was the only remaining
inhabitant of `filemaps.py`.

## Why

The study now has four components: resources, tabular stores, array stores, and dumps.

`FileMap` earned its place on a real observation — a suite2p output tree is five `.npy` files
across per-plane folders, and a resource template names only one path. But addressing those
files individually turned out to be a want, not a need: a resource can name the *folder*
(`Resource.exists()` and `Resource.discover()` both match directories), and reading files inside
a folder is what `pathlib` is for. What `FileMap` actually bought over that was a persisted index
— and a persisted index is a second source of truth about the filesystem, which the architecture
otherwise refuses to keep.

The fingerprint work made the cost visible. Answering "did this change?" required a depth axis, a
tier system, scope pinning, a fourth report type, and a terminology collision with the existing
open-world sense of "drift" — roughly 630 lines and five documentation pages, to defend against a
silent re-run that had not yet happened to anyone. That is the shape of a feature answering a
question the project has not yet been asked.

Removing the fingerprints alone would have left `FileMap` behind. It was worth asking whether
`FileMap` itself was carrying its weight, and it was not.

## What this costs

Nothing addresses a per-identity folder of many files by relative key any more. A suite2p tree is
a resource pointing at the folder, and per-file addressing is caller code. Glob-based retrieval
across a tree (`s2p.path("*iscell*", ...)`) is gone; `Path.rglob` covers it.

No migration path is provided. `FileMap` was never released, so any `_filemap.json` on disk is an
inert file that nothing reads. `Study.load` ignores a `"filemaps"` key in an old `study.json`
without comment.

## If this comes back

The thing to re-derive first is not `FileMap` but the question it was answering. "I need to
address individual files inside a per-identity folder" is served by a resource plus `pathlib`
until someone can say what the persisted index buys that a live directory walk does not. "I need
to know whether my inputs changed underneath me" is a genuinely different feature with a
different cost model, and it does not need `FileMap` to exist — a fingerprint could hang off a
resource just as well.
