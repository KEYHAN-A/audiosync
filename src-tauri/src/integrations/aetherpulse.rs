//! AetherPulse integration — generate social media content.
//!
//! After syncing, users can auto-generate social posts about their projects.
//! AetherPulse creates Twitter/YouTube/Bluesky content automatically.

use serde::{Deserialize, Serialize};
use std::time::Duration;
use reqwest::Client;

// ---------------------------------------------------------------------------
//  Serializable types for AetherPulse API
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct SyncProjectData {
    pub project_name: String,
    pub total_clips: usize,
    pub total_duration_s: f64,
    pub avg_confidence: f64,
    pub drift_detected: bool,
    pub warnings_count: usize,
    pub reference_track: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct GenerateRequest {
    pub topic: String,
    pub platforms: Vec<String>,
    pub tone: String,
    pub source_data: SyncProjectData,
}

#[derive(Debug, Deserialize)]
pub struct GenerateResponse {
    pub status: String,
    pub content: Option<PlatformContent>,
    pub message: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct PlatformContent {
    pub twitter: Option<String>,
    pub youtube: Option<String>,
    pub bluesky: Option<String>,
}

// ---------------------------------------------------------------------------
//  Tauri command: Generate social content
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn generate_social_content(
    project_name: String,
    sync_result_json: String,  // JSON string from frontend
    api_endpoint: Option<String>,
) -> Result<String, String> {
    // Parse the sync result
    let sync_data: SyncProjectData = serde_json::from_str(&sync_result_json)
        .map_err(|e| format!("Failed to parse sync data: {}", e))?;

    let request = GenerateRequest {
        topic: format!(
            "AudioSync Pro project: {}",
            project_name
        ),
        platforms: vec!["twitter".to_string(), "youtube".to_string()],
        tone: "professional_casual".to_string(),
        source_data: sync_data,
    };

    let endpoint = api_endpoint.unwrap_or_else(|| {
        "https://aetherpulse.keyhan.info/api/v1/generate".to_string()
    });

    let client = Client::new()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let response = client
        .post(&endpoint)
        .header("Content-Type", "application/json")
        .timeout(Duration::from_secs(60))
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("Failed to send to AetherPulse: {}", e))?;

    if response.status().is_success() {
        let body: GenerateResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;

        if let Some(content) = body.content {
            // Return the best available content
            let content_str = content
                .twitter
                .or(content.youtube)
                .or(content.bluesky)
                .unwrap_or_else(|| "Content generated but empty".to_string());
            Ok(format!(
                "Generated content: {}",
                content_str
            ))
        } else {
            Ok(format!(
                "Generation status: {} - {}",
                body.status,
                body.message.unwrap_or_default()
            ))
        }
    } else {
        let status = response.status();
        let text = response
            .text()
            .await
            .unwrap_or_else(|_| "Unknown error".to_string());
        Err(format!(
            "AetherPulse returned {}: {}",
            status, text
        ))
    }
}

// ---------------------------------------------------------------------------
//  Helper: Build SyncProjectData from state
// ---------------------------------------------------------------------------

pub fn build_sync_project_data(
    tracks: &[Track],
    result: &SyncResult,
    project_name: &str,
) -> SyncProjectData {
    let total_clips = tracks.iter().map(|t| t.clips.len()).sum();

    SyncProjectData {
        project_name: project_name.to_string(),
        total_clips,
        total_duration_s: result.total_timeline_s,
        avg_confidence: result.avg_confidence,
        drift_detected: result.drift_detected,
        warnings_count: result.warnings.len(),
        reference_track: tracks
            .get(result.reference_track_index)
            .map(|t| t.name.clone())
            .unwrap_or_else(|| "Unknown".to_string()),
    }
}

// ---------------------------------------------------------------------------
//  Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Track, SyncResult};

    #[test]
    fn test_build_sync_project_data() {
        let tracks = vec![
            Track {
                name: "CamA".to_string(),
                is_reference: true,
                clips: vec![],
                synced_audio: None,
                synced_channels: 1,
            },
            Track {
                name: "Zoom".to_string(),
                is_reference: false,
                clips: vec![],
                synced_audio: None,
                synced_channels: 1,
            },
        ];

        let result = SyncResult {
            reference_track_index: 0,
            total_timeline_samples: 480000,
            total_timeline_s: 10.0,
            sample_rate: 8000,
            clip_offsets: std::collections::HashMap::new(),
            avg_confidence: 4.5,
            drift_detected: true,
            warnings: vec!["Low confidence for clip 3".to_string()],
        };

        let data = build_sync_project_data(&tracks, &result, "Test Project");

        assert_eq!(data.project_name, "Test Project");
        assert_eq!(data.total_clips, 0);
        assert_eq!(data.total_duration_s, 10.0);
        assert!((data.avg_confidence - 4.5).abs() < 1e-6);
        assert!(data.drift_detected);
        assert_eq!(data.warnings_count, 1);
        assert_eq!(data.reference_track, "CamA");
    }
}
