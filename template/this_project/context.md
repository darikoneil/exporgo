# {{PROJECT_NAME}}

- **Status:** {{STATUS}}
- **Owner:** {{OWNER}} · {{OWNER_EMAIL}} · created {{CREATED_DATE}}

## Aims

<!-- What the project is trying to establish, if it has stated aims. Projects already underway
(or that never went through a proposal) may not have any — delete this section if so. -->

## Repositories

<!-- One line per repo: URL — what it holds. There is usually more than one. Repos tied to a
single experiment belong in that experiment's resources.md instead. -->

## Data

<!-- General pointers only (lab share, acquisition machines, big storage). Each experiment
records its own raw/processed locations in experiments/<name>/resources.md. -->

## Where to look

This file is intentionally short — it loads on every prompt. It points; it does not contain.

- **`experiments/`** — one folder per experiment, each with its scientific description, protocol,
  analysis/pipeline, and resource locations (repo, data). Open the one for the task at hand.
- **`plans/`** — unexecuted aims, ideas, and timelines (things not yet being done).
- **`visuals/`** — figures, panels, schematics, illustrations.
- **`literature/`, `manuscript/`, `presentations/`** — references and writing.
- **`.claude/skills/`** — reusable skills; `SKILLS.md` indexes them; Python conventions in
  `.claude/skills/exporgo/code/CLAUDE.md`.

> Agents: read this file first, then open only the specific `experiments/<name>/` file the task
> needs — don't load the whole project. Anything still in double braces was not filled at setup.
