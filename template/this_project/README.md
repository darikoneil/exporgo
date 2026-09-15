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

- **`context.md`** — deliberately short. The project's status and owner, short sections for aims
  (if any), repositories, and general data pointers, and pointers to everything else. This is the
  file that loads on every prompt, so it stays brief.
- **`experiments/`** — one folder per experiment, each a self-contained unit: `experiment.md`
  (scientific description), `protocol.md`, `analysis.md` (pipeline), `resources.md` (where its code
  and data live — repos and data roots are recorded per experiment). Start one with
  `exporgo experiment new "<name>"` — it stamps `experiments/_TEMPLATE/`, prompting for optional
  data-root hints.
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
├─ context.md                  SMALL router: status, aims/repos/data sections, pointers
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
│     │  ├─ sync/              multi-machine project sync guide (SKILL.md)
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
exporgo new "Grid Cell Remapping" --path "C:\Users\dao25\Projects" --status active
```

Owner and email default from the machine config (`exporgo config --owner .. --email ..`, set
once per machine); anything still missing is prompted for (press Enter to skip — skipped values
stay visible as `{{TOKENS}}` in `context.md` to fill later). `--no-input` skips all prompts for
scripting. Aims, repositories, and data
locations are *not* collected up front — a project may have several repos and no formal aims;
fill the matching `context.md` sections (and each experiment's `resources.md`) as they become
real.

## Keep a project's template up to date

When the template gains a better skill, install the newer `exporgo` release, then refresh the
project in place. Only the exporgo-owned files are rewritten (`.claude/skills/exporgo/`,
`CLAUDE.md`, `README.md`, `SKILLS.md`, `templates/`, `experiments/_TEMPLATE/`); your `context.md`,
experiments, plans, writing, `.claude/local.md`, and `.claude/skills/local/` are never touched:

```powershell
exporgo check     # what would change (also reports unfilled tokens, missing folders)
exporgo update    # apply; --dry-run to preview, --skills-only to narrow
```

## Work from several machines

The binary carries the template; `exporgo sync` carries **this workspace** between your
computers. Each machine syncs its local project folder, through a per-machine cache exporgo
manages by itself, against one shared remote copy (`<remote_root>\<project-slug>`). Tell each
machine where the shared location lives, once:

```powershell
exporgo config --remote-root "G:\My Drive\exporgo-projects"
```

```powershell
exporgo sync              # bidirectional: pull newer, push newer — never deletes
exporgo sync push         # one-way, local -> remote (add --mirror to also delete)
exporgo sync pull         # one-way, remote -> local
exporgo sync --dry-run    # preview only
exporgo clone "Grid Cell Remapping" --path "C:\Users\dao25\Projects"   # new machine
```

Run `exporgo sync` at the start and end of a session and every machine converges on the newest
version of each file. Bring the project onto a new machine with `exporgo clone`, never by
re-stamping `exporgo new` there. Operational details (deletion semantics, mount constraints,
scheduling) are in the **`project-sync`** skill: `.claude/skills/exporgo/sync/SKILL.md`.
