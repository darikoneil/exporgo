//! `exporgo new`: stamp a fresh project from the embedded template.

use std::path::{Path, PathBuf};

use crate::{
    error::Error,
    manifest::{Manifest, Version},
    template,
    tokens::{self, Token, TokenValues},
};

/// Inputs for [`stamp`], fully resolved — prompting for missing values is the
/// caller's job (the CLI's, or a future GUI's).
pub struct NewOptions
{
    /// Human project name; the folder name is its slug.
    pub name: String,
    /// Directory the project folder is created in.
    pub parent: PathBuf,
    /// Resolved token values. `PROJECT_NAME` defaults to `name` and
    /// `CREATED_DATE` to today when absent.
    pub values: TokenValues,
    /// Overwrite colliding files in a non-empty target (never wipes the
    /// target).
    pub force: bool,
}

/// What [`stamp`] did.
pub struct StampReport
{
    /// The created project root.
    pub root: PathBuf,
    pub files_written: usize,
    pub dirs_created: usize,
    /// Placeholders still visible in the stamped `context.md`.
    pub unfilled: Vec<String>,
}

/// Stamps the embedded template into `parent/<slug>`.
///
/// Guards: refuses a non-empty target without `force`, and refuses a target
/// that already contains an `exporgo.toml` even with `force` (that calls for
/// `exporgo update`, not a re-stamp).
pub fn stamp(options: &NewOptions) -> Result<StampReport, Error>
{
    let slug =
        tokens::slugify(&options.name).ok_or_else(|| Error::BadSlug(options.name.clone()))?;
    if is_windows_reserved(&slug)
    {
        // CON, NUL, COM1… cannot be created as directories on Windows; fail
        // with a clear message instead of a raw I/O error.
        return Err(Error::BadSlug(options.name.clone()));
    }
    let root = options.parent.join(&slug);

    if Manifest::exists(&root)
    {
        return Err(Error::AlreadyAProject(root));
    }
    if root.exists() && !options.force && !is_empty_dir(&root)?
    {
        return Err(Error::TargetNotEmpty(root));
    }

    let mut values = options.values.clone();
    values
        .entry(Token::ProjectName)
        .or_insert_with(|| options.name.clone());
    values
        .entry(Token::CreatedDate)
        .or_insert_with(|| jiff::Zoned::now().date().to_string());

    let mut files_written = 0;
    let mut unfilled = Vec::new();
    for (rel, contents) in template::files()
    {
        let destination = template::dest_path(&root, rel);
        if let Some(parent) = destination.parent()
        {
            std::fs::create_dir_all(parent).map_err(Error::io(parent.to_path_buf()))?;
        }
        if rel == template::CONTEXT_FILE
        {
            let text = std::str::from_utf8(contents).expect("embedded context.md is UTF-8");
            let filled = tokens::substitute(text, &values);
            unfilled = tokens::unfilled(&filled);
            std::fs::write(&destination, filled).map_err(Error::io(destination.clone()))?;
        }
        else
        {
            std::fs::write(&destination, contents).map_err(Error::io(destination.clone()))?;
        }
        files_written += 1;
    }

    let mut dirs_created = 0;
    for dir in template::STANDARD_DIRS
    {
        let path = template::dest_path(&root, dir);
        if !path.is_dir()
        {
            std::fs::create_dir_all(&path).map_err(Error::io(path.clone()))?;
            dirs_created += 1;
        }
    }

    let manifest = Manifest {
        project: options.name.clone(),
        created: values.get(&Token::CreatedDate).cloned().unwrap_or_default(),
        template_version: Version::current(),
        tokens: values
            .iter()
            .filter(|(_, value)| !value.is_empty())
            .map(|(token, value)| (token.manifest_key().to_string(), value.clone()))
            .collect(),
    };
    manifest.save(&root)?;

    Ok(StampReport {
        root,
        files_written,
        dirs_created,
        unfilled,
    })
}

/// Windows reserved device names, which cannot be used as file or folder names.
/// `slug` is already lowercase.
pub(crate) fn is_windows_reserved(slug: &str) -> bool
{
    matches!(slug, "con" | "prn" | "aux" | "nul")
        || ((slug.starts_with("com") || slug.starts_with("lpt"))
            && slug.len() == 4
            && slug.as_bytes()[3].is_ascii_digit())
}

fn is_empty_dir(path: &Path) -> Result<bool, Error>
{
    if !path.is_dir()
    {
        // A colliding *file* counts as a non-empty target.
        return Ok(false);
    }
    let mut entries = std::fs::read_dir(path).map_err(Error::io(path.to_path_buf()))?;
    Ok(entries.next().is_none())
}
