# exporgo (2.0)

Experiment organization, logging, and analysis monitoring for scientific studies.
The successor to the original `exporgo`, rebuilt as a layered framework.

`exporgo` never executes your analysis — it **describes, validates, and reports**,
leaving orchestration to your code or an LLM agent.

## Layers

- **logging** (base install, `loguru` only) — a reusable logging framework:
  parameterized console + rotating file/exception sinks and logging decorators
  that any project can drive via `init_logger(name="my_project", ...)`.
- **study** (`exporgo[study]`, adds `pydantic`) — the Study & Identity model: a
  study's identity coordinate system (1–3 keys, default `Subject`), the resources
  (files/folders) it expects at each identity, and file-existence self-validation.
  Declarations persist to `study.toml` and reload via `Study.load(root)`. Saving a
  study also auto-creates a `<root>/<name>.log` the logger writes to, so every study
  gets logging for free.
- **datastore** (`exporgo[datastore]`, adds `polars`/`pyarrow`/`numpy`) — fast,
  schema-enforced polars/Parquet component stores for a study's bulk data
  (behavior, neural, …), Hive-partitioned on the identity keys, with lazy,
  partition-pruned retrieval and append / overwrite-by-key writes.
- **monitoring** (`exporgo[monitor]`) — progress *derived* from the filesystem
  (declared outputs' existence/freshness), rendered into an agent-readable map.
  *(Planned; not yet implemented.)*

## Installation

For development, using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Add optional layers as needed:

```bash
uv add "exporgo[study]"      # Study & Identity model
uv add "exporgo[datastore]"  # polars/Parquet datastore
```

## Development

```bash
uv run ruff format .
uv run ruff check .
uv run pyrefly check
uv run coverage run && uv run coverage report
```

## License

See [LICENSE](LICENSE).
