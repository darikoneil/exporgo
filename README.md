# exporgo (2.0)

Experiment organization, logging, and analysis monitoring for scientific studies.
The successor to the original `exporgo`, rebuilt as a layered framework.

## Layers

- **logging** (base install, `loguru` only) — a reusable logging framework:
  parameterized console + rotating file/exception sinks and logging decorators
  that any project can drive via `init_logger(name="my_project", ...)`.
- **organization + monitoring** (`exporgo[monitor]`, adds `pydantic`) — a
  study/subject/path model, file-existence self-validation, and progress tracking
  *derived* from the filesystem, rendered into an agent-readable map. *(Planned;
  not yet implemented.)*

`exporgo` never executes your analysis — it **describes, validates, and reports**,
leaving orchestration to your code or an LLM agent.

## Installation

For development, using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
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
