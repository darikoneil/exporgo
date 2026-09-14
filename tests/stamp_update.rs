//! End-to-end library tests: stamp a project into a temp dir, mutate it, update it.

use std::path::{Path, PathBuf};

use exporgo::error::Error;
use exporgo::manifest::{Manifest, Version};
use exporgo::plan::ChangeKind;
use exporgo::stamp::{NewOptions, stamp};
use exporgo::tokens::{Token, TokenValues};
use exporgo::update::{UpdateOptions, update};
use exporgo::{check, template};
use pretty_assertions::assert_eq;

fn options(name: &str, parent: &Path) -> NewOptions {
    let mut values = TokenValues::new();
    values.insert(Token::OneLineAim, "Does it remap?".to_string());
    values.insert(Token::Status, "active".to_string());
    NewOptions {
        name: name.to_string(),
        parent: parent.to_path_buf(),
        values,
        force: false,
        git_init: false,
    }
}

fn stamp_fresh(parent: &Path) -> PathBuf {
    stamp(&options("Grid Cell Remapping", parent))
        .expect("stamp succeeds")
        .root
}

#[test]
fn stamp_creates_a_complete_project() {
    let dir = tempfile::tempdir().unwrap();
    let report = stamp(&options("Grid Cell Remapping", dir.path())).expect("stamp succeeds");

    assert_eq!(report.root, dir.path().join("grid-cell-remapping"));
    assert!(report.root.join("exporgo.toml").is_file());

    let manifest = Manifest::load(&report.root).expect("manifest parses");
    assert_eq!(manifest.project, "Grid Cell Remapping");
    assert_eq!(manifest.template_version, Version::current());
    assert_eq!(
        manifest.tokens.get("status").map(String::as_str),
        Some("active")
    );

    for standard_dir in template::STANDARD_DIRS {
        assert!(
            template::dest_path(&report.root, standard_dir).is_dir(),
            "missing standard dir {standard_dir}"
        );
    }

    let context = std::fs::read_to_string(report.root.join("context.md")).unwrap();
    assert!(context.contains("# Grid Cell Remapping"));
    assert!(context.contains("Does it remap?"));
    assert!(
        context.contains("{{REPO_URL}}"),
        "skipped token stays visible"
    );
    assert!(report.unfilled.contains(&"{{REPO_URL}}".to_string()));

    // Excluded files must not materialize.
    for forbidden in [
        "HANDOFF.md",
        ".claude/skills/exporgo/code/agents/references",
    ] {
        assert!(!template::dest_path(&report.root, forbidden).exists());
    }
}

#[test]
fn stamp_guards_against_collisions() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().join("grid-cell-remapping");
    std::fs::create_dir_all(&root).unwrap();
    std::fs::write(root.join("existing.txt"), "hello").unwrap();

    let refused = stamp(&options("Grid Cell Remapping", dir.path()));
    assert!(matches!(refused, Err(Error::TargetNotEmpty(_))));

    let mut forced = options("Grid Cell Remapping", dir.path());
    forced.force = true;
    stamp(&forced).expect("force stamps into non-empty dir");
    assert!(root.join("existing.txt").is_file(), "force never wipes");

    // Re-stamping an existing project is refused even with force.
    let mut again = options("Grid Cell Remapping", dir.path());
    again.force = true;
    assert!(matches!(stamp(&again), Err(Error::AlreadyAProject(_))));
}

#[test]
fn update_restores_owned_and_leaves_user_files_alone() {
    let dir = tempfile::tempdir().unwrap();
    let root = stamp_fresh(dir.path());

    let owned = root.join("SKILLS.md");
    let user = root.join("context.md");
    let stray = root.join(".claude/skills/exporgo/stray-note.md");
    std::fs::write(&owned, "vandalized").unwrap();
    let user_content = std::fs::read_to_string(&user).unwrap();
    std::fs::write(&stray, "user file inside owned dir").unwrap();

    let changes = update(
        &root,
        &UpdateOptions {
            dry_run: false,
            skills_only: false,
        },
    )
    .expect("update succeeds");

    assert_eq!(changes.len(), 1);
    assert_eq!(changes[0].rel, "SKILLS.md");
    assert_eq!(changes[0].kind, ChangeKind::Overwrite);

    let restored = std::fs::read(&owned).unwrap();
    let embedded = template::file_contents("SKILLS.md").unwrap();
    assert!(exporgo::plan::normalized_eq(&restored, embedded));
    assert_eq!(std::fs::read_to_string(&user).unwrap(), user_content);
    assert!(stray.is_file(), "update never deletes");

    let manifest = Manifest::load(&root).unwrap();
    assert_eq!(manifest.template_version, Version::current());
    assert_eq!(manifest.project, "Grid Cell Remapping");
}

#[test]
fn dry_run_and_skills_only_scope_correctly() {
    let dir = tempfile::tempdir().unwrap();
    let root = stamp_fresh(dir.path());

    std::fs::write(root.join("SKILLS.md"), "changed").unwrap();
    std::fs::write(
        root.join(".claude/skills/exporgo/code/CLAUDE.md"),
        "changed",
    )
    .unwrap();

    let planned = update(
        &root,
        &UpdateOptions {
            dry_run: true,
            skills_only: false,
        },
    )
    .unwrap();
    assert_eq!(planned.len(), 2);
    assert_eq!(
        std::fs::read_to_string(root.join("SKILLS.md")).unwrap(),
        "changed"
    );

    let applied = update(
        &root,
        &UpdateOptions {
            dry_run: false,
            skills_only: true,
        },
    )
    .unwrap();
    assert_eq!(applied.len(), 1);
    assert_eq!(applied[0].rel, ".claude/skills/exporgo/code/CLAUDE.md");
    assert_eq!(
        std::fs::read_to_string(root.join("SKILLS.md")).unwrap(),
        "changed",
        "--skills-only must not touch root docs"
    );
}

#[test]
fn stamp_rejects_bad_and_reserved_names() {
    let dir = tempfile::tempdir().unwrap();
    for name in ["!!!", "CON", "lpt7"] {
        let refused = stamp(&options(name, dir.path()));
        assert!(
            matches!(refused, Err(Error::BadSlug(_))),
            "'{name}' should be rejected"
        );
    }
}

#[test]
fn update_bumps_an_older_version_and_skills_only_does_not() {
    let dir = tempfile::tempdir().unwrap();
    let root = stamp_fresh(dir.path());

    let mut manifest = Manifest::load(&root).unwrap();
    manifest.template_version = Version(0, 0, 1);
    manifest.save(&root).unwrap();

    update(
        &root,
        &UpdateOptions {
            dry_run: false,
            skills_only: true,
        },
    )
    .unwrap();
    assert_eq!(
        Manifest::load(&root).unwrap().template_version,
        Version(0, 0, 1),
        "--skills-only must leave the manifest version alone"
    );

    update(
        &root,
        &UpdateOptions {
            dry_run: false,
            skills_only: false,
        },
    )
    .unwrap();
    let after = Manifest::load(&root).unwrap();
    assert_eq!(after.template_version, Version::current());
    assert_eq!(
        after.project, "Grid Cell Remapping",
        "other fields preserved"
    );
}

#[test]
fn check_ignores_line_ending_differences() {
    let dir = tempfile::tempdir().unwrap();
    let root = stamp_fresh(dir.path());

    // Rewrite an owned file with the opposite line endings from the embed.
    let embedded = std::str::from_utf8(template::file_contents("CLAUDE.md").unwrap()).unwrap();
    let flipped = if embedded.contains("\r\n") {
        embedded.replace("\r\n", "\n")
    } else {
        embedded.replace('\n', "\r\n")
    };
    std::fs::write(root.join("CLAUDE.md"), flipped).unwrap();

    let report = check::check(&root).unwrap();
    assert!(
        report.changes.is_empty(),
        "line-ending-only differences must not count as drift: {:?}",
        report.changes
    );
}

#[test]
fn update_refuses_project_from_a_newer_template() {
    let dir = tempfile::tempdir().unwrap();
    let root = stamp_fresh(dir.path());

    let mut manifest = Manifest::load(&root).unwrap();
    manifest.template_version = Version(999, 0, 0);
    manifest.save(&root).unwrap();

    let refused = update(
        &root,
        &UpdateOptions {
            dry_run: false,
            skills_only: false,
        },
    );
    assert!(matches!(refused, Err(Error::BinaryTooOld { .. })));
}

#[test]
fn update_outside_a_project_is_refused() {
    let dir = tempfile::tempdir().unwrap();
    let refused = update(
        dir.path(),
        &UpdateOptions {
            dry_run: false,
            skills_only: false,
        },
    );
    assert!(matches!(refused, Err(Error::NotAProject(_))));
}

#[test]
fn check_reports_drift_and_cleanliness() {
    let dir = tempfile::tempdir().unwrap();
    let root = stamp_fresh(dir.path());

    let fresh = check::check(&root).unwrap();
    assert!(fresh.changes.is_empty());
    assert!(fresh.missing_dirs.is_empty());
    assert_eq!(fresh.project_version, fresh.binary_version);
    // REPO_URL etc. were skipped at stamp time, so a fresh project is not "clean".
    assert!(!fresh.unfilled_tokens.is_empty());
    assert!(!fresh.is_clean());

    std::fs::write(root.join("CLAUDE.md"), "changed").unwrap();
    std::fs::remove_dir(root.join("literature")).unwrap();
    let drifted = check::check(&root).unwrap();
    assert_eq!(drifted.changes.len(), 1);
    assert_eq!(drifted.changes[0].rel, "CLAUDE.md");
    assert_eq!(drifted.missing_dirs, vec!["literature".to_string()]);
}
