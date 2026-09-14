//! Copies `template/this_project` into `$OUT_DIR/template`, skipping files that
//! must never ship inside the binary (private profiles, maintainer docs,
//! superseded files, OS cruft). `src/template.rs` then embeds the filtered copy
//! with `include_dir!`.
//!
//! This denylist is one of two layers: a unit test in `src/template.rs`
//! additionally asserts that every embedded file is git-tracked, so an
//! untracked private file in a maintainer's checkout fails `cargo test` instead
//! of shipping silently.

use std::{fs, io, path::Path};

const TEMPLATE_SOURCE: &str = "template/this_project";

/// File names excluded wherever they appear (compared case-insensitively —
/// Windows and macOS filesystems treat `HANDOFF.MD` as the same file).
const EXCLUDED_NAMES: &[&str] = &[
    "handoff.md",
    "darik-voice.md",
    "sync_skill.md",
    "context.template.md",
    "thumbs.db",
    ".ds_store",
];

/// Directory names excluded (with their entire contents) wherever they appear.
const EXCLUDED_DIR_NAMES: &[&str] = &["claude outputs", ".git"];

/// Template-relative directory paths excluded with their entire contents.
/// `agents/references/` is private territory (voice profiles, writing samples).
const EXCLUDED_DIR_PATHS: &[&str] = &[".claude/skills/exporgo/code/agents/references"];

/// File-name suffixes excluded wherever they appear.
const EXCLUDED_SUFFIXES: &[&str] = &[".log", ".identifier"];

fn excluded_file(name: &str) -> bool
{
    let name = name.to_ascii_lowercase();
    EXCLUDED_NAMES.contains(&name.as_str()) || EXCLUDED_SUFFIXES.iter().any(|s| name.ends_with(s))
}

fn excluded_dir(name: &str, rel: &str) -> bool
{
    EXCLUDED_DIR_NAMES.contains(&name.to_ascii_lowercase().as_str())
        || EXCLUDED_DIR_PATHS
            .iter()
            .any(|p| rel.eq_ignore_ascii_case(p))
}

/// `rel` is the `/`-separated path of `source` relative to the template root
/// (empty at the top level).
fn copy_filtered(source: &Path, destination: &Path, rel: &str) -> io::Result<()>
{
    fs::create_dir_all(destination)?;
    for entry in fs::read_dir(source)?
    {
        let entry = entry?;
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        let entry_rel = if rel.is_empty()
        {
            name_str.to_string()
        }
        else
        {
            format!("{rel}/{name_str}")
        };
        // Never follow symlinks: one pointing into private territory would be
        // dereferenced and copied into the embed.
        let file_type = entry.file_type()?;
        if file_type.is_symlink()
        {
            println!("cargo:warning=template embed: skipping symlink {entry_rel}");
            continue;
        }
        let target = destination.join(&name);
        if file_type.is_dir()
        {
            if excluded_dir(&name_str, &entry_rel)
            {
                println!("cargo:warning=template embed: excluding directory {entry_rel}");
            }
            else
            {
                copy_filtered(&entry.path(), &target, &entry_rel)?;
            }
        }
        else if excluded_file(&name_str)
        {
            println!("cargo:warning=template embed: excluding file {entry_rel}");
        }
        else
        {
            fs::copy(entry.path(), &target)?;
        }
    }
    Ok(())
}

fn main()
{
    println!("cargo:rerun-if-changed={TEMPLATE_SOURCE}");
    let out_dir = std::env::var("OUT_DIR").expect("OUT_DIR is set by cargo");
    let destination = Path::new(&out_dir).join("template");
    // Start clean so files deleted from the source template also disappear from
    // the embed.
    if destination.exists()
    {
        fs::remove_dir_all(&destination).expect("clean stale template copy");
    }
    copy_filtered(Path::new(TEMPLATE_SOURCE), &destination, "")
        .expect("copy template into OUT_DIR");
}
