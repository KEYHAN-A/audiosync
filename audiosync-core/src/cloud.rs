//! Cloud API client — upload/download projects.
//!
//! Phase 3+ implementation. Provides the public interface used by CLI and Tauri.

use anyhow::Result;
use log::info;

/// Cloud service configuration.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CloudConfig {
    pub endpoint: String,
    pub api_key: Option<String>,
}

impl Default for CloudConfig {
    fn default() -> Self {
        Self {
            endpoint: "https://api.audiosync.pro".to_string(),
            api_key: None,
        }
    }
}

/// Upload a project file to the cloud.
pub async fn upload_project(_config: &CloudConfig, _project_path: &str) -> Result<String> {
    info!("Cloud upload not yet implemented (Phase 3+)");
    Ok("not-implemented".to_string())
}

/// Download a project file from the cloud.
pub async fn download_project(
    _config: &CloudConfig,
    _project_id: &str,
    _output_path: &str,
) -> Result<()> {
    info!("Cloud download not yet implemented (Phase 3+)");
    Ok(())
}
