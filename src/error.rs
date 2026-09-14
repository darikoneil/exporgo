//! The single error type for the exporgo library.

use std::path::PathBuf;

use crate::manifest::Version;

/// Everything that can go wrong while stamping, checking, or updating a
/// project.
#[derive(Debug, thiserror::Error)]
pub enum Error
{
    #[error("{path}: {source}")]
    Io
    {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },

    #[error("target '{0}' already exists and is not empty (use --force to stamp anyway)")]
    TargetNotEmpty(PathBuf),

    #[error("target '{0}' is already an exporgo project; did you mean `exporgo update`?")]
    AlreadyAProject(PathBuf),

    #[error("'{0}' is not an exporgo project: no exporgo.toml found")]
    NotAProject(PathBuf),

    #[error(
        "project template_version {project} is newer than this exporgo binary ({binary}); \
         download a newer exporgo release"
    )]
    BinaryTooOld
    {
        project: Version, binary: Version
    },

    #[error("invalid manifest {path}: {message}")]
    Manifest
    {
        path: PathBuf, message: String
    },

    #[error("could not derive a usable folder name from '{0}'")]
    BadSlug(String),

    #[error("experiment '{0}' already exists")]
    ExperimentExists(PathBuf),

    #[error(
        "experiment template not found at '{0}'; run `exporgo update` to restore \
         experiments/_TEMPLATE/"
    )]
    MissingExperimentTemplate(PathBuf),

    #[error("sync source not found: '{0}' (drive not mounted? share offline?)")]
    SyncSourceMissing(PathBuf),

    #[error(
        "sync paths overlap: '{a}' and '{b}' are the same directory or nested in each other; \
         source, intermediate, and destination must be disjoint"
    )]
    SyncPathsOverlap
    {
        a: PathBuf, b: PathBuf
    },

    #[error(
        "sync paths incomplete (missing {0}); pass --source/--intermediate/--destination or add a \
         [sync] section to exporgo.toml"
    )]
    SyncUnconfigured(String),
}

impl Error
{
    /// Wraps an I/O error with the path it occurred on.
    pub fn io(path: impl Into<PathBuf>) -> impl FnOnce(std::io::Error) -> Error
    {
        let path = path.into();
        move |source| Error::Io { path, source }
    }
}

#[cfg(test)]
mod tests
{
    use std::path::PathBuf;

    use rstest::rstest;

    use super::*;

    /// Every user-facing message names what went wrong AND what to do about
    /// it (or at least the offending path/value). These are contracts: error
    /// text is part of the CLI's interface, asserted by the assert_cmd tests.
    #[rstest]
    #[case(Error::TargetNotEmpty(PathBuf::from("proj")), &["proj", "--force"])]
    #[case(Error::AlreadyAProject(PathBuf::from("proj")), &["proj", "exporgo update"])]
    #[case(Error::NotAProject(PathBuf::from("here")), &["here", "no exporgo.toml"])]
    #[case(
        Error::BinaryTooOld { project: Version(9, 9, 9), binary: Version(1, 0, 0) },
        &["9.9.9", "1.0.0", "newer"]
    )]
    #[case(
        Error::Manifest { path: PathBuf::from("exporgo.toml"), message: "bad toml".to_string() },
        &["exporgo.toml", "bad toml"]
    )]
    #[case(Error::BadSlug("!!!".to_string()), &["!!!", "folder name"])]
    #[case(Error::ExperimentExists(PathBuf::from("pilot")), &["pilot", "already exists"])]
    #[case(
        Error::MissingExperimentTemplate(PathBuf::from("_TEMPLATE")),
        &["_TEMPLATE", "exporgo update"]
    )]
    #[case(Error::SyncSourceMissing(PathBuf::from("G:/x")), &["G:/x", "mounted"])]
    #[case(
        Error::SyncPathsOverlap { a: PathBuf::from("a"), b: PathBuf::from("a/b") },
        &["overlap", "disjoint"]
    )]
    #[case(
        Error::SyncUnconfigured("source, destination".to_string()),
        &["source, destination", "[sync]"]
    )]
    fn messages_name_the_problem_and_the_remedy(
        #[case] error: Error,
        #[case] expected_fragments: &[&str],
    )
    {
        let message = error.to_string();
        for fragment in expected_fragments
        {
            assert!(
                message.contains(fragment),
                "message '{message}' should contain '{fragment}'"
            );
        }
    }

    #[test]
    fn io_helper_carries_path_and_source()
    {
        let source = std::io::Error::new(std::io::ErrorKind::PermissionDenied, "locked");
        let error = Error::io(PathBuf::from("some/file.md"))(source);
        let message = error.to_string();
        assert!(message.contains("file.md"), "path missing from '{message}'");
        assert!(
            message.contains("locked"),
            "source missing from '{message}'"
        );
        // The source is also exposed through the error chain for callers that
        // want the raw io::ErrorKind.
        let chained = std::error::Error::source(&error).expect("has a source");
        assert!(chained.to_string().contains("locked"));
    }
}
