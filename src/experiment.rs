//! `exporgo experiment new`: stamp a documented experiment inside a project.
//!
//! Copies the project's own `experiments/_TEMPLATE/` (an owned zone, kept
//! current by `exporgo update`) into `experiments/<slug>/` and fills its
//! `{{TOKENS}}`. The raw data root is derived from the project manifest's
//! `data_root` by convention — `<data_root>/<slug>` — so the pointer from the
//! workspace to the lab server is computed once instead of hand-typed. The
//! stamped folder is user territory: `exporgo update` never touches it.

use std::{collections::BTreeMap, path::PathBuf};

use crate::{
    error::Error,
    manifest::Manifest,
    stamp,
    tokens::{self, Token},
};

/// The placeholders `experiments/_TEMPLATE/` files may carry.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub enum ExperimentToken
{
    ExperimentName,
    RawDataRoot,
    ProcessedDataRoot,
}

impl ExperimentToken
{
    pub const ALL: [ExperimentToken; 3] = [
        ExperimentToken::ExperimentName,
        ExperimentToken::RawDataRoot,
        ExperimentToken::ProcessedDataRoot,
    ];

    /// The literal placeholder as it appears in the template files.
    pub fn placeholder(self) -> &'static str
    {
        match self
        {
            ExperimentToken::ExperimentName => "{{EXPERIMENT_NAME}}",
            ExperimentToken::RawDataRoot => "{{RAW_DATA_ROOT}}",
            ExperimentToken::ProcessedDataRoot => "{{PROCESSED_DATA_ROOT}}",
        }
    }
}

/// Inputs for [`stamp_experiment`], fully resolved — prompting is the CLI's
/// job.
pub struct NewExperimentOptions
{
    /// The project root (must contain `exporgo.toml`).
    pub project_root: PathBuf,
    /// Human experiment name; the folder name is its slug.
    pub name: String,
    /// Raw data root. `None` derives `<manifest data_root>/<slug>`; if the
    /// manifest has no `data_root` either, the placeholder stays visible.
    pub raw_data_root: Option<String>,
    /// Processed data root; never derived (labs differ), stays visible if
    /// absent.
    pub processed_data_root: Option<String>,
}

/// What [`stamp_experiment`] did.
pub struct ExperimentReport
{
    /// The created `experiments/<slug>` directory.
    pub dir: PathBuf,
    pub files_written: usize,
    /// Placeholders still visible across the stamped files.
    pub unfilled: Vec<String>,
}

/// Stamps `experiments/_TEMPLATE/` into `experiments/<slug>/`, filling tokens.
///
/// Refuses outside a project, when the template folder is missing, and when
/// the experiment folder already exists (experiments are never re-stamped).
pub fn stamp_experiment(options: &NewExperimentOptions) -> Result<ExperimentReport, Error>
{
    let manifest = Manifest::load(&options.project_root)?;

    let slug =
        tokens::slugify(&options.name).ok_or_else(|| Error::BadSlug(options.name.clone()))?;
    if stamp::is_windows_reserved(&slug)
    {
        return Err(Error::BadSlug(options.name.clone()));
    }

    let template_dir = options.project_root.join("experiments").join("_TEMPLATE");
    if !template_dir.is_dir()
    {
        return Err(Error::MissingExperimentTemplate(template_dir));
    }
    let destination = options.project_root.join("experiments").join(&slug);
    if destination.exists()
    {
        return Err(Error::ExperimentExists(destination));
    }

    let raw_root = options.raw_data_root.clone().or_else(|| {
        manifest
            .tokens
            .get(Token::DataRoot.manifest_key())
            .map(|root| join_data_path(root, &slug))
    });

    let mut values = BTreeMap::new();
    values.insert(
        ExperimentToken::ExperimentName.placeholder().to_string(),
        options.name.clone(),
    );
    if let Some(raw) = raw_root
    {
        values.insert(ExperimentToken::RawDataRoot.placeholder().to_string(), raw);
    }
    if let Some(processed) = &options.processed_data_root
    {
        values.insert(
            ExperimentToken::ProcessedDataRoot.placeholder().to_string(),
            processed.clone(),
        );
    }

    std::fs::create_dir_all(&destination).map_err(Error::io(destination.clone()))?;
    let mut files_written = 0;
    let mut unfilled = std::collections::BTreeSet::new();
    for entry in std::fs::read_dir(&template_dir).map_err(Error::io(template_dir.clone()))?
    {
        let entry = entry.map_err(Error::io(template_dir.clone()))?;
        if !entry
            .file_type()
            .map_err(Error::io(entry.path()))?
            .is_file()
        {
            continue;
        }
        let target = destination.join(entry.file_name());
        let contents = std::fs::read(entry.path()).map_err(Error::io(entry.path()))?;
        match std::str::from_utf8(&contents)
        {
            Ok(text) =>
            {
                let filled = tokens::substitute_placeholders(text, &values);
                unfilled.extend(tokens::scan(&filled));
                std::fs::write(&target, filled).map_err(Error::io(target.clone()))?;
            }
            Err(_) =>
            {
                std::fs::write(&target, &contents).map_err(Error::io(target.clone()))?;
            }
        }
        files_written += 1;
    }

    Ok(ExperimentReport {
        dir: destination,
        files_written,
        unfilled: unfilled.into_iter().collect(),
    })
}

/// Appends `slug` to a data root using the root's own separator style, so a
/// UNC root stays backslashed and a POSIX root stays forward-slashed.
fn join_data_path(root: &str, slug: &str) -> String
{
    let trimmed = root.trim_end_matches(['/', '\\']);
    let separator = if trimmed.contains('\\') { '\\' } else { '/' };
    format!("{trimmed}{separator}{slug}")
}

#[cfg(test)]
mod tests
{
    use pretty_assertions::assert_eq;
    use rstest::rstest;

    use super::*;
    use crate::template;

    /// The template files and this module cannot drift apart: every
    /// `{{TOKEN}}` in the embedded `_TEMPLATE` files must be a declared
    /// [`ExperimentToken`], and every declared token must appear somewhere.
    #[test]
    fn experiment_tokens_match_embedded_template()
    {
        let mut scanned = std::collections::BTreeSet::new();
        for (rel, contents) in template::files()
        {
            if rel.starts_with("experiments/_TEMPLATE/")
            {
                let text = std::str::from_utf8(contents).expect("_TEMPLATE files are UTF-8");
                scanned.extend(tokens::scan(text));
            }
        }
        let declared: std::collections::BTreeSet<String> = ExperimentToken::ALL
            .iter()
            .map(|t| t.placeholder().to_string())
            .collect();
        assert_eq!(
            scanned, declared,
            "_TEMPLATE placeholders and ExperimentToken have drifted apart"
        );
    }

    #[rstest]
    #[case(
        r"\\ktdata\snlkt\data\proj",
        "pilot",
        r"\\ktdata\snlkt\data\proj\pilot"
    )]
    #[case(
        r"\\ktdata\snlkt\data\proj\",
        "pilot",
        r"\\ktdata\snlkt\data\proj\pilot"
    )]
    #[case("/mnt/data/proj", "pilot", "/mnt/data/proj/pilot")]
    #[case("/mnt/data/proj/", "pilot", "/mnt/data/proj/pilot")]
    fn join_data_path_keeps_the_root_separator(
        #[case] root: &str,
        #[case] slug: &str,
        #[case] expected: &str,
    )
    {
        assert_eq!(join_data_path(root, slug), expected);
    }
}
