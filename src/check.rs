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
#[derive(Debug)]
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
///
/// A `project_version` newer than the binary is *reported*, not an error —
/// unlike `update`, which refuses to downgrade owned files.
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

#[cfg(test)]
mod tests
{
    use rstest::rstest;

    use super::*;
    use crate::plan::ChangeKind;

    fn clean_report() -> CheckReport
    {
        CheckReport {
            project_version: Version(2, 4, 0),
            binary_version: Version(2, 4, 0),
            changes: Vec::new(),
            unfilled_tokens: Vec::new(),
            missing_dirs: Vec::new(),
        }
    }

    #[test]
    fn a_report_with_nothing_to_say_is_clean()
    {
        assert!(clean_report().is_clean());
    }

    /// Each dimension independently flips cleanliness: version drift (either
    /// direction), pending changes, unfilled tokens, missing directories.
    #[rstest]
    #[case::older_project(|r: &mut CheckReport| r.project_version = Version(2, 3, 0))]
    #[case::newer_project(|r: &mut CheckReport| r.project_version = Version(9, 0, 0))]
    #[case::pending_change(|r: &mut CheckReport| {
        r.changes.push(PlannedChange { rel: "SKILLS.md".to_string(), kind: ChangeKind::Overwrite })
    })]
    #[case::unfilled_token(|r: &mut CheckReport| {
        r.unfilled_tokens.push("{{REPO_URL}}".to_string())
    })]
    #[case::missing_dir(|r: &mut CheckReport| r.missing_dirs.push("literature".to_string()))]
    fn any_single_finding_makes_the_report_unclean(#[case] perturb: fn(&mut CheckReport))
    {
        let mut report = clean_report();
        perturb(&mut report);
        assert!(!report.is_clean());
    }
}
