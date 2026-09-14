//! The project manifest, `exporgo.toml`.
//!
//! Its presence is what marks a directory as an exporgo project. It records the
//! project name, the stamp date, the template version the project is on, and the
//! token values that were filled at stamp time. The file belongs to exporgo:
//! `update` rewrites it (bumping `template_version`), and hand-written comments
//! are not preserved.

use std::fmt;
use std::path::Path;
use std::str::FromStr;

use serde::{Deserialize, Serialize};

use crate::error::Error;

/// The manifest file name at the project root.
pub const FILE_NAME: &str = "exporgo.toml";

/// A `major.minor.patch` version. Hand-rolled: exporgo never emits pre-release
/// tags, so the full semver grammar is unnecessary.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct Version(pub u64, pub u64, pub u64);

impl Version {
    /// The version this binary carries (== the embedded template's version).
    pub fn current() -> Version {
        crate::template::VERSION
            .parse()
            .expect("CARGO_PKG_VERSION is a valid x.y.z version")
    }
}

impl fmt::Display for Version {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}.{}", self.0, self.1, self.2)
    }
}

impl FromStr for Version {
    type Err = String;

    fn from_str(s: &str) -> Result<Version, String> {
        let mut parts = s.split('.');
        let mut component = |name: &str| -> Result<u64, String> {
            parts
                .next()
                .ok_or_else(|| format!("missing {name} component in version '{s}'"))?
                .parse()
                .map_err(|_| format!("invalid {name} component in version '{s}'"))
        };
        let version = Version(
            component("major")?,
            component("minor")?,
            component("patch")?,
        );
        if parts.next().is_some() {
            return Err(format!("too many components in version '{s}'"));
        }
        Ok(version)
    }
}

impl TryFrom<String> for Version {
    type Error = String;

    fn try_from(s: String) -> Result<Version, String> {
        s.parse()
    }
}

impl From<Version> for String {
    fn from(v: Version) -> String {
        v.to_string()
    }
}

/// The contents of `exporgo.toml`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Manifest {
    /// The project name as given to `exporgo new` (not the slug).
    pub project: String,
    /// Stamp date, `YYYY-MM-DD`, local time.
    pub created: String,
    /// The template version the project's owned files are on.
    pub template_version: Version,
    /// Token values filled at stamp time, keyed by [`crate::tokens::Token::manifest_key`].
    #[serde(default)]
    pub tokens: std::collections::BTreeMap<String, String>,
    /// Optional standing configuration for `exporgo sync`, so a project can be
    /// synced with no arguments. Added by hand; preserved across updates.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sync: Option<SyncConfig>,
}

/// The `[sync]` table of `exporgo.toml`: the three paths (and extra excludes)
/// `exporgo sync` uses when flags don't override them.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SyncConfig {
    pub source: String,
    pub intermediate: String,
    pub destination: String,
    #[serde(default)]
    pub exclude: Vec<String>,
}

impl Manifest {
    /// Loads the manifest from `project_root`, or [`Error::NotAProject`] when absent.
    pub fn load(project_root: &Path) -> Result<Manifest, Error> {
        let path = project_root.join(FILE_NAME);
        let text = match std::fs::read_to_string(&path) {
            Ok(text) => text,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return Err(Error::NotAProject(project_root.to_path_buf()));
            }
            Err(e) => return Err(Error::io(path)(e)),
        };
        toml::from_str(&text).map_err(|e| Error::Manifest {
            path,
            message: e.to_string(),
        })
    }

    /// Writes the manifest to `project_root`, replacing any existing file.
    pub fn save(&self, project_root: &Path) -> Result<(), Error> {
        let path = project_root.join(FILE_NAME);
        let text = toml::to_string_pretty(self).map_err(|e| Error::Manifest {
            path: path.clone(),
            message: e.to_string(),
        })?;
        std::fs::write(&path, text).map_err(Error::io(path))
    }

    /// Whether `path` contains a manifest file (cheap existence check).
    pub fn exists(project_root: &Path) -> bool {
        project_root.join(FILE_NAME).is_file()
    }
}

#[cfg(test)]
mod tests {
    use pretty_assertions::assert_eq;
    use rstest::rstest;

    use super::*;

    #[rstest]
    #[case("2.3.0", Ok(Version(2, 3, 0)))]
    #[case("0.0.0", Ok(Version(0, 0, 0)))]
    #[case("2.3", Err(()))]
    #[case("2.3.0.1", Err(()))]
    #[case("2.x.0", Err(()))]
    #[case("", Err(()))]
    fn version_parsing(#[case] text: &str, #[case] expected: Result<Version, ()>) {
        assert_eq!(text.parse::<Version>().map_err(|_| ()), expected);
    }

    #[test]
    fn version_ordering_is_numeric_not_lexical() {
        assert!(Version(2, 3, 0) < Version(2, 10, 0));
        assert!(Version(2, 3, 0) < Version(10, 0, 0));
        assert!(Version(2, 3, 1) > Version(2, 3, 0));
    }

    #[test]
    fn current_version_parses() {
        assert_eq!(Version::current().to_string(), crate::template::VERSION);
    }

    #[test]
    fn manifest_roundtrips_through_toml() {
        let manifest = Manifest {
            project: "Grid Cell Remapping".to_string(),
            created: "2026-09-13".to_string(),
            template_version: Version(2, 3, 0),
            tokens: [("status".to_string(), "active".to_string())].into(),
            sync: Some(SyncConfig {
                source: r"G:\My Drive\projects\grid".to_string(),
                intermediate: r"C:\Users\dao25\SyncMirror\grid".to_string(),
                destination: r"\\ktdata\snlkt\backup\grid".to_string(),
                exclude: vec!["*.tmp".to_string()],
            }),
        };
        let dir = tempfile::tempdir().expect("tempdir");
        manifest.save(dir.path()).expect("save");
        let loaded = Manifest::load(dir.path()).expect("load");
        assert_eq!(loaded, manifest);
    }

    #[test]
    fn manifest_without_sync_section_loads_and_omits_it_on_save() {
        let manifest = Manifest {
            project: "Pilot".to_string(),
            created: "2026-09-13".to_string(),
            template_version: Version(2, 3, 0),
            tokens: Default::default(),
            sync: None,
        };
        let dir = tempfile::tempdir().expect("tempdir");
        manifest.save(dir.path()).expect("save");
        let text = std::fs::read_to_string(dir.path().join(FILE_NAME)).expect("read");
        assert!(!text.contains("[sync]"));
        assert_eq!(Manifest::load(dir.path()).expect("load").sync, None);
    }

    #[test]
    fn missing_manifest_is_not_a_project() {
        let dir = tempfile::tempdir().expect("tempdir");
        assert!(matches!(
            Manifest::load(dir.path()),
            Err(Error::NotAProject(_))
        ));
        assert!(!Manifest::exists(dir.path()));
    }

    #[test]
    fn garbage_manifest_is_a_manifest_error_not_not_a_project() {
        let dir = tempfile::tempdir().expect("tempdir");
        std::fs::write(dir.path().join(FILE_NAME), "not = [valid").expect("write");
        assert!(matches!(
            Manifest::load(dir.path()),
            Err(Error::Manifest { .. })
        ));
    }
}
