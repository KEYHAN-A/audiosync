//! AetherDistill integration — send sync timeline data for AI summarization.
//!
//! AudioSync produces timeline data (clip offsets, confidence, drift).
//! AetherDistill can ingest this, summarize it, and enrich it.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::time::Duration;
use reqwest::Client;

// ---------------------------------------------------------------------------
//  Serializable types for AetherDistill API
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct TimelineExport {
    pub project_name: String,
    pub total_timeline_s: f64,
    pub reference_track: String,
    pub avg_confidence: f64,
    pub drift_detected: bool,
    pub clips: Vec<ClipExport>,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ClipExport {
    pub file_path: String,
    pub name: String,
    pub device: String,
    pub timeline_offset_s: f64,
    pub confidence: f64,
    pub drift_ppm: f64,
    pub duration_s: f64,
}

#[derive(Debug, Deserialize)]
pub struct IngestResponse {
    pub status: String,
    pub message: String,
    pub artifact_id: Option<String>,
}

// ---------------------------------------------------------------------------
//  AetherDistill client
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn export_to_aetherdistill(
    timeline_data: Value,
    api_endpoint: String,
) -> Result<String, String> {
    let client = Client::new()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let response = client
        .post(&format!("{}/api/v1/ingest", api_endpoint))
        .header("Content-Type", "application/json")
        .timeout(Duration::from_secs(30))
        .json(&timeline_data)
        .send()
        .await
        .map_err(|e| format!("Failed to send to AetherDistill: {}", e))?;

    if response.status().is_success() {
        let body: IngestResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;
        Ok(format!(
            "Exported to AetherDistill: {} (artifact: {:?})",
            body.message, body.artifact_id
        ))
    } else {
        let status = response.status();
        let text = response
            .text()
            .await
            .unwrap_or_else(|_| "Unknown error".to_string());
        Err(format!(
            "AetherDistill returned {}: {}",
            status, text
        ))
    }
}

/// Build timeline export from current state.
pub fn build_timeline_export(
    tracks: &[Track],
    result: &SyncResult,
    project_name: &str,
) -> TimelineExport {
    let mut clips = Vec::new();

    for track in tracks {
        for clip in &track.clips {
            clips.push(ClipExport {
                file_path: clip.file_path.clone(),
                name: clip.name.clone(),
                device: track.name.clone(),
                timeline_offset_s: clip.timeline_offset_s,
                confidence: clip.confidence,
                drift_ppm: clip.drift_ppm,
                duration_s: clip.duration_s,
            });
        }
    }

    TimelineExport {
        project_name: project_name.to_string(),
        total_timeline_s: result.total_timeline_s,
        reference_track: tracks
            .get(result.reference_track_index)
            .map(|t| t.name.clone())
            .unwrap_or_else(|| "Unknown".to_string()),
        avg_confidence: result.avg_confidence,
        drift_detected: result.drift_detected,
        clips,
        warnings: result.warnings.clone(),
    }
}

/// Convert TimelineExport to JSON for sending.
pub fn timeline_to_json(export: &TimelineExport) -> Result<String, String> {
    serde_json::to_string(export).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
//  Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Clip, SyncResult, Track};

    #[test]
    fn test_build_timeline_export() {
        let tracks = vec![
            Track {
                name: "CamA".to_string(),
                is_reference: true,
                clips: vec![Clip {
                    file_path: "/path/to/cam_a.mp4".to_string(),
                    name: "cam_a.mp4".to_string(),
                    timeline_offset_s: 0.0,
                    confidence: 5.0,
                    drift_ppm: 0.0,
                    duration_s: 10.0,
                    ..Default::default()
                }],
                ..Default::default()
            },
            Track {
                name: "Zoom".to_string(),
                is_reference: false,
                clips: vec![Clip {
                    file_path: "/path/to/zoom.wav".to_string(),
                    name: "zoom.wav".to_string(),
                    timeline_offset_s: 10.0,
                    confidence: 4.5,
                    drift_ppm: 50.0,
                    duration_s: 8.0,
                    ..Default::default()
                }],
                ..Default::default()
            },
        ];

        let result = SyncResult {
            reference_track_index: 0,
            total_timeline_s: 18.0,
            avg_confidence: 4.75,
            drift_detected: true,
            warnings: vec!["Low confidence for 'zoom.wav'".to_string()],
            ..Default::default()
        };

        let export = build_timeline_export(&tracks, &result, "Test Project");

        assert_eq!(export.project_name, "Test Project");
        assert_eq!(export.clips.len(), 2);
        assert_eq!(export.total_timeline_s, 18.0);
        assert!(export.drift_detected);
        assert_eq!(export.warnings.len(), 1);
    }
}
