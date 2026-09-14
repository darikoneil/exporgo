# Science project workspace

The standard layout for one science project — and, unstamped, the template every new project is
copied from. A workspace is the project's **brain**: its context, its documented experiments and
plans, its curated Claude skills, and its reusable writing and visuals. It is not where code or
data live. Code lives in the project's GitHub repo; raw and processed data live on the lab share.
This workspace records *where those are* and holds the tools for working with them.

Every project is a **full copy** of the template, carrying its own complete `.claude/skills/`, so
it works anywhere without depending on a central library.

## How the documentation is organized

Small and pointed, so an agent loads only what a task needs:

- **`context.md`** — deliberately short. The project's aim, status, primary repo and data root, and
  pointers to everything else. This is the file that loads on every prompt, so it stays brief.
- **`experiments/`** — one folder per experiment, each a self-contained unit: `experiment.md`
  (scientific description), `protocol.md`, `analysis.md` (pipeline), `resources.md` (where its code
  and data live). Start one with `exporgo experiment new "<name>"` — it stamps
  `experiments/_TEMPLATE/` and pre-fills the raw data root from the project's `data_root`.
- **`plans/`** — unexecuted aims, ideas, and timelines. What you *intend* to do, distinct from the
  experiments you're running.

## The one rule

**No code, no raw data in this workspace.** It holds context, documentation, skills, and reusable
assets. Code belongs in the project's repo; data stays on the lab share. Keeping them out is what
lets the workspace sync cheaply and travel with the project.

## Folder map

```
<project>/                     one project (or, unstamped, the template)
├─ exporgo.toml                manifest: name, created, template version, stamp values
├─ context.md                  SMALL router: aim, status, repo/data root, pointers
├─ README.md                   this file — project-agnostic, same in every copy
├─ CLAUDE.md                   orientation for Claude — read first
├─ SKILLS.md                   index of the skills carried in .claude/skills
├─ experiments/
│  ├─ _TEMPLATE/               copy this to start an experiment
│  │  ├─ experiment.md  protocol.md  analysis.md  resources.md
│  └─ README.md
├─ plans/                      unexecuted aims, ideas, timelines (+ README)
├─ templates/
│  └─ SKILL.template.md        scaffold for authoring a new skill
├─ .claude/
│  ├─ local.md                 YOUR standing instructions — never overwritten
│  └─ skills/
│     ├─ exporgo/              shipped library — OVERWRITTEN by `exporgo update`
│     │  ├─ third_party_skills.md
│     │  ├─ sync/              Google Drive ↔ folder sync (SKILL.md + sync.ps1)
│     │  ├─ code/              Python conventions + review/documentation agents
│     │  └─ science/           science skills — to fill (upstream, in the template)
│     └─ local/                YOUR skills — never touched by update
├─ literature/                 reusable references + reading notes
├─ manuscript/                 drafts / reusable methods text
├─ presentations/              slides, talk material
├─ documents/                  everything that isn't one of the above
├─ artifacts/                  generated outputs worth keeping
└─ visuals/                    reusable visual assets
   ├─ figures/  illustrations/  panels/  schematics/  vibes/
```

## Distributed as a binary

The template travels inside the **`exporgo` CLI** — a single binary with the template embedded, so
creating a project needs no network, no toolchain, and no cloned repo. Install it from the template
repo's GitHub Releases; updating the binary is how a machine gets newer skills.

## Make a new project

```powershell
exporgo new "Grid Cell Remapping" `
    --path "C:\Users\dao25\Projects" `
    --aim "Does grid-cell remapping track task boundaries?" `
    --repo "https://github.com/darik/gridremap" `
    --data-root "\\ktdata\snlkt\data\gridremap" --status active
```

Any value you omit is prompted for (press Enter to skip — skipped values stay visible as
`{{TOKENS}}` in `context.md` to fill later). `--no-input` skips all prompts for scripting;
`--git` also runs `git init` (it never commits).

## Keep a project's template up to date

When the template gains a better skill, install the newer `exporgo` release, then refresh the
project in place. Only the exporgo-owned files are rewritten (`.claude/skills/exporgo/`,
`CLAUDE.md`, `README.md`, `SKILLS.md`, `templates/`, `experiments/_TEMPLATE/`); your `context.md`,
experiments, plans, writing, `.claude/local.md`, and `.claude/skills/local/` are never touched:

```powershell
exporgo check     # what would change (also reports unfilled tokens, missing folders)
exporgo update    # apply; --dry-run to preview, --skills-only to narrow
```

## Sync data and outputs

The binary carries the template; `exporgo sync` moves **data and outputs**. It mirrors a source
to a destination through a durable local intermediate, non-destructively (new and newer files
only, never deletes), on any OS. Put the paths in `exporgo.toml` once and the command needs no
arguments:

```toml
[sync]
source = 'G:\My Drive\projects\this_project'
intermediate = 'C:\Users\dao25\SyncMirror\this_project'
destination = '\\ktdata\snlkt\backup\this_project'
```

```powershell
exporgo sync                        # forward: source -> intermediate -> destination
exporgo sync --direction reverse   # pull the destination back
exporgo sync --dry-run             # preview only
```

Operational details (drive-mount constraints, UNC paths, scheduling) are in the
**`gdrive-folder-sync`** skill: `.claude/skills/exporgo/sync/SKILL.md`.
