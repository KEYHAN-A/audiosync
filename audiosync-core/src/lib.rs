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
pub mod engine;
pub mod error;

#[cfg(feature = "audio-io")]
pub mod audio_io;
#[cfg(feature = "audio-io")]
pub mod metadata;
#[cfg(feature = "project")]
pub mod project_io;
#[cfg(feature = "export")]
pub mod timeline_export;
#[cfg(feature = "cloud")]
pub mod cloud;
#[cfg(feature = "logging")]
pub mod logging;
#[cfg(feature = "validation")]
pub mod validation;

// Re-export key types for convenience.
pub use models::*;
pub use error::{AudioSyncError, Result as AudioSyncResult};

#[cfg(feature = "logging")]
pub use logging::{DiagnosticsReport, init_logging, init_cli_logging, init_gui_logging, log_sync_result};

#[cfg(feature = "validation")]
pub use validation::{ValidationResult, MissingFileInfo, RelinkResult, validate_source_files, relink_files, find_missing_files_in_directory};
