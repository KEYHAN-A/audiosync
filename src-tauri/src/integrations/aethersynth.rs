//! AetherSynth integration — use synced audio for AI music generation.
//!
//! AudioSync produces synced audio → AetherSynth can generate
//! matching background music or soundtracks.

use serde::{Deserialize, Serialize};
use std::path::Path;
use tokio::process::Command;
use std::time::Duration;

// ---------------------------------------------------------------------------
//  Serializable types for AetherSynth API
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioInput {
    pub audio_path: String,
    pub timeline_markers: Vec<TimelineMarker>,
    pub project_name: String,
    pub mood: Option<String>,
    pub genre: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineMarker {
    pub time_s: f64,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerateRequest {
    pub audio_input: AudioInput,
    pub prompt: Option<String>,
    pub duration: Option<f64>,
    pub output_format: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerateResponse {
    pub status: String,
    pub generated_audio_path: Option<String>,
    pub message: Option<String>,
    pub job_id: Option<String>,
}

// ---------------------------------------------------------------------------
//  Tauri command: Send synced audio to AetherSynth for music generation
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn generate_music_with_aethersynth(
    audio_path: String,
    project_name: String,
    api_endpoint: Option<String>,
) -> Result<String, String> {
    let endpoint = api_endpoint.unwrap_or_else(|| {
        "https://aethersynth.keyhan.info/api/v1/generate/track".to_string()
    });

    // Build timeline markers from audio (scene changes, etc.)
    let markers = extract_timeline_markers(&audio_path).await
        .map_err(|e| format!("Failed to analyze audio: {}", e))?;

    let request = GenerateRequest {
        audio_input: AudioInput {
            audio_path: audio_path.clone(),
            timeline_markers: markers,
            project_name,
            mood: Some("matching_video".to_string()),
            genre: Some(vec!["synthwave".to_string(), "electronic".to_string()]),
        },
        prompt: Some("Generate background music that matches the synced video timeline".to_string()),
        duration: None, // Match audio duration
        output_format: Some("wav".to_string()),
    };

    let client = reqwest::Client::new();
    let response = client
        .post(&endpoint)
        .header("Content-Type", "application/json")
        .timeout(Duration::from_secs(120))
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("Failed to send to AetherSynth: {}", e))?;

    if response.status().is_success() {
        let body: GenerateResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;
        
        if let Some(ref path) = body.generated_audio_path {
            Ok(format!(
                "Music generated: {} (job: {:?})",
                path, body.job_id
            ))
        } else {
            Ok(format!(
                "Generation started: {:?} - {}",
                body.job_id,
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
            "AetherSynth returned {}: {}",
            status, text
        ))
    }
}

// ---------------------------------------------------------------------------
//  Helper: Extract timeline markers from audio (scene changes)
// ---------------------------------------------------------------------------

async fn extract_timeline_markers(audio_path: &str) -> Result<Vec<TimelineMarker>, String> {
    // Use ffmpeg to detect scene changes or use audio analysis
    // For now, create simple markers based on file structure
    
    let mut markers = Vec::new();
    
    // Example: Add markers at significant points
    // In real implementation, analyze audio for scene changes, silence gaps, etc.
    markers.push(TimelineMarker {
        time_s: 0.0,
        description: "Start".to_string(),
    });
    
    // TODO: Use ffmpeg or custom analysis to find scene changes
    // Example command: ffmpeg -i input.wav -vf "select='gt(scene,0.4)',showinfo -f null -
    
    Ok(markers)
}

// ---------------------------------------------------------------------------
//  Helper: Fallback - copy audio to AetherSynth imports folder
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn copy_to_aethersynth_imports(audio_path: String) -> Result<String, String> {
    let possible_paths = vec![
        dirs::document_dir().map(|mut d| {
            d.push("AetherSynth/imports");
            d
        }),
        dirs::home_dir().map(|mut d| {
            d.push("Projects/AetherSynth/imports");
            d
        }),
    ];

    for path in possible_paths {
        if let Ok(mut imports_dir) = path {
            if imports_dir.exists() {
                let file_name = Path::new(&audio_path)
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy();
                
                let dest = imports_dir.join(file_name);
                
                tokio::fs::copy(audio_path, &dest)
                    .await
                    .map_err(|e| format!("Failed to copy file: {}", e))?;
                
                return Ok(format!("Copied to AetherSynth imports: {}", dest.display()));
            }
        }
    }

    Err("AetherSynth imports folder not found. Please copy manually.".to_string())
}

// ---------------------------------------------------------------------------
//  Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_timeline_marker_creation() {
        let marker = TimelineMarker {
            time_s: 10.5,
            description: "Scene change".to_string(),
        };
        assert_eq!(marker.time_s, 10.5);
        assert_eq!(marker.description, "Scene change");
    }

    #[test]
    fn test_generate_request_serialization() {
        let request = GenerateRequest {
            audio_input: AudioInput {
                audio_path: "/path/to/audio.wav".to_string(),
                timeline_markers: vec![],
                project_name: "Test".to_string(),
                mood: Some("calm".to_string()),
                genre: Some(vec!["ambient".to_string()]),
            },
            prompt: None,
            duration: Some(60.0),
            output_format: Some("wav".to_string()),
        };

        let json = serde_json::to_string(&request).unwrap();
        assert!(json.contains("Test"));
        assert!(json.contains("calm"));
    }
}
