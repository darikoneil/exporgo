//! End-to-end tests for `exporgo sync` and `exporgo clone`: two simulated
//! machines (separate local dirs and caches) converging through one shared
//! remote.

use std::path::{Path, PathBuf};

use exporgo::{
    error::Error,
    sync::{CloneOptions, Mode, SyncOptions, clone_project, sync},
};
use pretty_assertions::assert_eq;

/// One machine's view of the project: its local copy, cache, and logs.
struct Machine
{
    local: PathBuf,
    cache: PathBuf,
    logs: PathBuf,
}

/// Two machines sharing a single remote, as in real multi-computer use.
struct Fixture
{
    _dir: tempfile::TempDir,
    remote: PathBuf,
    a: Machine,
    b: Machine,
}

fn fixture() -> Fixture
{
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let machine = |name: &str| Machine {
        local: root.join(name).join("projects/pilot"),
        cache: root.join(name).join("cache/pilot"),
        logs: root.join(name).join("logs/pilot"),
    };
    let fixture = Fixture {
        remote: root.join("remote-root/pilot"),
        a: machine("machine-a"),
        b: machine("machine-b"),
        _dir: dir,
    };
    // Machine A starts with the project; B starts empty (it will clone or
    // receive files via the remote).
    std::fs::create_dir_all(fixture.a.local.join("experiments")).unwrap();
    std::fs::create_dir_all(&fixture.b.local).unwrap();
    std::fs::write(fixture.a.local.join("context.md"), "# Pilot\n").unwrap();
    std::fs::write(fixture.a.local.join("experiments/notes.md"), "observations").unwrap();
    std::fs::write(fixture.a.local.join("Thumbs.db"), "cruft").unwrap();
    fixture
}

fn options(fixture: &Fixture, machine: &Machine, mode: Mode) -> SyncOptions
{
    SyncOptions {
        local: machine.local.clone(),
        cache: machine.cache.clone(),
        remote: fixture.remote.clone(),
        mode,
        exclude: Vec::new(),
        mirror: false,
        dry_run: false,
        log_dir: machine.logs.clone(),
    }
}

#[test]
fn first_sync_creates_the_remote_and_skips_the_pull()
{
    let f = fixture();
    let report = sync(&options(&f, &f.a, Mode::Both)).expect("first sync succeeds");

    // No remote existed, so only the push phase ran (two hops, not four).
    assert_eq!(report.hops.len(), 2);
    for root in [&f.a.cache, &f.remote]
    {
        assert_eq!(
            std::fs::read_to_string(root.join("context.md")).unwrap(),
            "# Pilot\n"
        );
        assert!(root.join("experiments/notes.md").is_file());
        assert!(!root.join("Thumbs.db").exists(), "default excludes apply");
    }
    assert!(report.summary.contains("=> OK"));
    assert!(f.a.logs.join("_sync_history.log").is_file());
    assert!(f.a.logs.join("_sync_detail.log").is_file());
}

#[test]
fn an_edit_on_a_reaches_b_through_the_remote()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    let report = sync(&options(&f, &f.b, Mode::Both)).unwrap();

    assert_eq!(report.hops.len(), 4, "remote exists: pull then push");
    assert_eq!(
        std::fs::read_to_string(f.b.local.join("context.md")).unwrap(),
        "# Pilot\n"
    );
    assert!(f.b.local.join("experiments/notes.md").is_file());
}

#[test]
fn divergent_edits_to_different_files_converge()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    sync(&options(&f, &f.b, Mode::Both)).unwrap();

    std::fs::write(f.a.local.join("from-a.md"), "a's work").unwrap();
    std::fs::write(f.b.local.join("from-b.md"), "b's work").unwrap();

    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    sync(&options(&f, &f.b, Mode::Both)).unwrap();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();

    for local in [&f.a.local, &f.b.local]
    {
        assert_eq!(
            std::fs::read_to_string(local.join("from-a.md")).unwrap(),
            "a's work"
        );
        assert_eq!(
            std::fs::read_to_string(local.join("from-b.md")).unwrap(),
            "b's work"
        );
    }
}

#[test]
fn same_file_edited_on_both_sides_newest_wins_everywhere()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    sync(&options(&f, &f.b, Mode::Both)).unwrap();

    // B's edit is clearly newer than A's (past the 2-second slack).
    let now = filetime::FileTime::now().unix_seconds();
    let a_file = f.a.local.join("context.md");
    let b_file = f.b.local.join("context.md");
    std::fs::write(&a_file, "# Pilot (a's stale edit)\n").unwrap();
    filetime::set_file_mtime(&a_file, filetime::FileTime::from_unix_time(now, 0)).unwrap();
    std::fs::write(&b_file, "# Pilot (b's newer edit)\n").unwrap();
    filetime::set_file_mtime(&b_file, filetime::FileTime::from_unix_time(now + 10, 0)).unwrap();

    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    sync(&options(&f, &f.b, Mode::Both)).unwrap();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();

    for path in [&a_file, &b_file, &f.remote.join("context.md")]
    {
        assert_eq!(
            std::fs::read_to_string(path).unwrap(),
            "# Pilot (b's newer edit)\n"
        );
    }
}

#[test]
fn a_newer_local_file_is_never_overwritten_by_a_pull()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();

    let local_file = f.a.local.join("context.md");
    std::fs::write(&local_file, "fresh local work").unwrap();
    let future =
        filetime::FileTime::from_unix_time(filetime::FileTime::now().unix_seconds() + 3600, 0);
    filetime::set_file_mtime(&local_file, future).unwrap();

    sync(&options(&f, &f.a, Mode::Pull)).unwrap();
    assert_eq!(
        std::fs::read_to_string(&local_file).unwrap(),
        "fresh local work"
    );
}

#[test]
fn git_directories_never_propagate()
{
    let f = fixture();
    std::fs::create_dir_all(f.a.local.join(".git/objects")).unwrap();
    std::fs::write(f.a.local.join(".git/config"), "[core]").unwrap();

    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    assert!(
        !f.a.cache.join(".git").exists(),
        ".git kept out of the cache"
    );
    assert!(!f.remote.join(".git").exists(), ".git kept off the remote");
}

#[test]
fn pull_with_no_remote_copy_is_refused()
{
    let f = fixture();
    let refused = sync(&options(&f, &f.a, Mode::Pull));
    assert!(matches!(refused, Err(Error::RemoteProjectMissing(_))));
}

#[test]
fn mirror_without_an_explicit_direction_is_refused()
{
    let f = fixture();
    let mut opts = options(&f, &f.a, Mode::Both);
    opts.mirror = true;
    assert!(matches!(sync(&opts), Err(Error::MirrorNeedsDirection)));
}

#[test]
fn deletion_resurrects_on_sync_but_push_mirror_cleans_up()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();

    // Non-destructive sync pulls a locally deleted file straight back — the
    // documented tradeoff of never propagating deletions.
    let deleted = f.a.local.join("experiments/notes.md");
    std::fs::remove_file(&deleted).unwrap();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    assert!(deleted.is_file(), "bidirectional sync resurrects deletions");

    // The deliberate cleanup: push --mirror makes cache and remote match the
    // local tree exactly.
    std::fs::remove_file(&deleted).unwrap();
    let mut opts = options(&f, &f.a, Mode::Push);
    opts.mirror = true;
    let report = sync(&opts).unwrap();
    assert!(!f.a.cache.join("experiments/notes.md").exists());
    assert!(!f.remote.join("experiments/notes.md").exists());
    assert_eq!(report.hops.iter().map(|h| h.deleted).sum::<usize>(), 2);
}

#[test]
fn dry_run_changes_nothing()
{
    let f = fixture();
    let mut opts = options(&f, &f.a, Mode::Both);
    opts.dry_run = true;
    let report = sync(&opts).unwrap();
    assert!(report.hops[0].copied > 0, "dry run still plans the copies");
    assert!(!cache_has_entries(&f.a.cache));
    assert!(!f.remote.exists());
    assert!(report.summary.contains("(dry run)"));
}

fn cache_has_entries(path: &Path) -> bool
{
    std::fs::read_dir(path)
        .map(|mut d| d.next().is_some())
        .unwrap_or(false)
}

#[test]
fn missing_local_aborts_a_push_and_still_writes_a_history_line()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    let remote_before = std::fs::read_to_string(f.remote.join("context.md")).unwrap();

    std::fs::remove_dir_all(&f.a.local).unwrap();
    std::fs::write(f.a.cache.join("context.md"), "stale").unwrap();
    let future =
        filetime::FileTime::from_unix_time(filetime::FileTime::now().unix_seconds() + 3600, 0);
    filetime::set_file_mtime(f.a.cache.join("context.md"), future).unwrap();

    let refused = sync(&options(&f, &f.a, Mode::Push));
    assert!(matches!(refused, Err(Error::SyncSourceMissing(_))));
    assert_eq!(
        std::fs::read_to_string(f.remote.join("context.md")).unwrap(),
        remote_before,
        "the cache->remote hop must not run after local->cache fails"
    );
    let history = std::fs::read_to_string(f.a.logs.join("_sync_history.log")).unwrap();
    assert!(
        history.contains("FAIL"),
        "audit trail must record failed runs: {history}"
    );
}

#[test]
fn overlapping_paths_are_rejected()
{
    let f = fixture();

    let mut nested = options(&f, &f.a, Mode::Both);
    nested.cache = f.a.local.join("_cache");
    assert!(matches!(sync(&nested), Err(Error::SyncPathsOverlap { .. })));
    assert!(!f.a.local.join("_cache").exists(), "nothing was created");

    let mut same = options(&f, &f.a, Mode::Both);
    same.remote = f.a.local.clone();
    assert!(matches!(sync(&same), Err(Error::SyncPathsOverlap { .. })));
}

#[test]
fn two_second_slack_is_respected_on_push()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();
    let local_file = f.a.local.join("context.md");
    let cache_time = filetime::FileTime::from_last_modification_time(
        &std::fs::metadata(f.a.cache.join("context.md")).unwrap(),
    );

    // 1 second newer: within slack, must not copy.
    filetime::set_file_mtime(
        &local_file,
        filetime::FileTime::from_unix_time(cache_time.unix_seconds() + 1, 0),
    )
    .unwrap();
    let report = sync(&options(&f, &f.a, Mode::Push)).unwrap();
    assert_eq!(report.hops[0].copied, 0, "within-slack change is skipped");

    // 5 seconds newer: past slack, must copy through both hops.
    filetime::set_file_mtime(
        &local_file,
        filetime::FileTime::from_unix_time(cache_time.unix_seconds() + 5, 0),
    )
    .unwrap();
    let report = sync(&options(&f, &f.a, Mode::Push)).unwrap();
    assert_eq!(report.hops[0].copied, 1, "past-slack change is copied");
    assert_eq!(report.hops[1].copied, 1);
}

#[test]
fn custom_excludes_apply()
{
    let f = fixture();
    std::fs::write(f.a.local.join("scratch.tmp"), "x").unwrap();
    let mut opts = options(&f, &f.a, Mode::Both);
    opts.exclude = vec!["*.tmp".to_string()];
    sync(&opts).unwrap();
    assert!(!f.remote.join("scratch.tmp").exists());
    assert!(f.remote.join("context.md").is_file());
}

#[test]
fn clone_reproduces_the_remote_and_a_following_sync_is_idle()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();

    // A brand-new machine: fresh target, its own cache and logs.
    let target = f.b.local.parent().unwrap().join("cloned-pilot");
    clone_project(&CloneOptions {
        remote: f.remote.clone(),
        cache: f.b.cache.clone(),
        target: target.clone(),
        log_dir: f.b.logs.clone(),
    })
    .expect("clone succeeds");

    assert_eq!(
        std::fs::read_to_string(target.join("context.md")).unwrap(),
        "# Pilot\n"
    );
    assert!(target.join("experiments/notes.md").is_file());

    // Cloned copies keep the remote's mtimes, so the next sync moves nothing.
    let report = sync(&SyncOptions {
        local: target,
        cache: f.b.cache.clone(),
        remote: f.remote.clone(),
        mode: Mode::Both,
        exclude: Vec::new(),
        mirror: false,
        dry_run: false,
        log_dir: f.b.logs.clone(),
    })
    .unwrap();
    assert_eq!(
        report.hops.iter().map(|h| h.copied).sum::<usize>(),
        0,
        "a fresh clone is already converged"
    );
}

#[test]
fn clone_refuses_a_non_empty_target_and_a_missing_remote()
{
    let f = fixture();
    sync(&options(&f, &f.a, Mode::Both)).unwrap();

    let refused = clone_project(&CloneOptions {
        remote: f.remote.clone(),
        cache: f.b.cache.clone(),
        target: f.a.local.clone(),
        log_dir: f.b.logs.clone(),
    });
    assert!(matches!(refused, Err(Error::CloneTargetNotEmpty(_))));

    let no_remote = clone_project(&CloneOptions {
        remote: f.remote.parent().unwrap().join("never-pushed"),
        cache: f.b.cache.clone(),
        target: f.b.local.parent().unwrap().join("fresh"),
        log_dir: f.b.logs.clone(),
    });
    assert!(matches!(no_remote, Err(Error::RemoteProjectMissing(_))));
}
