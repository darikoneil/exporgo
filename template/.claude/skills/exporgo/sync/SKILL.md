---
name: project-sync
description: >
  Keep this project workspace converged across multiple computers with `exporgo sync`, or bring
  it onto a new machine with `exporgo clone`. Each machine syncs its local project folder,
  through a per-machine cache, against a shared remote (a Google Drive mount, a lab UNC share —
  whatever the machine config's remote_root points at). Use when the user wants the project's
  context, experiments, plans, or artifacts identical on two or more machines, wants to set up a
  new machine, or wants to schedule the sync. Cross-platform: the engine is built into the
  exporgo binary.
---

# Project sync across machines (`exporgo sync`)

Keep the same project workspace converged on several computers. Each machine holds the project at
its own path and syncs against one shared remote copy:

```
machine A:  <project dir A>  ⇄  cache  ⇄  <remote_root>\<slug>
machine B:  <project dir B>  ⇄  cache  ⇄  <remote_root>\<slug>   (same physical remote)
```

The cache is a stable per-machine staging folder (`%LOCALAPPDATA%\exporgo\cache\<slug>` on
Windows) that exporgo manages by itself — you never configure or think about it. It exists
because cloud-drive mounts are flaky about direct copies; every hop is disk↔mount, never
mount↔mount. The remote subfolder is the project's slug, so every machine addresses the same
remote copy automatically.

## One-time setup, per machine

Tell each machine where the shared remote lives (its own path to it — a Drive mount here, maybe
a UNC share there):

```powershell
exporgo config --remote-root "G:\My Drive\exporgo-projects"
```

`exporgo config` with no flags shows the current settings and where the config file lives.
Optional: `--owner`/`--email` set the defaults `exporgo new` stamps into new projects.

## Daily use

From inside the project (or with `--project DIR`):

```powershell
exporgo sync              # bidirectional: pull newer, then push newer — never deletes
exporgo sync pull         # one-way: remote -> cache -> local
exporgo sync push         # one-way: local -> cache -> remote
exporgo sync --dry-run    # list what would copy, change nothing
```

Run `exporgo sync` at the start and end of a work session and two machines stay converged: for
each file, the newest modification wins (2-second timestamp slack for cloud mounts; copies
preserve mtimes, so re-runs are stable and cheap). The very first sync of a project simply
creates the remote copy.

## New machine

Do **not** stamp `exporgo new` on the second machine and pull — the freshly stamped files would
be newer than the remote's and a later sync would push the blank stamp over the real project.
Bootstrap with a plain copy instead:

```powershell
exporgo config --remote-root "<this machine's path to the shared location>"
exporgo clone "Grid Cell Remapping" --path "C:\Users\dao25\Projects"
```

`clone` refuses a non-empty target and requires the remote copy to exist (push it from the
first machine beforehand).

## Read these constraints first — they decide the design

- **The cloud side cannot reach drive mounts, mapped drives, or UNC shares.** Sync runs
  natively on the machine; schedule with the OS scheduler (Task Scheduler on Windows,
  cron/launchd elsewhere), never a cloud cron.
- **Prefer the UNC path for a network remote** (`\\ktdata\snlkt\...`), not a mapped letter
  (`A:`). UNC doesn't depend on the session's drive mapping.
- **Deletions never propagate.** Non-destructive sync means a file deleted on one machine is
  pulled straight back from the remote on the next sync. To genuinely remove files everywhere:
  delete locally, then `exporgo sync push --mirror` (destructive — it makes cache and remote
  match the local tree exactly), then `pull --mirror` on the other machines.
- **`--mirror` needs an explicit `push` or `pull`** — a bidirectional mirror would delete on
  both sides, so exporgo refuses it.
- **`.git/` never syncs.** It is excluded by default (mtime-copying a live git directory
  corrupts repositories); the project's git history travels through its git remote, not
  through exporgo. OS cruft (`Thumbs.db`, `.DS_Store`, ...) is excluded too; add extras with
  `--exclude "*.tmp"` (repeatable, `*` wildcards, matches file and directory names).
- **An unmounted remote fails loudly, and safely.** A missing remote root aborts before any
  copy; a hop whose source vanished aborts before the next hop, so a bad mount never
  overwrites a good target.
- **First run may be heavy:** reading from a cloud mount hydrates cloud-only placeholders.

## Schedule it

Windows Task Scheduler, a bidirectional sync each workday morning:

```
schtasks /Create /TN "ThisProjectSync" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:00 /F ^
  /TR "\"C:\path\to\exporgo.exe\" sync --project \"C:\path\to\project\""
```

macOS/Linux: a cron entry running `exporgo sync --project /path/to/project`.

## Logs and exit codes

Logs live per machine, outside the synced tree (`%LOCALAPPDATA%\exporgo\logs\<slug>\`; the sync
report prints the exact paths):

- `_sync_detail.log` — overwritten each run: one line per copied/deleted file.
- `_sync_history.log` — appended: one timestamped summary line per run (the audit trail).
- Exit 0 = success; exit 2 = failure (unset or unmounted remote root, missing remote on a
  pull, I/O error). Failures still append a FAIL line to the history log.

## Verify

- First run by hand with `--dry-run`, then for real; read the printed summary and confirm the
  remote now holds the project.
- On the second machine, `exporgo clone`, edit one file, `exporgo sync` on both — confirm the
  edit arrived and `_sync_history.log` shows the `OK` verdicts.
