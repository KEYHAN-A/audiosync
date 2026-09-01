//! AudioSync Protocol — open .sync sidecar format for sync metadata.
//!
//! Defines a JSON-based interchange format that describes how multiple
//! device recordings align on a shared timeline. Other tools (NLEs,
//! DAWs, asset managers) can read/write .sync files to interoperate
//! with AudioSync without re-running analysis.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::models::*;

// ---------------------------------------------------------------------------
//  Schema types
// ---------------------------------------------------------------------------

pub const SYNC_FORMAT_VERSION: &str = "1.0.0";
pub const SYNC_SCHEMA_URL: &str = "https://audiosync.pro/schema/sync-v1.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncFile {
    pub version: String,
    pub schema: String,
    pub project: SyncProject,
    pub timeline: SyncTimeline,
    pub devices: Vec<SyncDevice>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub analysis: Option<SyncAnalysis>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncProject {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<String>,
    pub created_by: String,
    pub tool_version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncTimeline {
    pub duration_s: f64,
    pub sample_rate: u32,
    pub units: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncDevice {
    pub id: String,
    pub name: String,
    pub is_reference: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clock: Option<SyncClock>,
    pub files: Vec<SyncFileEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncClock {
    pub nominal_rate: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub measured_rate: Option<f64>,
    pub drift_ppm: f64,
    pub drift_confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncFileEntry {
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hash: Option<String>,
    pub duration_s: f64,
    pub offset_s: f64,
    pub confidence: f64,
    pub sync_method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recorded_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncAnalysis {
    pub engine: String,
    pub engine_version: String,
    pub analysis_sample_rate: u32,
    pub confidence_threshold: f64,
    pub drift_method: String,
    pub completed_at: Option<String>,
}

// ---------------------------------------------------------------------------
//  Export
// ---------------------------------------------------------------------------

/// Export tracks and sync result to the .sync sidecar format.
pub fn export_sync(
    tracks: &[Track],
    result: &SyncResult,
    project_name: &str,
) -> Result<SyncFile> {
    let devices: Vec<SyncDevice> = tracks
        .iter()
        .enumerate()
        .map(|(i, t)| {
            let avg_drift = if t.clips.is_empty() {
                0.0
            } else {
                t.clips.iter().map(|c| c.drift_ppm).sum::<f64>() / t.clips.len() as f64
            };
            let avg_drift_conf = if t.clips.is_empty() {
                0.0
            } else {
                t.clips
                    .iter()
                    .map(|c| c.drift_confidence)
                    .sum::<f64>()
                    / t.clips.len() as f64
            };

            SyncDevice {
                id: format!("device-{}", i),
                name: t.name.clone(),
                is_reference: t.is_reference,
                clock: if avg_drift.abs() > 0.01 {
                    Some(SyncClock {
                        nominal_rate: 48000,
                        measured_rate: Some(48000.0 * (1.0 + avg_drift * 1e-6)),
                        drift_ppm: avg_drift,
                        drift_confidence: avg_drift_conf,
                    })
                } else {
                    None
                },
                files: t
                    .clips
                    .iter()
                    .map(|c| SyncFileEntry {
                        path: c.file_path.clone(),
                        hash: None,
                        duration_s: c.duration_s,
                        offset_s: c.timeline_offset_s,
                        confidence: c.confidence,
                        sync_method: if c.confidence < 0.0 {
                            "manual".to_string()
                        } else if c.confidence < CONFIDENCE_THRESHOLD {
                            "metadata".to_string()
                        } else {
                            "correlation".to_string()
                        },
                        recorded_at: c.creation_time.map(|t| format!("{:.3}", t)),
                    })
                    .collect(),
            }
        })
        .collect();

    let analysis = SyncAnalysis {
        engine: "audiosync-core".to_string(),
        engine_version: env!("CARGO_PKG_VERSION").to_string(),
        analysis_sample_rate: ANALYSIS_SR,
        confidence_threshold: CONFIDENCE_THRESHOLD,
        drift_method: "windowed_correlation".to_string(),
        completed_at: None,
    };

    Ok(SyncFile {
        version: SYNC_FORMAT_VERSION.to_string(),
        schema: SYNC_SCHEMA_URL.to_string(),
        project: SyncProject {
            name: project_name.to_string(),
            created_at: None,
            created_by: "AudioSync Pro".to_string(),
            tool_version: env!("CARGO_PKG_VERSION").to_string(),
        },
        timeline: SyncTimeline {
            duration_s: result.total_timeline_s,
            sample_rate: result.sample_rate,
            units: "seconds".to_string(),
        },
        devices,
        analysis: Some(analysis),
    })
}

/// Write a .sync file to disk.
pub fn write_sync_file(sync: &SyncFile, path: &str) -> Result<()> {
    let json = serde_json::to_string_pretty(sync).context("Failed to serialize .sync file")?;
    std::fs::write(path, json).context("Failed to write .sync file")?;
    Ok(())
}

// ---------------------------------------------------------------------------
//  Import
// ---------------------------------------------------------------------------

/// Read a .sync file from disk.
pub fn read_sync_file(path: &str) -> Result<SyncFile> {
    let content = std::fs::read_to_string(path)
        .with_context(|| format!("Failed to read .sync file: {}", path))?;
    let sync: SyncFile =
        serde_json::from_str(&content).context("Failed to parse .sync file")?;
    Ok(sync)
}

/// Validate a .sync file, returning a list of warnings.
pub fn validate_sync(sync: &SyncFile) -> Vec<String> {
    let mut warnings = Vec::new();

    if sync.version != SYNC_FORMAT_VERSION {
        warnings.push(format!(
            "Unexpected .sync version: {} (expected {})",
            sync.version, SYNC_FORMAT_VERSION
        ));
    }

    if sync.devices.is_empty() {
        warnings.push("No devices in .sync file".to_string());
    }

    let ref_count = sync.devices.iter().filter(|d| d.is_reference).count();
    if ref_count == 0 {
        warnings.push("No reference device specified".to_string());
    } else if ref_count > 1 {
        warnings.push(format!("Multiple reference devices ({})", ref_count));
    }

    for device in &sync.devices {
        if device.files.is_empty() {
            warnings.push(format!("Device '{}' has no files", device.name));
        }
        for file in &device.files {
            if file.duration_s <= 0.0 {
                warnings.push(format!(
                    "File '{}' has invalid duration: {}",
                    file.path, file.duration_s
                ));
            }
            if !file.sync_method.is_empty()
                && !["correlation", "metadata", "manual"].contains(&file.sync_method.as_str())
            {
                warnings.push(format!(
                    "Unknown sync method '{}' for '{}'",
                    file.sync_method, file.path
                ));
            }
        }
    }

    if sync.timeline.duration_s <= 0.0 {
        warnings.push("Timeline duration must be positive".to_string());
    }

    warnings
}

/// Import offsets from a .sync file, returning a mapping of file_path → offset_s.
pub fn import_offsets(sync: &SyncFile) -> HashMap<String, f64> {
    let mut offsets = HashMap::new();
    for device in &sync.devices {
        for file in &device.files {
            offsets.insert(file.path.clone(), file.offset_s);
        }
    }
    offsets
}

/// Compute SHA-256 hash of a file for verification.
pub fn compute_file_hash(path: &str) -> Result<String> {
    use std::io::Read;
    let mut file = std::fs::File::open(path)
        .with_context(|| format!("Failed to open file for hashing: {}", path))?;
    let mut hasher = sha256_compact();
    let mut buf = [0u8; 8192];
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hasher.finalize_hex())
}

// ---------------------------------------------------------------------------
//  Minimal SHA-256 (avoids adding a crypto dependency)
// ---------------------------------------------------------------------------

struct Sha256Compact {
    state: [u32; 8],
    buffer: Vec<u8>,
    length: u64,
}

fn sha256_compact() -> Sha256Compact {
    Sha256Compact {
        state: [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c,
            0x1f83d9ab, 0x5be0cd19,
        ],
        buffer: Vec::new(),
        length: 0,
    }
}

impl Sha256Compact {
    fn update(&mut self, data: &[u8]) {
        self.length += data.len() as u64;
        self.buffer.extend_from_slice(data);
        while self.buffer.len() >= 64 {
            let block: [u8; 64] = self.buffer[..64].try_into().unwrap();
            self.transform(&block);
            self.buffer.drain(..64);
        }
    }

    fn finalize_hex(&mut self) -> String {
        let bit_len = self.length * 8;
        self.buffer.push(0x80);
        while self.buffer.len() % 64 != 56 {
            self.buffer.push(0);
        }
        self.buffer
            .extend_from_slice(&bit_len.to_be_bytes());
        while !self.buffer.is_empty() {
            let block: [u8; 64] = if self.buffer.len() >= 64 {
                self.buffer[..64].try_into().unwrap()
            } else {
                let mut b = [0u8; 64];
                b[..self.buffer.len()].copy_from_slice(&self.buffer);
                b
            };
            self.transform(&block);
            if self.buffer.len() <= 64 {
                break;
            }
            self.buffer.drain(..64);
        }
        self.state
            .iter()
            .flat_map(|&w| w.to_be_bytes())
            .map(|b| format!("{:02x}", b))
            .collect()
    }

    fn transform(&mut self, block: &[u8; 64]) {
        const K: [u32; 64] = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
            0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
            0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
            0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
            0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
            0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
            0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
            0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
            0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
        ];

        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                block[i * 4],
                block[i * 4 + 1],
                block[i * 4 + 2],
                block[i * 4 + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }

        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h] = self.state;

        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let temp1 = h
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let temp2 = s0.wrapping_add(maj);

            h = g;
            g = f;
            f = e;
            e = d.wrapping_add(temp1);
            d = c;
            c = b;
            b = a;
            a = temp1.wrapping_add(temp2);
        }

        self.state[0] = self.state[0].wrapping_add(a);
        self.state[1] = self.state[1].wrapping_add(b);
        self.state[2] = self.state[2].wrapping_add(c);
        self.state[3] = self.state[3].wrapping_add(d);
        self.state[4] = self.state[4].wrapping_add(e);
        self.state[5] = self.state[5].wrapping_add(f);
        self.state[6] = self.state[6].wrapping_add(g);
        self.state[7] = self.state[7].wrapping_add(h);
    }
}

// ---------------------------------------------------------------------------
//  Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_export_sync_structure() {
        let mut track = Track::new("Zoom H6".to_string());
        track.is_reference = true;
        track.clips.push(Clip {
            file_path: "zoom_001.wav".to_string(),
            name: "zoom_001.wav".to_string(),
            samples: vec![0.0; 8000],
            sample_rate: 8000,
            original_sr: 48000,
            original_channels: 2,
            duration_s: 1.0,
            is_video: false,
            creation_time: Some(1000.0),
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: 10.0,
            analyzed: true,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        });

        let result = SyncResult {
            reference_track_index: 0,
            total_timeline_samples: 8000,
            total_timeline_s: 1.0,
            sample_rate: 8000,
            clip_offsets: HashMap::new(),
            avg_confidence: 10.0,
            drift_detected: false,
            warnings: vec![],
        };

        let sync = export_sync(&[track], &result, "Test Project").unwrap();

        assert_eq!(sync.version, "1.0.0");
        assert_eq!(sync.devices.len(), 1);
        assert!(sync.devices[0].is_reference);
        assert_eq!(sync.devices[0].files.len(), 1);
        assert_eq!(sync.devices[0].files[0].offset_s, 0.0);
        assert_eq!(sync.devices[0].files[0].sync_method, "correlation");
    }

    #[test]
    fn test_sync_roundtrip() {
        let mut track1 = Track::new("Camera A".to_string());
        track1.is_reference = true;
        track1.clips.push(Clip {
            file_path: "camA_001.wav".to_string(),
            name: "camA_001.wav".to_string(),
            samples: vec![0.0; 8000],
            sample_rate: 8000,
            original_sr: 48000,
            original_channels: 1,
            duration_s: 1.0,
            is_video: false,
            creation_time: None,
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: 10.0,
            analyzed: true,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        });

        let result = SyncResult {
            reference_track_index: 0,
            total_timeline_samples: 8000,
            total_timeline_s: 1.0,
            sample_rate: 8000,
            clip_offsets: HashMap::new(),
            avg_confidence: 10.0,
            drift_detected: false,
            warnings: vec![],
        };

        let sync = export_sync(&[track1], &result, "Roundtrip Test").unwrap();
        let json = serde_json::to_string(&sync).unwrap();
        let parsed: SyncFile = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.version, sync.version);
        assert_eq!(parsed.devices.len(), 1);
        assert_eq!(parsed.devices[0].files[0].path, "camA_001.wav");
    }

    #[test]
    fn test_validate_sync() {
        let sync = SyncFile {
            version: "1.0.0".to_string(),
            schema: SYNC_SCHEMA_URL.to_string(),
            project: SyncProject {
                name: "Test".to_string(),
                created_at: None,
                created_by: "Test".to_string(),
                tool_version: "3.2.0".to_string(),
            },
            timeline: SyncTimeline {
                duration_s: 100.0,
                sample_rate: 48000,
                units: "seconds".to_string(),
            },
            devices: vec![SyncDevice {
                id: "device-0".to_string(),
                name: "Cam".to_string(),
                is_reference: true,
                clock: None,
                files: vec![SyncFileEntry {
                    path: "test.wav".to_string(),
                    hash: None,
                    duration_s: 60.0,
                    offset_s: 0.0,
                    confidence: 10.0,
                    sync_method: "correlation".to_string(),
                    recorded_at: None,
                }],
            }],
            analysis: None,
        };

        let warnings = validate_sync(&sync);
        assert!(warnings.is_empty(), "Expected no warnings: {:?}", warnings);
    }

    #[test]
    fn test_validate_sync_problems() {
        let sync = SyncFile {
            version: "0.9.0".to_string(),
            schema: SYNC_SCHEMA_URL.to_string(),
            project: SyncProject {
                name: "Test".to_string(),
                created_at: None,
                created_by: "Test".to_string(),
                tool_version: "3.2.0".to_string(),
            },
            timeline: SyncTimeline {
                duration_s: -1.0,
                sample_rate: 48000,
                units: "seconds".to_string(),
            },
            devices: vec![],
            analysis: None,
        };

        let warnings = validate_sync(&sync);
        assert!(warnings.iter().any(|w| w.contains("version")));
        assert!(warnings.iter().any(|w| w.contains("No devices")));
        assert!(warnings.iter().any(|w| w.contains("No reference")));
        assert!(warnings.iter().any(|w| w.contains("duration")));
    }

    #[test]
    fn test_import_offsets() {
        let sync = SyncFile {
            version: "1.0.0".to_string(),
            schema: SYNC_SCHEMA_URL.to_string(),
            project: SyncProject {
                name: "Test".to_string(),
                created_at: None,
                created_by: "Test".to_string(),
                tool_version: "3.2.0".to_string(),
            },
            timeline: SyncTimeline {
                duration_s: 100.0,
                sample_rate: 48000,
                units: "seconds".to_string(),
            },
            devices: vec![
                SyncDevice {
                    id: "d0".to_string(),
                    name: "A".to_string(),
                    is_reference: true,
                    clock: None,
                    files: vec![SyncFileEntry {
                        path: "a.wav".to_string(),
                        hash: None,
                        duration_s: 10.0,
                        offset_s: 0.0,
                        confidence: 10.0,
                        sync_method: "correlation".to_string(),
                        recorded_at: None,
                    }],
                },
                SyncDevice {
                    id: "d1".to_string(),
                    name: "B".to_string(),
                    is_reference: false,
                    clock: None,
                    files: vec![SyncFileEntry {
                        path: "b.wav".to_string(),
                        hash: None,
                        duration_s: 10.0,
                        offset_s: 1.5,
                        confidence: 8.0,
                        sync_method: "correlation".to_string(),
                        recorded_at: None,
                    }],
                },
            ],
            analysis: None,
        };

        let offsets = import_offsets(&sync);
        assert_eq!(offsets.get("a.wav"), Some(&0.0));
        assert_eq!(offsets.get("b.wav"), Some(&1.5));
    }

    #[test]
    fn test_sha256_empty() {
        let mut h = sha256_compact();
        let hash = h.finalize_hex();
        // SHA-256 of empty string
        assert_eq!(
            hash,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn test_sync_method_classification() {
        // confidence >= 3.0 → correlation
        let mut track = Track::new("test".to_string());
        track.clips.push(Clip {
            file_path: "high.wav".to_string(),
            name: "high.wav".to_string(),
            samples: vec![],
            sample_rate: 8000,
            original_sr: 48000,
            original_channels: 1,
            duration_s: 1.0,
            is_video: false,
            creation_time: None,
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: 5.0,
            analyzed: true,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        });
        // confidence < 3.0 → metadata
        track.clips.push(Clip {
            file_path: "low.wav".to_string(),
            name: "low.wav".to_string(),
            samples: vec![],
            sample_rate: 8000,
            original_sr: 48000,
            original_channels: 1,
            duration_s: 1.0,
            is_video: false,
            creation_time: None,
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: 1.5,
            analyzed: true,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        });
        // confidence < 0 → manual
        track.clips.push(Clip {
            file_path: "manual.wav".to_string(),
            name: "manual.wav".to_string(),
            samples: vec![],
            sample_rate: 8000,
            original_sr: 48000,
            original_channels: 1,
            duration_s: 1.0,
            is_video: false,
            creation_time: None,
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: -1.0,
            analyzed: true,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        });

        let result = SyncResult {
            reference_track_index: 0,
            total_timeline_samples: 8000,
            total_timeline_s: 1.0,
            sample_rate: 8000,
            clip_offsets: HashMap::new(),
            avg_confidence: 1.83,
            drift_detected: false,
            warnings: vec![],
        };

        let sync = export_sync(&[track], &result, "Methods").unwrap();
        let methods: Vec<&str> = sync.devices[0].files.iter().map(|f| f.sync_method.as_str()).collect();
        assert_eq!(methods, vec!["correlation", "metadata", "manual"]);
    }
}
