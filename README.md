# exporgo

Experiment organization, logging, and analysis monitoring for scientific studies.
The successor to the original `exporgo`, rebuilt as a layered framework.

`exporgo` never executes your analysis — it **describes, validates, and reports**,
leaving orchestration to your code or an LLM agent.

## Layers

- **logging** (base install, `loguru` only) — a reusable logging framework:
  parameterized console + rotating file/exception sinks and logging decorators
  that any project can drive via `init_logger(name="my_project", ...)`.
- **experiment** (base install, adds `pydantic`) — the Experiment & Identity model.
  An experiment is the data-side unit living at the data root on the lab server:
  one root, one identity coordinate system (1–3 keys, default `Subject`), one
  store catalog, plus the resources (files/folders) it expects at each identity
  and file-existence self-validation. Declarations persist to `experiment.json`
  (with registered identities in an `entities.jsonl` sidecar) and reload via
  `Experiment.load(root)`. Saving an experiment also wires up logging into
  `<root>/.logs/` (a per-writer log, merged on read), so every experiment gets
  logging for free. A workspace's `experiments/<name>/` folder (Rust CLI side)
  merely points at that data root.
- **datastore** (`exporgo[datastore]`, adds `polars`/`pyarrow`/`numpy`) — fast,
  schema-enforced polars/Parquet component stores for an experiment's bulk data
  (behavior, neural, …), Hive-partitioned on the identity keys, with lazy,
  partition-pruned retrieval and append / overwrite-by-key writes.
- **monitoring** (`exporgo[monitor]`) — progress *derived* from the filesystem
  (declared outputs' existence/freshness), rendered into an agent-readable map.
  *(Planned; not yet implemented.)*

## Workspace CLI (Rust)

Alongside the Python package, this repo carries a **Rust CLI** (crate at the repo root,
`src/` + `Cargo.toml`) that stamps and maintains *project workspaces* from the template in
[`template/`](template/README.md). The template is embedded in the
binary at build time, so the crate version is the template version and no network or toolchain
is needed on lab machines — install a binary from GitHub Releases.

```bash
exporgo config --remote-root "G:\\My Drive\\exporgo-projects"   # once per machine
exporgo new "Grid Cell Remapping" --status active   # stamp a project (owner/email from config)
exporgo check    # report drift from this binary's template
exporgo update   # refresh exporgo-owned files; never touches project content
exporgo sync     # converge this workspace with its shared remote (pull newer, push newer)
exporgo clone "Grid Cell Remapping"     # bring an existing project onto this machine
exporgo experiment new "Remap Pilot"    # stamp experiments/_TEMPLATE/ inside the project
```

## Installation

For development, using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

The base install includes the experiment layer. Add the datastore extra as needed:

```bash
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
