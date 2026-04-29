//! Playback — streaming audio chunks for preview.
//!
//! Provides a synced audio buffer that can be queried in chunks
//! for Web Audio API playback in the frontend.

use anyhow::Result;
use crate::audio_io::{detect_project_sample_rate, read_clip_full_res};
use crate::models::*;

/// Manages synced audio for playback. Audio is produced lazily per track
/// by stitching full-resolution clips at their timeline offsets.
pub struct PlaybackBuffer {
    sample_rate: u32,
    total_samples: usize,
    track_audio: Vec<Option<Vec<f64>>>,
}

impl PlaybackBuffer {
    /// Build a playback buffer from analyzed tracks.
    /// Audio is NOT loaded eagerly — tracks start as None and are filled on demand.
    pub fn new(tracks: &[Track], result: &SyncResult) -> Self {
        let sr = detect_project_sample_rate(tracks);
        let total = (result.total_timeline_s * sr as f64).round() as usize;

        Self {
            sample_rate: sr,
            total_samples: total,
            track_audio: vec![None; tracks.len()],
        }
    }

    pub fn sample_rate(&self) -> u32 {
        self.sample_rate
    }

    pub fn duration_s(&self) -> f64 {
        self.total_samples as f64 / self.sample_rate as f64
    }

    pub fn total_samples(&self) -> usize {
        self.total_samples
    }

    pub fn track_count(&self) -> usize {
        self.track_audio.len()
    }

    /// Prepare a single track's audio by stitching clips at full resolution.
    /// Returns true if the track was prepared (or was already prepared).
    pub fn prepare_track(&mut self, track: &Track, result: &SyncResult) -> Result<bool> {
        let sr = self.sample_rate;
        let total_len = self.total_samples;

        if track.clips.is_empty() {
            self.track_audio.push(Some(vec![0.0f64; total_len]));
            return Ok(true);
        }

        let mut output = vec![0.0f64; total_len];

        for clip in &track.clips {
            let audio = read_clip_full_res(clip, sr, &None)?;

            let start = clip.timeline_offset_at_sr(sr).max(0) as usize;
            let end = (start + audio.len()).min(total_len);
            if start >= total_len {
                continue;
            }

            let seg_len = end - start;
            for i in 0..seg_len {
                let existing = output[start + i];
                let new_val = audio[i];
                if existing.abs() > 1e-10 {
                    output[start + i] = (existing + new_val) / 2.0;
                } else {
                    output[start + i] = new_val;
                }
            }
        }

        self.track_audio[0] = Some(output);
        Ok(true)
    }

    /// Prepare all tracks at once.
    pub fn prepare_all(&mut self, tracks: &[Track], result: &SyncResult) -> Result<()> {
        for ti in 0..tracks.len() {
            let sr = self.sample_rate;
            let total_len = self.total_samples;

            if tracks[ti].clips.is_empty() {
                if ti < self.track_audio.len() {
                    self.track_audio[ti] = Some(vec![0.0f64; total_len]);
                }
                continue;
            }

            let mut output = vec![0.0f64; total_len];

            for clip in &tracks[ti].clips {
                let audio = read_clip_full_res(clip, sr, &None)?;

                let start = clip.timeline_offset_at_sr(sr).max(0) as usize;
                let end = (start + audio.len()).min(total_len);
                if start >= total_len {
                    continue;
                }

                let seg_len = end - start;
                for i in 0..seg_len {
                    let existing = output[start + i];
                    let new_val = audio[i];
                    if existing.abs() > 1e-10 {
                        output[start + i] = (existing + new_val) / 2.0;
                    } else {
                        output[start + i] = new_val;
                    }
                }
            }

            if ti < self.track_audio.len() {
                self.track_audio[ti] = Some(output);
            }
        }

        Ok(())
    }

    /// Get a chunk of audio for a specific track.
    /// Returns f32 samples normalized to [-1.0, 1.0] for Web Audio.
    /// Returns silence if the track is not yet prepared.
    pub fn get_chunk(&self, track_index: usize, start_sample: u64, num_samples: u32) -> Vec<f32> {
        let num = num_samples as usize;
        let start = start_sample as usize;

        if track_index >= self.track_audio.len() {
            return vec![0.0f32; num];
        }

        match &self.track_audio[track_index] {
            Some(audio) => {
                let mut chunk = Vec::with_capacity(num);
                for i in 0..num {
                    let idx = start + i;
                    if idx < audio.len() {
                        chunk.push(audio[idx] as f32);
                    } else {
                        chunk.push(0.0);
                    }
                }
                chunk
            }
            None => vec![0.0f32; num],
        }
    }

    /// Check if a specific track has been prepared.
    pub fn is_track_ready(&self, track_index: usize) -> bool {
        track_index < self.track_audio.len() && self.track_audio[track_index].is_some()
    }

    /// Check if all tracks are prepared.
    pub fn all_ready(&self) -> bool {
        self.track_audio.iter().all(|t| t.is_some())
    }
}
