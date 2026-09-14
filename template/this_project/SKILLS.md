# Skills index

Every reusable instruction set carried in this project, in one place. A skill is a self-contained
procedure: it makes Claude do a recurring task the same way each time. The skill files live under
`.claude/skills/`; this file is the index over them. Each project carries a **full copy** of the
library, so everything here travels with the project.

> This index sits at the workspace root, not inside `.claude/`, because the cloud file tools treat
> `.claude/` as protected. Author and edit skill *files* inside `.claude/skills/`; keep this index
> in step by hand.

Two zones, one rule: `.claude/skills/exporgo/` is the shipped library — `exporgo update`
**overwrites it**, so improve those skills upstream in the template repo, never in a project.
`.claude/skills/local/` is this project's own skills — the update never touches them.

## Catalog

### Project ops — `.claude/skills/exporgo/`

- **`sync/`** — Google Drive ↔ folder sync for **data and outputs** (not the template — that
  travels with the `exporgo` binary). `exporgo sync` runs a two-hop, non-destructive mirror
  through a durable local intermediate; paths live in the project's `exporgo.toml` `[sync]`
  section (or flags). Cross-platform; schedule with the OS scheduler. The `SKILL.md` here is the
  operational guide (mount constraints, UNC paths, scheduling).

Project ops are otherwise not skills: the **`exporgo` CLI** does the work.
`exporgo new <name>` stamps a project from the template embedded in the binary; `exporgo check`
previews what an update would change; `exporgo update` refreshes the exporgo-owned files (this
library + boilerplate) and never touches project content; `exporgo sync` moves data.

### Code — `.claude/skills/exporgo/code/`

Conventions and agents for scientific Python. Copy `code/CLAUDE.md` into a repo to enforce the
same toolchain there.

- **`CLAUDE.md`** — the rules: `uv` only (never bare `python`/`pip`), `ruff` for lint+format,
  `pyrefly` for types, Google-style docstrings, keyword-only past three args, never commit or
  push. The file to drop into a new repo's root.
- **`agents/senior-reviewer.md`** — reviews a `git diff` before commit; severity-tagged; read-only.
- **`agents/docstring-writer.md`** — Google-style docstrings for research code; never invents
  behavior; emphasizes shapes, units, mutation, unchecked assumptions.
- **`agents/documentation-writer.md`** — authors the Sphinx/ReadTheDocs site (Diátaxis); moves
  conceptual prose out of docstrings onto the site.
- **`agents/voice-matcher.md`** — restyles docs into Darik's voice without changing any fact; loads
  the private profile in `agents/references/darik-voice.md` when present.
- **`agents/copy-editor.md`** — audits docs and docstrings for stale references, doc/code
  contradictions, leftover AI/plan prose, corporate-speak, and claudisms; read-only.

### Science — `.claude/skills/exporgo/science/`

Your science procedures. Empty today; this is the half of the library to grow. Candidates below.

### Local skills — `.claude/skills/local/`

This project's own skills — never touched by `exporgo update`. Start here for anything
project-specific; promote a skill to the template repo when it proves useful across projects.

### Third-party — `.claude/skills/exporgo/third_party_skills.md`

External skill sources worth pulling from (CatalystNeuro, pynapple, marimo, and more).

## Science skills to build

Sketched, not built — pick the ones that save the most repeated effort. Each is one `SKILL.md`
(plus a `references/` folder for anything long). Author from `templates/SKILL.template.md`, then
add a line to the catalog above.

- **Data-store conventions** — how raw and processed data are laid out on `\\ktdata\snlkt`, naming,
  provenance/manifest expectations, and how Claude locates a dataset from `context.md`. Pairs
  directly with `context.md`; probably the highest-leverage first skill.
- **Figure & panel making** — publication figures for `visuals/`: standard tool, panel sizing and
  DPI, color and typography conventions, export settings, and the style "vibes" in `visuals/vibes/`.
- **Statistics & analysis** — statistical defaults: which tests, multiple-comparison handling,
  effect sizes and their reporting, reproducibility (seeds, config). Pairs with pynapple.
- **Literature review** — a repeatable search-and-synthesize workflow over PubMed, bioRxiv, and
  Scholar Feed, with how citations get captured into `literature/`.
- **Manuscript drafting** — drafting and revising in your voice for `manuscript/`, reusing the
  `voice-matcher` and `copy-editor` agents.

## How skills flow

The shipped library travels inside the **`exporgo` binary**: the template repo is the master copy,
and each release embeds it. A new project (`exporgo new`) already has every skill — nothing to
deploy. Improve a shipped skill by committing to the template repo and cutting a release; then, in
an existing project, run `exporgo check` to preview and `exporgo update` to pull the newer
exporgo-owned files in without disturbing project content. To use a skill inside a code repo, copy
the relevant folder (or `code/CLAUDE.md`) into that repo's `.claude/`.

## How to author a new skill

1. Start from `templates/SKILL.template.md`.
2. Project-specific → a folder under `.claude/skills/local/`. Reusable across projects → the
   template repo, under `.claude/skills/exporgo/` (`code/`, `science/`, `sync/`, or a new domain
   folder). One folder per skill, `SKILL.md` inside.
3. Write the `description` to *trigger* — include the words a future request would use.
4. Add it to the catalog above so it's discoverable.
