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

pub mod models;
pub mod grouping;
pub mod metadata;
pub mod audio_io;
pub mod engine;
pub mod project_io;
pub mod timeline_export;
pub mod cloud;

// Re-export key types for convenience.
pub use models::*;
