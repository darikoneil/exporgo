//! `exporgo check`: report a project's drift from the binary's template.

use std::path::Path;

use crate::{
    error::Error,
    manifest::{Manifest, Version},
    plan::{PlannedChange, plan},
    template, tokens,
};

/// Everything `check` found. Empty `changes`/`unfilled_tokens`/`missing_dirs`
/// with matching versions means the project is clean.
pub struct CheckReport
{
    pub project_version: Version,
    pub binary_version: Version,
    /// Owned files `exporgo update` would create or overwrite.
    pub changes: Vec<PlannedChange>,
    /// Placeholders still visible in the project's `context.md`.
    pub unfilled_tokens: Vec<String>,
    /// Standard directories absent from the project.
    pub missing_dirs: Vec<String>,
}

impl CheckReport
{
    /// Whether there is nothing to report.
    pub fn is_clean(&self) -> bool
    {
        self.project_version == self.binary_version
            && self.changes.is_empty()
            && self.unfilled_tokens.is_empty()
            && self.missing_dirs.is_empty()
    }
}

/// Checks the project at `project_root`; errors if it is not an exporgo
/// project.
pub fn check(project_root: &Path) -> Result<CheckReport, Error>
{
    let manifest = Manifest::load(project_root)?;

    let context_path = template::dest_path(project_root, template::CONTEXT_FILE);
    let unfilled_tokens = match std::fs::read_to_string(&context_path)
    {
        Ok(text) => tokens::unfilled(&text),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Vec::new(),
        Err(e) => return Err(Error::io(context_path)(e)),
    };

    let missing_dirs = template::STANDARD_DIRS
        .iter()
        .filter(|dir| !template::dest_path(project_root, dir).is_dir())
        .map(|dir| dir.to_string())
        .collect();

    Ok(CheckReport {
        project_version: manifest.template_version,
        binary_version: Version::current(),
        changes: plan(project_root, false)?,
        unfilled_tokens,
        missing_dirs,
    })
}
