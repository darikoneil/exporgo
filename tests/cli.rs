//! End-to-end tests of the compiled `exporgo` binary.
//!
//! Every invocation that touches machine state (config, cache, logs) sets
//! `EXPORGO_HOME` to a temp directory, so the tests never read or write the
//! developer's real `%APPDATA%`/`%LOCALAPPDATA%`.
#![cfg(feature = "cli")]

use std::path::Path;

use assert_cmd::Command;

/// A `exporgo` command sandboxed to `home` for all machine state.
fn exporgo(home: &Path) -> Command
{
    let mut command = Command::cargo_bin("exporgo").unwrap();
    command.env("EXPORGO_HOME", home);
    command
}

fn stamped_project(dir: &Path, extra_args: &[&str]) -> std::path::PathBuf
{
    exporgo(dir)
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
    exporgo(dir.path())
        .args(["new", "Pilot Study", "--no-input", "--status", "planning"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicates::str::contains("Created"));
    assert!(dir.path().join("pilot-study/exporgo.toml").is_file());
}

#[test]
fn removed_project_level_flags_no_longer_parse()
{
    let dir = tempfile::tempdir().unwrap();
    for args in [
        ["--aim", "x"].as_slice(),
        ["--repo", "x"].as_slice(),
        ["--data-root", "x"].as_slice(),
        ["--git"].as_slice(),
    ]
    {
        exporgo(dir.path())
            .args(["new", "Pilot", "--no-input"])
            .args(args)
            .args(["--path", dir.path().to_str().unwrap()])
            .assert()
            .failure()
            .stderr(predicates::str::contains("unexpected argument"));
    }
    assert!(!dir.path().join("pilot").exists(), "nothing stamped");
}

#[test]
fn new_fills_owner_and_email_from_the_machine_config()
{
    let dir = tempfile::tempdir().unwrap();
    exporgo(dir.path())
        .args(["config", "--owner", "Darik", "--email", "doneil@salk.edu"])
        .assert()
        .success();

    let project = stamped_project(dir.path(), &[]);
    let context = std::fs::read_to_string(project.join("context.md")).unwrap();
    assert!(context.contains("Darik"), "owner from config: {context}");
    assert!(context.contains("doneil@salk.edu"), "email from config");
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
    exporgo(dir.path())
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
    exporgo(dir.path())
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
    exporgo(dir.path())
        .args(["new", "Pilot", "--no-input", "--status", "procrastinating"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .failure()
        .stderr(predicates::str::contains("invalid value"));
    assert!(!dir.path().join("pilot").exists(), "nothing stamped");
}

#[test]
fn check_exits_zero_on_a_fully_filled_project_and_two_outside_one()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(
        dir.path(),
        &[
            "--status",
            "active",
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
fn config_shows_guidance_then_records_the_remote_root()
{
    let dir = tempfile::tempdir().unwrap();
    exporgo(dir.path())
        .arg("config")
        .assert()
        .success()
        .stdout(predicates::str::contains("remote_root = (unset)"))
        .stdout(predicates::str::contains("--remote-root"));

    let remote_root = dir.path().join("shared");
    exporgo(dir.path())
        .args(["config", "--remote-root", remote_root.to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicates::str::contains("shared"));
    assert!(dir.path().join("config.toml").is_file());
}

#[test]
fn sync_without_a_remote_root_points_at_exporgo_config()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);
    exporgo(dir.path())
        .arg("sync")
        .current_dir(&project)
        .assert()
        .code(2)
        .stderr(predicates::str::contains("exporgo config --remote-root"));
}

#[test]
fn sync_outside_a_project_is_refused()
{
    let dir = tempfile::tempdir().unwrap();
    exporgo(dir.path())
        .arg("sync")
        .current_dir(dir.path())
        .assert()
        .code(2)
        .stderr(predicates::str::contains("not an exporgo project"));
}

#[test]
fn malformed_machine_config_reports_the_parse_error()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);
    std::fs::write(dir.path().join("config.toml"), "remote_root = [broken").unwrap();
    exporgo(dir.path())
        .arg("sync")
        .current_dir(&project)
        .assert()
        .code(2)
        .stderr(predicates::str::contains("invalid machine config"));
}

/// The full multi-machine story on one filesystem: stamp, push to the remote,
/// clone as a "second machine" (its own EXPORGO_HOME), and edit both ways.
#[test]
fn sync_and_clone_round_trip_between_two_machine_homes()
{
    let dir = tempfile::tempdir().unwrap();
    let remote_root = dir.path().join("shared");
    std::fs::create_dir_all(&remote_root).unwrap();
    let machine_a = dir.path().join("machine-a");
    let machine_b = dir.path().join("machine-b");

    for machine in [&machine_a, &machine_b]
    {
        exporgo(machine)
            .args(["config", "--remote-root", remote_root.to_str().unwrap()])
            .assert()
            .success();
    }

    // Machine A: stamp and push.
    let project_a = stamped_project(&machine_a, &[]);
    exporgo(&machine_a)
        .arg("sync")
        .current_dir(&project_a)
        .assert()
        .success()
        .stdout(predicates::str::contains("=> OK"));
    assert!(remote_root.join("pilot-study/exporgo.toml").is_file());

    // Machine B: clone, then receive an edit from A.
    let clones = machine_b.join("projects");
    std::fs::create_dir_all(&clones).unwrap();
    exporgo(&machine_b)
        .args(["clone", "Pilot Study", "--path", clones.to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicates::str::contains("Cloned into"));
    let project_b = clones.join("pilot-study");
    assert!(project_b.join("exporgo.toml").is_file());

    std::fs::write(project_a.join("plans/idea.md"), "try remapping").unwrap();
    exporgo(&machine_a)
        .arg("sync")
        .current_dir(&project_a)
        .assert()
        .success();
    exporgo(&machine_b)
        .arg("sync")
        .current_dir(&project_b)
        .assert()
        .success();
    assert_eq!(
        std::fs::read_to_string(project_b.join("plans/idea.md")).unwrap(),
        "try remapping"
    );
}

#[test]
fn clone_into_an_occupied_target_is_refused()
{
    let dir = tempfile::tempdir().unwrap();
    let remote_root = dir.path().join("shared");
    std::fs::create_dir_all(&remote_root).unwrap();
    exporgo(dir.path())
        .args(["config", "--remote-root", remote_root.to_str().unwrap()])
        .assert()
        .success();

    let project = stamped_project(dir.path(), &[]);
    exporgo(dir.path())
        .arg("sync")
        .current_dir(&project)
        .assert()
        .success();

    // The stamped project itself already occupies <path>/pilot-study.
    exporgo(dir.path())
        .args([
            "clone",
            "Pilot Study",
            "--path",
            dir.path().to_str().unwrap(),
        ])
        .assert()
        .code(2)
        .stderr(predicates::str::contains("not empty"));
}

#[test]
fn sync_mirror_requires_an_explicit_direction()
{
    let dir = tempfile::tempdir().unwrap();
    let remote_root = dir.path().join("shared");
    std::fs::create_dir_all(&remote_root).unwrap();
    exporgo(dir.path())
        .args(["config", "--remote-root", remote_root.to_str().unwrap()])
        .assert()
        .success();
    let project = stamped_project(dir.path(), &[]);

    exporgo(dir.path())
        .args(["sync", "--mirror"])
        .current_dir(&project)
        .assert()
        .code(2)
        .stderr(predicates::str::contains("explicit direction"));

    exporgo(dir.path())
        .args(["sync", "push", "--mirror"])
        .current_dir(&project)
        .assert()
        .success()
        .stderr(predicates::str::contains("DELETES"));
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
    let project = stamped_project(dir.path(), &[]);

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
fn check_is_quietly_scriptable()
{
    let dir = tempfile::tempdir().unwrap();
    let project = stamped_project(dir.path(), &[]);
    // Fresh project has unfilled tokens, so check reports (exit 1) without
    // erroring.
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(&project)
        .assert()
        .code(1)
        .stdout(predicates::str::contains("Unfilled tokens"));
}
