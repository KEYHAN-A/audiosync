//! Metadata extraction — creation timestamps and file info via ffprobe.
//!
//! Mirrors `python/core/metadata.py`.

use anyhow::Result;
use chrono::DateTime;
use log::debug;
use serde::Deserialize;
use std::process::Command;

/// Extract creation_time as a Unix timestamp from an audio/video file.
///
/// Fallback chain:
///   1. `format_tags.creation_time` (most reliable for MP4/MOV)
///   2. `stream_tags.creation_time` on the first audio stream
///   3. File modification time
pub fn probe_creation_time(path: &str) -> Option<f64> {
    // Try ffprobe first
    if let Some(ts) = probe_creation_time_ffprobe(path) {
        return Some(ts);
    }

    // Fallback to file modification time
    file_mtime(path)
}

fn probe_creation_time_ffprobe(path: &str) -> Option<f64> {
    let output = Command::new("ffprobe")
        .args([
            "-v", "quiet",
            "-print_format", "json",
            "-show_entries",
            "format_tags=creation_time:stream_tags=creation_time",
            path,
        ])
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let data: FfprobeOutput = serde_json::from_slice(&output.stdout).ok()?;

    // Try format-level creation_time first
    if let Some(ref format) = data.format {
        if let Some(ref tags) = format.tags {
            if let Some(ref ct) = tags.creation_time {
                if let Some(ts) = parse_iso_timestamp(ct) {
                    return Some(ts);
                }
            }
        }
    }

    // Try stream-level creation_time
    if let Some(ref streams) = data.streams {
        for stream in streams {
            if let Some(ref tags) = stream.tags {
                if let Some(ref ct) = tags.creation_time {
                    if let Some(ts) = parse_iso_timestamp(ct) {
                        return Some(ts);
                    }
                }
            }
        }
    }

    None
}

fn file_mtime(path: &str) -> Option<f64> {
    let metadata = std::fs::metadata(path).ok()?;
    let modified = metadata.modified().ok()?;
    let duration = modified
        .duration_since(std::time::UNIX_EPOCH)
        .ok()?;
    Some(duration.as_secs_f64())
}

fn parse_iso_timestamp(value: &str) -> Option<f64> {
    let value = value.trim();

    // Try standard ISO 8601 formats
    let formats = [
        "%Y-%m-%dT%H:%M:%S%.fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%.f%:z",
        "%Y-%m-%dT%H:%M:%S%:z",
        "%Y-%m-%dT%H:%M:%S%.f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ];

    for fmt in &formats {
        // Try parsing with timezone
        if let Ok(dt) = DateTime::parse_from_str(value, fmt) {
            return Some(dt.timestamp() as f64 + dt.timestamp_subsec_nanos() as f64 * 1e-9);
        }
        // Try parsing as naive UTC
        if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(value, fmt) {
            let utc = dt.and_utc();
            return Some(utc.timestamp() as f64 + utc.timestamp_subsec_nanos() as f64 * 1e-9);
        }
    }

    debug!("Failed to parse timestamp: {}", value);
    None
}

// ---------------------------------------------------------------------------
//  ffprobe JSON structures
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct FfprobeOutput {
    format: Option<FfprobeFormat>,
    streams: Option<Vec<FfprobeStream>>,
}

#[derive(Debug, Deserialize)]
struct FfprobeFormat {
    tags: Option<FfprobeTags>,
}

#[derive(Debug, Deserialize)]
struct FfprobeStream {
    tags: Option<FfprobeTags>,
}

#[derive(Debug, Deserialize)]
struct FfprobeTags {
    creation_time: Option<String>,
}

/// Get (sample_rate, channels) from an audio/video file using ffprobe.
pub fn probe_audio_info(path: &str) -> Result<(u32, u32)> {
    let output = Command::new("ffprobe")
        .args([
            "-v", "quiet",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels",
            "-of", "csv=p=0",
            path,
        ])
        .output()?;

    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        let parts: Vec<&str> = stdout.trim().split(',').collect();
        if parts.len() >= 2 {
            let sr: u32 = parts[0].parse().unwrap_or(48000);
            let ch: u32 = parts[1].parse().unwrap_or(2);
            return Ok((sr, ch));
        }
    }

    // Safe fallback
    Ok((48000, 2))
}
