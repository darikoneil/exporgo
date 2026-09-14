# {{PROJECT_NAME}}

{{ONE_LINE_AIM}}

- **Status:** {{STATUS}}
- **Primary repo:** {{REPO_URL}}
- **Data root:** {{DATA_ROOT}}
- **Owner:** {{OWNER}} · {{OWNER_EMAIL}} · created {{CREATED_DATE}}

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
