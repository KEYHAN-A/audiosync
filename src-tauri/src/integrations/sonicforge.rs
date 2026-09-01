//! SonicForge integration — master synced audio files.
//!
//! After syncing, users can master audio via SonicForge's
//! AI-powered mastering engine.

use serde::{Deserialize, Serialize};
use std::path::Path;
use tokio::process::Command;
use std::time::Duration;

// ---------------------------------------------------------------------------
//  Serializable types for SonicForge API
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct MasterRequest {
    pub audio_path: String,
    pub preset: String,           // "podcast", "music_video", "ambient", etc.
    pub loudness_lufs: Option<f64>,
    pub output_format: Option<String>, // "wav", "mp3", "flac"
}

#[derive(Debug, Deserialize)]
pub struct MasterResponse {
    pub status: String,
    pub message: String,
    pub mastered_path: Option<String>,
    pub job_id: Option<String>,
}

// ---------------------------------------------------------------------------
//  Tauri command: Master audio with SonicForge
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn master_with_sonicforge(
    audio_path: String,
    preset: Option<String>,
    output_dir: Option<String>,
    api_endpoint: Option<String>,
) -> Result<String, String> {
    let path = Path::new(&audio_path);
    if !path.exists() {
        return Err(format!("Audio file not found: {}", audio_path));
    }

    let preset = preset.unwrap_or_else(|| "standard".to_string());
    let endpoint = api_endpoint.unwrap_or_else(|| {
        "https://sonicforge.keyhan.info/api/master".to_string()
    });

    // Try API call first
    let api_result = call_mastering_api(&audio_path, &preset, &endpoint).await;
    
    match api_result {
        Ok(response) => {
            if response.status == "ok" {
                Ok(format!(
                    "Mastered via SonicForge: {:?}",
                    response.mastered_path
                ))
            } else {
                // Fallback: Use local mastering (if SonicForge CLI available)
                fallback_mastering(&audio_path, &preset, &output_dir).await
            }
        }
        Err(_) => {
            // Fallback: Use local mastering
            fallback_mastering(&audio_path, &preset, &output_dir).await
        }
    }
}

// ---------------------------------------------------------------------------
//  Helper: Call SonicForge API
// ---------------------------------------------------------------------------

async fn call_mastering_api(
    audio_path: &str,
    preset: &str,
    endpoint: &str,
) -> Result<MasterResponse, String> {
    let client = reqwest::Client::new();
    
    let request = MasterRequest {
        audio_path: audio_path.to_string(),
        preset: preset.to_string(),
        loudness_lufs: None,
        output_format: Some("wav".to_string()),
    };

    let response = client
        .post(endpoint)
        .header("Content-Type", "application/json")
        .timeout(Duration::from_secs(120))
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("Failed to call SonicForge API: {}", e))?;

    if response.status().is_success() {
        response
            .json::<MasterResponse>()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))
    } else {
        Err(format!(
            "SonicForge returned {}: {}",
            response.status(),
            response.text().await.unwrap_or_default()
        ))
    }
}

// ---------------------------------------------------------------------------
//  Helper: Fallback mastering (if SonicForge CLI available)
// ---------------------------------------------------------------------------

async fn fallback_mastering(
    audio_path: &str,
    preset: &str,
    output_dir: &Option<String>,
) -> Result<String, String> {
    // Check if SonicForge CLI is available
    let output = Command::new("which")
        .arg("sonicforge")
        .output()
        .await
        .map_err(|e| format!("Failed to check for SonicForge CLI: {}", e))?;

    if !output.status.success() {
        return Err(
            "SonicForge CLI not found. Please install SonicForge or use the API.".to_string()
        );
    }

    let output_path = output_dir.as_ref().map(|dir| {
        let file_name = Path::new(audio_path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy();
        format!("{}/{}_mastered.wav", dir, file_name)
    }).unwrap_or_else(|| {
        let file_name = Path::new(audio_path)
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy();
        format!("/tmp/{}_mastered.wav", file_name)
    });

    let status = Command::new("sonicforge")
        .arg("master")
        .arg(audio_path)
        .arg("--preset")
        .arg(preset)
        .arg("--output")
        .arg(&output_path)
        .status()
        .await
        .map_err(|e| format!("Failed to run SonicForge: {}", e))?;

    if status.success() {
        Ok(format!("Mastered (local): {}", output_path))
    } else {
        Err("SonicForge mastering failed".to_string())
    }
}

// ---------------------------------------------------------------------------
//  Tauri command: Check if SonicForge is available
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn check_sonicforge() -> bool {
    // Check if API is running
    if let Ok(response) = reqwest::blocking::get("https://sonicforge.keyhan.info/api/health") {
        if response.status().is_success() {
            return true;
        }
    }
    
    // Check if CLI is available
    if let Ok(output) = std::process::Command::new("which")
        .arg("sonicforge")
        .output() 
    {
        output.status.success()
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
    fn test_master_request_serialization() {
        let request = MasterRequest {
            audio_path: "/path/to/audio.wav".to_string(),
            preset: "music_video".to_string(),
            loudness_lufs: Some(-14.0),
            output_format: Some("wav".to_string()),
        };

        let json = serde_json::to_string(&request).unwrap();
        assert!(json.contains("music_video"));
        assert!(json.contains("/path/to/audio.wav"));
    }

    #[test]
    fn test_fallback_mastering_no_cli() {
        // This test expects SonicForge CLI to NOT be installed
        let rt = tokio::runtime::Runtime::new().unwrap();
        let result = rt.block_on(fallback_mastering(
            "/tmp/test.wav",
            "standard",
            &None,
        ));
        // Should fail gracefully if CLI not installed
        assert!(result.is_err());
    }
}
