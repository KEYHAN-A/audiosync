//! Structured logging with tracing, file rotation, and diagnostics export.

use std::path::PathBuf;
use std::time::SystemTime;
use tracing::Level;
use tracing_subscriber::{
    fmt::{self, format::FmtSpan},
    layer::SubscriberExt,
    util::SubscriberInitExt,
    EnvFilter,
};

/// Default log file name
const LOG_FILE_NAME: &str = "audiosync.log";

/// Maximum log file size before rotation (10 MB) - reserved for future use
#[allow(dead_code)]
const MAX_LOG_SIZE_BYTES: u64 = 10 * 1024 * 1024;

/// Number of log files to keep - reserved for future use
#[allow(dead_code)]
const LOG_RETENTION: usize = 3;

/// Initialize the logging system with file and console output.
///
/// # Arguments
/// * `log_dir` - Directory to store log files (uses platform default if None)
/// * `level` - Minimum log level (uses RUST_LOG env var if None)
/// * `console` - Whether to also log to console
pub fn init_logging(log_dir: Option<PathBuf>, level: Option<Level>, console: bool) -> anyhow::Result<()> {
    // Determine log directory
    let log_path = if let Some(dir) = log_dir {
        dir
    } else {
        get_default_log_dir()?
    };

    // Create log directory if it doesn't exist
    std::fs::create_dir_all(&log_path)?;

    // Set up file appender with rotation
    let file_appender = tracing_appender::rolling::never(&log_path, LOG_FILE_NAME);
    let (file_writer, _guard) = tracing_appender::non_blocking(file_appender);

    // Build the environment filter
    let env_filter = if let Some(lvl) = level {
        EnvFilter::new(lvl.to_string().to_lowercase())
    } else {
        EnvFilter::from_default_env()
            .add_directive("audiosync_core=debug".parse()?)
            .add_directive("audiosync_cli=info".parse()?)
    };

    // Add file layer (always with timestamps and spans)
    let file_layer = fmt::layer()
        .with_writer(file_writer)
        .with_ansi(false)
        .with_span_events(FmtSpan::CLOSE)
        .with_target(true)
        .with_thread_ids(true);

    // Build the subscriber based on console flag
    if console {
        // Console + file logging
        let console_layer = fmt::layer()
            .with_span_events(FmtSpan::CLOSE)
            .with_target(false)
            .with_thread_ids(false);

        tracing_subscriber::registry()
            .with(env_filter)
            .with(file_layer)
            .with(console_layer)
            .init();
    } else {
        // File only logging
        tracing_subscriber::registry()
            .with(env_filter)
            .with(file_layer)
            .init();
    }

    tracing::info!(
        log_path = %log_path.display(),
        "AudioSync logging initialized"
    );

    Ok(())
}

/// Initialize logging for the CLI with a progress bar.
///
/// This is a convenience function for the CLI that sets up
/// logging with console output and progress bar support.
pub fn init_cli_logging(verbose: bool) -> anyhow::Result<()> {
    let level = if verbose {
        Level::DEBUG
    } else {
        Level::INFO
    };
    init_logging(None, Some(level), true)
}

/// Initialize minimal logging (errors only) for GUI apps.
///
/// This prevents log spam in the GUI while still capturing
/// important information for debugging.
pub fn init_gui_logging() -> anyhow::Result<()> {
    init_logging(None, Some(Level::WARN), false)
}

/// Get the default log directory for the current platform.
pub fn get_default_log_dir() -> anyhow::Result<PathBuf> {
    let base = dirs::home_dir()
        .ok_or_else(|| anyhow::anyhow!("Could not determine home directory"))?;

    let log_dir = if cfg!(target_os = "macos") {
        base.join("Library/Logs/AudioSync")
    } else if cfg!(target_os = "windows") {
        base.join("AppData/Roaming/AudioSync/logs")
    } else {
        // Linux and others
        base.join(".local/share/audiosync/logs")
    };

    Ok(log_dir)
}

/// Get the path to the current log file.
pub fn get_log_path() -> PathBuf {
    let log_dir = get_default_log_dir().unwrap_or_else(|_| PathBuf::from("."));
    log_dir.join(LOG_FILE_NAME)
}

/// Export diagnostic information as JSON.
///
/// This includes:
/// - Sync quality metrics (confidence scores per clip)
/// - Drift measurements with R² values
/// - Timeline integrity report
/// - System information
#[derive(Debug, Clone, serde::Serialize)]
pub struct DiagnosticsReport {
    pub timestamp: String,
    pub version: String,
    pub os: String,
    pub project_summary: ProjectSummary,
    pub sync_quality: SyncQualityMetrics,
    pub drift_info: Vec<ClipDriftInfo>,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct ProjectSummary {
    pub total_tracks: usize,
    pub total_clips: usize,
    pub total_timeline_s: f64,
    pub reference_track: String,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct SyncQualityMetrics {
    pub avg_confidence: f64,
    pub min_confidence: f64,
    pub max_confidence: f64,
    pub low_confidence_clips: Vec<String>,
    pub metadata_fallback_clips: Vec<String>,
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct ClipDriftInfo {
    pub track_name: String,
    pub clip_name: String,
    pub drift_ppm: f64,
    pub confidence_r_squared: f64,
    pub significant: bool,
}

impl DiagnosticsReport {
    /// Generate a diagnostics report from sync results.
    pub fn from_sync_result(
        tracks: &[crate::Track],
        result: &crate::SyncResult,
    ) -> Self {
        use crate::Track;

        let low_confidence: Vec<String> = tracks
            .iter()
            .flat_map(|t| {
                t.clips
                    .iter()
                    .filter(|c| c.confidence < 3.0 && c.analyzed)
                    .map(|c| format!("{}: {}", t.name, c.name))
            })
            .collect();

        let metadata_fallback: Vec<String> = tracks
            .iter()
            .flat_map(|t| {
                t.clips
                    .iter()
                    .filter(|c| c.confidence < 1.0 && c.timeline_offset_samples > 0)
                    .map(|c| format!("{}: {}", t.name, c.name))
            })
            .collect();

        let mut drift_info = Vec::new();
        for track in tracks {
            for clip in &track.clips {
                if clip.drift_ppm.abs() > 0.1 {
                    drift_info.push(ClipDriftInfo {
                        track_name: track.name.clone(),
                        clip_name: clip.name.clone(),
                        drift_ppm: clip.drift_ppm,
                        confidence_r_squared: clip.drift_confidence,
                        significant: clip.drift_ppm.abs() > 0.3 && clip.drift_confidence > 0.5,
                    });
                }
            }
        }

        let confidences: Vec<f64> = tracks
            .iter()
            .flat_map(|t| t.clips.iter().map(|c| c.confidence))
            .collect();

        let avg_confidence = if confidences.is_empty() {
            0.0
        } else {
            confidences.iter().sum::<f64>() / confidences.len() as f64
        };

        let min_confidence = confidences
            .iter()
            .cloned()
            .fold(f64::INFINITY, f64::min);
        let max_confidence = confidences
            .iter()
            .cloned()
            .fold(f64::NEG_INFINITY, f64::max);

        let reference_track_name = tracks
            .get(result.reference_track_index)
            .map(|t| t.name.clone())
            .unwrap_or_else(|| "Unknown".to_string());

        DiagnosticsReport {
            timestamp: format!("{:?}", SystemTime::now()),
            version: env!("CARGO_PKG_VERSION").to_string(),
            os: format!("{} {}", std::env::consts::OS, std::env::consts::ARCH),
            project_summary: ProjectSummary {
                total_tracks: tracks.len(),
                total_clips: tracks.iter().map(|t| t.clips.len()).sum(),
                total_timeline_s: result.total_timeline_s,
                reference_track: reference_track_name,
            },
            sync_quality: SyncQualityMetrics {
                avg_confidence,
                min_confidence: if min_confidence.is_finite() {
                    min_confidence
                } else {
                    0.0
                },
                max_confidence: if max_confidence.is_finite() {
                    max_confidence
                } else {
                    0.0
                },
                low_confidence_clips: low_confidence,
                metadata_fallback_clips: metadata_fallback,
            },
            drift_info,
            warnings: result.warnings.clone(),
        }
    }

    /// Export diagnostics as JSON string.
    pub fn to_json(&self) -> anyhow::Result<String> {
        serde_json::to_string_pretty(self).map_err(Into::into)
    }

    /// Export diagnostics to a file.
    pub fn save_to_file(&self, path: &str) -> anyhow::Result<()> {
        let json = self.to_json()?;
        std::fs::write(path, json)?;
        tracing::info!("Diagnostics saved to {}", path);
        Ok(())
    }

    /// Get a human-readable text summary.
    pub fn to_text_summary(&self) -> String {
        let mut summary = String::new();
        summary.push_str("=== AudioSync Diagnostics Report ===\n\n");
        summary.push_str(&format!("Generated: {}\n", self.timestamp));
        summary.push_str(&format!("Version: {}\n", self.version));
        summary.push_str(&format!("OS: {}\n\n", self.os));

        summary.push_str("--- Project Summary ---\n");
        summary.push_str(&format!("Total Tracks: {}\n", self.project_summary.total_tracks));
        summary.push_str(&format!("Total Clips: {}\n", self.project_summary.total_clips));
        summary.push_str(&format!("Timeline Duration: {:.1}s\n", self.project_summary.total_timeline_s));
        summary.push_str(&format!("Reference Track: {}\n\n", self.project_summary.reference_track));

        summary.push_str("--- Sync Quality ---\n");
        summary.push_str(&format!(
            "Average Confidence: {:.2}\n",
            self.sync_quality.avg_confidence
        ));
        summary.push_str(&format!(
            "Min/Max Confidence: {:.2} / {:.2}\n",
            self.sync_quality.min_confidence, self.sync_quality.max_confidence
        ));

        if !self.sync_quality.low_confidence_clips.is_empty() {
            summary.push_str("\nLow Confidence Clips (<3.0):\n");
            for clip in &self.sync_quality.low_confidence_clips {
                summary.push_str(&format!("  - {}\n", clip));
            }
        }

        if !self.sync_quality.metadata_fallback_clips.is_empty() {
            summary.push_str("\nMetadata Fallback Clips:\n");
            for clip in &self.sync_quality.metadata_fallback_clips {
                summary.push_str(&format!("  - {}\n", clip));
            }
        }

        if !self.drift_info.is_empty() {
            summary.push_str("\n--- Clock Drift ---\n");
            for info in &self.drift_info {
                let marker = if info.significant { "⚠️" } else { "" };
                summary.push_str(&format!(
                    "{}  {} / {} : {:+.2} ppm (R²={:.3})\n",
                    marker, info.track_name, info.clip_name, info.drift_ppm, info.confidence_r_squared
                ));
            }
        }

        if !self.warnings.is_empty() {
            summary.push_str("\n--- Warnings ---\n");
            for warning in &self.warnings {
                summary.push_str(&format!("  ⚠️  {}\n", warning));
            }
        }

        summary.push_str("\n==============================\n");
        summary
    }
}

/// Log sync result with quality metrics.
pub fn log_sync_result(
    tracks: &[crate::Track],
    result: &crate::SyncResult,
) {
    let diagnostics = DiagnosticsReport::from_sync_result(tracks, result);

    tracing::info!(
        total_tracks = diagnostics.project_summary.total_tracks,
        total_clips = diagnostics.project_summary.total_clips,
        timeline_s = diagnostics.project_summary.total_timeline_s,
        avg_confidence = diagnostics.sync_quality.avg_confidence,
        drift_detected = result.drift_detected,
        warnings = diagnostics.warnings.len(),
        "Sync analysis complete"
    );

    // Log low confidence warnings
    for clip in &diagnostics.sync_quality.low_confidence_clips {
        tracing::warn!(clip = %clip, "Low confidence match");
    }

    // Log drift information
    for info in &diagnostics.drift_info {
        if info.significant {
            tracing::warn!(
                track = %info.track_name,
                clip = %info.clip_name,
                drift_ppm = info.drift_ppm,
                r_squared = info.confidence_r_squared,
                "Significant clock drift detected"
            );
        } else {
            tracing::info!(
                track = %info.track_name,
                clip = %info.clip_name,
                drift_ppm = info.drift_ppm,
                r_squared = info.confidence_r_squared,
                "Clock drift measured"
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Clip, Track};

    #[test]
    fn test_diagnostics_report() {
        let mut track = Track::new("TestTrack".to_string());
        let mut clip = Clip::new(
            "test.wav".to_string(),
            "test.wav".to_string(),
            48000,
            2,
        );
        clip.confidence = 5.0;
        clip.drift_ppm = 25.0;
        clip.drift_confidence = 0.9;
        track.clips.push(clip);

        let result = crate::SyncResult {
            reference_track_index: 0,
            total_timeline_samples: 48000,
            total_timeline_s: 1.0,
            sample_rate: 48000,
            clip_offsets: std::collections::HashMap::new(),
            avg_confidence: 5.0,
            drift_detected: true,
            warnings: vec!["Test warning".to_string()],
        };

        let diagnostics = DiagnosticsReport::from_sync_result(&[track], &result);

        assert_eq!(diagnostics.project_summary.total_tracks, 1);
        assert_eq!(diagnostics.project_summary.total_clips, 1);
        assert_eq!(diagnostics.sync_quality.avg_confidence, 5.0);
        assert_eq!(diagnostics.drift_info.len(), 1);
        assert!(diagnostics.drift_info[0].significant);
    }

    #[test]
    fn test_diagnostics_json_export() {
        let diagnostics = DiagnosticsReport {
            timestamp: "2024-01-01T00:00:00Z".to_string(),
            version: "1.0.0".to_string(),
            os: "linux x86_64".to_string(),
            project_summary: ProjectSummary {
                total_tracks: 1,
                total_clips: 1,
                total_timeline_s: 60.0,
                reference_track: "Main".to_string(),
            },
            sync_quality: SyncQualityMetrics {
                avg_confidence: 8.5,
                min_confidence: 5.0,
                max_confidence: 12.0,
                low_confidence_clips: vec![],
                metadata_fallback_clips: vec![],
            },
            drift_info: vec![],
            warnings: vec![],
        };

        let json = diagnostics.to_json().unwrap();
        assert!(json.contains("avg_confidence"));
        assert!(json.contains("8.5"));
    }
}
