# exporgo 2.0 — Architecture & Logging Module Design

*Design record, 2026-08-23.*

## Context

This began as a plan to consolidate utilities shared across Darik's repos into one
package (`dlis`). Through design discussion it became clear two different kinds of
thing were being conflated: a stateless **utilities** grab-bag, and a stateful
**framework** for organizing/monitoring scientific studies. They have different
dependency profiles, stability, and audiences, so they are split into two repos.

## The ecosystem: two packages

### `dlis` — utilities (separate repo)
Stateless, low-dependency grab-bag: visuals/plot styles, file pickers, decorators,
small helpers. Heavy libs (matplotlib, pandas) live behind optional extras
(`dlis[vis]`, `dlis[analysis]`). Depends on nothing else in the ecosystem.

### `exporgo` v2 — the framework (this repo)
Successor to the original `exporgo`, rebuilt as layers:

| Layer | Install | Deps | Purpose |
|---|---|---|---|
| **logging** | base | `loguru` | Reusable logging framework (this document's build). Foundation. |
| **organization** | `exporgo[monitor]` | `pydantic` | Study → subjects → paths model + file-existence self-validation. *(future)* |
| **monitoring / manifest** | `exporgo[monitor]` | `pydantic` | Progress *derived* from filesystem (outputs exist & fresh), rendered into an agent-readable map. *(future)* |

> **Update (2026-08-24):** the "organization" row above has since been split into two
> built layers — the **Study & Identity model** (in the base install, not a separate extra) and
> **`exporgo[datastore]`** (polars/Parquet component stores). Monitoring remains planned.
> See `2026-08-23-study-identity-design.md` and `2026-08-23-datastore-design.md`.

**Guiding principle:** exporgo *describes, validates, and reports* — it never executes
the analysis. Orchestration is delegated to project code or an LLM agent that reads the
validated map and acts. Progress is **derived** from the filesystem (declared outputs'
existence/freshness), not tracked in a mutable ledger — so "self-validate existence",
DVC-style staleness, and progress-monitoring are one mechanism.

exporgo's base install is **loguru + pydantic + tomli-w** (the log + study foundation); it
pulls no matplotlib and none of the heavy analytical stack (numpy/polars/pyarrow live only in
the `datastore` extra). *(Corrected 2026-08-29: the base is no longer loguru-only.)*

## Build sequence

1. **Now — logging module** (this document). The spine everything builds on.
2. **Next — organization + monitoring.** Its own brainstorm → spec → build session.
3. **Anytime — `dlis` utilities**, independently.

---

## Logging module design (first build)

Ported and improved from `dariks_fomo/fomo/log.py` (the strongest existing logger,
already backed by a ~420-LOC test suite). Not copy-pasted — reworked to fix three
things and to pass this repo's strict `ruff ALL` + Google-docstring + keyword-only gate.

### Layout — `exporgo/log/` subpackage

| File | Contents |
|---|---|
| `exporgo/log/__init__.py` | Public API re-exports + `__all__`. |
| `exporgo/log/levels.py` | `LogLevel(IntEnum)` — NOTSET/TRACE(5)/DEBUG/INFO/SUCCESS(25)/WARNING/ERROR/CRITICAL. |
| `exporgo/log/rendering.py` | `render_object` (`singledispatch`): stdlib collection/dict handlers + **lazily-registered** numpy/polars handlers. |
| `exporgo/log/sinks.py` | Formats, filters, sink builders, `init_logger(...)`, optional `reset_tqdm`. |
| `exporgo/log/decorators.py` | `log_function_call`, `log_major_function_call`, `log_class` + `_report_*` helpers. |

Dependency order: `levels` ← `rendering` ← `decorators`; `levels` ← `sinks`.
`exporgo/__init__.py` adds `logger.disable("exporgo")` so importing the package is
silent until `init_logger` runs.

### Three improvements over fomo

1. **Parameterized for reuse.** `init_logger(name=None, base_directory=None, *,
   log_level_console=INFO, log_level_custom=None, file_stem=None)`. `name` selects the
   loguru namespace to enable (`logger.enable(name)`, or enable-all when `None`);
   `file_stem` (default `name or "exporgo"`) drives log filenames. Replaces fomo's
   hardcoded `"fomo"` / `fomo.log`.
2. **numpy/polars stay optional.** Their rich renderers register only if importable, so
   the base install needs neither; output degrades to `str()` when absent.
3. **Conventions.** Google docstrings, full type hints, keyword-only args beyond three,
   `__all__` limited to the public surface.

### Optional `reset_tqdm`
An import-gated sink (`tqdm.write`) so progress bars and logs coexist; raises a clear
`ImportError` if tqdm is absent. `tqdm` is in the `dev` group for testing.

### Testing (TDD)
Adapt `dariks_fomo/tests/test_log.py` (monkeypatches loguru, asserts exact sink
kwargs — transfers almost verbatim). Write/adjust tests first, watch fail, implement.
Add coverage for the new parameterization (custom `name`/`file_stem`, enable-all,
warn-without-directory) and the lazy-rendering fallback. Coverage floor 75%.

### Verification
`uv run ruff format --check .` · `uv run ruff check .` · `uv run pyrefly check` ·
`uv run coverage run && uv run coverage report`, plus a scratchpad smoke test of
`init_logger` + a decorated function writing real console/file output.
