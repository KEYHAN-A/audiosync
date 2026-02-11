//! Data models for AudioSync core engine.
//!
//! Mirrors the Python `core/models.py` data structures.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// Analysis sample rate — low-res mono used for cross-correlation only.
pub const ANALYSIS_SR: u32 = 8000;

/// Confidence threshold — clips below this are considered poorly matched.
pub const CONFIDENCE_THRESHOLD: f64 = 3.0;

/// Minimum overlap (seconds) to attempt drift measurement.
pub const MIN_DRIFT_OVERLAP_S: f64 = 60.0;

/// Minimum number of measurement windows for a reliable regression.
pub const MIN_DRIFT_WINDOWS: usize = 3;

// ---------------------------------------------------------------------------
//  Cancellation
// ---------------------------------------------------------------------------

/// Cancellation token — shared atomic bool for cooperative cancellation.
pub type CancelToken = Arc<AtomicBool>;

/// Create a new cancellation token.
pub fn new_cancel_token() -> CancelToken {
    Arc::new(AtomicBool::new(false))
}

/// Check if cancelled; return Err if so.
pub fn check_cancelled(cancel: &Option<CancelToken>) -> Result<(), CancelledError> {
    if let Some(token) = cancel {
        if token.load(Ordering::Relaxed) {
            return Err(CancelledError("Operation cancelled".to_string()));
        }
    }
    Ok(())
}

/// Progress callback type: (current_step, total_steps, message).
pub type ProgressCallback = Box<dyn Fn(usize, usize, &str) + Send + Sync>;

// ---------------------------------------------------------------------------
//  Clip
// ---------------------------------------------------------------------------

/// A single audio or video file imported into a track.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Clip {
    pub file_path: String,
    pub name: String,

    /// 8 kHz mono samples for analysis (not serialized to project files).
    #[serde(skip)]
    pub samples: Vec<f32>,

    pub sample_rate: u32,
    pub original_sr: u32,
    pub original_channels: u32,
    pub duration_s: f64,
    pub is_video: bool,
    pub creation_time: Option<f64>,

    // Populated after analysis
    pub timeline_offset_samples: i64,
    pub timeline_offset_s: f64,
    pub confidence: f64,
    pub analyzed: bool,

    // Clock drift
    pub drift_ppm: f64,
    pub drift_confidence: f64,
    pub drift_corrected: bool,
}

impl Clip {
    pub fn new(file_path: String, name: String, original_sr: u32, original_channels: u32) -> Self {
        Self {
            file_path,
            name,
            samples: Vec::new(),
            sample_rate: ANALYSIS_SR,
            original_sr,
            original_channels,
            duration_s: 0.0,
            is_video: false,
            creation_time: None,
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: 0.0,
            analyzed: false,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        }
    }

    pub fn length_samples(&self) -> usize {
        self.samples.len()
    }

    pub fn end_samples(&self) -> i64 {
        self.timeline_offset_samples + self.samples.len() as i64
    }

    /// Convert timeline offset from analysis SR to a target SR.
    pub fn timeline_offset_at_sr(&self, target_sr: u32) -> i64 {
        if self.sample_rate == target_sr {
            return self.timeline_offset_samples;
        }
        (self.timeline_offset_s * target_sr as f64).round() as i64
    }

    /// Clip length in samples at a target SR.
    pub fn length_at_sr(&self, target_sr: u32) -> usize {
        (self.duration_s * target_sr as f64).round() as usize
    }
}

// ---------------------------------------------------------------------------
//  Track
// ---------------------------------------------------------------------------

/// A device track containing one or more clips.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Track {
    pub name: String,
    pub clips: Vec<Clip>,
    pub is_reference: bool,

    #[serde(skip)]
    pub synced_audio: Option<Vec<f64>>,

    /// For multi-channel export: number of channels in synced audio.
    #[serde(skip)]
    pub synced_channels: u32,
}

impl Track {
    pub fn new(name: String) -> Self {
        Self {
            name,
            clips: Vec::new(),
            is_reference: false,
            synced_audio: None,
            synced_channels: 1,
        }
    }

    pub fn total_duration_s(&self) -> f64 {
        self.clips.iter().map(|c| c.duration_s).sum()
    }

    pub fn clip_count(&self) -> usize {
        self.clips.len()
    }

    pub fn total_samples(&self) -> usize {
        self.clips.iter().map(|c| c.length_samples()).sum()
    }

    /// Sort clips by creation_time (then filename as fallback).
    pub fn sort_clips_by_time(&mut self) {
        self.clips.sort_by(|a, b| {
            let ta = a.creation_time.unwrap_or(0.0);
            let tb = b.creation_time.unwrap_or(0.0);
            ta.partial_cmp(&tb)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.name.cmp(&b.name))
        });
    }
}

// ---------------------------------------------------------------------------
//  SyncResult
// ---------------------------------------------------------------------------

/// Results produced by the analysis engine.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncResult {
    pub reference_track_index: usize,
    pub total_timeline_samples: i64,
    pub total_timeline_s: f64,
    pub sample_rate: u32,
    pub clip_offsets: HashMap<String, i64>,
    pub avg_confidence: f64,
    pub drift_detected: bool,
    pub warnings: Vec<String>,
}

// ---------------------------------------------------------------------------
//  SyncConfig
// ---------------------------------------------------------------------------

/// Configuration for the sync engine.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncConfig {
    pub max_offset_s: Option<f64>,
    pub export_format: String,
    pub export_bit_depth: u32,
    pub export_bitrate_kbps: u32,
    pub export_sr: Option<u32>,
    pub crossfade_ms: f64,
    pub drift_correction: bool,
    pub drift_threshold_ppm: f64,
}

impl Default for SyncConfig {
    fn default() -> Self {
        Self {
            max_offset_s: None,
            export_format: "wav".to_string(),
            export_bit_depth: 24,
            export_bitrate_kbps: 320,
            export_sr: None,
            crossfade_ms: 50.0,
            drift_correction: true,
            drift_threshold_ppm: 0.3,
        }
    }
}

impl SyncConfig {
    pub fn is_lossy(&self) -> bool {
        matches!(self.export_format.to_lowercase().as_str(), "mp3")
    }

    /// Soundfile subtype string for the chosen bit depth.
    pub fn subtype(&self) -> &str {
        match self.export_bit_depth {
            16 => "PCM_16",
            24 => "PCM_24",
            32 => "FLOAT",
            _ => "PCM_24",
        }
    }
}

// ---------------------------------------------------------------------------
//  Errors
// ---------------------------------------------------------------------------

#[derive(Debug, thiserror::Error)]
#[error("Operation cancelled: {0}")]
pub struct CancelledError(pub String);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clip_new() {
        let clip = Clip::new("test.wav".into(), "test.wav".into(), 48000, 2);
        assert_eq!(clip.sample_rate, ANALYSIS_SR);
        assert_eq!(clip.original_sr, 48000);
        assert_eq!(clip.original_channels, 2);
        assert!(!clip.analyzed);
        assert_eq!(clip.duration_s, 0.0);
    }

    #[test]
    fn test_clip_length_at_sr() {
        let mut clip = Clip::new("test.wav".into(), "test.wav".into(), 48000, 1);
        clip.duration_s = 10.0;
        assert_eq!(clip.length_at_sr(48000), 480000);
        assert_eq!(clip.length_at_sr(44100), 441000);
    }

    #[test]
    fn test_clip_timeline_offset_at_sr() {
        let mut clip = Clip::new("test.wav".into(), "test.wav".into(), 48000, 1);
        clip.timeline_offset_samples = 8000; // 1s at ANALYSIS_SR
        clip.timeline_offset_s = 1.0;
        // Convert to 48 kHz
        assert_eq!(clip.timeline_offset_at_sr(48000), 48000);
    }

    #[test]
    fn test_track_sort_clips_by_time() {
        let mut track = Track::new("Test".into());
        let mut c1 = Clip::new("a.wav".into(), "a.wav".into(), 48000, 1);
        c1.creation_time = Some(200.0);
        let mut c2 = Clip::new("b.wav".into(), "b.wav".into(), 48000, 1);
        c2.creation_time = Some(100.0);
        track.clips.push(c1);
        track.clips.push(c2);
        track.sort_clips_by_time();
        assert_eq!(track.clips[0].name, "b.wav");
        assert_eq!(track.clips[1].name, "a.wav");
    }

    #[test]
    fn test_sync_config_defaults() {
        let cfg = SyncConfig::default();
        assert_eq!(cfg.export_format, "wav");
        assert_eq!(cfg.export_bit_depth, 24);
        assert!(cfg.drift_correction);
        assert!(!cfg.is_lossy());
    }

    #[test]
    fn test_sync_config_lossy() {
        let mut cfg = SyncConfig::default();
        cfg.export_format = "mp3".into();
        assert!(cfg.is_lossy());
    }

    #[test]
    fn test_cancel_token() {
        let token = new_cancel_token();
        assert!(check_cancelled(&Some(token.clone())).is_ok());
        token.store(true, std::sync::atomic::Ordering::Relaxed);
        assert!(check_cancelled(&Some(token)).is_err());
    }

    #[test]
    fn test_check_cancelled_none() {
        assert!(check_cancelled(&None).is_ok());
    }

    #[test]
    fn test_track_total_duration() {
        let mut track = Track::new("Test".into());
        let mut c1 = Clip::new("a.wav".into(), "a.wav".into(), 48000, 1);
        c1.duration_s = 5.0;
        let mut c2 = Clip::new("b.wav".into(), "b.wav".into(), 48000, 1);
        c2.duration_s = 10.0;
        track.clips.push(c1);
        track.clips.push(c2);
        assert!((track.total_duration_s() - 15.0).abs() < 1e-6);
        assert_eq!(track.clip_count(), 2);
    }
}
