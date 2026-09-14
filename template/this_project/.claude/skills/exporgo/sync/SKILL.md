---
name: gdrive-folder-sync
description: >
  Set up or run a two-hop, non-destructive folder sync with `exporgo sync`, with the source,
  intermediate, and destination paths supplied as flags or stored in the project's exporgo.toml.
  Use when the user wants to mirror a Google Drive folder (the Drive-for-Desktop mount) to or
  from a network share or local folder, keep a project's data synced across machines, or
  schedule a backup — especially when files exceed the Drive connector's ~10 MB limit or the
  target is a UNC share. Cross-platform: the sync engine is built into the exporgo binary.
---

# Google Drive ↔ folder sync (`exporgo sync`)

Mirror a folder through a durable local intermediate. The engine is built into the `exporgo`
binary (pure Rust — no robocopy, no rsync), so the same command works on Windows, macOS, and
Linux.

```
Forward : Source        -> Intermediate -> Destination
Reverse : Destination   -> Intermediate -> Source
```

Any of the three can be a cloud-drive mount (`G:\...` on Windows, `~/Google Drive/...` on
macOS), a local folder, or a UNC share (`\\server\share\...`). The intermediate is a plain
local folder that acts as the durable mirror and the dedup reference.

## When to use

- Keep a project's data identical on every machine via Google Drive.
- Back a Drive folder up to the lab share, or pull the share back into Drive.
- Move files too big for the Drive connector's ~10 MB cap — the mount has no such limit.
- Not for: cloud-scheduled sync. The cloud/Cowork side cannot reach drive mounts or
  `\\server` shares; this must run natively on the machine.

## Read these constraints first — they decide the design

- **The cloud side cannot reach drive mounts, mapped drives, or UNC shares.** Schedule with the
  OS scheduler (Task Scheduler on Windows, cron/launchd elsewhere), never a cloud cron.
- **Use the UNC path for a network target** (`\\ktdata\snlkt\...`), not a mapped letter (`A:`).
  UNC doesn't depend on the session's drive mapping. Find the UNC behind a letter with `net use`.
- **Non-destructive by default:** new and newer files only (2-second timestamp slack for cloud
  mounts), never deletes. `--mirror` *will* delete at the target — use only when you mean it.
- **Runtime:** the machine must be on and logged in; if a drive-mount path is used, the drive
  client must be running and signed in. A missing source aborts before the second hop and exits
  nonzero, so the scheduler's "Last Run Result" flags it and a bad mount never overwrites a
  good target.
- **First run may be heavy:** reading from a cloud mount hydrates cloud-only placeholders.

## Configure it once (recommended)

Add a `[sync]` table to the project's `exporgo.toml`; then `exporgo sync` needs no arguments:

```toml
[sync]
source = 'G:\My Drive\projects\this_project'
intermediate = 'C:\Users\dao25\SyncMirror\this_project'
destination = '\\ktdata\snlkt\backup\this_project'
exclude = ["*.tmp"]          # optional extras; OS cruft is always excluded
```

## Run it

```powershell
exporgo sync                          # forward, using the [sync] section
exporgo sync --direction reverse     # share -> mirror -> Drive (client then uploads)
exporgo sync --dry-run               # list what would copy, change nothing
exporgo sync --exclude "*.tmp" --exclude "~$*"   # extra file-name patterns

# Or fully flag-driven, outside a project:
exporgo sync --source "G:\My Drive\projects\this_project" `
             --intermediate "C:\Users\dao25\SyncMirror\this_project" `
             --destination "\\ktdata\snlkt\backup\this_project"
```

Flags: `--source/--intermediate/--destination` (override the manifest), `--direction`
(forward|reverse), `--exclude` (repeatable, `*` wildcards on file names), `--log-dir`
(default: the project root), `--mirror` (destructive), `--dry-run`.

## Schedule the forward run

Windows Task Scheduler:

```
schtasks /Create /TN "ThisProjectForwardSync" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:00 /F ^
  /TR "\"C:\path\to\exporgo.exe\" sync \"C:\path\to\project\""
```

macOS/Linux: a cron entry running `exporgo sync /path/to/project`. Run the reverse on demand
unless the user asks to schedule it too.

## Logs and exit codes

- `_sync_detail.log` — overwritten each run: one line per copied/deleted file.
- `_sync_history.log` — appended: one timestamped summary line per run (the audit trail).
- Exit 0 = success; exit 2 = failure (missing source, I/O error). A missing source aborts
  before the second hop, so a bad mount never overwrites a good target.
- Both logs match the project `.gitignore`'s `*.log` rule, so they never enter git.

## Verify

- First run by hand with `--dry-run`, then for real; confirm both hops report success and a
  >10 MB file copied intact.
- Read `_sync_history.log` to confirm counts and the `OK` verdict.
