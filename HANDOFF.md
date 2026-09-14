> **SUPERSEDED (2026-09-13).** The PowerShell-script plan below was replaced by the `exporgo`
> Rust CLI (embedded template; `exporgo new` / `check` / `update`). The runbook steps no longer
> apply: skills were restructured to `.claude/skills/exporgo/` + `.claude/skills/local/`,
> `project-setup`/`update-template` were retired, and empty dirs are created by the CLI (no
> `.gitkeep`). Kept for reference; safe to delete.

# HANDOFF — stand up the science-project template as a git repo

This document hands off the remaining work to **Claude Code** running locally in this folder, where
it has a real shell (git, gh, PowerShell) that the Cowork session did not. Read it top to bottom
before acting, confirm the open choices with Darik, then work the runbook.

This is a maintainer/setup doc, not part of the template itself. Delete it once the repo is stood
up and verified (or keep it as maintainer notes — but remove it from project clones).

---

## What this repo is (don't re-litigate this)

A **standard science-project template** Darik copies for each new project, distributed as a GitHub
repo. The design was settled over several rounds; honor it:

- **Copy-per-project.** Each project is a full, self-contained copy (clone) of this template,
  including a complete `.claude/skills/`. Nothing is referenced from a central library.
- **`context.md` is deliberately small** — a big-picture router with pointers, cheap to load on
  every prompt. Detail lives elsewhere, not here.
- **Experiments are first-class units.** `experiments/<name>/` holds four small, single-purpose
  files: `experiment.md` (description), `protocol.md`, `analysis.md` (pipeline), `resources.md`
  (where the code and data live). Start one by copying `experiments/_TEMPLATE/`.
- **`plans/`** holds unexecuted aims, ideas, and timelines. `plans/` = intent; `experiments/` =
  execution.
- **No code, no raw data in the workspace.** Code lives in the project's own GitHub repo; data on
  the lab share (`\\ktdata\snlkt\...`). This workspace records *where* those are and holds skills.
- **Git distributes the template; a skill pulls updates.** `update-template` (`update.ps1`)
  refreshes conserved files from the repo on demand; `gdrive-folder-sync` (`sync.ps1`) is for
  **data/outputs**, not the template.

Full detail is in `README.md` (humans), `CLAUDE.md` (agents), and `SKILLS.md` (the skill catalog).
Read those; they are the source of truth for the structure.

---

## Current state

**On disk and correct:** `context.md` (small, tokenized), `README.md`, `CLAUDE.md`, `SKILLS.md`,
`experiments/_TEMPLATE/` (+ `experiments/README.md`), `plans/README.md`, `templates/SKILL.template.md`,
`.gitignore`, and the pre-existing `.claude/skills/custom/code/` (conventions + agents) and
`third_party_skills.md`.

**May still be missing** (they were delivered as a zip the Cowork bridge couldn't write into
`.claude/`): the three skill folders
`.claude/skills/custom/{project-setup,sync,update-template}/`. Verify they exist; if not, unzip
`science-template-claude-skills.zip` at the repo root.

**To be removed** (superseded; already in `.gitignore`, so they won't be tracked, but clean the
working copy): `.claude/skills/custom/sync_skill.md`, `templates/context.template.md`, and the stray
`Claude outputs/` folder.

**Private, must stay untracked:** `.claude/skills/custom/code/agents/references/darik-voice.md`
(personal writing samples) — already in `.gitignore`. Confirm `git status` never lists it.

---

## Runbook

Confirm the open choices below with Darik first, then:

1. **Verify structure.** Check the three skill folders exist:
   `.claude/skills/custom/project-setup/`, `.../sync/`, `.../update-template/`, each with a
   `SKILL.md` and its `.ps1`. If missing, unzip `science-template-claude-skills.zip` at the root.

2. **Preserve empty folders in git.** Git won't track empty directories, so the skeleton would be
   lost on clone. Add a `.gitkeep` to each empty dir that should ship:
   `artifacts/`, `documents/`, `literature/`, `manuscript/`, `presentations/`,
   `visuals/figures/`, `visuals/illustrations/`, `visuals/panels/`, `visuals/schematics/`,
   `.claude/skills/custom/science/`. (`visuals/vibes/` has images; `plans/` and `experiments/`
   have READMEs — no keep needed.)

3. **Clean the working copy.** Delete `.claude/skills/custom/sync_skill.md`,
   `templates/context.template.md`, and `Claude outputs/`.

4. **Initialize and commit.** `git init`, `git add .`, review `git status` (confirm
   `darik-voice.md` and `Claude outputs/` are NOT staged), then commit.

5. **Create the GitHub repo and push.** With `gh` (adjust owner/name/visibility per Darik):
   ```bash
   gh repo create doneil/science-template --private --source . --remote origin --push
   ```
   To make it a true GitHub *template repository* (adds "Use this template" + `gh --template`):
   ```bash
   gh api -X PATCH repos/doneil/science-template -f is_template=true
   ```

6. **Verify the scripts on Windows** (PowerShell). Report results back to Darik; do not treat as
   done until these pass:
   - `new_project.ps1` — dry-run into a throwaway destination and inspect the result:
     ```powershell
     & ".\.claude\skills\custom\project-setup\new_project.ps1" -Name "Smoke Test" `
         -Destination "$env:TEMP\smoketest" -Aim "verify setup" -Status planning
     ```
     Confirm it created the tree, filled `context.md` (name/aim/status/date), left unset tokens
     visible, and copied `.claude/skills/` and `experiments/_TEMPLATE/`. Then delete the throwaway.
   - `sync.ps1` — `-WhatIf` only (lists, changes nothing):
     ```powershell
     & ".\.claude\skills\custom\sync\sync.ps1" -Source <a> -Intermediate <b> -Destination <c> -WhatIf
     ```
   - `update.ps1` — after the repo exists, from a fresh clone: `update.ps1 -Check` (previews).

7. **Delete this HANDOFF.md** (or move it to maintainer notes) once 1–6 pass.

---

## Constraints Claude Code must respect

- **Commit/push authorization is scoped.** Darik has asked for *this template repo* to be created
  and pushed — that is authorized. The standing rule elsewhere (see
  `.claude/skills/custom/code/CLAUDE.md`) is that **only the user commits and pushes** to project
  **code** repos; do not generalize this template's push to those.
- **Never write project code or data into the template.** It holds context, docs, skills, and
  reusable assets only.
- **Keep `context.md` small.** Detail belongs in `experiments/<name>/` files, not the router.
- **Python conventions**, if any tooling is added later: `uv` only, `ruff`, `pyrefly`, Google-style
  docstrings — see `.claude/skills/custom/code/CLAUDE.md`.

---

## Open choices to confirm with Darik

1. **Repo identity:** owner/name/visibility. Assumed `doneil/science-template`, **private**, default
   branch `main`. (If the default branch isn't `main`, pass `-Ref <branch>` to `update.ps1`.)
2. **Template-repo toggle:** set `is_template=true` (step 5) for the "Use this template" flow, or
   leave it a plain repo cloned directly? Either works with the scripts.
3. **Experiment granularity:** currently four small files per experiment (best for keeping context
   small). Collapse to a single `experiment.md` with four sections instead? Darik's call.
4. **Science skills:** `.claude/skills/custom/science/` is an empty, ready-to-fill area. The first
   one worth building is **data-store conventions** (how raw/processed data is laid out on
   `\\ktdata\snlkt`), since `context.md` and each experiment's `resources.md` lean on it.

---

## Why this was handed off

The Cowork session that built this runs in the cloud and reaches the Windows machine through a
file bridge that (a) cannot write into `.claude/` and (b) has no GitHub auth, and its
run-commands-on-the-machine path was down due to a Sept 8 Windows update. So it prepared every
file and the exact commands but could not create the repo or execute the scripts. That is the work
above — mechanical, but it needs the local shell you have.
