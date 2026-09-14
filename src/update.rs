//! `exporgo update`: refresh a project's owned files from the embedded template.

use std::path::Path;

use crate::error::Error;
use crate::manifest::{Manifest, Version};
use crate::plan::{PlannedChange, plan};
use crate::template;

pub struct UpdateOptions {
    /// Plan only; write nothing.
    pub dry_run: bool,
    /// Restrict to `.claude/skills/exporgo/` and leave the manifest version alone.
    pub skills_only: bool,
}

/// Applies (or, with `dry_run`, only reports) the owned-zone diff.
///
/// Refuses when the project's `template_version` is newer than this binary —
/// owned files are never downgraded. The manifest version is bumped only after
/// every file write succeeds, so an interrupted update re-plans correctly on the
/// next run.
pub fn update(project_root: &Path, options: &UpdateOptions) -> Result<Vec<PlannedChange>, Error> {
    let mut manifest = Manifest::load(project_root)?;
    let binary = Version::current();
    if manifest.template_version > binary {
        return Err(Error::BinaryTooOld {
            project: manifest.template_version,
            binary,
        });
    }

    let changes = plan(project_root, options.skills_only)?;
    if options.dry_run {
        return Ok(changes);
    }

    for change in &changes {
        debug_assert!(
            matches!(
                crate::zones::classify(&change.rel),
                crate::zones::Zone::Owned(_)
            ),
            "update must never write a user-zone path: {}",
            change.rel
        );
        let destination = template::dest_path(project_root, &change.rel);
        if let Some(parent) = destination.parent() {
            std::fs::create_dir_all(parent).map_err(Error::io(parent.to_path_buf()))?;
        }
        let contents =
            template::file_contents(&change.rel).expect("planned changes come from the embed");
        std::fs::write(&destination, contents).map_err(Error::io(destination.clone()))?;
    }

    if !options.skills_only && manifest.template_version != binary {
        manifest.template_version = binary;
        manifest.save(project_root)?;
    }

    Ok(changes)
}
