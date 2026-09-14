//! `{{TOKEN}}` placeholders in the template's `context.md`, and name
//! slugification.
//!
//! The token set is a hardcoded enum because each token needs a static CLI
//! flag, prompt text, and manifest key. A unit test asserts the enum matches
//! the placeholders actually present in the embedded `context.md`, so the
//! template and this module cannot drift apart silently.

use std::collections::{BTreeMap, BTreeSet};

/// A placeholder the template expects to be filled at stamp time.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum Token
{
    ProjectName,
    OneLineAim,
    Status,
    RepoUrl,
    DataRoot,
    Owner,
    OwnerEmail,
    CreatedDate,
}

/// Resolved token values; tokens absent from the map are left unfilled.
pub type TokenValues = BTreeMap<Token, String>;

impl Token
{
    pub const ALL: [Token; 8] = [
        Token::ProjectName,
        Token::OneLineAim,
        Token::Status,
        Token::RepoUrl,
        Token::DataRoot,
        Token::Owner,
        Token::OwnerEmail,
        Token::CreatedDate,
    ];

    /// The literal placeholder as it appears in `context.md`, e.g.
    /// `{{PROJECT_NAME}}`.
    pub fn placeholder(self) -> &'static str
    {
        match self
        {
            Token::ProjectName => "{{PROJECT_NAME}}",
            Token::OneLineAim => "{{ONE_LINE_AIM}}",
            Token::Status => "{{STATUS}}",
            Token::RepoUrl => "{{REPO_URL}}",
            Token::DataRoot => "{{DATA_ROOT}}",
            Token::Owner => "{{OWNER}}",
            Token::OwnerEmail => "{{OWNER_EMAIL}}",
            Token::CreatedDate => "{{CREATED_DATE}}",
        }
    }

    /// The key under which a filled value is recorded in `exporgo.toml`.
    pub fn manifest_key(self) -> &'static str
    {
        match self
        {
            Token::ProjectName => "project_name",
            Token::OneLineAim => "one_line_aim",
            Token::Status => "status",
            Token::RepoUrl => "repo_url",
            Token::DataRoot => "data_root",
            Token::Owner => "owner",
            Token::OwnerEmail => "owner_email",
            Token::CreatedDate => "created_date",
        }
    }
}

/// All `{{UPPER_SNAKE}}` placeholders present in `text`, whether or not they
/// are known [`Token`]s (users may add their own to a project's `context.md`).
pub fn scan(text: &str) -> BTreeSet<String>
{
    let mut found = BTreeSet::new();
    // `i` strictly increases in both branches, so the loop terminates.
    let mut i = 0;
    while let Some(start) = text[i..].find("{{").map(|p| p + i)
    {
        let body_start = start + 2;
        let Some(end) = text[body_start..].find("}}").map(|p| p + body_start)
        else
        {
            break;
        };
        let body = &text[body_start..end];
        let valid = !body.is_empty()
            && body
                .bytes()
                .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_');
        if valid
        {
            found.insert(text[start..end + 2].to_string());
            i = end + 2;
        }
        else
        {
            i = body_start;
        }
    }
    found
}

/// Replaces known tokens with their non-empty values; empty values and unknown
/// placeholders are left literal so they stay visible for later filling.
///
/// A single left-to-right pass: substituted values are emitted verbatim and
/// never rescanned, so a value that itself contains a placeholder (e.g. an aim
/// quoting `{{OWNER}}`) is not substituted recursively.
pub fn substitute(text: &str, values: &TokenValues) -> String
{
    let by_placeholder: BTreeMap<String, String> = values
        .iter()
        .map(|(token, value)| (token.placeholder().to_string(), value.clone()))
        .collect();
    substitute_placeholders(text, &by_placeholder)
}

/// [`substitute`] for an arbitrary placeholder set: keys are full literal
/// placeholders (`{{EXPERIMENT_NAME}}`), empty values and unknown placeholders
/// stay literal, and substituted values are never rescanned.
pub fn substitute_placeholders(text: &str, values: &BTreeMap<String, String>) -> String
{
    let mut result = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(start) = rest.find("{{")
    {
        let after_open = start + 2;
        let Some(close) = rest[after_open..].find("}}").map(|p| p + after_open + 2)
        else
        {
            break;
        };
        let placeholder = &rest[start..close];
        let replacement = values.get(placeholder).filter(|value| !value.is_empty());
        if let Some(value) = replacement
        {
            result.push_str(&rest[..start]);
            result.push_str(value);
            rest = &rest[close..];
        }
        else
        {
            result.push_str(&rest[..after_open]);
            rest = &rest[after_open..];
        }
    }
    result.push_str(rest);
    result
}

/// The placeholders still literal in `text`, in sorted order.
pub fn unfilled(text: &str) -> Vec<String>
{
    scan(text).into_iter().collect()
}

/// Derives a folder name: lowercase, runs of non-alphanumerics collapse to `-`,
/// leading/trailing `-` trimmed. Returns `None` when nothing survives.
pub fn slugify(name: &str) -> Option<String>
{
    let mut slug = String::with_capacity(name.len());
    let mut pending_dash = false;
    for c in name.chars()
    {
        if c.is_ascii_alphanumeric()
        {
            if pending_dash && !slug.is_empty()
            {
                slug.push('-');
            }
            pending_dash = false;
            slug.push(c.to_ascii_lowercase());
        }
        else
        {
            pending_dash = true;
        }
    }
    (!slug.is_empty()).then_some(slug)
}

#[cfg(test)]
mod tests
{
    use pretty_assertions::assert_eq;
    use rstest::rstest;

    use super::*;
    use crate::template;

    #[test]
    fn token_enum_matches_embedded_context_md()
    {
        let context = std::str::from_utf8(
            template::file_contents(template::CONTEXT_FILE).expect("context.md is embedded"),
        )
        .expect("context.md is UTF-8");
        let scanned = scan(context);
        let declared: BTreeSet<String> = Token::ALL
            .iter()
            .map(|t| t.placeholder().to_string())
            .collect();
        assert_eq!(
            scanned, declared,
            "context.md placeholders and the Token enum have drifted apart"
        );
    }

    #[rstest]
    #[case("no tokens here", &[])]
    #[case("{{A}} and {{B_2}}", &["{{A}}", "{{B_2}}"])]
    #[case("{{lower}} {{Mixed_CASE}} {{}}", &[])]
    #[case("{{UNCLOSED and {{OK}}", &["{{OK}}"])]
    #[case("{{{TRIPLE}}}", &[])]
    fn scan_finds_only_upper_snake_placeholders(#[case] text: &str, #[case] expected: &[&str])
    {
        let found: Vec<String> = scan(text).into_iter().collect();
        assert_eq!(found, expected);
    }

    #[test]
    fn substitute_fills_known_and_leaves_empty_and_unknown()
    {
        let mut values = TokenValues::new();
        values.insert(Token::ProjectName, "Grid Cells".to_string());
        values.insert(Token::Status, String::new());
        let text = "# {{PROJECT_NAME}} ({{STATUS}}) {{CUSTOM_THING}}";
        assert_eq!(
            substitute(text, &values),
            "# Grid Cells ({{STATUS}}) {{CUSTOM_THING}}"
        );
    }

    #[test]
    fn substitute_never_rescans_substituted_values()
    {
        let mut values = TokenValues::new();
        values.insert(Token::OneLineAim, "about {{OWNER}}'s data".to_string());
        values.insert(Token::Owner, "Darik".to_string());
        assert_eq!(
            substitute("{{ONE_LINE_AIM}} by {{OWNER}}", &values),
            "about {{OWNER}}'s data by Darik"
        );
    }

    #[test]
    fn unfilled_reports_remaining_placeholders()
    {
        assert_eq!(
            unfilled("{{B}} then {{A}}"),
            vec!["{{A}}".to_string(), "{{B}}".to_string()]
        );
    }

    #[rstest]
    #[case("Grid Cell Remapping", Some("grid-cell-remapping"))]
    #[case("  spaces  ", Some("spaces"))]
    #[case("Already-Slugged", Some("already-slugged"))]
    #[case("A/B: pilot #2", Some("a-b-pilot-2"))]
    #[case("üñïçödé", Some("d"))]
    #[case("---", None)]
    #[case("", None)]
    fn slugify_cases(#[case] name: &str, #[case] expected: Option<&str>)
    {
        assert_eq!(slugify(name).as_deref(), expected);
    }
}
