# Installation

exporgo requires **Python 3.12 or newer**.

## Base install

The base install is the **logging** and **study** layers together. It depends only on
`loguru` and `pydantic`. With [uv](https://docs.astral.sh/uv/):

```bash
uv add exporgo
```

## Optional layers

The heavier layers are optional extras. Add them when you need them:

```bash
uv add "exporgo[datastore]"   # polars/Parquet component stores (adds polars, pyarrow, numpy)
```

The **monitoring** layer (`exporgo[monitor]`) is planned and not yet implemented; its extra
is currently a placeholder.

## From source

To work on exporgo itself, clone the repository and sync the full development environment:

```bash
uv sync
```

Add extras to the synced environment as needed:

```bash
uv sync --extra datastore
```
