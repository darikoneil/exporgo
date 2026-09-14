# CLAUDE.md — project workspace orientation

Read `context.md` first. This folder is a **science project workspace**: the project's brain, not
its code or data. It holds context, documented experiments, plans, a full copy of the skills, and
reusable assets. Code lives in the project's GitHub repo; data lives on the lab share. This file is
project-agnostic (identical in every copy) and is **overwritten by `exporgo update`** — the
project-specific facts are in `context.md` and the `experiments/` files, and project-specific
standing instructions belong in `.claude/local.md` (imported below, never overwritten).

@.claude/local.md

## Read order (keep context small)

1. **`context.md`** — short by design; the aim, status, where things live, and pointers.
2. **The specific `experiments/<name>/` file the task needs** — `analysis.md` for an analysis
   question, `resources.md` to locate data or code, `protocol.md` for how data was produced. Open
   only what the task needs; do not load every experiment.
3. **`plans/`** only when the task is about future/unstarted work.

## What this folder is

- **`exporgo.toml`** — the project manifest (name, created date, template version, stamp values).
  Written by `exporgo new`; its presence is what marks this folder as an exporgo project.
- **`context.md`** — the router and source of truth for the big picture and locations.
- **`experiments/`** — one folder per experiment: description, protocol, analysis, resources.
- **`plans/`** — unexecuted aims, ideas, timelines (what you intend to do).
- **`.claude/skills/`** — the full skills library, carried per project. Index: `SKILLS.md`.
  `skills/exporgo/` is shipped and overwritten on update; `skills/local/` is this project's own.
- **Reusable assets** — `visuals/`, `literature/`, `manuscript/`, and the rest.

## Hard rules

1. **No code or raw data in this workspace.** Analysis code goes in the project's repo; data stays
   on the lab share. If asked to write a script "here," clarify it belongs in the repo — unless it's
   a *reusable procedure*, which belongs in `.claude/skills/` as a skill.
2. **Locations are canonical, never guessed.** Use the GitHub URLs and UNC paths in `context.md` and
   each experiment's `resources.md`. If a path isn't recorded, ask.
3. **Keep the docs current and small.** When work reveals a new or moved location, update the right
   `resources.md` (or `context.md`) the same session, and say so. Don't let `context.md` grow —
   detail belongs in the experiment files.
4. **Plans vs. experiments.** `plans/` is intent; `experiments/` is execution. Promote a plan by
   copying `experiments/_TEMPLATE/` into a new experiment folder.
5. **Never edit `.claude/skills/exporgo/` in a project.** Those files are overwritten by
   `exporgo update`; improvements go to the template repo. Project-specific skills go in
   `.claude/skills/local/`, and project-specific instructions in `.claude/local.md`.

## Reach for the right tool

- **Start a new project** → the `exporgo` CLI: `exporgo new <name>` (flags for aim/repo/data-root/
  status; prompts for anything missing; `--git` to init a repo — it never commits).
- **Update a project from the template** → `exporgo check` to preview, then `exporgo update`.
  Refreshes only the exporgo-owned files; never touches project content.
- **Sync data and outputs across machines** → `exporgo sync` (paths from `exporgo.toml`'s
  `[sync]` section or flags); the `gdrive-folder-sync` skill
  (`.claude/skills/exporgo/sync/SKILL.md`) is the operational guide. Data travels via Drive,
  the template via the binary.
- **Write or review Python** → `.claude/skills/exporgo/code/CLAUDE.md` (uv; ruff; pyrefly;
  Google-style docstrings; never commit or push). Review/doc agents in `code/agents/`.
- **Science procedures** → `.claude/skills/exporgo/science/`.
- **This project's own procedures** → `.claude/skills/local/`.
- Full catalog: `SKILLS.md`.

## Environment note

The cloud/Cowork side cannot reach the lab share (`\\ktdata\snlkt`), the `G:` Drive mount, or
mapped drives — those are local to the machine. The `exporgo` binary (including `exporgo sync`)
runs locally; cloud sessions should read and write workspace documents only.
