//! End-to-end tests for `exporgo experiment new`: stamping
//! `experiments/_TEMPLATE/` into a documented experiment folder with derived
//! data-root pointers.

use std::path::{Path, PathBuf};

use exporgo::{
    error::Error,
    experiment::{NewExperimentOptions, stamp_experiment},
    stamp::{NewOptions, stamp},
    tokens::{Token, TokenValues},
};
use pretty_assertions::assert_eq;

fn project_with_data_root(parent: &Path) -> PathBuf
{
    let mut values = TokenValues::new();
    values.insert(
        Token::DataRoot,
        r"\\ktdata\snlkt\data\gridremap".to_string(),
    );
    stamp(&NewOptions {
        name: "Grid Remap".to_string(),
        parent: parent.to_path_buf(),
        values,
        force: false,
        git_init: false,
    })
    .expect("project stamps")
    .root
}

fn experiment_options(root: &Path, name: &str) -> NewExperimentOptions
{
    NewExperimentOptions {
        project_root: root.to_path_buf(),
        name: name.to_string(),
        raw_data_root: None,
        processed_data_root: None,
    }
}

#[test]
fn stamps_all_template_files_with_name_and_derived_raw_root()
{
    let dir = tempfile::tempdir().unwrap();
    let root = project_with_data_root(dir.path());

    let report = stamp_experiment(&experiment_options(&root, "Remapping Pilot 1")).expect("stamps");

    assert_eq!(
        report.dir,
        root.join("experiments").join("remapping-pilot-1")
    );
    assert_eq!(report.files_written, 4);
    for file in [
        "experiment.md",
        "protocol.md",
        "analysis.md",
        "resources.md",
    ]
    {
        assert!(report.dir.join(file).is_file(), "missing {file}");
    }

    let experiment = std::fs::read_to_string(report.dir.join("experiment.md")).unwrap();
    assert!(experiment.contains("# Experiment: Remapping Pilot 1"));

    let resources = std::fs::read_to_string(report.dir.join("resources.md")).unwrap();
    assert!(
        resources.contains(r"\\ktdata\snlkt\data\gridremap\remapping-pilot-1"),
        "raw root must be derived as <data_root>\\<slug>: {resources}"
    );
    // Processed root is never derived; it stays visible and is reported.
    assert!(resources.contains("{{PROCESSED_DATA_ROOT}}"));
    assert!(
        report
            .unfilled
            .contains(&"{{PROCESSED_DATA_ROOT}}".to_string())
    );
    assert!(!report.unfilled.contains(&"{{RAW_DATA_ROOT}}".to_string()));
}

#[test]
fn explicit_roots_override_derivation()
{
    let dir = tempfile::tempdir().unwrap();
    let root = project_with_data_root(dir.path());

    let mut options = experiment_options(&root, "Pilot");
    options.raw_data_root = Some(r"\\elsewhere\raw".to_string());
    options.processed_data_root = Some(r"\\elsewhere\processed".to_string());
    let report = stamp_experiment(&options).unwrap();

    let resources = std::fs::read_to_string(report.dir.join("resources.md")).unwrap();
    assert!(resources.contains(r"\\elsewhere\raw"));
    assert!(resources.contains(r"\\elsewhere\processed"));
    assert!(
        report.unfilled.is_empty(),
        "everything filled: {:?}",
        report.unfilled
    );
}

#[test]
fn without_project_data_root_the_placeholder_stays_visible()
{
    let dir = tempfile::tempdir().unwrap();
    let root = stamp(&NewOptions {
        name: "No Root".to_string(),
        parent: dir.path().to_path_buf(),
        values: TokenValues::new(),
        force: false,
        git_init: false,
    })
    .unwrap()
    .root;

    let report = stamp_experiment(&experiment_options(&root, "Pilot")).unwrap();
    assert!(report.unfilled.contains(&"{{RAW_DATA_ROOT}}".to_string()));
}

#[test]
fn guards_duplicates_bad_names_and_non_projects()
{
    let dir = tempfile::tempdir().unwrap();
    let root = project_with_data_root(dir.path());

    stamp_experiment(&experiment_options(&root, "Pilot")).unwrap();
    assert!(matches!(
        stamp_experiment(&experiment_options(&root, "Pilot")),
        Err(Error::ExperimentExists(_))
    ));
    assert!(matches!(
        stamp_experiment(&experiment_options(&root, "!!!")),
        Err(Error::BadSlug(_))
    ));
    assert!(matches!(
        stamp_experiment(&experiment_options(dir.path(), "Pilot")),
        Err(Error::NotAProject(_))
    ));
}

#[test]
fn missing_template_folder_is_a_clear_error()
{
    let dir = tempfile::tempdir().unwrap();
    let root = project_with_data_root(dir.path());
    std::fs::remove_dir_all(root.join("experiments").join("_TEMPLATE")).unwrap();
    assert!(matches!(
        stamp_experiment(&experiment_options(&root, "Pilot")),
        Err(Error::MissingExperimentTemplate(_))
    ));
}

#[test]
fn stamped_experiments_survive_update()
{
    let dir = tempfile::tempdir().unwrap();
    let root = project_with_data_root(dir.path());
    let report = stamp_experiment(&experiment_options(&root, "Pilot")).unwrap();

    let notes = report.dir.join("experiment.md");
    std::fs::write(&notes, "my running notes").unwrap();
    exporgo::update::update(
        &root,
        &exporgo::update::UpdateOptions {
            dry_run: false,
            skills_only: false,
        },
    )
    .unwrap();
    assert_eq!(
        std::fs::read_to_string(&notes).unwrap(),
        "my running notes",
        "experiments/<slug>/ is user territory"
    );
}
