//! Ownership zones: the single source of truth for what `exporgo update` may touch.
//!
//! Owned paths belong to the template and are freely overwritten on update. Everything
//! else is user territory and is never written after stamping — notably `context.md`,
//! `.claude/local.md`, `.claude/skills/local/`, `exporgo.toml`, real experiments, and
//! `plans/`. Update is additive: files are created or overwritten, never deleted.

/// Whether a project-relative path belongs to the template or to the user.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Zone {
    Owned(OwnedArea),
    User,
}

/// The owned areas, used to scope `--skills-only`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum OwnedArea {
    SkillsExporgo,
    RootDoc,
    Templates,
    ExperimentTemplate,
}

enum MatchKind {
    Exact,
    Prefix,
}

const OWNED_RULES: &[(&str, OwnedArea, MatchKind)] = &[
    (
        ".claude/skills/exporgo/",
        OwnedArea::SkillsExporgo,
        MatchKind::Prefix,
    ),
    ("CLAUDE.md", OwnedArea::RootDoc, MatchKind::Exact),
    ("README.md", OwnedArea::RootDoc, MatchKind::Exact),
    ("SKILLS.md", OwnedArea::RootDoc, MatchKind::Exact),
    ("templates/", OwnedArea::Templates, MatchKind::Prefix),
    (
        "experiments/_TEMPLATE/",
        OwnedArea::ExperimentTemplate,
        MatchKind::Prefix,
    ),
];

/// Classifies a `/`-separated project-relative path.
pub fn classify(rel_unix: &str) -> Zone {
    for (pattern, area, kind) in OWNED_RULES {
        let matches = match kind {
            MatchKind::Exact => rel_unix == *pattern,
            MatchKind::Prefix => rel_unix.starts_with(pattern),
        };
        if matches {
            return Zone::Owned(*area);
        }
    }
    Zone::User
}

#[cfg(test)]
mod tests {
    use rstest::rstest;

    use super::*;

    #[rstest]
    #[case(
        ".claude/skills/exporgo/code/CLAUDE.md",
        Zone::Owned(OwnedArea::SkillsExporgo)
    )]
    #[case(
        ".claude/skills/exporgo/third_party_skills.md",
        Zone::Owned(OwnedArea::SkillsExporgo)
    )]
    #[case("CLAUDE.md", Zone::Owned(OwnedArea::RootDoc))]
    #[case("README.md", Zone::Owned(OwnedArea::RootDoc))]
    #[case("SKILLS.md", Zone::Owned(OwnedArea::RootDoc))]
    #[case("templates/SKILL.template.md", Zone::Owned(OwnedArea::Templates))]
    #[case(
        "experiments/_TEMPLATE/protocol.md",
        Zone::Owned(OwnedArea::ExperimentTemplate)
    )]
    #[case("context.md", Zone::User)]
    #[case("exporgo.toml", Zone::User)]
    #[case(".claude/local.md", Zone::User)]
    #[case(".claude/skills/local/README.md", Zone::User)]
    #[case("experiments/README.md", Zone::User)]
    #[case("experiments/pilot-1/analysis.md", Zone::User)]
    #[case("plans/README.md", Zone::User)]
    #[case(".gitignore", Zone::User)]
    #[case("visuals/vibes/pseudopop.png", Zone::User)]
    fn classification(#[case] rel: &str, #[case] expected: Zone) {
        assert_eq!(classify(rel), expected);
    }
}
