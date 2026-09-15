# exporgo

- a **workspace** — the project's brain (context, documented experiments, plans, reusable
  skills and assets), stamped and maintained by a Rust CLI and kept converged across your
  machines. It records *where* code and data live; it holds neither.
- a **Python package** — the data side: an experiment/identity model, schema-enforced Parquet
  datastores, and logging, living at the data root on the lab server.

## The workspace (Rust CLI)

A workspace is one folder per project with a deliberate shape: a short `context.md` router,
one documented folder per experiment, plans, and a full copy of the Claude skills library —
see the [template's README](template/README.md) for the layout and rules. The template ships
*inside* the `exporgo` binary (crate version == template version), so creating a project needs
no network, no toolchain, and no cloned repo — install a binary from GitHub Releases.

```bash
exporgo config --remote-root "G:\\My Drive\\exporgo-projects"   # once per machine
exporgo new "Grid Cell Remapping" --status active   # stamp a project (owner/email from config)
exporgo check    # report drift from this binary's template
exporgo update   # refresh exporgo-owned files; never touches project content
exporgo sync     # converge this workspace with its shared remote (pull newer, push newer)
exporgo clone "Grid Cell Remapping"     # bring an existing project onto this machine
exporgo experiment new "Remap Pilot"    # stamp experiments/_TEMPLATE/ inside the project
```

Two rules make this safe to automate: `update` rewrites only the exporgo-owned files (the
skills library and boilerplate), never project content; and `sync` is non-destructive
(newest file wins, nothing deleted) through a per-machine cache to a shared remote.

## The Python package

Where the workspace documents an experiment, the Python package **is** the experiment's
data-side: one data root, one identity coordinate system, one store catalog. A workspace's
`experiments/<name>/resources.md` merely points at it. Built as layers:

- **logging** (base install, `loguru` only) — a reusable logging framework:
  parameterized console + rotating file/exception sinks and logging decorators
  that any project can drive via `init_logger(name="my_project", ...)`.
- **experiment** (base install, adds `pydantic`) — the Experiment & Identity model:
  one root, one identity coordinate system (1–3 keys, default `Subject`), the
  resources (files/folders) expected at each identity, and file-existence
  self-validation. Declarations persist to `experiment.json` (registered
  identities in an `entities.jsonl` sidecar) and reload via `Experiment.load(root)`.
  Saving also wires logging into `<root>/.logs/` (a per-writer log, merged on
  read), so every experiment gets logging for free.
- **datastore** (`exporgo[datastore]`, adds `polars`/`pyarrow`/`numpy`) — fast,
  schema-enforced polars/Parquet component stores for an experiment's bulk data
  (behavior, neural, …), Hive-partitioned on the identity keys, with lazy,
  partition-pruned retrieval and append / overwrite-by-key writes.
- **monitoring** (`exporgo[monitor]`) — progress *derived* from the filesystem
  (declared outputs' existence/freshness), rendered into an agent-readable map.
  *(Planned; not yet implemented.)*

## Installation

**Workspace CLI:** download a prebuilt binary from GitHub Releases and put it on your PATH,
or build from this repo:

```bash
cargo install --path .
```

**Python package**, for development, using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

The base install includes the experiment layer. Add the datastore extra as needed:

```bash
uv add "exporgo[datastore]"  # polars/Parquet datastore
```

## Development

Python:

```bash
uv run ruff format .
uv run ruff check .
uv run pyrefly check
uv run coverage run && uv run coverage report
```

Rust (formatting needs nightly — `rustfmt.toml` uses nightly-only options):

```bash
cargo +nightly fmt
cargo clippy --all-targets -- -D warnings
cargo test
```

## License

See [LICENSE](LICENSE).
