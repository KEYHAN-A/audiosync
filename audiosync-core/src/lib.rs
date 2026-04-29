//! AudioSync Core — Multi-device audio/video synchronization engine.
//!
//! This crate provides:
//! - **models**: Data structures (Clip, Track, SyncConfig, SyncResult).
//! - **audio_io**: Audio/video loading via symphonia + ffmpeg, resampling, WAV export.
//! - **engine**: FFT cross-correlation analysis, drift detection, sync stitching.
//! - **grouping**: Auto-group files by device name.
//! - **metadata**: Probe creation timestamps and audio info via ffprobe.
//! - **project_io**: JSON project save/load.
//! - **timeline_export**: FCPXML and EDL generation.
//! - **cloud**: Cloud API client (Phase 3+).
//! - **error**: Structured error types with user-friendly messages.

pub mod models;
pub mod grouping;
pub mod metadata;
pub mod audio_io;
pub mod engine;
pub mod project_io;
pub mod timeline_export;
pub mod cloud;
pub mod error;
pub mod logging;
pub mod validation;
pub mod playback;

// Re-export key types for convenience.
pub use models::*;
pub use error::{AudioSyncError, Result as AudioSyncResult};
pub use logging::{DiagnosticsReport, init_logging, init_cli_logging, init_gui_logging, log_sync_result};
pub use validation::{ValidationResult, MissingFileInfo, RelinkResult, validate_source_files, relink_files, find_missing_files_in_directory};
