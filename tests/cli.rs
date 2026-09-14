//! End-to-end tests of the compiled `exporgo` binary.
#![cfg(feature = "cli")]

use std::path::Path;

use assert_cmd::Command;

fn stamped_project(dir: &Path, extra_args: &[&str]) -> std::path::PathBuf
{
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input"])
        .args(["--path", dir.to_str().unwrap()])
        .args(extra_args)
        .assert()
        .success();
    dir.join("pilot-study")
}

#[test]
fn version_prints_crate_version()
{
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("--version")
        .assert()
        .success()
        .stdout(predicates::str::contains(env!("CARGO_PKG_VERSION")));
}

#[test]
fn new_no_input_stamps_a_project()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input", "--status", "planning"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicates::str::contains("Created"));
    assert!(dir.path().join("pilot-study/exporgo.toml").is_file());
}

#[test]
fn update_outside_a_project_fails_with_message()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("update")
        .current_dir(dir.path())
        .assert()
        .failure()
        .stderr(predicates::str::contains("not an exporgo project"));
}

#[test]
fn new_refuses_a_duplicate_project_with_a_pointer_to_update()
{
    let dir = tempfile::tempdir().unwrap();
    stamped_project(dir.path(), &[]);
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input", "--force"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .code(2)
        .stderr(predicates::str::contains("exporgo update"));
}

#[test]
fn new_refuses_a_name_with_no_usable_slug()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "!!!", "--no-input"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .code(2)
        .stderr(predicates::str::contains("folder name"));
}

#[test]
fn new_rejects_an_unknown_status_value()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot", "--no-input", "--status", "procrastinating"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .failure()
        .stderr(predicates::str::contains("invalid value"));
    assert!(!dir.path().join("pilot").exists(), "nothing stamped");
}

#[test]
fn new_git_flag_initializes_a_repository()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &["--git"]);
    assert!(project.join(".git").is_dir(), "git init ran");
}

#[test]
fn check_exits_zero_on_a_fully_filled_project_and_two_outside_one()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(
        dir.path(),
        &[
            "--aim",
            "Does it remap?",
            "--status",
            "active",
            "--repo",
            "https://github.com/org/repo",
            "--data-root",
            r"\\ktdata\snlkt\data\pilot",
            "--owner",
            "Darik",
            "--email",
            "doneil@salk.edu",
        ],
    );
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(&project)
        .assert()
        .code(0)
        .stdout(predicates::str::contains("up to date"));

    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(dir.path())
        .assert()
        .code(2)
        .stderr(predicates::str::contains("not an exporgo project"));
}

#[test]
fn update_output_distinguishes_clean_dry_run_and_applied()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);

    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("update")
        .current_dir(&project)
        .assert()
        .success()
        .stdout(predicates::str::contains("Already up to date"));

    std::fs::write(project.join("SKILLS.md"), "vandalized").unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["update", "--dry-run"])
        .current_dir(&project)
        .assert()
        .success()
        .stdout(predicates::str::contains("Would apply"));
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("update")
        .current_dir(&project)
        .assert()
        .success()
        .stdout(predicates::str::contains("Applied"));
}

#[test]
fn sync_runs_flag_driven_warns_on_mirror_and_rejects_overlap()
{
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("src");
    std::fs::create_dir_all(&source).unwrap();
    std::fs::write(source.join("a.txt"), "x").unwrap();
    let flags = |from: &Path, mid: &str, to: &str| {
        vec![
            "--source".to_string(),
            from.to_string_lossy().to_string(),
            "--intermediate".to_string(),
            dir.path().join(mid).to_string_lossy().to_string(),
            "--destination".to_string(),
            dir.path().join(to).to_string_lossy().to_string(),
            "--log-dir".to_string(),
            dir.path().join("logs").to_string_lossy().to_string(),
        ]
    };

    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("sync")
        .args(flags(&source, "mid", "dst"))
        .arg("--mirror")
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicates::str::contains("=> OK"))
        .stderr(predicates::str::contains("DELETES"));

    // Intermediate nested inside the source: refused before anything runs.
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("sync")
        .args(flags(&source, "src/nested-mid", "dst2"))
        .current_dir(dir.path())
        .assert()
        .code(2)
        .stderr(predicates::str::contains("overlap"));
    assert!(!dir.path().join("dst2").exists());
}

#[test]
fn sync_reads_the_manifest_config_and_reports_reverse_runs()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);
    let source = dir.path().join("src");
    std::fs::create_dir_all(&source).unwrap();
    std::fs::write(source.join("a.txt"), "x").unwrap();

    let manifest_path = project.join("exporgo.toml");
    let mut manifest_text = std::fs::read_to_string(&manifest_path).unwrap();
    manifest_text.push_str(&format!(
        "\n[sync]\nsource = '{}'\nintermediate = '{}'\ndestination = '{}'\n",
        source.display(),
        dir.path().join("mid").display(),
        dir.path().join("dst").display(),
    ));
    std::fs::write(&manifest_path, manifest_text).unwrap();

    // Forward, no flags at all: every path comes from the [sync] table.
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("sync")
        .current_dir(&project)
        .assert()
        .success()
        .stdout(predicates::str::contains("=> OK"));
    assert!(dir.path().join("dst/a.txt").is_file());

    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["sync", "--direction", "reverse"])
        .current_dir(&project)
        .assert()
        .success()
        .stdout(predicates::str::contains("Reverse done"));
}

#[test]
fn sync_with_no_paths_anywhere_is_unconfigured()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("sync")
        .current_dir(dir.path())
        .assert()
        .code(2)
        .stderr(predicates::str::contains("sync paths incomplete"));
}

#[test]
fn check_prints_version_drift_in_both_directions()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);
    let manifest_path = project.join("exporgo.toml");
    let manifest_text = std::fs::read_to_string(&manifest_path).unwrap();

    let older = manifest_text.replace(
        &format!("template_version = \"{}\"", env!("CARGO_PKG_VERSION")),
        "template_version = \"0.0.1\"",
    );
    assert_ne!(older, manifest_text, "version line must have been replaced");
    std::fs::write(&manifest_path, &older).unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(&project)
        .assert()
        .code(1)
        .stdout(predicates::str::contains("0.0.1"))
        .stdout(predicates::str::contains(env!("CARGO_PKG_VERSION")));

    let newer = manifest_text.replace(
        &format!("template_version = \"{}\"", env!("CARGO_PKG_VERSION")),
        "template_version = \"999.0.0\"",
    );
    std::fs::write(&manifest_path, newer).unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(&project)
        .assert()
        .code(1)
        .stdout(predicates::str::contains("NEWER"));
}

#[test]
fn check_reports_missing_dirs_and_deleted_owned_files_as_creates()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);
    std::fs::remove_dir(project.join("literature")).unwrap();
    std::fs::remove_file(project.join("SKILLS.md")).unwrap();

    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(&project)
        .assert()
        .code(1)
        .stdout(predicates::str::contains(
            "Missing standard directories: literature",
        ))
        .stdout(predicates::str::contains("create"))
        .stdout(predicates::str::contains("SKILLS.md"));
}

#[test]
fn new_git_flag_warns_instead_of_failing_when_git_is_unavailable()
{
    let dir = tempfile::tempdir().unwrap();
    let empty_path_dir = dir.path().join("empty-path");
    std::fs::create_dir_all(&empty_path_dir).unwrap();
    // With PATH pointing at an empty directory, `git` cannot be spawned; the
    // stamp must still succeed and surface a warning (legacy behavior).
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "No Git Here", "--no-input", "--git"])
        .args(["--path", dir.path().to_str().unwrap()])
        .env("PATH", empty_path_dir.to_str().unwrap())
        .assert()
        .success()
        .stderr(predicates::str::contains("warning"));
    let project = dir.path().join("no-git-here");
    assert!(project.join("exporgo.toml").is_file(), "stamp completed");
    assert!(!project.join(".git").exists(), "git never ran");
}

#[test]
fn experiment_new_outside_a_project_is_refused()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["experiment", "new", "Pilot", "--no-input"])
        .current_dir(dir.path())
        .assert()
        .code(2)
        .stderr(predicates::str::contains("not an exporgo project"));
}

#[test]
fn experiment_new_stamps_inside_a_project()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input"])
        .args(["--data-root", r"\\ktdata\snlkt\data\pilot"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .success();
    let project = dir.path().join("pilot-study");

    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["experiment", "new", "Remap Test", "--no-input"])
        .args(["--path", project.to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicates::str::contains("Created"));
    assert!(
        project
            .join("experiments/remap-test/resources.md")
            .is_file()
    );
}

#[test]
fn malformed_sync_config_reports_the_parse_error()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .success();
    let project = dir.path().join("pilot-study");
    // A [sync] table missing required fields must surface the real manifest
    // parse error, not "no [sync] section".
    let manifest_path = project.join("exporgo.toml");
    let mut manifest_text = std::fs::read_to_string(&manifest_path).unwrap();
    manifest_text.push_str("\n[sync]\nsource = 'X:\\somewhere'\n");
    std::fs::write(&manifest_path, manifest_text).unwrap();

    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("sync")
        .current_dir(&project)
        .assert()
        .code(2)
        .stderr(predicates::str::contains("invalid manifest"));
}

#[test]
fn check_is_quietly_scriptable()
{
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .success();
    // Fresh project has unfilled tokens, so check reports (exit 1) without
    // erroring.
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(dir.path().join("pilot-study"))
        .assert()
        .code(1)
        .stdout(predicates::str::contains("Unfilled tokens"));
}
