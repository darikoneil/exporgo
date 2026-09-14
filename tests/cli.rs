//! End-to-end tests of the compiled `exporgo` binary.
#![cfg(feature = "cli")]

use assert_cmd::Command;

#[test]
fn version_prints_crate_version() {
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("--version")
        .assert()
        .success()
        .stdout(predicates::str::contains(env!("CARGO_PKG_VERSION")));
}

#[test]
fn new_no_input_stamps_a_project() {
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
fn update_outside_a_project_fails_with_message() {
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
fn check_is_quietly_scriptable() {
    let dir = tempfile::tempdir().unwrap();
    Command::cargo_bin("exporgo")
        .unwrap()
        .args(["new", "Pilot Study", "--no-input"])
        .args(["--path", dir.path().to_str().unwrap()])
        .assert()
        .success();
    // Fresh project has unfilled tokens, so check reports (exit 1) without erroring.
    Command::cargo_bin("exporgo")
        .unwrap()
        .arg("check")
        .current_dir(dir.path().join("pilot-study"))
        .assert()
        .code(1)
        .stdout(predicates::str::contains("Unfilled tokens"));
}
