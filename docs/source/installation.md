# Installation

exporgo requires **Python 3.12 or newer**.

## Base install

The base install is the **logging** and **experiment** layers together. It depends only on
`loguru` and `pydantic`. With [uv](https://docs.astral.sh/uv/):

```bash
uv add exporgo
```

## Optional layers

The heavier layers are optional extras. Add them when you need them:

```bash
uv add "exporgo[datastore]"   # polars/Parquet component stores (adds polars, pyarrow, numpy, xarray)
```

The **monitoring** layer (`exporgo[monitor]`) is planned and not yet implemented; its extra
is currently a placeholder.

### Loading a datastore-bearing experiment on a base install

The layers are separable at runtime, and exporgo says so when you cross a boundary.
{meth}`~exporgo.experiment.Experiment.load` on an `experiment.json` that declares any store or
array store needs the datastore layer to rebuild those specs, so on a base install it raises an
`ImportError` naming the extra:

```text
ImportError: Experiment 'mouse_experiment' declares stores or array stores, which require the
datastore layer; install the datastore extra (exporgo[datastore]).
```

Two other calls fail the same way for the same reason:
{meth}`~exporgo.experiment.CoverageReport.to_polars` needs polars, and
{meth}`~exporgo.datastore.ArrayStore.load` needs xarray. Both ship with the `datastore` extra.

## Upgrading from 2.x

The unit that was a *study* in 2.x is an {class}`~exporgo.experiment.Experiment` in 3.x, and its
on-disk manifest was renamed with it: `study.json` became `experiment.json`. There is no
back-compatible read, since 3.x looks for `experiment.json` and nothing else, so the migration is
renaming the file:

```powershell
Rename-Item <root>\study.json experiment.json
```

or, on macOS/Linux:

```bash
mv <root>/study.json <root>/experiment.json
```

Nothing inside the file has to change. The manifest's keys (`name`, `identity`, `resources`,
`stores`, `array_stores`, `dumps`) and the `entities.jsonl` registry sidecar beside it are
unchanged, and a manifest with no `"format"` field is read as a legacy file and accepted (see
[Persistence](explanation/architecture.md#persistence)). The next
{meth}`~exporgo.experiment.Experiment.save` stamps `"format": 1` into it. One 2.x-era key is an
exception: a manifest still carrying the long-removed `"filemaps"` key loads with a logged
warning, and the next save drops the key.

In code, `exporgo.study` becomes `exporgo.experiment`, `Study` becomes `Experiment`, and the
per-experiment log directory is still `<root>/.logs/`.

## From source

To work on exporgo itself, clone the repository and sync the full development environment:

```bash
uv sync
```

Add extras to the synced environment as needed:

```bash
uv sync --extra datastore
```
