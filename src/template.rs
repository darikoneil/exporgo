//! The embedded project template and its standard directory set.
//!
//! `build.rs` copies `template/this_project` into `$OUT_DIR/template`,
//! excluding files that must never ship (private profiles, maintainer docs,
//! superseded files, OS cruft); this module embeds that filtered copy into the
//! binary. The crate version is therefore also the template version.

use std::path::{Path, PathBuf};

use include_dir::{Dir, include_dir};

/// The filtered template tree, embedded at compile time.
pub static TEMPLATE: Dir<'static> = include_dir!("$OUT_DIR/template");

/// The binary's version, which is also the template version it carries.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Relative path of the file that receives `{{TOKEN}}` substitution at stamp
/// time.
pub const CONTEXT_FILE: &str = "context.md";

/// Directories every project must have but which are empty in the template
/// (empty directories cannot be embedded, so `stamp` creates them explicitly).
pub const STANDARD_DIRS: &[&str] = &[
    "artifacts",
    "documents",
    "experiments",
    "literature",
    "manuscript",
    "plans",
    "presentations",
    "visuals/figures",
    "visuals/illustrations",
    "visuals/panels",
    "visuals/schematics",
    "visuals/vibes",
    ".claude/skills/exporgo/science",
    ".claude/skills/local",
];

/// All embedded files as `(relative unix-style path, contents)`, in depth-first
/// order.
pub fn files() -> Vec<(&'static str, &'static [u8])>
{
    let mut collected = Vec::new();
    collect(&TEMPLATE, &mut collected);
    collected
}

fn collect(dir: &Dir<'static>, into: &mut Vec<(&'static str, &'static [u8])>)
{
    for file in dir.files()
    {
        let rel = file
            .path()
            .to_str()
            .expect("embedded paths are valid UTF-8");
        into.push((rel, file.contents()));
    }
    for sub in dir.dirs()
    {
        collect(sub, into);
    }
}

/// Returns the embedded contents of the file at `rel_unix`, if present.
pub fn file_contents(rel_unix: &str) -> Option<&'static [u8]>
{
    TEMPLATE.get_file(rel_unix).map(|f| f.contents())
}

/// Joins an embedded `/`-separated relative path onto `root` using native
/// separators.
///
/// This is the only function between the embed and filesystem writes, so it
/// refuses anything but plain relative components: `..`, `.`, empty components,
/// backslashes, and drive prefixes all panic rather than escape `root`.
pub fn dest_path(root: &Path, rel_unix: &str) -> PathBuf
{
    let mut path = root.to_path_buf();
    for component in rel_unix.split('/')
    {
        assert!(
            !component.is_empty()
                && component != "."
                && component != ".."
                && !component.contains(['\\', ':']),
            "embedded path component is not a plain name: {rel_unix}"
        );
        path.push(component);
    }
    path
}

#[cfg(test)]
mod tests
{
    use super::*;

    /// Names that must never appear in the embedded tree: private profiles,
    /// maintainer docs, superseded files, staging dumps, logs.
    #[test]
    fn embedded_tree_contains_no_private_or_superseded_files()
    {
        const FORBIDDEN: &[&str] = &[
            "darik-voice",
            "Claude outputs",
            "HANDOFF",
            "sync_skill",
            "context.template",
            ".log",
        ];
        for (rel, _) in files()
        {
            for forbidden in FORBIDDEN
            {
                assert!(
                    !rel.contains(forbidden),
                    "embedded file '{rel}' matches forbidden pattern '{forbidden}'"
                );
            }
        }
    }

    #[test]
    fn embedded_tree_contains_expected_files()
    {
        for expected in [
            "context.md",
            "CLAUDE.md",
            "README.md",
            "SKILLS.md",
            ".gitignore",
            ".claude/local.md",
            ".claude/skills/exporgo/sync/SKILL.md",
            ".claude/skills/exporgo/code/CLAUDE.md",
            ".claude/skills/local/README.md",
            "experiments/_TEMPLATE/experiment.md",
            "templates/SKILL.template.md",
        ]
        {
            assert!(
                file_contents(expected).is_some(),
                "expected embedded file '{expected}' is missing"
            );
        }
    }

    /// The strong privacy gate: every embedded file must be git-tracked. The
    /// denylist in build.rs cannot know about a *new* private file dropped into
    /// a maintainer's checkout (untracked or gitignored); this test fails for
    /// any such file before a binary built from that checkout gets shared.
    #[test]
    fn every_embedded_file_is_git_tracked()
    {
        let output = std::process::Command::new("git")
            .args(["ls-files", "-z", "--cached", "template/this_project"])
            .current_dir(env!("CARGO_MANIFEST_DIR"))
            .output()
            .expect("git is available in the development environment");
        assert!(output.status.success(), "git ls-files failed");
        let tracked: std::collections::BTreeSet<&str> = std::str::from_utf8(&output.stdout)
            .expect("git ls-files output is UTF-8")
            .split('\0')
            .filter_map(|p| p.strip_prefix("template/this_project/"))
            .collect();
        for (rel, _) in files()
        {
            assert!(
                tracked.contains(rel),
                "embedded file '{rel}' is not git-tracked — a private or stray file is about to \
                 ship in the binary"
            );
        }
    }

    #[test]
    fn dest_path_joins_with_native_separators()
    {
        let joined = dest_path(Path::new("root"), "a/b/c.md");
        let expected: PathBuf = ["root", "a", "b", "c.md"].iter().collect();
        assert_eq!(joined, expected);
    }

    #[test]
    #[should_panic(expected = "not a plain name")]
    fn dest_path_rejects_traversal()
    {
        dest_path(Path::new("root"), "../escape.md");
    }
}
