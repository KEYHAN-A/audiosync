//! Project I/O — save / load session state as JSON.
//!
//! Format: JSON object with tracks, config, result, and metadata.
//! Compatible with the Python version's project file format.

use anyhow::{Context, Result};
use log::info;
use serde::{Deserialize, Serialize};
use std::path::Path;

use crate::models::{SyncConfig, SyncResult, Track};

const PROJECT_VERSION: u32 = 2;

/// Top-level project structure for serialization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectFile {
    /// Schema version for future-proofing.
    pub version: u32,

    /// Application version that created this file.
    pub app_version: String,

    /// ISO-8601 timestamp of last save.
    pub saved_at: String,

    /// All tracks with their clips and analysis results.
    pub tracks: Vec<Track>,

    /// Engine configuration used for the last analysis/sync.
    pub config: SyncConfig,

    /// Analysis result (None if not yet analyzed).
    pub result: Option<SyncResult>,
}

impl ProjectFile {
    /// Create a new project file from the current state.
    pub fn new(tracks: Vec<Track>, config: SyncConfig, result: Option<SyncResult>) -> Self {
        Self {
            version: PROJECT_VERSION,
            app_version: env!("CARGO_PKG_VERSION").to_string(),
            saved_at: chrono::Utc::now().to_rfc3339(),
            tracks,
            config,
            result,
        }
    }
}

/// Save project to a JSON file.
pub fn save_project(
    path: &str,
    tracks: &[Track],
    config: &SyncConfig,
    result: Option<&SyncResult>,
) -> Result<()> {
    let project = ProjectFile {
        version: PROJECT_VERSION,
        app_version: env!("CARGO_PKG_VERSION").to_string(),
        saved_at: chrono::Utc::now().to_rfc3339(),
        tracks: tracks.to_vec(),
        config: config.clone(),
        result: result.cloned(),
    };

    let json = serde_json::to_string_pretty(&project)
        .context("Failed to serialize project to JSON")?;

    if let Some(parent) = Path::new(path).parent() {
        std::fs::create_dir_all(parent).ok();
    }

    std::fs::write(path, &json)
        .with_context(|| format!("Failed to write project file: {}", path))?;

    info!("Project saved: {} ({} bytes)", path, json.len());
    Ok(())
}

/// Load project from a JSON file.
pub fn load_project(path: &str) -> Result<ProjectFile> {
    let json = std::fs::read_to_string(path)
        .with_context(|| format!("Cannot read project file: {}", path))?;

    let project: ProjectFile = serde_json::from_str(&json)
        .with_context(|| format!("Failed to parse project file: {}", path))?;

    if project.version > PROJECT_VERSION {
        anyhow::bail!(
            "Project file version {} is newer than supported version {}. \
             Please update AudioSync Pro.",
            project.version,
            PROJECT_VERSION
        );
    }

    info!(
        "Project loaded: {} ({} tracks, saved {})",
        path,
        project.tracks.len(),
        project.saved_at
    );
    Ok(project)
}

/// Get the default project directory.
pub fn default_projects_dir() -> std::path::PathBuf {
    if let Some(docs) = dirs::document_dir() {
        docs.join("AudioSync Pro")
    } else if let Some(home) = dirs::home_dir() {
        home.join("AudioSync Pro")
    } else {
        std::path::PathBuf::from(".")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_roundtrip() {
        let config = SyncConfig::default();
        let tracks = vec![Track::new("Test".to_string())];

        let json = serde_json::to_string(&ProjectFile::new(
            tracks.clone(),
            config.clone(),
            None,
        ))
        .unwrap();

        let loaded: ProjectFile = serde_json::from_str(&json).unwrap();
        assert_eq!(loaded.version, PROJECT_VERSION);
        assert_eq!(loaded.tracks.len(), 1);
        assert_eq!(loaded.tracks[0].name, "Test");
    }
}
