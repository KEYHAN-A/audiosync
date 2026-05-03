//! Echovault integration — create interactive audio dramas.
//!
//! After syncing, users can turn their footage into interactive
//! audio dramas with Echovault's AI engine.

use serde::{Deserialize, Serialize};
use std::time::Duration;
use reqwest::Client;

// ---------------------------------------------------------------------------
//  Serializable types for Echovault API
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct DramaRequest {
    pub project_name: String,
    pub timeline_data: TimelineData,
    pub genre: String,           // "horror", "sci-fi", "mystery", etc.
    pub mood: String,             // "tense", "melancholic", etc.
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineData {
    pub clips: Vec<ClipData>,
    pub total_duration_s: f64,
    pub reference_track: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipData {
    pub file_path: String,
    pub name: String,
    pub device: String,
    pub timeline_offset_s: f64,
    pub duration_s: f64,
    pub is_video: bool,
}

#[derive(Debug, Deserialize)]
pub struct DramaResponse {
    pub status: String,
    pub drama_id: Option<String>,
    pub message: Option<String>,
    pub play_url: Option<String>,
}

// ---------------------------------------------------------------------------
//  Tauri command: Create drama from sync project
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn create_drama_from_sync(
    project_name: String,
    timeline_json: String,  // JSON from frontend
    api_endpoint: Option<String>,
) -> Result<String, String> {
    let endpoint = api_endpoint.unwrap_or_else(|| {
        "https://echovault.keyhan.info/api/v1/generate".to_string()
    });

    // Parse timeline data
    let timeline: TimelineData = serde_json::from_str(&timeline_json)
        .map_err(|e| format!("Failed to parse timeline: {}", e))?;

    let request = DramaRequest {
        project_name,
        timeline_data: timeline,
        genre: "sci-fi".to_string(),  // Default genre
        mood: "mysterious".to_string(),  // Default mood
    };

    let client = Client::new()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let response = client
        .post(&endpoint)
        .header("Content-Type", "application/json")
        .timeout(Duration::from_secs(60))
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("Failed to send to Echovault: {}", e))?;

    if response.status().is_success() {
        let body: DramaResponse = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;
        
        if let Some(play_url) = body.play_url {
            Ok(format!(
                "Drama created: {} (play at: {})",
                body.message.unwrap_or_default(),
                play_url
            ))
        } else {
            Ok(format!(
                "Drama generation started: {:?}",
                body.drama_id
            ))
        }
    } else {
        let status = response.status();
        let text = response
            .text()
            .await
            .unwrap_or_else(|_| "Unknown error".to_string());
        Err(format!(
            "Echovault returned {}: {}",
            status, text
        ))
    }
}

// ---------------------------------------------------------------------------
//  Helper: Build TimelineData from state
// ---------------------------------------------------------------------------

pub fn build_timeline_data(
    tracks: &[Track],
    result: &SyncResult,
    project_name: &str,
) -> TimelineData {
    let mut clips = Vec::new();

    for track in tracks {
        for clip in &track.clips {
            clips.push(ClipData {
                file_path: clip.file_path.clone(),
                name: clip.name.clone(),
                device: track.name.clone(),
                timeline_offset_s: clip.timeline_offset_s,
                duration_s: clip.duration_s,
                is_video: clip.is_video,
            });
        }
    }

    let reference_track = tracks
        .get(result.reference_track_index)
        .map(|t| t.name.clone())
        .unwrap_or_else(|| "Unknown".to_string());

    TimelineData {
        clips,
        total_duration_s: result.total_timeline_s,
        reference_track,
    }
}

// ---------------------------------------------------------------------------
//  Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Clip, SyncResult, Track};

    #[test]
    fn test_build_timeline_data() {
        let tracks = vec![
            Track {
                name: "CamA".to_string(),
                is_reference: true,
                clips: vec![
                    Clip {
                        file_path: "/path/to/cam_a.mp4".to_string(),
                        name: "cam_a.mp4".to_string(),
                        timeline_offset_s: 0.0,
                        duration_s: 10.0,
                        is_video: true,
                        ..Default::default()
                    },
                ],
                ..Default::default()
            },
            Track {
                name: "Zoom".to_string(),
                is_reference: false,
                clips: vec![
                    Clip {
                        file_path: "/path/to/zoom.wav".to_string(),
                        name: "zoom.wav".to_string(),
                        timeline_offset_s: 10.0,
                        duration_s: 8.0,
                        is_video: false,
                        ..Default::default()
                    },
                ],
                ..Default::default()
            },
        ];

        let result = SyncResult {
            reference_track_index: 0,
            total_timeline_s: 18.0,
            ..Default::default()
        };

        let data = build_timeline_data(&tracks, &result, "Test Project");

        assert_eq!(data.clips.len(), 2);
        assert_eq!(data.total_duration_s, 18.0);
        assert_eq!(data.reference_track, "CamA");
        assert_eq!(data.clips[0].device, "CamA");
        assert!(data.clips[0].is_video);
        assert!(!data.clips[1].is_video);
    }

    #[test]
    fn test_clip_data_creation() {
        let clip_data = ClipData {
            file_path: "/test/path.mp4".to_string(),
            name: "test.mp4".to_string(),
            device: "Camera1".to_string(),
            timeline_offset_s: 5.5,
            duration_s: 12.0,
            is_video: true,
        };

        assert_eq!(clip_data.device, "Camera1");
        assert_eq!(clip_data.timeline_offset_s, 5.5);
        assert!(clip_data.is_video);
    }
}
