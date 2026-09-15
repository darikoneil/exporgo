//! `exporgo experiment new`: stamp a documented experiment inside a project.
//!
//! Copies the project's own `experiments/_TEMPLATE/` (an owned zone, kept
//! current by `exporgo update`) into `experiments/<slug>/` and fills its
//! `{{TOKENS}}`. Data roots are per-experiment hints, given (or skipped) at
//! stamp time — there is no project-level data root to derive from, because
//! each experiment's data can live somewhere different. The stamped folder is
//! user territory: `exporgo update` never touches it.

use std::{collections::BTreeMap, path::PathBuf};

use crate::{error::Error, manifest::Manifest, stamp, tokens};

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
    /// Raw data root, a hint for where this experiment's data may live; the
    /// placeholder stays visible when absent.
    pub raw_data_root: Option<String>,
    /// Processed data root; the placeholder stays visible when absent.
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
    // Loaded only as the "is this an exporgo project?" gate.
    Manifest::load(&options.project_root)?;

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

    let mut values = BTreeMap::new();
    values.insert(
        ExperimentToken::ExperimentName.placeholder().to_string(),
        options.name.clone(),
    );
    if let Some(raw) = &options.raw_data_root
    {
        values.insert(
            ExperimentToken::RawDataRoot.placeholder().to_string(),
            raw.clone(),
        );
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

#[cfg(test)]
mod tests
{
    use pretty_assertions::assert_eq;

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
}
