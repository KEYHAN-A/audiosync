//! WebAssembly bindings for AudioSync core engine.
//!
//! Exposes the sync engine to JavaScript for browser-based audio synchronization.
//! Audio files are loaded from ArrayBuffer (File API), analysis runs via FFT
//! cross-correlation entirely in the browser.

use wasm_bindgen::prelude::*;
use serde::{Deserialize, Serialize};
use audiosync_core::models::*;
use audiosync_core::engine;

// ---------------------------------------------------------------------------
//  Serializable types for JS interop
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize)]
pub struct WasmClipInfo {
    pub name: String,
    pub duration_s: f64,
    pub original_sr: u32,
    pub is_video: bool,
    pub timeline_offset_s: f64,
    pub confidence: f64,
    pub analyzed: bool,
    pub drift_ppm: f64,
    pub waveform_peaks: Vec<f32>,
}

#[derive(Serialize, Deserialize)]
pub struct WasmTrackInfo {
    pub name: String,
    pub is_reference: bool,
    pub clips: Vec<WasmClipInfo>,
    pub total_duration_s: f64,
}

#[derive(Serialize)]
pub struct WasmSyncResult {
    pub tracks: Vec<WasmTrackInfo>,
    pub total_timeline_s: f64,
    pub avg_confidence: f64,
    pub drift_detected: bool,
    pub warnings: Vec<String>,
}

// ---------------------------------------------------------------------------
//  Engine wrapper
// ---------------------------------------------------------------------------

/// Main WASM sync engine, holding loaded clips in memory.
#[wasm_bindgen]
pub struct WasmSyncEngine {
    tracks: Vec<Track>,
    result: Option<SyncResult>,
}

#[wasm_bindgen]
impl WasmSyncEngine {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self {
            tracks: Vec::new(),
            result: None,
        }
    }

    /// Load audio from raw bytes (e.g., from File API ArrayBuffer).
    /// Decodes WAV data and returns clip info as JSON.
    pub fn load_clip_from_bytes(&mut self, name: &str, data: &[u8]) -> Result<JsValue, JsValue> {
        // Decode WAV from bytes
        let samples = decode_wav_bytes(data)
            .map_err(|e| JsValue::from_str(&format!("Decode failed: {}", e)))?;

        let sr = 8000u32; // Analysis sample rate
        let duration_s = samples.len() as f64 / sr as f64;

        let clip = Clip {
            file_path: name.to_string(),
            name: name.to_string(),
            samples,
            sample_rate: sr,
            original_sr: sr,
            original_channels: 1,
            duration_s,
            is_video: false,
            creation_time: None,
            timeline_offset_samples: 0,
            timeline_offset_s: 0.0,
            confidence: 0.0,
            analyzed: false,
            drift_ppm: 0.0,
            drift_confidence: 0.0,
            drift_corrected: false,
        };

        let info = WasmClipInfo {
            name: clip.name.clone(),
            duration_s: clip.duration_s,
            original_sr: clip.original_sr,
            is_video: clip.is_video,
            timeline_offset_s: 0.0,
            confidence: 0.0,
            analyzed: false,
            drift_ppm: 0.0,
            waveform_peaks: downsample_peaks(&clip.samples, 400),
        };

        // Auto-group by device prefix (before first separator)
        let device_name = extract_device_name(name);
        if let Some(track) = self.tracks.iter_mut().find(|t| t.name == device_name) {
            track.clips.push(clip);
        } else {
            let mut track = Track::new(device_name);
            track.clips.push(clip);
            self.tracks.push(track);
        }

        serde_wasm_bindgen::to_value(&info).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Group loaded clips by device name. Returns track info as JSON.
    pub fn get_tracks(&self) -> Result<JsValue, JsValue> {
        let infos: Vec<WasmTrackInfo> = self.tracks.iter().map(|t| WasmTrackInfo {
            name: t.name.clone(),
            is_reference: t.is_reference,
            clips: t.clips.iter().map(|c| WasmClipInfo {
                name: c.name.clone(),
                duration_s: c.duration_s,
                original_sr: c.original_sr,
                is_video: c.is_video,
                timeline_offset_s: c.timeline_offset_s,
                confidence: c.confidence,
                analyzed: c.analyzed,
                drift_ppm: c.drift_ppm,
                waveform_peaks: downsample_peaks(&c.samples, 400),
            }).collect(),
            total_duration_s: t.total_duration_s(),
        }).collect();

        serde_wasm_bindgen::to_value(&infos).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Run the FFT analysis pipeline. Returns sync result as JSON.
    pub fn analyze(&mut self) -> Result<JsValue, JsValue> {
        if self.tracks.is_empty() {
            return Err(JsValue::from_str("No tracks loaded"));
        }

        let config = SyncConfig::default();
        let result = engine::analyze(&mut self.tracks, &config, &None, &None)
            .map_err(|e| JsValue::from_str(&format!("Analysis failed: {}", e)))?;

        let wasm_result = WasmSyncResult {
            total_timeline_s: result.total_timeline_s,
            avg_confidence: result.avg_confidence,
            drift_detected: result.drift_detected,
            warnings: result.warnings.clone(),
            tracks: self.tracks.iter().map(|t| WasmTrackInfo {
                name: t.name.clone(),
                is_reference: t.is_reference,
                clips: t.clips.iter().map(|c| WasmClipInfo {
                    name: c.name.clone(),
                    duration_s: c.duration_s,
                    original_sr: c.original_sr,
                    is_video: c.is_video,
                    timeline_offset_s: c.timeline_offset_s,
                    confidence: c.confidence,
                    analyzed: c.analyzed,
                    drift_ppm: c.drift_ppm,
                    waveform_peaks: downsample_peaks(&c.samples, 400),
                }).collect(),
                total_duration_s: t.total_duration_s(),
            }).collect(),
        };

        self.result = Some(result);
        serde_wasm_bindgen::to_value(&wasm_result).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Get the version string.
    pub fn version() -> String {
        env!("CARGO_PKG_VERSION").to_string()
    }

    /// Get the number of loaded tracks.
    pub fn track_count(&self) -> usize {
        self.tracks.len()
    }

    /// Reset the engine state.
    pub fn reset(&mut self) {
        self.tracks.clear();
        self.result = None;
    }
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

/// Decode WAV bytes to mono f32 samples at the native sample rate.
/// Supports 16-bit and 24-bit PCM WAV files.
fn decode_wav_bytes(data: &[u8]) -> Result<Vec<f32>, String> {
    if data.len() < 44 {
        return Err("Data too short for WAV header".to_string());
    }

    // Check RIFF header
    if &data[0..4] != b"RIEF" && &data[0..4] != b"RIFF" {
        return Err("Not a WAV file".to_string());
    }

    let channels = u16::from_le_bytes([data[22], data[23]]) as usize;
    let sample_rate = u32::from_le_bytes([data[24], data[25], data[26], data[27]]);
    let bits_per_sample = u16::from_le_bytes([data[34], data[35]]) as usize;
    let data_size = u32::from_le_bytes([data[40], data[41], data[42], data[43]]) as usize;

    let audio_start = 44;
    let bytes_per_sample = bits_per_sample / 8;
    let num_samples = data_size / (bytes_per_sample * channels);

    let mut mono = Vec::with_capacity(num_samples);

    for i in 0..num_samples {
        let sample_offset = audio_start + i * bytes_per_sample * channels;
        let mut sum = 0.0f64;

        for ch in 0..channels {
            let offset = sample_offset + ch * bytes_per_sample;
            if offset + bytes_per_sample > data.len() {
                break;
            }

            let val = match bits_per_sample {
                16 => {
                    let s = i16::from_le_bytes([data[offset], data[offset + 1]]);
                    s as f64 / 32768.0
                }
                24 => {
                    let s = (data[offset] as i32)
                        | ((data[offset + 1] as i32) << 8)
                        | ((data[offset + 2] as i32) << 16);
                    let s = if s >= 0x800000 { s - 0x1000000 } else { s };
                    s as f64 / 8388608.0
                }
                32 => {
                    let s = f32::from_le_bytes([
                        data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
                    ]);
                    s as f64
                }
                _ => return Err(format!("Unsupported bit depth: {}", bits_per_sample)),
            };
            sum += val;
        }

        mono.push((sum / channels as f64) as f32);
    }

    // Resample to 8kHz if needed
    if sample_rate != 8000 {
        let ratio = sample_rate as f64 / 8000.0;
        let new_len = (mono.len() as f64 / ratio) as usize;
        let mut resampled = Vec::with_capacity(new_len);
        for i in 0..new_len {
            let src_idx = (i as f64 * ratio) as usize;
            if src_idx < mono.len() {
                resampled.push(mono[src_idx]);
            }
        }
        Ok(resampled)
    } else {
        Ok(mono)
    }
}

fn extract_device_name(filename: &str) -> String {
    let stem = filename.rsplit('.').nth(1).unwrap_or(filename);
    let parts: Vec<&str> = stem.splitn(2, |c: char| c == '_' || c == '-' || c == ' ').collect();
    parts.first().unwrap_or(&stem).to_string()
}

fn downsample_peaks(samples: &[f32], n: usize) -> Vec<f32> {
    if samples.is_empty() || n == 0 {
        return Vec::new();
    }
    if samples.len() <= n {
        return samples.iter().map(|s| s.abs()).collect();
    }

    let bucket_size = samples.len() as f64 / n as f64;
    let mut peaks = Vec::with_capacity(n);

    for i in 0..n {
        let start = (i as f64 * bucket_size) as usize;
        let end = ((i + 1) as f64 * bucket_size).ceil() as usize;
        let end = end.min(samples.len());
        let peak = samples[start..end]
            .iter()
            .map(|s| s.abs())
            .fold(0.0f32, f32::max);
        peaks.push(peak);
    }

    peaks
}
