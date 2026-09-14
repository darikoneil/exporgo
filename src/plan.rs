//! The shared diff planner behind `exporgo check` and `exporgo update`.
//!
//! A plan lists the owned-zone files whose embedded contents differ from the
//! project's. There is deliberately no `Delete` variant: update only adds and
//! overwrites, so stray files in a project (including gitignored private ones)
//! always survive.

use std::path::Path;

use crate::{
    error::Error,
    template,
    zones::{OwnedArea, Zone, classify},
};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ChangeKind
{
    /// The file does not exist in the project yet.
    Create,
    /// The project's copy differs from the embedded template's.
    Overwrite,
}

#[derive(Clone, Debug)]
pub struct PlannedChange
{
    /// Project-relative, `/`-separated path.
    pub rel: String,
    pub kind: ChangeKind,
}

/// Diffs the embedded owned-zone files against the project.
///
/// `skills_only` restricts the plan to `.claude/skills/exporgo/`.
pub fn plan(project_root: &Path, skills_only: bool) -> Result<Vec<PlannedChange>, Error>
{
    let mut changes = Vec::new();
    for (rel, embedded) in template::files()
    {
        let in_scope = match classify(rel)
        {
            Zone::Owned(OwnedArea::SkillsExporgo) => true,
            Zone::Owned(_) => !skills_only,
            Zone::User => false,
        };
        if !in_scope
        {
            continue;
        }
        let destination = template::dest_path(project_root, rel);
        let kind = match std::fs::read(&destination)
        {
            Ok(existing) if normalized_eq(embedded, &existing) => continue,
            Ok(_) => ChangeKind::Overwrite,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => ChangeKind::Create,
            Err(e) => return Err(Error::io(destination)(e)),
        };
        changes.push(PlannedChange {
            rel: rel.to_string(),
            kind,
        });
    }
    Ok(changes)
}

/// Content equality that ignores CRLF/LF differences on text, so a binary built
/// from a LF checkout never flags a Windows-stamped project as changed.
/// Non-UTF-8 content (images) is compared byte-for-byte.
pub fn normalized_eq(a: &[u8], b: &[u8]) -> bool
{
    match (std::str::from_utf8(a), std::str::from_utf8(b))
    {
        (Ok(a), Ok(b)) =>
        {
            let a = a.replace("\r\n", "\n");
            let b = b.replace("\r\n", "\n");
            a == b
        }
        _ => a == b,
    }
}

#[cfg(test)]
mod tests
{
    use rstest::rstest;

    use super::*;

    #[rstest]
    #[case(b"a\nb\n", b"a\r\nb\r\n", true)]
    #[case(b"a\nb\n", b"a\nb\n", true)]
    #[case(b"a\nb\n", b"a\nc\n", false)]
    #[case(&[0xFF, 0x0A], &[0xFF, 0x0A], true)]
    #[case(&[0xFF, 0x0D, 0x0A], &[0xFF, 0x0A], false)]
    fn normalized_equality(#[case] a: &[u8], #[case] b: &[u8], #[case] expected: bool)
    {
        assert_eq!(normalized_eq(a, b), expected);
    }
}
