//! Tauri command handlers — IPC bridge between Vue frontend and Rust backend.
//!
//! Each `#[tauri::command]` function is callable from JavaScript via `invoke()`.
//! Long-running operations (analyze, sync) run on a blocking thread and emit
//! progress events back to the frontend.

use audiosync_core::audio_io::{export_track, is_supported_file, load_clip};
use audiosync_core::engine;
use audiosync_core::grouping::group_files_by_device;
use audiosync_core::models::*;
use audiosync_core::project_io;
use audiosync_core::timeline_export;

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State};

// ---------------------------------------------------------------------------
//  App state — shared across all commands
// ---------------------------------------------------------------------------

#[derive(Default)]
pub struct AppState {
    pub tracks: Mutex<Vec<Track>>,
    pub result: Mutex<Option<SyncResult>>,
    pub config: Mutex<SyncConfig>,
    pub cancel_token: Mutex<Option<CancelToken>>,
}

// ---------------------------------------------------------------------------
//  Serializable types for the frontend
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClipInfo {
    pub file_path: String,
    pub name: String,
    pub duration_s: f64,
    pub original_sr: u32,
    pub original_channels: u32,
    pub is_video: bool,
    pub creation_time: Option<f64>,
    pub timeline_offset_s: f64,
    pub timeline_offset_samples: i64,
    pub confidence: f64,
    pub analyzed: bool,
    pub drift_ppm: f64,
    pub drift_confidence: f64,
    pub drift_corrected: bool,
    /// Waveform peaks for Canvas rendering (downsampled).
    pub waveform_peaks: Vec<f32>,
}

impl From<&Clip> for ClipInfo {
    fn from(c: &Clip) -> Self {
        // Downsample analysis samples to ~400 peaks for UI rendering
        let peaks = downsample_peaks(&c.samples, 400);
        Self {
            file_path: c.file_path.clone(),
            name: c.name.clone(),
            duration_s: c.duration_s,
            original_sr: c.original_sr,
            original_channels: c.original_channels,
            is_video: c.is_video,
            creation_time: c.creation_time,
            timeline_offset_s: c.timeline_offset_s,
            timeline_offset_samples: c.timeline_offset_samples,
            confidence: c.confidence,
            analyzed: c.analyzed,
            drift_ppm: c.drift_ppm,
            drift_confidence: c.drift_confidence,
            drift_corrected: c.drift_corrected,
            waveform_peaks: peaks,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackInfo {
    pub name: String,
    pub is_reference: bool,
    pub clips: Vec<ClipInfo>,
    pub total_duration_s: f64,
}

impl From<&Track> for TrackInfo {
    fn from(t: &Track) -> Self {
        Self {
            name: t.name.clone(),
            is_reference: t.is_reference,
            clips: t.clips.iter().map(ClipInfo::from).collect(),
            total_duration_s: t.total_duration_s(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ProgressPayload {
    pub step: usize,
    pub total: usize,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct AnalysisResult {
    pub tracks: Vec<TrackInfo>,
    pub result: SyncResult,
}

#[derive(Debug, Clone, Serialize)]
pub struct DriftResult {
    pub delay_samples: i64,
    pub delay_s: f64,
    pub confidence: f64,
    pub drift_ppm: f64,
    pub drift_r_squared: f64,
    pub drift_significant: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportConfig {
    pub output_dir: String,
    pub format: String,
    pub bit_depth: u32,
    pub drift_correction: bool,
    pub fcpxml_path: Option<String>,
    pub edl_path: Option<String>,
}

// ---------------------------------------------------------------------------
//  Commands
// ---------------------------------------------------------------------------

#[tauri::command]
pub fn get_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// Import files — group by device, load clips, return track info with waveform peaks.
#[tauri::command]
pub async fn import_files(
    paths: Vec<String>,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<Vec<TrackInfo>, String> {
    let supported: Vec<String> = paths
        .into_iter()
        .filter(|p| is_supported_file(p))
        .collect();

    if supported.is_empty() {
        return Err("No supported audio/video files found.".to_string());
    }

    let groups = group_files_by_device(&supported);
    let total_files: usize = groups.values().map(|v| v.len()).sum();
    let app_clone = app.clone();

    let result = tokio::task::spawn_blocking(move || {
        let mut tracks: Vec<Track> = Vec::new();
        let mut loaded = 0usize;

        for (device_name, paths) in &groups {
            let mut track = Track::new(device_name.clone());
            for path in paths {
                loaded += 1;
                let fname = Path::new(path)
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                let _ = app_clone.emit(
                    "import-progress",
                    ProgressPayload {
                        step: loaded,
                        total: total_files,
                        message: format!("Loading '{}'...", fname),
                    },
                );

                match load_clip(path, &None) {
                    Ok(clip) => track.clips.push(clip),
                    Err(e) => {
                        log::warn!("Failed to load {}: {}", path, e);
                    }
                }
            }
            if !track.clips.is_empty() {
                tracks.push(track);
            }
        }

        tracks
    })
    .await
    .map_err(|e| format!("Import task failed: {}", e))?;

    let track_infos: Vec<TrackInfo> = result.iter().map(TrackInfo::from).collect();

    // Store in app state
    let mut state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    *state_tracks = result;

    // Clear previous results
    let mut state_result = state.result.lock().map_err(|e| e.to_string())?;
    *state_result = None;

    Ok(track_infos)
}

/// Add files to an existing track (by index).
#[tauri::command]
pub async fn add_files_to_track(
    track_index: usize,
    paths: Vec<String>,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<Vec<TrackInfo>, String> {
    let supported: Vec<String> = paths
        .into_iter()
        .filter(|p| is_supported_file(p))
        .collect();

    if supported.is_empty() {
        return Err("No supported files.".to_string());
    }

    let total = supported.len();
    let app_clone = app.clone();

    let new_clips = tokio::task::spawn_blocking(move || {
        let mut clips = Vec::new();
        for (i, path) in supported.iter().enumerate() {
            let _ = app_clone.emit(
                "import-progress",
                ProgressPayload {
                    step: i + 1,
                    total,
                    message: format!("Loading '{}'...", Path::new(path).file_name().unwrap_or_default().to_string_lossy()),
                },
            );
            match load_clip(path, &None) {
                Ok(clip) => clips.push(clip),
                Err(e) => log::warn!("Failed to load {}: {}", path, e),
            }
        }
        clips
    })
    .await
    .map_err(|e| format!("Load failed: {}", e))?;

    let mut state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    if track_index >= state_tracks.len() {
        return Err(format!("Track index {} out of range", track_index));
    }
    state_tracks[track_index].clips.extend(new_clips);

    // Clear previous analysis
    let mut state_result = state.result.lock().map_err(|e| e.to_string())?;
    *state_result = None;

    Ok(state_tracks.iter().map(TrackInfo::from).collect())
}

/// Create a new empty track.
#[tauri::command]
pub fn create_track(name: String, state: State<'_, AppState>) -> Result<Vec<TrackInfo>, String> {
    let mut state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    state_tracks.push(Track::new(name));
    Ok(state_tracks.iter().map(TrackInfo::from).collect())
}

/// Remove a track by index.
#[tauri::command]
pub fn remove_track(index: usize, state: State<'_, AppState>) -> Result<Vec<TrackInfo>, String> {
    let mut state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    if index >= state_tracks.len() {
        return Err(format!("Track index {} out of range", index));
    }
    state_tracks.remove(index);
    Ok(state_tracks.iter().map(TrackInfo::from).collect())
}

/// Remove a clip from a track.
#[tauri::command]
pub fn remove_clip(
    track_index: usize,
    clip_index: usize,
    state: State<'_, AppState>,
) -> Result<Vec<TrackInfo>, String> {
    let mut state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    if track_index >= state_tracks.len() {
        return Err("Track index out of range".to_string());
    }
    if clip_index >= state_tracks[track_index].clips.len() {
        return Err("Clip index out of range".to_string());
    }
    state_tracks[track_index].clips.remove(clip_index);
    Ok(state_tracks.iter().map(TrackInfo::from).collect())
}

/// Get current tracks state.
#[tauri::command]
pub fn get_tracks(state: State<'_, AppState>) -> Result<Vec<TrackInfo>, String> {
    let state_tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    Ok(state_tracks.iter().map(TrackInfo::from).collect())
}

/// Run analysis — emits "analysis-progress" events, returns full result.
#[tauri::command]
pub async fn run_analysis(
    max_offset_s: Option<f64>,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<AnalysisResult, String> {
    // Prepare cancel token
    let cancel = new_cancel_token();
    {
        let mut ct = state.cancel_token.lock().map_err(|e| e.to_string())?;
        *ct = Some(cancel.clone());
    }

    // Clone tracks out of state for processing
    let mut tracks = {
        let st = state.tracks.lock().map_err(|e| e.to_string())?;
        st.clone()
    };
    let config = {
        let cfg = state.config.lock().map_err(|e| e.to_string())?;
        let mut c = cfg.clone();
        c.max_offset_s = max_offset_s;
        c
    };

    let app_clone = app.clone();
    let cancel_clone = cancel.clone();

    let result = tokio::task::spawn_blocking(move || {
        let progress: Option<ProgressCallback> =
            Some(Box::new(move |step, total, msg| {
                let _ = app_clone.emit(
                    "analysis-progress",
                    ProgressPayload {
                        step,
                        total,
                        message: msg.to_string(),
                    },
                );
            }));

        engine::analyze(&mut tracks, &config, &progress, &Some(cancel_clone))
            .map(|r| (tracks, r))
    })
    .await
    .map_err(|e| format!("Analysis task failed: {}", e))?
    .map_err(|e| e.to_string())?;

    let (tracks, sync_result) = result;

    // Update state
    let track_infos: Vec<TrackInfo> = tracks.iter().map(TrackInfo::from).collect();
    {
        let mut st = state.tracks.lock().map_err(|e| e.to_string())?;
        *st = tracks;
    }
    {
        let mut sr = state.result.lock().map_err(|e| e.to_string())?;
        *sr = Some(sync_result.clone());
    }

    Ok(AnalysisResult {
        tracks: track_infos,
        result: sync_result,
    })
}

/// Run sync and export — emits "sync-progress" events, returns exported file paths.
#[tauri::command]
pub async fn run_sync_and_export(
    export_config: ExportConfig,
    app: AppHandle,
    state: State<'_, AppState>,
) -> Result<Vec<String>, String> {
    let cancel = new_cancel_token();
    {
        let mut ct = state.cancel_token.lock().map_err(|e| e.to_string())?;
        *ct = Some(cancel.clone());
    }

    let mut tracks = {
        let st = state.tracks.lock().map_err(|e| e.to_string())?;
        st.clone()
    };
    let sync_result = {
        let sr = state.result.lock().map_err(|e| e.to_string())?;
        sr.clone()
            .ok_or_else(|| "No analysis result — run analysis first.".to_string())?
    };

    let mut config = {
        let cfg = state.config.lock().map_err(|e| e.to_string())?;
        cfg.clone()
    };
    config.export_format = export_config.format.clone();
    config.export_bit_depth = export_config.bit_depth;
    config.drift_correction = export_config.drift_correction;

    let output_dir = export_config.output_dir.clone();
    let fcpxml_path = export_config.fcpxml_path.clone();
    let edl_path = export_config.edl_path.clone();
    let format = export_config.format.clone();

    let app_clone = app.clone();
    let cancel_clone = cancel.clone();

    let exported = tokio::task::spawn_blocking(move || -> Result<Vec<String>, String> {
        let progress: Option<ProgressCallback> =
            Some(Box::new(move |step, total, msg| {
                let _ = app_clone.emit(
                    "sync-progress",
                    ProgressPayload {
                        step,
                        total,
                        message: msg.to_string(),
                    },
                );
            }));

        // Run sync (stitch)
        engine::sync(
            &mut tracks,
            &sync_result,
            &mut config,
            &progress,
            &Some(cancel_clone),
        )
        .map_err(|e| e.to_string())?;

        // Create output directory
        std::fs::create_dir_all(&output_dir).map_err(|e| e.to_string())?;

        let export_sr = config.export_sr.unwrap_or(48000);
        let mut files: Vec<String> = Vec::new();

        for track in &tracks {
            let filename = format!(
                "{}_{}.{}",
                sanitize_filename(&track.name),
                export_sr,
                format,
            );
            let out_path = Path::new(&output_dir).join(&filename);
            let out_str = out_path.to_string_lossy().to_string();
            export_track(track, &out_str, &config).map_err(|e| e.to_string())?;
            files.push(out_str);
        }

        // Export FCPXML if requested
        if let Some(ref path) = fcpxml_path {
            timeline_export::export_fcpxml(&tracks, &sync_result, path, None)
                .map_err(|e| e.to_string())?;
        }

        // Export EDL if requested
        if let Some(ref path) = edl_path {
            timeline_export::export_edl(&tracks, &sync_result, path, None)
                .map_err(|e| e.to_string())?;
        }

        Ok(files)
    })
    .await
    .map_err(|e| format!("Sync task failed: {}", e))?
    .map_err(|e| e.to_string())?;

    Ok(exported)
}

/// Measure drift between two files.
#[tauri::command]
pub async fn measure_drift(
    reference_path: String,
    target_path: String,
) -> Result<DriftResult, String> {
    tokio::task::spawn_blocking(move || {
        let ref_clip = load_clip(&reference_path, &None).map_err(|e| e.to_string())?;
        let mut tgt_clip = load_clip(&target_path, &None).map_err(|e| e.to_string())?;

        let (delay, conf) = engine::compute_delay(
            &ref_clip.samples,
            &tgt_clip.samples,
            ANALYSIS_SR,
            None,
        );

        tgt_clip.timeline_offset_samples = delay;
        tgt_clip.timeline_offset_s = delay as f64 / ANALYSIS_SR as f64;
        tgt_clip.confidence = conf;
        tgt_clip.analyzed = true;

        let (drift_ppm, r_sq) =
            engine::measure_drift(&ref_clip.samples, &tgt_clip, ANALYSIS_SR);

        Ok(DriftResult {
            delay_samples: delay,
            delay_s: tgt_clip.timeline_offset_s,
            confidence: conf,
            drift_ppm,
            drift_r_squared: r_sq,
            drift_significant: drift_ppm.abs() > 0.3 && r_sq > 0.5,
        })
    })
    .await
    .map_err(|e| format!("Drift measurement failed: {}", e))?
}

/// Cancel a running operation.
#[tauri::command]
pub fn cancel_operation(state: State<'_, AppState>) -> Result<(), String> {
    let ct = state.cancel_token.lock().map_err(|e| e.to_string())?;
    if let Some(ref token) = *ct {
        token.store(true, std::sync::atomic::Ordering::Relaxed);
    }
    Ok(())
}

/// Save the current project to a file.
#[tauri::command]
pub fn save_project(path: String, state: State<'_, AppState>) -> Result<(), String> {
    let tracks = state.tracks.lock().map_err(|e| e.to_string())?;
    let config = state.config.lock().map_err(|e| e.to_string())?;
    let result = state.result.lock().map_err(|e| e.to_string())?;

    project_io::save_project(&path, &tracks, &config, result.as_ref())
        .map_err(|e| e.to_string())
}

/// Load a project from a file — replaces current state.
#[tauri::command]
pub fn load_project(path: String, state: State<'_, AppState>) -> Result<AnalysisResult, String> {
    let project =
        project_io::load_project(&path).map_err(|e| e.to_string())?;

    let track_infos: Vec<TrackInfo> = project.tracks.iter().map(TrackInfo::from).collect();

    {
        let mut st = state.tracks.lock().map_err(|e| e.to_string())?;
        *st = project.tracks;
    }
    {
        let mut cfg = state.config.lock().map_err(|e| e.to_string())?;
        *cfg = project.config;
    }
    {
        let mut sr = state.result.lock().map_err(|e| e.to_string())?;
        *sr = project.result.clone();
    }

    Ok(AnalysisResult {
        tracks: track_infos,
        result: project.result.unwrap_or(SyncResult {
            reference_track_index: 0,
            total_timeline_samples: 0,
            total_timeline_s: 0.0,
            sample_rate: ANALYSIS_SR,
            clip_offsets: std::collections::HashMap::new(),
            avg_confidence: 0.0,
            drift_detected: false,
            warnings: Vec::new(),
        }),
    })
}

/// Update the sync configuration.
#[tauri::command]
pub fn update_config(
    config: SyncConfig,
    state: State<'_, AppState>,
) -> Result<(), String> {
    let mut cfg = state.config.lock().map_err(|e| e.to_string())?;
    *cfg = config;
    Ok(())
}

/// Get file grouping info (for preview before full import).
#[tauri::command]
pub fn get_file_groups(paths: Vec<String>) -> BTreeMap<String, Vec<String>> {
    let supported: Vec<String> = paths
        .into_iter()
        .filter(|p| is_supported_file(p))
        .collect();
    group_files_by_device(&supported)
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

/// Downsample audio samples to N peaks (max absolute value per bucket).
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
        let end = ((i + 1) as f64 * bucket_size) as usize;
        let end = end.min(samples.len());
        let peak = samples[start..end]
            .iter()
            .map(|s| s.abs())
            .fold(0.0f32, f32::max);
        peaks.push(peak);
    }

    peaks
}

fn sanitize_filename(name: &str) -> String {
    name.chars()
        .map(|c| {
            if c.is_alphanumeric() || c == '_' || c == '-' || c == '.' {
                c
            } else {
                '_'
            }
        })
        .collect()
}
