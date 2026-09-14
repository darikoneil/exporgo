//! End-to-end tests for `exporgo::check::check` against real stamped projects.

use std::path::{Path, PathBuf};

use exporgo::{
    check::check,
    error::Error,
    manifest::{Manifest, Version},
    stamp::{NewOptions, stamp},
    tokens::{Token, TokenValues},
};
use pretty_assertions::assert_eq;

/// A project stamped with every prompted token supplied, so nothing is
/// unfilled (PROJECT_NAME and CREATED_DATE are auto-filled by stamp).
fn fully_filled_project(parent: &Path) -> PathBuf
{
    let mut values = TokenValues::new();
    values.insert(Token::OneLineAim, "Does it remap?".to_string());
    values.insert(Token::Status, "active".to_string());
    values.insert(Token::RepoUrl, "https://github.com/org/repo".to_string());
    values.insert(Token::DataRoot, r"\\ktdata\snlkt\data\proj".to_string());
    values.insert(Token::Owner, "Darik".to_string());
    values.insert(Token::OwnerEmail, "doneil@salk.edu".to_string());
    stamp(&NewOptions {
        name: "Fully Filled".to_string(),
        parent: parent.to_path_buf(),
        values,
        force: false,
        git_init: false,
    })
    .expect("stamp succeeds")
    .root
}

#[test]
fn a_fully_filled_fresh_project_is_clean()
{
    let dir = tempfile::tempdir().unwrap();
    let report = check(&fully_filled_project(dir.path())).unwrap();
    assert_eq!(report.project_version, report.binary_version);
    assert!(report.changes.is_empty(), "{:?}", report.changes);
    assert!(
        report.unfilled_tokens.is_empty(),
        "{:?}",
        report.unfilled_tokens
    );
    assert!(report.missing_dirs.is_empty(), "{:?}", report.missing_dirs);
    assert!(report.is_clean());
}

#[test]
fn version_drift_alone_is_reported_in_both_directions()
{
    let dir = tempfile::tempdir().unwrap();
    let root = fully_filled_project(dir.path());

    let mut manifest = Manifest::load(&root).unwrap();
    manifest.template_version = Version(0, 0, 1);
    manifest.save(&root).unwrap();
    let older = check(&root).unwrap();
    assert!(older.project_version < older.binary_version);
    assert!(
        older.changes.is_empty(),
        "files match; only the version drifted"
    );
    assert!(!older.is_clean());

    // A project from a NEWER template is reported, not an error — unlike
    // `update`, which refuses to downgrade.
    let mut manifest = Manifest::load(&root).unwrap();
    manifest.template_version = Version(999, 0, 0);
    manifest.save(&root).unwrap();
    let newer = check(&root).unwrap();
    assert!(newer.project_version > newer.binary_version);
    assert!(!newer.is_clean());
}

#[test]
fn missing_context_md_is_tolerated()
{
    let dir = tempfile::tempdir().unwrap();
    let root = fully_filled_project(dir.path());
    std::fs::remove_file(root.join("context.md")).unwrap();
    let report = check(&root).unwrap();
    assert!(report.unfilled_tokens.is_empty());
    // context.md is user territory, so its absence is not a pending change.
    assert!(report.changes.is_empty());
}

#[test]
fn unreadable_context_md_is_an_io_error_naming_the_path()
{
    let dir = tempfile::tempdir().unwrap();
    let root = fully_filled_project(dir.path());
    // A directory where the file should be: read_to_string fails with a
    // non-NotFound kind, which must surface rather than be swallowed.
    std::fs::remove_file(root.join("context.md")).unwrap();
    std::fs::create_dir(root.join("context.md")).unwrap();
    let refused = check(&root);
    match refused
    {
        Err(Error::Io { path, .. }) => assert!(path.ends_with("context.md")),
        other => panic!("expected Io error, got {other:?}"),
    }
}

#[test]
fn user_added_placeholders_are_reported()
{
    let dir = tempfile::tempdir().unwrap();
    let root = fully_filled_project(dir.path());
    let context = root.join("context.md");
    let mut text = std::fs::read_to_string(&context).unwrap();
    text.push_str("\n- **Ethics protocol:** {{ETHICS_PROTOCOL}}\n");
    std::fs::write(&context, text).unwrap();

    let report = check(&root).unwrap();
    assert_eq!(
        report.unfilled_tokens,
        vec!["{{ETHICS_PROTOCOL}}".to_string()]
    );
    assert!(!report.is_clean());
}

#[test]
fn check_outside_a_project_is_refused()
{
    let dir = tempfile::tempdir().unwrap();
    assert!(matches!(check(dir.path()), Err(Error::NotAProject(_))));
}
