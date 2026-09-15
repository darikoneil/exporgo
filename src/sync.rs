//! `exporgo sync`: keep a project directory converged across machines.
//!
//! Every machine holds the project at its own local path and syncs it, through
//! a stable per-machine cache, against a shared remote copy named by the
//! project's slug:
//!
//! ```text
//! Pull : Remote  -> Cache -> Local
//! Push : Local   -> Cache -> Remote
//! Both : pull, then push (per-file newest-mtime wins everywhere)
//! ```
//!
//! The cache hop exists because cloud-drive mounts are flaky about direct
//! copies; the cache is real local disk, so each hop is mount-to-disk or
//! disk-to-mount, never mount-to-mount.
//!
//! Non-destructive by default: new and newer files are copied, nothing is ever
//! deleted — which also means a deletion never propagates (bidirectional sync
//! resurrects locally deleted files from the remote; `push --mirror` is the
//! deliberate cleanup). `mirror` deletes entries at the target that are absent
//! from the source — destructive, opt-in, and only meaningful with an explicit
//! direction. If a hop's source is missing (Drive not mounted, share offline)
//! the run aborts before the next hop, so a bad mount never overwrites a good
//! target.
//!
//! File comparison is by modification time with a 2-second slack (FAT and cloud
//! mounts round timestamps); copies preserve the source's mtime so re-runs are
//! stable. Exclusion patterns match file *and directory* names (robocopy `/XF`
//! style, `*` wildcards, ASCII case-insensitive); `.git/` is excluded by
//! default because mtime-copying a live git directory corrupts repositories.

use std::{
    io::Write,
    path::{Path, PathBuf},
    time::Duration,
};

use crate::error::Error;

/// What a sync run does.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode
{
    /// Pull, then push: converge local and remote on the newest of each file.
    Both,
    /// Local -> Cache -> Remote only.
    Push,
    /// Remote -> Cache -> Local only.
    Pull,
}

impl Mode
{
    pub fn as_str(self) -> &'static str
    {
        match self
        {
            Mode::Both => "Sync",
            Mode::Push => "Push",
            Mode::Pull => "Pull",
        }
    }
}

/// Names that never propagate: OS cruft, git's live object store, this tool's
/// own logs, and leftover temporaries from interrupted atomic copies. Matched
/// against file and directory names alike.
pub const DEFAULT_EXCLUDES: &[&str] = &[
    ".git",
    "Thumbs.db",
    "*.Identifier",
    ".DS_Store",
    DETAIL_LOG,
    HISTORY_LOG,
    "*.exporgo-partial",
];

/// Overwritten each run with per-file detail.
pub const DETAIL_LOG: &str = "_sync_detail.log";
/// Appended each run with one summary line — the audit trail.
pub const HISTORY_LOG: &str = "_sync_history.log";

/// Fully resolved inputs for [`sync`] (the CLI resolves the cache and remote
/// from the machine config and the project slug).
pub struct SyncOptions
{
    /// The project directory on this machine.
    pub local: PathBuf,
    /// This machine's staging copy, `<cache_root>/<slug>`.
    pub cache: PathBuf,
    /// The shared copy, `<remote_root>/<slug>`.
    pub remote: PathBuf,
    pub mode: Mode,
    /// Extra name patterns, on top of [`DEFAULT_EXCLUDES`].
    pub exclude: Vec<String>,
    /// Also delete target entries absent from the source. Destructive, and
    /// only accepted with an explicit [`Mode::Push`] or [`Mode::Pull`].
    pub mirror: bool,
    /// Plan and log only; copy and delete nothing.
    pub dry_run: bool,
    /// Where the two log files are written (outside all three trees).
    pub log_dir: PathBuf,
}

/// What one hop did.
pub struct HopReport
{
    pub label: String,
    pub copied: usize,
    pub deleted: usize,
}

/// What the whole run did.
pub struct SyncReport
{
    pub hops: Vec<HopReport>,
    /// The one-line summary appended to the history log.
    pub summary: String,
    pub history_log: PathBuf,
    pub detail_log: PathBuf,
}

/// One planned copy step.
struct Hop<'a>
{
    from: &'a Path,
    to: &'a Path,
    label: &'static str,
    /// The source is the cache, produced by the preceding hop in this same
    /// run — so in a dry run its absence is expected, not an error.
    lenient: bool,
}

/// Runs the mode's hops through the cache, writing the detail and history
/// logs.
///
/// Refuses up front when any two of the three paths are equal or nested (a
/// nested cache would make the copy recurse into its own output without
/// bound), and when `mirror` is combined with [`Mode::Both`]. A pull with no
/// remote copy is [`Error::RemoteProjectMissing`]; a bidirectional run skips
/// the pull phase instead (the push then creates the remote — the first-ever
/// sync of a project).
pub fn sync(options: &SyncOptions) -> Result<SyncReport, Error>
{
    if options.mirror && options.mode == Mode::Both
    {
        return Err(Error::MirrorNeedsDirection);
    }
    reject_overlaps(&[
        (&options.local, &options.cache),
        (&options.cache, &options.remote),
        (&options.local, &options.remote),
    ])?;

    let pull: [Hop; 2] = [
        Hop {
            from: &options.remote,
            to: &options.cache,
            label: "Remote->Cache",
            lenient: false,
        },
        Hop {
            from: &options.cache,
            to: &options.local,
            label: "Cache->Local",
            lenient: true,
        },
    ];
    let push: [Hop; 2] = [
        Hop {
            from: &options.local,
            to: &options.cache,
            label: "Local->Cache",
            lenient: false,
        },
        Hop {
            from: &options.cache,
            to: &options.remote,
            label: "Cache->Remote",
            lenient: true,
        },
    ];
    let mut skipped_pull = false;
    let hops: Vec<Hop> = match options.mode
    {
        Mode::Pull =>
        {
            if !options.remote.is_dir()
            {
                return Err(Error::RemoteProjectMissing(options.remote.clone()));
            }
            pull.into_iter().collect()
        }
        Mode::Push => push.into_iter().collect(),
        Mode::Both =>
        {
            if options.remote.is_dir()
            {
                pull.into_iter().chain(push).collect()
            }
            else
            {
                skipped_pull = true;
                push.into_iter().collect()
            }
        }
    };

    std::fs::create_dir_all(&options.log_dir).map_err(Error::io(options.log_dir.clone()))?;
    let detail_path = options.log_dir.join(DETAIL_LOG);
    let history_path = options.log_dir.join(HISTORY_LOG);
    let stamp = jiff::Zoned::now().strftime("%Y-%m-%d %H:%M:%S").to_string();

    let mut detail = std::fs::File::create(&detail_path).map_err(Error::io(detail_path.clone()))?;
    let dry = if options.dry_run { " (dry run)" } else { "" };
    let _ = writeln!(detail, "=== {} {stamp}{dry} ===", options.mode.as_str());
    if skipped_pull
    {
        let _ = writeln!(
            detail,
            "--- pull skipped: no remote copy at '{}' yet (this push creates it)",
            options.remote.display()
        );
    }

    let mut excludes: Vec<String> = DEFAULT_EXCLUDES.iter().map(|s| s.to_string()).collect();
    excludes.extend(options.exclude.iter().cloned());

    // Any failure below still leaves one FAIL line in the history log — the
    // audit trail records every run, not only the successful ones.
    let reports = match run_hops(options, &hops, &excludes, &mut detail)
    {
        Ok(reports) => reports,
        Err(e) =>
        {
            let summary = format!("[{stamp}] {}  => FAIL: {e}", options.mode.as_str());
            let _ = writeln!(detail, "=== {summary} ===");
            append_history(&history_path, &summary)?;
            return Err(e);
        }
    };

    let verb = if options.dry_run
    {
        "would copy"
    }
    else
    {
        "copied"
    };
    let summary = format!(
        "[{stamp}] {}  {}  => OK{dry}",
        options.mode.as_str(),
        reports
            .iter()
            .map(|h| {
                let deletions = if h.deleted > 0
                {
                    format!(", deleted {}", h.deleted)
                }
                else
                {
                    String::new()
                };
                format!("{}: {verb} {}{deletions}", h.label, h.copied)
            })
            .collect::<Vec<_>>()
            .join("   "),
    );
    let _ = writeln!(detail, "=== {summary} ===");
    append_history(&history_path, &summary)?;

    Ok(SyncReport {
        hops: reports,
        summary,
        history_log: history_path,
        detail_log: detail_path,
    })
}

/// Inputs for [`clone_project`]: bootstrap a project onto a machine that does
/// not have it yet.
pub struct CloneOptions
{
    /// The shared copy, `<remote_root>/<slug>` — must exist.
    pub remote: PathBuf,
    /// This machine's staging copy, `<cache_root>/<slug>`.
    pub cache: PathBuf,
    /// The local directory to create — must not exist, or be empty.
    pub target: PathBuf,
    /// Where the two log files are written.
    pub log_dir: PathBuf,
}

/// Copies the remote project into a fresh local directory (remote -> cache ->
/// target).
///
/// This is the supported way to get a project onto a second machine. Stamping
/// `exporgo new` there and pulling would be a trap: freshly stamped files
/// carry *current* mtimes, newer than the remote's, so a later newest-wins
/// sync would push the blank stamp over the real project. A clone is a plain
/// pull into an empty target — no mtime contest.
pub fn clone_project(options: &CloneOptions) -> Result<SyncReport, Error>
{
    if options.target.exists()
    {
        let occupied = std::fs::read_dir(&options.target)
            .map(|mut entries| entries.next().is_some())
            .unwrap_or(true);
        if occupied
        {
            return Err(Error::CloneTargetNotEmpty(options.target.clone()));
        }
    }
    sync(&SyncOptions {
        local: options.target.clone(),
        cache: options.cache.clone(),
        remote: options.remote.clone(),
        mode: Mode::Pull,
        exclude: Vec::new(),
        mirror: false,
        dry_run: false,
        log_dir: options.log_dir.clone(),
    })
}

fn run_hops(
    options: &SyncOptions,
    hops: &[Hop],
    excludes: &[String],
    detail: &mut std::fs::File,
) -> Result<Vec<HopReport>, Error>
{
    let log_dir = normalized(&options.log_dir);
    let mut reports = Vec::new();
    for hop in hops
    {
        let (from, to, label) = (hop.from, hop.to, hop.label);
        if !from.is_dir() && hop.lenient && options.dry_run
        {
            // The prior hop would have created the cache; without it this hop
            // cannot be planned, which is expected in a dry run.
            let _ = writeln!(
                detail,
                "--- {label}: skipped (cache does not exist yet; a real run creates it)"
            );
            reports.push(HopReport {
                label: label.to_string(),
                copied: 0,
                deleted: 0,
            });
            continue;
        }
        if !from.is_dir()
        {
            let _ = writeln!(detail, "--- {label}: source not found '{}'", from.display());
            return Err(Error::SyncSourceMissing(from.to_path_buf()));
        }
        let _ = writeln!(
            detail,
            "--- {label}: {} -> {}",
            from.display(),
            to.display()
        );
        let mut hop_report = HopReport {
            label: label.to_string(),
            copied: 0,
            deleted: 0,
        };
        copy_tree(from, to, excludes, options.dry_run, &mut hop_report, detail)?;
        if options.mirror
        {
            delete_extras(
                from,
                to,
                excludes,
                options.dry_run,
                &log_dir,
                &mut hop_report,
                detail,
            )?;
        }
        reports.push(hop_report);
    }
    Ok(reports)
}

/// Lowercased absolute form of a path, for overlap and identity comparisons.
///
/// Deliberately `std::path::absolute`, not `canonicalize`: canonicalize only
/// works on paths that exist and returns `\\?\`-prefixed verbatim paths on
/// Windows, so mixing the two makes an existing directory and its
/// not-yet-created child normalize into different prefixes — and the overlap
/// check would miss exactly the nested-path case it exists to catch.
fn normalized(path: &Path) -> PathBuf
{
    let absolute = std::path::absolute(path).unwrap_or_else(|_| path.to_path_buf());
    let text = absolute.to_string_lossy();
    let text = text.strip_prefix(r"\\?\").unwrap_or(&text);
    PathBuf::from(text.to_lowercase())
}

/// Errors when any pair is the same directory or one contains the other.
fn reject_overlaps(pairs: &[(&PathBuf, &PathBuf)]) -> Result<(), Error>
{
    for (a, b) in pairs
    {
        let na = normalized(a);
        let nb = normalized(b);
        if na.starts_with(&nb) || nb.starts_with(&na)
        {
            return Err(Error::SyncPathsOverlap {
                a: (*a).clone(),
                b: (*b).clone(),
            });
        }
    }
    Ok(())
}

fn append_history(path: &Path, line: &str) -> Result<(), Error>
{
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(Error::io(path.to_path_buf()))?;
    writeln!(file, "{line}").map_err(Error::io(path.to_path_buf()))
}

/// Copies new and newer files from `from` into `to`, recursively. Never
/// deletes.
fn copy_tree(
    from: &Path,
    to: &Path,
    excludes: &[String],
    dry_run: bool,
    hop: &mut HopReport,
    detail: &mut std::fs::File,
) -> Result<(), Error>
{
    if !dry_run
    {
        std::fs::create_dir_all(to).map_err(Error::io(to.to_path_buf()))?;
    }
    for entry in std::fs::read_dir(from).map_err(Error::io(from.to_path_buf()))?
    {
        let entry = entry.map_err(Error::io(from.to_path_buf()))?;
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        let file_type = entry.file_type().map_err(Error::io(entry.path()))?;
        // Symlinks are skipped: following one could copy or delete outside the
        // tree.
        if file_type.is_symlink()
        {
            let _ = writeln!(detail, "skip symlink {}", entry.path().display());
            continue;
        }
        // Exclusion applies to directory names too — most importantly `.git`,
        // whose live object store must never be mtime-copied between machines.
        if excluded(&name_str, excludes)
        {
            continue;
        }
        let target = to.join(&name);
        if file_type.is_dir()
        {
            copy_tree(&entry.path(), &target, excludes, dry_run, hop, detail)?;
        }
        else
        {
            if needs_copy(&entry.path(), &target)?
            {
                let _ = writeln!(detail, "copy {}", target.display());
                if !dry_run
                {
                    copy_with_retry(&entry.path(), &target)?;
                }
                hop.copied += 1;
            }
        }
    }
    Ok(())
}

/// Mirror mode: removes entries in `to` that do not exist in `from`.
#[allow(clippy::too_many_arguments)]
fn delete_extras(
    from: &Path,
    to: &Path,
    excludes: &[String],
    dry_run: bool,
    log_dir: &Path,
    hop: &mut HopReport,
    detail: &mut std::fs::File,
) -> Result<(), Error>
{
    if !to.is_dir()
    {
        return Ok(());
    }
    for entry in std::fs::read_dir(to).map_err(Error::io(to.to_path_buf()))?
    {
        let entry = entry.map_err(Error::io(to.to_path_buf()))?;
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if excluded(&name_str, excludes)
        {
            continue;
        }
        let file_type = entry.file_type().map_err(Error::io(entry.path()))?;
        // Never delete (or descend into) the directory holding our own logs —
        // the detail log is open for writing right now.
        if file_type.is_dir() && normalized(&entry.path()) == *log_dir
        {
            let _ = writeln!(detail, "skip log dir {}", entry.path().display());
            continue;
        }
        let counterpart = from.join(&name);
        // A failed stat (share hiccup, permissions) must count as "exists":
        // deleting on an error would destroy the target's only copy. A live
        // symlink also counts via try_exists; a dangling one via is_symlink.
        let counterpart_exists = match counterpart.try_exists()
        {
            Ok(true) => true,
            Ok(false) => counterpart.is_symlink(),
            Err(_) => true,
        };
        if !counterpart_exists
        {
            let _ = writeln!(detail, "delete {}", entry.path().display());
            if !dry_run
            {
                if file_type.is_dir()
                {
                    std::fs::remove_dir_all(entry.path()).map_err(Error::io(entry.path()))?;
                }
                else
                {
                    std::fs::remove_file(entry.path()).map_err(Error::io(entry.path()))?;
                }
            }
            hop.deleted += 1;
        }
        else if file_type.is_dir()
        {
            delete_extras(
                &counterpart,
                &entry.path(),
                excludes,
                dry_run,
                log_dir,
                hop,
                detail,
            )?;
        }
    }
    Ok(())
}

/// Copy if the target is missing, or the source is more than 2 seconds newer
/// (FAT and cloud mounts round modification times).
fn needs_copy(source: &Path, target: &Path) -> Result<bool, Error>
{
    let source_meta = std::fs::metadata(source).map_err(Error::io(source.to_path_buf()))?;
    let target_meta = match std::fs::metadata(target)
    {
        Ok(meta) => meta,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(true),
        Err(e) => return Err(Error::io(target.to_path_buf())(e)),
    };
    let source_time = filetime::FileTime::from_last_modification_time(&source_meta);
    let target_time = filetime::FileTime::from_last_modification_time(&target_meta);
    Ok(source_time.seconds() > target_time.seconds() + 2)
}

/// Copies one file atomically, preserving its modification time, with two
/// retries (transient share/mount hiccups — robocopy's /R:2 /W:5, shortened).
///
/// The copy lands in a `*.exporgo-partial` sibling first and is renamed over
/// the target only after its mtime is set. A copy that dies partway therefore
/// never leaves a truncated target with a fresh mtime (which `needs_copy`
/// would treat as up to date forever); at worst it leaves a `.exporgo-partial`
/// temp, which the default excludes keep from ever propagating.
fn copy_with_retry(source: &Path, target: &Path) -> Result<(), Error>
{
    let mut temp_name = target.file_name().unwrap_or_default().to_os_string();
    temp_name.push(".exporgo-partial");
    let temp = target.with_file_name(temp_name);

    let mut attempts = 0;
    let copied = loop
    {
        attempts += 1;
        match copy_via_temp(source, target, &temp)
        {
            Ok(()) => break Ok(()),
            Err(_e) if attempts <= 2 => std::thread::sleep(Duration::from_secs(2)),
            Err(e) => break Err(e),
        }
    };
    if copied.is_err()
    {
        let _ = std::fs::remove_file(&temp);
    }
    copied
}

fn copy_via_temp(source: &Path, target: &Path, temp: &Path) -> Result<(), Error>
{
    std::fs::copy(source, temp).map_err(Error::io(temp.to_path_buf()))?;
    let meta = std::fs::metadata(source).map_err(Error::io(source.to_path_buf()))?;
    let mtime = filetime::FileTime::from_last_modification_time(&meta);
    filetime::set_file_mtime(temp, mtime).map_err(Error::io(temp.to_path_buf()))?;
    std::fs::rename(temp, target).map_err(Error::io(target.to_path_buf()))
}

/// robocopy `/XF`-style match on file *and directory* names: `*` wildcards,
/// ASCII case-insensitive.
fn excluded(name: &str, patterns: &[String]) -> bool
{
    patterns.iter().any(|p| wildcard_match(p, name))
}

/// Linear two-pointer wildcard match with single-star backtracking —
/// O(pattern × name) worst case, unlike the naive recursive matcher, which is
/// exponential in the number of `*`s (a pattern like `*a*a*a*ax` against a long
/// name would hang a sync for minutes).
fn wildcard_match(pattern: &str, name: &str) -> bool
{
    let p = pattern.as_bytes();
    let n = name.as_bytes();
    let (mut pi, mut ni) = (0usize, 0usize);
    let mut backtrack: Option<(usize, usize)> = None; // (pattern idx after '*', name idx)

    while ni < n.len()
    {
        if pi < p.len() && p[pi] == b'*'
        {
            backtrack = Some((pi + 1, ni));
            pi += 1;
        }
        else if pi < p.len() && p[pi].eq_ignore_ascii_case(&n[ni])
        {
            pi += 1;
            ni += 1;
        }
        else if let Some((star_pi, star_ni)) = backtrack
        {
            // Let the last '*' swallow one more character and retry.
            backtrack = Some((star_pi, star_ni + 1));
            pi = star_pi;
            ni = star_ni + 1;
        }
        else
        {
            return false;
        }
    }
    while pi < p.len() && p[pi] == b'*'
    {
        pi += 1;
    }
    pi == p.len()
}

#[cfg(test)]
mod tests
{
    use rstest::rstest;

    use super::*;

    #[rstest]
    #[case("Thumbs.db", "thumbs.db", true)]
    #[case("*.Identifier", "movie.mkv.identifier", true)]
    #[case("*.tmp", "notes.tmp", true)]
    #[case("*.tmp", "notes.tmp.bak", false)]
    #[case("~$*", "~$draft.docx", true)]
    #[case("*", "anything", true)]
    #[case("data.csv", "data.csv.old", false)]
    #[case("*a*x", "aaax", true)]
    // Exponential blowup case for the old recursive matcher; the linear
    // matcher must answer instantly.
    #[case(
        "*a*a*a*a*a*a*a*ax",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        false
    )]
    fn wildcard_cases(#[case] pattern: &str, #[case] name: &str, #[case] expected: bool)
    {
        assert_eq!(
            wildcard_match(pattern, name),
            expected,
            "{pattern} vs {name}"
        );
    }
}
