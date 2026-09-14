//! exporgo — stamp and maintain science-project workspaces from an embedded template.
//!
//! The library is UI-free: all interactivity lives in the `exporgo` binary, so a GUI
//! can drive the same operations. The template ships inside the binary (see
//! [`template`]); the crate version is the template version.

pub mod check;
#[cfg(feature = "cli")]
pub mod cli;
pub mod error;
pub mod manifest;
pub mod plan;
pub mod stamp;
pub mod sync;
pub mod template;
pub mod tokens;
pub mod update;
pub mod zones;

pub use error::Error;
pub use template::VERSION;
