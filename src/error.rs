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

    #[error("sync source not found: '{0}' (drive not mounted? share offline?)")]
    SyncSourceMissing(PathBuf),

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
