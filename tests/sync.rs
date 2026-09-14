//! End-to-end tests for `exporgo sync`: two-hop copies through temp
//! directories.

use std::path::{Path, PathBuf};

use exporgo::{
    error::Error,
    sync::{Direction, SyncOptions, sync},
};
use pretty_assertions::assert_eq;

struct Fixture
{
    _dir: tempfile::TempDir,
    source: PathBuf,
    intermediate: PathBuf,
    destination: PathBuf,
    logs: PathBuf,
}

fn fixture() -> Fixture
{
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().to_path_buf();
    let fixture = Fixture {
        source: root.join("source"),
        intermediate: root.join("intermediate"),
        destination: root.join("destination"),
        logs: root.join("logs"),
        _dir: dir,
    };
    std::fs::create_dir_all(fixture.source.join("nested")).unwrap();
    std::fs::write(fixture.source.join("data.csv"), "a,b\n1,2\n").unwrap();
    std::fs::write(fixture.source.join("nested/notes.md"), "notes").unwrap();
    std::fs::write(fixture.source.join("Thumbs.db"), "cruft").unwrap();
    fixture
}

fn options(f: &Fixture) -> SyncOptions
{
    SyncOptions {
        source: f.source.clone(),
        intermediate: f.intermediate.clone(),
        destination: f.destination.clone(),
        direction: Direction::Forward,
        exclude: Vec::new(),
        mirror: false,
        dry_run: false,
        log_dir: f.logs.clone(),
    }
}

#[test]
fn forward_sync_copies_through_both_hops_and_skips_cruft()
{
    let f = fixture();
    let report = sync(&options(&f)).expect("sync succeeds");

    for root in [&f.intermediate, &f.destination]
    {
        assert_eq!(
            std::fs::read_to_string(root.join("data.csv")).unwrap(),
            "a,b\n1,2\n"
        );
        assert!(root.join("nested/notes.md").is_file());
        assert!(!root.join("Thumbs.db").exists(), "default excludes apply");
    }
    assert_eq!(report.hops.len(), 2);
    assert_eq!(report.hops[0].copied, 2);
    assert_eq!(report.hops[1].copied, 2);
    assert!(report.summary.contains("=> OK"));
    assert!(f.logs.join("_sync_history.log").is_file());
    assert!(f.logs.join("_sync_detail.log").is_file());
}

#[test]
fn rerun_copies_nothing_and_newer_target_is_not_overwritten()
{
    let f = fixture();
    sync(&options(&f)).unwrap();

    // Idempotent: mtimes were preserved, so nothing is newer.
    let rerun = sync(&options(&f)).unwrap();
    assert_eq!(rerun.hops[0].copied + rerun.hops[1].copied, 0);

    // A target file *newer* than the source must be left alone (robocopy /XO).
    let dest_file = f.destination.join("data.csv");
    std::fs::write(&dest_file, "newer content").unwrap();
    let future =
        filetime::FileTime::from_unix_time(filetime::FileTime::now().unix_seconds() + 3600, 0);
    filetime::set_file_mtime(&dest_file, future).unwrap();
    sync(&options(&f)).unwrap();
    assert_eq!(
        std::fs::read_to_string(&dest_file).unwrap(),
        "newer content"
    );
}

#[test]
fn non_destructive_by_default_but_mirror_deletes_extras()
{
    let f = fixture();
    sync(&options(&f)).unwrap();

    let extra = f.destination.join("only-here.txt");
    std::fs::write(&extra, "local work").unwrap();

    sync(&options(&f)).unwrap();
    assert!(extra.is_file(), "default sync never deletes");

    let mut mirrored = options(&f);
    mirrored.mirror = true;
    let report = sync(&mirrored).unwrap();
    assert!(!extra.exists(), "--mirror deletes extras");
    assert_eq!(report.hops[1].deleted, 1);
}

#[test]
fn dry_run_changes_nothing()
{
    let f = fixture();
    let mut opts = options(&f);
    opts.dry_run = true;
    let report = sync(&opts).unwrap();
    assert!(report.hops[0].copied > 0, "dry run still plans the copies");
    assert!(!f.intermediate.exists() || dir_is_empty(&f.intermediate));
    assert!(!f.destination.exists());
    assert!(report.summary.contains("(dry run)"));
}

fn dir_is_empty(path: &Path) -> bool
{
    std::fs::read_dir(path)
        .map(|mut d| d.next().is_none())
        .unwrap_or(true)
}

#[test]
fn missing_source_aborts_before_second_hop()
{
    let f = fixture();
    sync(&options(&f)).unwrap();
    let destination_before = std::fs::read_to_string(f.destination.join("data.csv")).unwrap();

    // Simulate an unmounted drive: the forward source disappears, and the
    // destination gains new work that a blind mirror would have clobbered.
    std::fs::remove_dir_all(&f.source).unwrap();
    std::fs::write(f.intermediate.join("data.csv"), "stale").unwrap();

    let refused = sync(&options(&f));
    assert!(matches!(refused, Err(Error::SyncSourceMissing(_))));
    assert_eq!(
        std::fs::read_to_string(f.destination.join("data.csv")).unwrap(),
        destination_before,
        "hop 2 must not run after hop 1 fails"
    );
}

#[test]
fn reverse_direction_pulls_destination_back_to_source()
{
    let f = fixture();
    sync(&options(&f)).unwrap();
    std::fs::write(f.destination.join("from-dest.txt"), "made remotely").unwrap();

    let mut reverse = options(&f);
    reverse.direction = Direction::Reverse;
    sync(&reverse).unwrap();
    assert_eq!(
        std::fs::read_to_string(f.source.join("from-dest.txt")).unwrap(),
        "made remotely"
    );
}

#[test]
fn newer_source_files_propagate()
{
    let f = fixture();
    sync(&options(&f)).unwrap();

    // Update the source and push its mtime clearly past the 2-second slack.
    let source_file = f.source.join("data.csv");
    std::fs::write(&source_file, "a,b\n9,9\n").unwrap();
    let dest_time = filetime::FileTime::from_last_modification_time(
        &std::fs::metadata(f.destination.join("data.csv")).unwrap(),
    );
    filetime::set_file_mtime(
        &source_file,
        filetime::FileTime::from_unix_time(dest_time.unix_seconds() + 10, 0),
    )
    .unwrap();

    let report = sync(&options(&f)).unwrap();
    assert_eq!(report.hops[0].copied, 1);
    assert_eq!(report.hops[1].copied, 1);
    assert_eq!(
        std::fs::read_to_string(f.destination.join("data.csv")).unwrap(),
        "a,b\n9,9\n"
    );
}

#[test]
fn copies_preserve_source_mtime()
{
    let f = fixture();
    sync(&options(&f)).unwrap();
    let source_time = filetime::FileTime::from_last_modification_time(
        &std::fs::metadata(f.source.join("data.csv")).unwrap(),
    );
    for root in [&f.intermediate, &f.destination]
    {
        let copied_time = filetime::FileTime::from_last_modification_time(
            &std::fs::metadata(root.join("data.csv")).unwrap(),
        );
        assert_eq!(copied_time, source_time, "mtime must survive the copy");
    }
}

#[test]
fn two_second_slack_is_respected()
{
    let f = fixture();
    sync(&options(&f)).unwrap();
    let source_file = f.source.join("data.csv");
    let target_time = filetime::FileTime::from_last_modification_time(
        &std::fs::metadata(f.intermediate.join("data.csv")).unwrap(),
    );

    // 1 second newer: within slack, must not copy.
    filetime::set_file_mtime(
        &source_file,
        filetime::FileTime::from_unix_time(target_time.unix_seconds() + 1, 0),
    )
    .unwrap();
    let report = sync(&options(&f)).unwrap();
    let detail = std::fs::read_to_string(f.logs.join("_sync_detail.log")).unwrap();
    assert_eq!(
        report.hops[0].copied, 0,
        "within-slack change must be skipped; detail log:\n{detail}"
    );

    // 5 seconds newer: past slack, must copy.
    filetime::set_file_mtime(
        &source_file,
        filetime::FileTime::from_unix_time(target_time.unix_seconds() + 5, 0),
    )
    .unwrap();
    let report = sync(&options(&f)).unwrap();
    assert_eq!(report.hops[0].copied, 1, "past-slack change must be copied");
}

#[test]
fn overlapping_paths_are_rejected()
{
    let f = fixture();

    let mut nested = options(&f);
    nested.intermediate = f.source.join("_mirror");
    assert!(matches!(sync(&nested), Err(Error::SyncPathsOverlap { .. })));
    assert!(!f.source.join("_mirror").exists(), "nothing was created");

    let mut same = options(&f);
    same.destination = f.source.clone();
    assert!(matches!(sync(&same), Err(Error::SyncPathsOverlap { .. })));
}

#[test]
fn failed_run_still_writes_a_history_line()
{
    let f = fixture();
    std::fs::remove_dir_all(&f.source).unwrap();
    let refused = sync(&options(&f));
    assert!(matches!(refused, Err(Error::SyncSourceMissing(_))));
    let history = std::fs::read_to_string(f.logs.join("_sync_history.log")).unwrap();
    assert!(
        history.contains("FAIL"),
        "audit trail must record failed runs: {history}"
    );
}

#[test]
fn mirror_never_deletes_the_log_directory()
{
    let f = fixture();
    let mut opts = options(&f);
    // Logs live inside the destination — the case where a mirror pass would
    // otherwise see them as extras and delete the open log directory.
    opts.log_dir = f.destination.join("_logs");
    opts.mirror = true;
    sync(&opts).unwrap();
    let report = sync(&opts).unwrap();
    assert!(opts.log_dir.join("_sync_history.log").is_file());
    assert_eq!(
        report.hops[1].deleted, 0,
        "log dir must not count as an extra"
    );
}

#[test]
fn custom_excludes_apply()
{
    let f = fixture();
    std::fs::write(f.source.join("scratch.tmp"), "x").unwrap();
    let mut opts = options(&f);
    opts.exclude = vec!["*.tmp".to_string()];
    sync(&opts).unwrap();
    assert!(!f.destination.join("scratch.tmp").exists());
    assert!(f.destination.join("data.csv").is_file());
}
