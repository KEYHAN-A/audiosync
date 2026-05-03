//! Synthwave Studio integration — export synced audio for music production.
//!
//! After syncing, users can export audio directly to Synthwave Studio
//! for music video production (matching audio with synced video).

use serde::{Deserialize, Serialize};
use std::path::Path;
use tokio::process::Command;
use std::time::Duration;

// ---------------------------------------------------------------------------
//  Serializable types for Synthwave Studio API
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SynthwaveExport {
    pub project_name: String,
    pub audio_path: String,
    pub timeline_offset_s: f64,
    pub duration_s: f64,
    pub sample_rate: u32,
    pub bit_depth: u32,
}

#[derive(Debug, Deserialize)]
pub struct SynthwaveResponse {
    pub status: String,
    pub message: String,
    pub project_id: Option<String>,
}

// ---------------------------------------------------------------------------
//  Tauri command: Export audio to Synthwave Studio
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn export_to_synthwave_studio(
    track_index: usize,
    audio_path: String,
    project_name: String,
    state: tauri::State<'_, super::AppState>,
) -> Result<String, String> {
    let state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    
    if track_index >= state_tracks.len() {
        return Err(format!("Track index {} out of range", track_index));
    }

    let track = &state_tracks[track_index];
    
    if track.synced_audio.is_none() {
        return Err("Track not synced yet - run sync first".to_string());
    }

    let audio_path = Path::new(&audio_path);
    if !audio_path.exists() {
        return Err(format!("Audio file not found: {}", audio_path.display()));
    }

    // Build export payload
    let export = SynthwaveExport {
        project_name,
        audio_path: audio_path.to_string_lossy().to_string(),
        timeline_offset_s: track.clips.first().map(|c| c.timeline_offset_s).unwrap_or(0.0),
        duration_s: track.total_duration_s(),
        sample_rate: 48000, // Synthwave Studio default
        bit_depth: 24,
    };

    // Try API call first (if Synthwave Studio is running)
    let api_result = try_api_export(&export).await;
    
    match api_result {
        Ok(response) => {
            if response.status == "ok" {
                Ok(format!("Exported to Synthwave Studio: {:?}", response.project_id))
            } else {
                // Fallback: copy to Synthwave Studio imports folder
                fallback_export(&export).await
            }
        }
        Err(_) => {
            // Fallback: copy to Synthwave Studio imports folder
            fallback_export(&export).await
        }
    }
}

// ---------------------------------------------------------------------------
//  Helper: Try API export (if Synthwave Studio is running)
// ---------------------------------------------------------------------------

async fn try_api_export(export: &SynthwaveExport) -> Result<SynthwaveResponse, String> {
    let client = reqwest::Client::new();
    
    let response = client
        .post("http://localhost:8080/api/import/audio")
        .header("Content-Type", "application/json")
        .timeout(Duration::from_secs(10))
        .json(export)
        .send()
        .await
        .map_err(|e| format!("API call failed: {}", e))?;

    if response.status().is_success() {
        response.json().await.map_err(|e| format!("Failed to parse response: {}", e))
    } else {
        Err(format!("Synthwave Studio API returned: {}", response.status()))
    }
}

// ---------------------------------------------------------------------------
//  Helper: Fallback export (copy to imports folder)
// ---------------------------------------------------------------------------

async fn fallback_export(export: &SynthwaveExport) -> Result<String, String> {
    // Common Synthwave Studio import paths
    let possible_paths = vec![
        dirs::document_dir().map(|mut d| {
            d.push("Synthwave Studio/imports");
            d
        }),
        dirs::home_dir().map(|mut d| {
            d.push("Projects/Synthwave Studio/imports");
            d
        }),
    ];

    for path in possible_paths {
        if let Ok(mut imports_dir) = path {
            if imports_dir.exists() {
                let file_name = Path::new(&export.audio_path)
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy();
                
                let dest = imports_dir.join(file_name);
                
                tokio::fs::copy(&export.audio_path, &dest)
                    .await
                    .map_err(|e| format!("Failed to copy file: {}", e))?;
                
                return Ok(format!("Copied to Synthwave Studio imports: {}", dest.display()));
            }
        }
    }

    Err("Synthwave Studio not found. Please copy {} manually to Synthwave Studio imports.".to_string())
}

// ---------------------------------------------------------------------------
//  Tauri command: Check if Synthwave Studio is available
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn check_synthwave_studio() -> bool {
    // Check if Synthwave Studio API is running
    if let Ok(response) = reqwest::blocking::get("http://localhost:8080/api/health") {
        response.status().is_success()
    } else {
        false
    }
}

// ---------------------------------------------------------------------------
//  Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_synthwave_export_creation() {
        let export = SynthwaveExport {
            project_name: "Music Video".to_string(),
            audio_path: "/tmp/test.wav".to_string(),
            timeline_offset_s: 10.5,
            duration_s: 30.0,
            sample_rate: 48000,
            bit_depth: 24,
        };

        assert_eq!(export.project_name, "Music Video");
        assert_eq!(export.timeline_offset_s, 10.5);
        assert_eq!(export.sample_rate, 48000);
    }
}
