//! Per-machine configuration and state directories.
//!
//! Machine-scoped facts must never live inside a project: the project
//! directory is what `exporgo sync` replicates between machines, so anything
//! machine-specific stored there would be clobbered by whichever machine
//! synced last. This module owns the split:
//!
//! - **Config** (`config.toml`): the machine's path to the shared sync remote,
//!   plus default owner/email for `exporgo new`.
//! - **Cache** (`cache/<slug>/`): the durable staging copy each sync runs
//!   through (cloud-drive mounts are flaky; the cache is real local disk).
//! - **Logs** (`logs/<slug>/`): sync audit logs, kept out of the synced tree.
//!
//! Locations: `%APPDATA%\exporgo` + `%LOCALAPPDATA%\exporgo` on Windows,
//! `$XDG_CONFIG_HOME/exporgo` + `$XDG_CACHE_HOME/exporgo` (with `~/.config` /
//! `~/.cache` fallbacks) elsewhere. Setting `EXPORGO_HOME` overrides all three
//! at once (used by tests, useful for portable installs).

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::Error;

/// The config file name inside the config directory.
pub const CONFIG_FILE: &str = "config.toml";

/// Environment variable that overrides every machine directory at once.
pub const HOME_ENV: &str = "EXPORGO_HOME";

/// The contents of the per-machine `config.toml`. Every field is optional so
/// the file can be grown one `exporgo config --<flag>` at a time.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct MachineConfig
{
    /// Default project owner for `exporgo new`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner: Option<String>,
    /// Default owner email for `exporgo new`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub email: Option<String>,
    /// This machine's path to the shared sync location (a Drive mount, a UNC
    /// share — anything that all machines can reach under their own path).
    /// Each project syncs to `<remote_root>/<project slug>`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub remote_root: Option<String>,
}

impl MachineConfig
{
    /// Loads the config from `path`; a missing file is an empty config, a
    /// malformed one is a [`Error::Config`].
    pub fn load(path: &Path) -> Result<MachineConfig, Error>
    {
        let text = match std::fs::read_to_string(path)
        {
            Ok(text) => text,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound =>
            {
                return Ok(MachineConfig::default());
            }
            Err(e) => return Err(Error::io(path.to_path_buf())(e)),
        };
        toml::from_str(&text).map_err(|e| Error::Config {
            path: path.to_path_buf(),
            message: e.to_string(),
        })
    }

    /// Writes the config to `path`, creating parent directories as needed.
    pub fn save(&self, path: &Path) -> Result<(), Error>
    {
        if let Some(parent) = path.parent()
        {
            std::fs::create_dir_all(parent).map_err(Error::io(parent.to_path_buf()))?;
        }
        let text = toml::to_string_pretty(self).map_err(|e| Error::Config {
            path: path.to_path_buf(),
            message: e.to_string(),
        })?;
        std::fs::write(path, text).map_err(Error::io(path.to_path_buf()))
    }
}

/// The machine's resolved exporgo directories.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MachineDirs
{
    /// The per-machine `config.toml`.
    pub config_file: PathBuf,
    /// Parent of every project's sync cache (`<cache_root>/<slug>`).
    pub cache_root: PathBuf,
    /// Parent of every project's sync logs (`<log_root>/<slug>`).
    pub log_root: PathBuf,
}

/// The environment values [`resolve_dirs`] consults, as plain data so the
/// resolution logic is a pure function (mutating the process environment in
/// tests is unsafe under edition 2024).
#[derive(Clone, Debug, Default)]
pub struct EnvPaths
{
    pub exporgo_home: Option<PathBuf>,
    pub appdata: Option<PathBuf>,
    pub local_appdata: Option<PathBuf>,
    pub xdg_config_home: Option<PathBuf>,
    pub xdg_cache_home: Option<PathBuf>,
    pub home: Option<PathBuf>,
}

impl EnvPaths
{
    /// Reads the real process environment.
    pub fn from_process() -> EnvPaths
    {
        let var = |name: &str| std::env::var_os(name).map(PathBuf::from);
        EnvPaths {
            exporgo_home: var(HOME_ENV),
            appdata: var("APPDATA"),
            local_appdata: var("LOCALAPPDATA"),
            xdg_config_home: var("XDG_CONFIG_HOME"),
            xdg_cache_home: var("XDG_CACHE_HOME"),
            home: var("HOME").or_else(|| var("USERPROFILE")),
        }
    }
}

/// Resolves the machine directories from environment values. `EXPORGO_HOME`
/// wins outright; otherwise the platform conventions apply in order
/// (`APPDATA`/`LOCALAPPDATA`, then XDG variables, then `~/.config`/`~/.cache`).
/// `None` when no anchor is set at all.
pub fn resolve_dirs(env: &EnvPaths) -> Option<MachineDirs>
{
    if let Some(home) = &env.exporgo_home
    {
        return Some(MachineDirs {
            config_file: home.join(CONFIG_FILE),
            cache_root: home.join("cache"),
            log_root: home.join("logs"),
        });
    }
    let config_dir = env
        .appdata
        .as_ref()
        .or(env.xdg_config_home.as_ref())
        .map(|base| base.join("exporgo"))
        .or_else(|| env.home.as_ref().map(|h| h.join(".config").join("exporgo")))?;
    let state_dir = env
        .local_appdata
        .as_ref()
        .or(env.xdg_cache_home.as_ref())
        .map(|base| base.join("exporgo"))
        .or_else(|| env.home.as_ref().map(|h| h.join(".cache").join("exporgo")))?;
    Some(MachineDirs {
        config_file: config_dir.join(CONFIG_FILE),
        cache_root: state_dir.join("cache"),
        log_root: state_dir.join("logs"),
    })
}

/// [`resolve_dirs`] over the real environment, or [`Error::NoConfigDir`].
pub fn machine_dirs() -> Result<MachineDirs, Error>
{
    resolve_dirs(&EnvPaths::from_process()).ok_or(Error::NoConfigDir)
}

#[cfg(test)]
mod tests
{
    use pretty_assertions::assert_eq;

    use super::*;

    fn windows_env() -> EnvPaths
    {
        EnvPaths {
            appdata: Some(PathBuf::from(r"C:\Users\d\AppData\Roaming")),
            local_appdata: Some(PathBuf::from(r"C:\Users\d\AppData\Local")),
            home: Some(PathBuf::from(r"C:\Users\d")),
            ..EnvPaths::default()
        }
    }

    #[test]
    fn windows_env_uses_appdata_and_localappdata()
    {
        let dirs = resolve_dirs(&windows_env()).expect("resolvable");
        assert_eq!(
            dirs.config_file,
            PathBuf::from(r"C:\Users\d\AppData\Roaming").join("exporgo/config.toml")
        );
        assert_eq!(
            dirs.cache_root,
            PathBuf::from(r"C:\Users\d\AppData\Local").join("exporgo/cache")
        );
        assert_eq!(
            dirs.log_root,
            PathBuf::from(r"C:\Users\d\AppData\Local").join("exporgo/logs")
        );
    }

    #[test]
    fn exporgo_home_overrides_everything()
    {
        let mut env = windows_env();
        env.exporgo_home = Some(PathBuf::from("/portable/exporgo"));
        let dirs = resolve_dirs(&env).expect("resolvable");
        assert_eq!(
            dirs.config_file,
            PathBuf::from("/portable/exporgo/config.toml")
        );
        assert_eq!(dirs.cache_root, PathBuf::from("/portable/exporgo/cache"));
        assert_eq!(dirs.log_root, PathBuf::from("/portable/exporgo/logs"));
    }

    #[test]
    fn xdg_variables_win_over_home_fallbacks()
    {
        let env = EnvPaths {
            xdg_config_home: Some(PathBuf::from("/x/config")),
            xdg_cache_home: Some(PathBuf::from("/x/cache")),
            home: Some(PathBuf::from("/home/d")),
            ..EnvPaths::default()
        };
        let dirs = resolve_dirs(&env).expect("resolvable");
        assert_eq!(
            dirs.config_file,
            PathBuf::from("/x/config/exporgo/config.toml")
        );
        assert_eq!(dirs.cache_root, PathBuf::from("/x/cache/exporgo/cache"));
    }

    #[test]
    fn bare_home_falls_back_to_dot_config_and_dot_cache()
    {
        let env = EnvPaths {
            home: Some(PathBuf::from("/home/d")),
            ..EnvPaths::default()
        };
        let dirs = resolve_dirs(&env).expect("resolvable");
        assert_eq!(
            dirs.config_file,
            PathBuf::from("/home/d/.config/exporgo/config.toml")
        );
        assert_eq!(
            dirs.cache_root,
            PathBuf::from("/home/d/.cache/exporgo/cache")
        );
        assert_eq!(dirs.log_root, PathBuf::from("/home/d/.cache/exporgo/logs"));
    }

    #[test]
    fn no_anchors_resolves_to_none()
    {
        assert_eq!(resolve_dirs(&EnvPaths::default()), None);
    }

    #[test]
    fn config_roundtrips_and_omits_unset_fields()
    {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("deep/config.toml");
        let config = MachineConfig {
            owner: Some("Darik".to_string()),
            email: None,
            remote_root: Some(r"G:\My Drive\exporgo-projects".to_string()),
        };
        config.save(&path).expect("save creates parents");
        let text = std::fs::read_to_string(&path).expect("read");
        assert!(!text.contains("email"), "unset fields stay out of the file");
        assert_eq!(MachineConfig::load(&path).expect("load"), config);
    }

    #[test]
    fn missing_config_file_is_an_empty_config()
    {
        let dir = tempfile::tempdir().expect("tempdir");
        let loaded = MachineConfig::load(&dir.path().join("config.toml")).expect("load");
        assert_eq!(loaded, MachineConfig::default());
    }

    #[test]
    fn malformed_config_is_a_config_error()
    {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("config.toml");
        std::fs::write(&path, "remote_root = [broken").expect("write");
        assert!(matches!(
            MachineConfig::load(&path),
            Err(Error::Config { .. })
        ));
    }
}
