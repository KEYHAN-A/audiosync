//! AudioSync Engine — metadata-aware analysis with FFT cross-correlation.
//!
//! Algorithm overview (identical to Python version):
//! 1. Sort each track's clips by creation_time.
//! 2. Auto-select reference track (widest time coverage).
//! 3. Build reference timeline from metadata gaps.
//! 4. Cross-correlate non-reference clips (Pass 1).
//! 5. Enhanced timeline retry for low-confidence clips (Pass 2).
//! 6. Metadata fallback for remaining unmatched.
//! 7. Normalize timeline so earliest offset is zero.
//! 8. Clock drift detection via windowed cross-correlation.

use anyhow::{anyhow, Result};
use log::{debug, info, warn};
use rustfft::{num_complex::Complex, FftPlanner};
use std::collections::HashMap;

use crate::audio_io::{detect_project_sample_rate, read_clip_full_res};
use crate::models::*;

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------

/// Full analysis pipeline — runs entirely at 8 kHz.
pub fn analyze(
    tracks: &mut [Track],
    config: &SyncConfig,
    progress: &Option<ProgressCallback>,
    cancel: &Option<CancelToken>,
) -> Result<SyncResult> {
    if tracks.is_empty() {
        return Err(anyhow!("No tracks to analyze."));
    }

    let total_clips: usize = tracks.iter().map(|t| t.clip_count()).sum();
    if total_clips == 0 {
        return Err(anyhow!("No clips loaded in any track."));
    }

    let sr = ANALYSIS_SR;
    let total_steps = total_clips + 4;

    macro_rules! prog {
        ($step:expr, $msg:expr) => {
            if let Some(cb) = progress {
                cb($step, total_steps, $msg);
            }
        };
    }

    // Phase 1: Sort clips
    prog!(0, "Sorting clips by creation time...");
    check_cancelled(cancel)?;
    for track in tracks.iter_mut() {
        track.sort_clips_by_time();
    }

    // Phase 2: Select reference track
    prog!(1, "Selecting reference track...");
    check_cancelled(cancel)?;
    let ref_idx = select_reference_index(tracks);
    tracks[ref_idx].is_reference = true;
    info!(
        "Reference track: '{}' (index {}, {} clips)",
        tracks[ref_idx].name,
        ref_idx,
        tracks[ref_idx].clip_count()
    );

    // Phase 3: Build reference timeline
    prog!(2, &format!("Building timeline from '{}' metadata...", tracks[ref_idx].name));
    check_cancelled(cancel)?;
    let ref_audio = build_reference_from_metadata(&mut tracks[ref_idx], sr)?;
    info!(
        "Reference timeline: {:.1} s ({} samples)",
        ref_audio.len() as f64 / sr as f64,
        ref_audio.len()
    );

    // Phase 4: Cross-correlate non-reference clips (Pass 1)
    let mut warnings: Vec<String> = Vec::new();
    let mut confidences: Vec<f64> = Vec::new();
    let mut clip_offsets: HashMap<String, i64> = HashMap::new();
    let mut placed_clips: Vec<(usize, usize)> = Vec::new(); // (track_idx, clip_idx)
    let mut unplaced_clips: Vec<(usize, usize)> = Vec::new();

    // Record reference clip offsets
    for clip in &tracks[ref_idx].clips {
        clip_offsets.insert(clip.file_path.clone(), clip.timeline_offset_samples);
        confidences.push(clip.confidence);
    }

    let mut step = 2usize;
    for ti in 0..tracks.len() {
        if ti == ref_idx {
            continue;
        }
        for ci in 0..tracks[ti].clips.len() {
            step += 1;
            let clip_name = tracks[ti].clips[ci].name.clone();
            prog!(step, &format!("Pass 1: correlating '{}'...", clip_name));
            check_cancelled(cancel)?;

            let (delay, conf) = compute_delay(
                &ref_audio,
                &tracks[ti].clips[ci].samples,
                sr,
                config.max_offset_s,
            );

            tracks[ti].clips[ci].timeline_offset_samples = delay;
            tracks[ti].clips[ci].timeline_offset_s = delay as f64 / sr as f64;
            tracks[ti].clips[ci].confidence = conf;
            tracks[ti].clips[ci].analyzed = true;

            clip_offsets.insert(tracks[ti].clips[ci].file_path.clone(), delay);
            confidences.push(conf);

            if conf >= CONFIDENCE_THRESHOLD {
                placed_clips.push((ti, ci));
            } else {
                unplaced_clips.push((ti, ci));
                let msg = format!("Low confidence ({:.1}) for '{}'", conf, clip_name);
                warnings.push(msg.clone());
                warn!("{}", msg);
            }
        }
    }

    check_cancelled(cancel)?;

    // Phase 5: Enhanced timeline for unmatched clips (Pass 2)
    if !unplaced_clips.is_empty() {
        prog!(step + 1, "Pass 2: building enhanced timeline...");
        check_cancelled(cancel)?;

        let enhanced = stitch_enhanced_timeline(&ref_audio, tracks, &placed_clips, sr);

        for &(ti, ci) in &unplaced_clips {
            step += 1;
            let clip_name = tracks[ti].clips[ci].name.clone();
            prog!(step, &format!("Pass 2: retrying '{}'...", clip_name));
            check_cancelled(cancel)?;

            let (delay, conf) = compute_delay(
                &enhanced,
                &tracks[ti].clips[ci].samples,
                sr,
                config.max_offset_s,
            );

            if conf > tracks[ti].clips[ci].confidence {
                tracks[ti].clips[ci].timeline_offset_samples = delay;
                tracks[ti].clips[ci].timeline_offset_s = delay as f64 / sr as f64;
                tracks[ti].clips[ci].confidence = conf;
                clip_offsets.insert(tracks[ti].clips[ci].file_path.clone(), delay);

                if conf >= CONFIDENCE_THRESHOLD {
                    info!(
                        "Pass 2 improved '{}': confidence {:.1}",
                        clip_name, conf
                    );
                    warnings.retain(|w| !w.contains(&clip_name));
                }
            }
        }
    }

    check_cancelled(cancel)?;

    // Phase 6: Metadata fallback
    let ref_origin = get_track_time_origin(&tracks[ref_idx]);
    for &(ti, ci) in &unplaced_clips {
        let clip = &tracks[ti].clips[ci];
        if clip.confidence < CONFIDENCE_THRESHOLD {
            if let (Some(ct), Some(origin)) = (clip.creation_time, ref_origin) {
                let time_diff = ct - origin;
                let estimated_offset = (time_diff * sr as f64) as i64;
                if estimated_offset >= 0 {
                    let name = clip.name.clone();
                    let conf = clip.confidence;
                    tracks[ti].clips[ci].timeline_offset_samples = estimated_offset;
                    tracks[ti].clips[ci].timeline_offset_s = estimated_offset as f64 / sr as f64;
                    clip_offsets.insert(
                        tracks[ti].clips[ci].file_path.clone(),
                        estimated_offset,
                    );
                    let msg = format!(
                        "'{}' placed via metadata fallback (confidence {:.1})",
                        name, conf
                    );
                    warnings.push(msg.clone());
                    warn!("{}", msg);
                }
            }
        }
    }

    // Phase 6.5: Enforce non-overlap within each track
    // A single device can only record one clip at a time, so clips from
    // the same track must be sequential — never overlapping.
    check_cancelled(cancel)?;
    for ti in 0..tracks.len() {
        if ti == ref_idx {
            continue;
        }
        fix_intra_track_overlaps(&mut tracks[ti], sr, &mut clip_offsets, &mut warnings);
    }

    // Phase 7: Normalize timeline
    prog!(total_steps - 1, "Normalizing timeline...");
    check_cancelled(cancel)?;

    let mut min_offset: i64 = 0;
    let mut max_end: i64 = 0;
    for track in tracks.iter() {
        for clip in &track.clips {
            min_offset = min_offset.min(clip.timeline_offset_samples);
            max_end = max_end.max(clip.end_samples());
        }
    }

    if min_offset < 0 {
        let shift = -min_offset;
        for track in tracks.iter_mut() {
            for clip in &mut track.clips {
                clip.timeline_offset_samples += shift;
                clip.timeline_offset_s = clip.timeline_offset_samples as f64 / sr as f64;
                clip_offsets.insert(clip.file_path.clone(), clip.timeline_offset_samples);
            }
        }
        max_end += shift;
    }

    let avg_conf = if confidences.is_empty() {
        0.0
    } else {
        confidences.iter().sum::<f64>() / confidences.len() as f64
    };

    // Phase 8: Clock drift detection
    prog!(total_steps - 1, "Measuring clock drift...");
    check_cancelled(cancel)?;

    let ref_audio_norm = build_reference_from_metadata(&mut tracks[ref_idx], sr)?;
    let mut drift_detected = false;

    for ti in 0..tracks.len() {
        if ti == ref_idx {
            continue;
        }
        for ci in 0..tracks[ti].clips.len() {
            if !tracks[ti].clips[ci].analyzed {
                continue;
            }
            if tracks[ti].clips[ci].duration_s < MIN_DRIFT_OVERLAP_S {
                continue;
            }

            let (drift_ppm, r_sq) =
                measure_drift(&ref_audio_norm, &tracks[ti].clips[ci], sr);

            if r_sq > 0.5 && drift_ppm.abs() > config.drift_threshold_ppm {
                tracks[ti].clips[ci].drift_ppm = drift_ppm;
                tracks[ti].clips[ci].drift_confidence = r_sq;
                drift_detected = true;
                info!(
                    "Drift detected for '{}': {:.2} ppm (R²={:.3})",
                    tracks[ti].clips[ci].name, drift_ppm, r_sq
                );
            }
        }
    }

    if drift_detected {
        inherit_drift_for_short_clips(tracks, ref_idx);
    }

    let result = SyncResult {
        reference_track_index: ref_idx,
        total_timeline_samples: max_end,
        total_timeline_s: max_end as f64 / sr as f64,
        sample_rate: sr,
        clip_offsets,
        avg_confidence: avg_conf,
        drift_detected,
        warnings,
    };

    prog!(total_steps, "Analysis complete.");
    info!(
        "Analysis complete: {} clips, timeline {:.1} s, avg confidence {:.1}, drift={}",
        total_clips,
        result.total_timeline_s,
        avg_conf,
        if drift_detected { "detected" } else { "none" }
    );

    Ok(result)
}

/// Stitch each track into a single continuous audio array at export SR.
pub fn sync(
    tracks: &mut [Track],
    result: &SyncResult,
    config: &mut SyncConfig,
    progress: &Option<ProgressCallback>,
    cancel: &Option<CancelToken>,
) -> Result<()> {
    let export_sr = match config.export_sr {
        Some(sr) => sr,
        None => {
            let sr = detect_project_sample_rate(tracks);
            config.export_sr = Some(sr);
            sr
        }
    };

    let total_len = (result.total_timeline_s * export_sr as f64).round() as usize;
    let total_steps: usize = tracks.iter().map(|t| t.clip_count()).sum();
    let mut step = 0usize;

    for ti in 0..tracks.len() {
        check_cancelled(cancel)?;

        if tracks[ti].clips.is_empty() {
            tracks[ti].synced_audio = Some(vec![0.0f64; total_len]);
            tracks[ti].synced_channels = 1;
            continue;
        }

        let mut output = vec![0.0f64; total_len];

        for ci in 0..tracks[ti].clips.len() {
            step += 1;
            let clip_name = tracks[ti].clips[ci].name.clone();
            if let Some(cb) = progress {
                cb(step, total_steps, &format!("Stitching '{}'...", clip_name));
            }
            check_cancelled(cancel)?;

            // Re-read at full resolution
            let mut audio = read_clip_full_res(&tracks[ti].clips[ci], export_sr, cancel)?;

            // Apply drift correction if enabled
            if config.drift_correction
                && tracks[ti].clips[ci].drift_ppm.abs() >= config.drift_threshold_ppm
                && tracks[ti].clips[ci].drift_confidence > 0.5
            {
                if let Some(cb) = progress {
                    cb(
                        step,
                        total_steps,
                        &format!(
                            "Correcting drift ({:+.1} ppm) for '{}'...",
                            tracks[ti].clips[ci].drift_ppm, clip_name
                        ),
                    );
                }
                audio = apply_drift_correction_f64(&audio, tracks[ti].clips[ci].drift_ppm);
                tracks[ti].clips[ci].drift_corrected = true;
                info!(
                    "Applied drift correction {:.2} ppm to '{}'",
                    tracks[ti].clips[ci].drift_ppm, clip_name
                );
            }

            // Convert offset from analysis SR to export SR
            let start = tracks[ti].clips[ci].timeline_offset_at_sr(export_sr).max(0) as usize;
            let end = (start + audio.len()).min(total_len);
            if start >= total_len {
                continue;
            }

            let seg_len = end - start;
            for i in 0..seg_len {
                let existing = output[start + i];
                let new_val = audio[i];
                if existing.abs() > 1e-10 {
                    // Mix where both have audio
                    output[start + i] = (existing + new_val) / 2.0;
                } else {
                    output[start + i] = new_val;
                }
            }
        }

        tracks[ti].synced_audio = Some(output);
        tracks[ti].synced_channels = 1;
    }

    info!("Sync complete: {} tracks stitched at {} Hz", tracks.len(), export_sr);
    Ok(())
}

/// Auto-select reference track index.
pub fn auto_select_reference(tracks: &[Track]) -> usize {
    select_reference_index(tracks)
}

// ---------------------------------------------------------------------------
//  Cross-correlation (operates on 8 kHz data)
// ---------------------------------------------------------------------------

/// FFT cross-correlation to find the delay of `target` relative to `reference`.
pub fn compute_delay(
    reference: &[f32],
    target: &[f32],
    sr: u32,
    max_offset_s: Option<f64>,
) -> (i64, f64) {
    if reference.is_empty() || target.is_empty() {
        return (0, 0.0);
    }

    // Normalize
    let ref_max = reference.iter().map(|x| x.abs()).fold(0.0f32, f32::max);
    let tgt_max = target.iter().map(|x| x.abs()).fold(0.0f32, f32::max);

    let ref_norm: Vec<f32> = if ref_max > 1e-10 {
        reference.iter().map(|x| x / ref_max).collect()
    } else {
        reference.to_vec()
    };
    let tgt_norm: Vec<f32> = if tgt_max > 1e-10 {
        target.iter().map(|x| x / tgt_max).collect()
    } else {
        target.to_vec()
    };

    // FFT cross-correlation (equivalent to fftconvolve(ref, tgt[::-1], mode="full"))
    let correlation = fft_correlate(&ref_norm, &tgt_norm);

    let n = correlation.len();
    let center = target.len() - 1;

    let peak_idx = if let Some(max_s) = max_offset_s {
        let max_samples = (max_s * sr as f64) as usize;
        let lo = center.saturating_sub(max_samples);
        let hi = (center + max_samples + 1).min(n);
        let region = &correlation[lo..hi];
        let local_peak = region
            .iter()
            .enumerate()
            .max_by(|(_, a), (_, b)| a.abs().partial_cmp(&b.abs()).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0);
        local_peak + lo
    } else {
        correlation
            .iter()
            .enumerate()
            .max_by(|(_, a), (_, b)| a.abs().partial_cmp(&b.abs()).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0)
    };

    let delay_samples = peak_idx as i64 - (target.len() as i64 - 1);

    // Confidence: peak / mean ratio
    let abs_corr: Vec<f32> = correlation.iter().map(|x| x.abs()).collect();
    let mean_corr: f64 = abs_corr.iter().map(|&x| x as f64).sum::<f64>() / abs_corr.len() as f64;
    let confidence = abs_corr[peak_idx] as f64 / (mean_corr + 1e-10);

    (delay_samples, confidence)
}

/// FFT-based cross-correlation (equivalent to scipy fftconvolve(a, b[::-1], "full")).
fn fft_correlate(reference: &[f32], target: &[f32]) -> Vec<f32> {
    let n = reference.len() + target.len() - 1;
    let fft_len = n.next_power_of_two();

    let mut planner = FftPlanner::<f32>::new();
    let fft = planner.plan_fft_forward(fft_len);
    let ifft = planner.plan_fft_inverse(fft_len);

    // Pad reference
    let mut ref_c: Vec<Complex<f32>> = reference
        .iter()
        .map(|&x| Complex::new(x, 0.0))
        .collect();
    ref_c.resize(fft_len, Complex::new(0.0, 0.0));

    // Reverse target for correlation (same as fftconvolve(ref, tgt[::-1]))
    let mut tgt_c: Vec<Complex<f32>> = target
        .iter()
        .rev()
        .map(|&x| Complex::new(x, 0.0))
        .collect();
    tgt_c.resize(fft_len, Complex::new(0.0, 0.0));

    // FFT both
    fft.process(&mut ref_c);
    fft.process(&mut tgt_c);

    // Multiply in frequency domain
    let mut result: Vec<Complex<f32>> = ref_c
        .iter()
        .zip(tgt_c.iter())
        .map(|(a, b)| a * b)
        .collect();

    // IFFT
    ifft.process(&mut result);

    // Normalize and extract real part
    let norm = 1.0 / fft_len as f32;
    result.iter().take(n).map(|c| c.re * norm).collect()
}

// ---------------------------------------------------------------------------
//  Clock drift detection
// ---------------------------------------------------------------------------

/// Measure clock drift of a clip relative to the reference timeline.
pub fn measure_drift(
    ref_timeline: &[f32],
    clip: &Clip,
    sr: u32,
) -> (f64, f64) {
    let window_s = 30.0f64;
    let stride_s = 15.0f64;
    let win_samples = (window_s * sr as f64) as usize;
    let stride_samples = (stride_s * sr as f64) as usize;

    let clip_start = clip.timeline_offset_samples;
    let clip_end = clip_start + clip.length_samples() as i64;
    let ref_len = ref_timeline.len() as i64;

    let overlap_start = clip_start.max(0) as usize;
    let overlap_end = clip_end.min(ref_len) as usize;
    let overlap_len = if overlap_end > overlap_start {
        overlap_end - overlap_start
    } else {
        0
    };

    if overlap_len < win_samples * 2 {
        return (0.0, 0.0);
    }

    let mut times: Vec<f64> = Vec::new();
    let mut offsets: Vec<f64> = Vec::new();

    let mut pos = overlap_start;
    while pos + win_samples <= overlap_end {
        let ref_win = &ref_timeline[pos..pos + win_samples];

        let clip_local = pos as i64 - clip_start;
        if clip_local < 0 || (clip_local as usize + win_samples) > clip.length_samples() {
            pos += stride_samples;
            continue;
        }
        let cl = clip_local as usize;
        let clip_win = &clip.samples[cl..cl + win_samples];

        // Skip silent windows
        let ref_energy: f32 = ref_win.iter().map(|x| x.abs()).fold(0.0f32, f32::max);
        let clip_energy: f32 = clip_win.iter().map(|x| x.abs()).fold(0.0f32, f32::max);
        if ref_energy < 1e-6 || clip_energy < 1e-6 {
            pos += stride_samples;
            continue;
        }

        let offset = windowed_offset(ref_win, clip_win);
        let time_s = (pos - overlap_start) as f64 / sr as f64;
        times.push(time_s);
        offsets.push(offset);

        pos += stride_samples;
    }

    if times.len() < MIN_DRIFT_WINDOWS {
        return (0.0, 0.0);
    }

    // Linear regression: offset = slope * time + intercept
    let n = times.len() as f64;
    let sum_t: f64 = times.iter().sum();
    let sum_o: f64 = offsets.iter().sum();
    let sum_tt: f64 = times.iter().map(|t| t * t).sum();
    let sum_to: f64 = times.iter().zip(offsets.iter()).map(|(t, o)| t * o).sum();

    let denom = n * sum_tt - sum_t * sum_t;
    if denom.abs() < 1e-30 {
        return (0.0, 0.0);
    }

    let slope = (n * sum_to - sum_t * sum_o) / denom;
    let intercept = (sum_o - slope * sum_t) / n;

    // R-squared
    let mean_o = sum_o / n;
    let ss_res: f64 = times
        .iter()
        .zip(offsets.iter())
        .map(|(t, o)| {
            let predicted = slope * t + intercept;
            (o - predicted).powi(2)
        })
        .sum();
    let ss_tot: f64 = offsets.iter().map(|o| (o - mean_o).powi(2)).sum();
    let r_squared = (1.0 - ss_res / (ss_tot + 1e-30)).clamp(0.0, 1.0);

    // Convert slope (samples/second at analysis SR) to ppm
    let drift_ppm = (slope / sr as f64) * 1e6;

    (drift_ppm, r_squared)
}

/// Sub-sample cross-correlation offset for a single window pair.
fn windowed_offset(ref_segment: &[f32], clip_segment: &[f32]) -> f64 {
    // Normalize
    let ref_max = ref_segment.iter().map(|x| x.abs()).fold(0.0f32, f32::max);
    let tgt_max = clip_segment.iter().map(|x| x.abs()).fold(0.0f32, f32::max);

    let r: Vec<f32> = if ref_max > 1e-10 {
        ref_segment.iter().map(|x| x / ref_max).collect()
    } else {
        ref_segment.to_vec()
    };
    let t: Vec<f32> = if tgt_max > 1e-10 {
        clip_segment.iter().map(|x| x / tgt_max).collect()
    } else {
        clip_segment.to_vec()
    };

    let corr = fft_correlate(&r, &t);
    let abs_corr: Vec<f32> = corr.iter().map(|x| x.abs()).collect();
    let peak_idx = abs_corr
        .iter()
        .enumerate()
        .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap())
        .map(|(i, _)| i)
        .unwrap_or(0);

    // Sub-sample precision via parabolic interpolation
    let refined = subsample_peak(&abs_corr, peak_idx);
    refined - (t.len() as f64 - 1.0)
}

/// Parabolic interpolation around peak for sub-sample precision.
fn subsample_peak(correlation: &[f32], peak_idx: usize) -> f64 {
    let n = correlation.len();
    if peak_idx == 0 || peak_idx >= n - 1 {
        return peak_idx as f64;
    }

    let alpha = correlation[peak_idx - 1] as f64;
    let beta = correlation[peak_idx] as f64;
    let gamma = correlation[peak_idx + 1] as f64;

    let denom = alpha - 2.0 * beta + gamma;
    if denom.abs() < 1e-30 {
        return peak_idx as f64;
    }

    let adjustment = 0.5 * (alpha - gamma) / denom;
    peak_idx as f64 + adjustment
}

/// Apply drift correction by resampling.
pub fn apply_drift_correction(audio: &[f32], drift_ppm: f64) -> Vec<f32> {
    if drift_ppm.abs() < 1e-6 {
        return audio.to_vec();
    }

    let original_len = audio.len();
    let corrected_len = (original_len as f64 / (1.0 + drift_ppm * 1e-6)).round() as usize;

    if corrected_len == original_len || corrected_len < 1 {
        return audio.to_vec();
    }

    // Simple linear interpolation resampling
    let ratio = original_len as f64 / corrected_len as f64;
    let mut result = Vec::with_capacity(corrected_len);
    for i in 0..corrected_len {
        let pos = i as f64 * ratio;
        let idx = pos as usize;
        let frac = (pos - idx as f64) as f32;
        if idx + 1 < original_len {
            result.push(audio[idx] * (1.0 - frac) + audio[idx + 1] * frac);
        } else if idx < original_len {
            result.push(audio[idx]);
        }
    }
    result
}

fn apply_drift_correction_f64(audio: &[f64], drift_ppm: f64) -> Vec<f64> {
    if drift_ppm.abs() < 1e-6 {
        return audio.to_vec();
    }

    let original_len = audio.len();
    let corrected_len = (original_len as f64 / (1.0 + drift_ppm * 1e-6)).round() as usize;

    if corrected_len == original_len || corrected_len < 1 {
        return audio.to_vec();
    }

    let ratio = original_len as f64 / corrected_len as f64;
    let mut result = Vec::with_capacity(corrected_len);
    for i in 0..corrected_len {
        let pos = i as f64 * ratio;
        let idx = pos as usize;
        let frac = pos - idx as f64;
        if idx + 1 < original_len {
            result.push(audio[idx] * (1.0 - frac) + audio[idx + 1] * frac);
        } else if idx < original_len {
            result.push(audio[idx]);
        }
    }
    result
}

// ---------------------------------------------------------------------------
//  Internal helpers
// ---------------------------------------------------------------------------

fn select_reference_index(tracks: &[Track]) -> usize {
    // Check for user override
    for (i, t) in tracks.iter().enumerate() {
        if t.is_reference {
            return i;
        }
    }

    // Try metadata-based coverage span
    let mut best_idx = 0;
    let mut best_span = 0.0f64;
    for (i, t) in tracks.iter().enumerate() {
        let span = get_coverage_span(t);
        if span > best_span {
            best_span = span;
            best_idx = i;
        }
    }

    // Fallback: longest total duration
    if best_span <= 0.0 {
        let mut best_dur = 0.0f64;
        for (i, t) in tracks.iter().enumerate() {
            let dur = t.total_duration_s();
            if dur > best_dur {
                best_dur = dur;
                best_idx = i;
            }
        }
    }

    best_idx
}

fn get_coverage_span(track: &Track) -> f64 {
    let times: Vec<(f64, f64)> = track
        .clips
        .iter()
        .filter_map(|c| c.creation_time.map(|ct| (ct, c.duration_s)))
        .collect();
    if times.is_empty() {
        return 0.0;
    }
    let earliest = times.iter().map(|(t, _)| *t).fold(f64::INFINITY, f64::min);
    let latest = times.iter().map(|(t, d)| t + d).fold(f64::NEG_INFINITY, f64::max);
    latest - earliest
}

fn get_track_time_origin(track: &Track) -> Option<f64> {
    track
        .clips
        .iter()
        .filter_map(|c| c.creation_time)
        .reduce(f64::min)
}

fn build_reference_from_metadata(track: &mut Track, sr: u32) -> Result<Vec<f32>> {
    let clips = &mut track.clips;
    if clips.is_empty() {
        return Err(anyhow!("Reference track '{}' has no clips.", track.name));
    }

    // Single clip: trivial
    if clips.len() == 1 {
        clips[0].timeline_offset_samples = 0;
        clips[0].timeline_offset_s = 0.0;
        clips[0].confidence = 100.0;
        clips[0].analyzed = true;
        return Ok(clips[0].samples.clone());
    }

    // Place clips using metadata gaps
    clips[0].timeline_offset_samples = 0;
    clips[0].timeline_offset_s = 0.0;
    clips[0].confidence = 100.0;
    clips[0].analyzed = true;

    for i in 1..clips.len() {
        let gap_s = if let (Some(prev_ct), Some(curr_ct)) =
            (clips[i - 1].creation_time, clips[i].creation_time)
        {
            let gap = curr_ct - (prev_ct + clips[i - 1].duration_s);
            gap.max(0.0)
        } else {
            0.5 // No metadata: assume small gap
        };

        let offset = clips[i - 1].timeline_offset_samples
            + clips[i - 1].length_samples() as i64
            + (gap_s * sr as f64) as i64;
        clips[i].timeline_offset_samples = offset;
        clips[i].timeline_offset_s = offset as f64 / sr as f64;
        clips[i].confidence = 100.0;
        clips[i].analyzed = true;
    }

    // Stitch into a single array
    let max_end = clips
        .iter()
        .map(|c| c.end_samples())
        .max()
        .unwrap_or(0) as usize;
    let mut ref_audio = vec![0.0f32; max_end];

    for c in clips.iter() {
        let start = c.timeline_offset_samples as usize;
        let seg_len = c.samples.len().min(max_end.saturating_sub(start));
        for j in 0..seg_len {
            ref_audio[start + j] = c.samples[j];
        }
    }

    Ok(ref_audio)
}

fn stitch_enhanced_timeline(
    ref_audio: &[f32],
    tracks: &[Track],
    placed_clips: &[(usize, usize)],
    _sr: u32,
) -> Vec<f32> {
    if placed_clips.is_empty() {
        return ref_audio.to_vec();
    }

    let mut max_end = ref_audio.len();
    for &(ti, ci) in placed_clips {
        let end = tracks[ti].clips[ci].end_samples() as usize;
        if end > max_end {
            max_end = end;
        }
    }

    let mut enhanced = vec![0.0f32; max_end];
    for (i, &val) in ref_audio.iter().enumerate() {
        enhanced[i] = val;
    }

    for &(ti, ci) in placed_clips {
        let clip = &tracks[ti].clips[ci];
        let start = clip.timeline_offset_samples.max(0) as usize;
        let seg_len = clip.samples.len().min(max_end.saturating_sub(start));
        if seg_len == 0 {
            continue;
        }

        for j in 0..seg_len {
            let existing = enhanced[start + j];
            let new_val = clip.samples[j];
            if existing.abs() < 1e-10 {
                enhanced[start + j] = new_val;
            } else {
                enhanced[start + j] = (existing + new_val) / 2.0;
            }
        }
    }

    enhanced
}

/// Enforce non-overlap constraint within a single track.
///
/// After cross-correlation some clips from the same device may land at
/// overlapping positions, which is physically impossible (a single camera
/// records sequentially).  When overlap is detected the track is
/// re-sequenced using the best-placed clip as an anchor and creation-time
/// gaps for the rest.
fn fix_intra_track_overlaps(
    track: &mut Track,
    sr: u32,
    clip_offsets: &mut HashMap<String, i64>,
    warnings: &mut Vec<String>,
) {
    if track.clips.len() < 2 {
        return;
    }

    // Sort clips by creation_time (then by name as tiebreaker)
    track.sort_clips_by_time();

    // Check for overlaps
    let mut has_overlap = false;
    for i in 0..track.clips.len() - 1 {
        let end_i = track.clips[i].timeline_offset_samples
            + track.clips[i].length_samples() as i64;
        let start_next = track.clips[i + 1].timeline_offset_samples;
        if end_i > start_next {
            has_overlap = true;
            break;
        }
    }

    if !has_overlap {
        return;
    }

    // Find the clip with the best (highest) confidence to use as anchor
    let anchor_idx = track
        .clips
        .iter()
        .enumerate()
        .max_by(|(_, a), (_, b)| {
            a.confidence
                .partial_cmp(&b.confidence)
                .unwrap_or(std::cmp::Ordering::Equal)
        })
        .map(|(i, _)| i)
        .unwrap_or(0);

    let msg = format!(
        "Track '{}': overlap detected — re-sequencing using '{}' as anchor",
        track.name, track.clips[anchor_idx].name
    );
    warnings.push(msg.clone());
    warn!("{}", msg);

    // Re-build offsets: walk forward from anchor, then backward
    // Forward pass: anchor_idx+1 .. end
    for i in (anchor_idx + 1)..track.clips.len() {
        let gap_s = if let (Some(prev_ct), Some(curr_ct)) = (
            track.clips[i - 1].creation_time,
            track.clips[i].creation_time,
        ) {
            let gap = curr_ct - (prev_ct + track.clips[i - 1].duration_s);
            gap.max(0.0)
        } else {
            0.5
        };

        let offset = track.clips[i - 1].timeline_offset_samples
            + track.clips[i - 1].length_samples() as i64
            + (gap_s * sr as f64) as i64;
        track.clips[i].timeline_offset_samples = offset;
        track.clips[i].timeline_offset_s = offset as f64 / sr as f64;
        clip_offsets.insert(track.clips[i].file_path.clone(), offset);
    }

    // Backward pass: anchor_idx-1 .. 0
    for i in (0..anchor_idx).rev() {
        let gap_s = if let (Some(curr_ct), Some(next_ct)) = (
            track.clips[i].creation_time,
            track.clips[i + 1].creation_time,
        ) {
            let gap = next_ct - (curr_ct + track.clips[i].duration_s);
            gap.max(0.0)
        } else {
            0.5
        };

        let offset = track.clips[i + 1].timeline_offset_samples
            - track.clips[i].length_samples() as i64
            - (gap_s * sr as f64) as i64;
        track.clips[i].timeline_offset_samples = offset;
        track.clips[i].timeline_offset_s = offset as f64 / sr as f64;
        clip_offsets.insert(track.clips[i].file_path.clone(), offset);
    }

    info!(
        "Track '{}': re-sequenced {} clips around anchor '{}'",
        track.name,
        track.clips.len(),
        track.clips[anchor_idx].name
    );
}

fn inherit_drift_for_short_clips(tracks: &mut [Track], ref_idx: usize) {
    for ti in 0..tracks.len() {
        if ti == ref_idx {
            continue;
        }

        // Find best measured drift for this track
        let best = tracks[ti]
            .clips
            .iter()
            .filter(|c| c.drift_ppm.abs() > 1e-6 && c.drift_confidence > 0.5)
            .max_by(|a, b| {
                a.drift_confidence
                    .partial_cmp(&b.drift_confidence)
                    .unwrap()
            })
            .map(|c| (c.drift_ppm, c.drift_confidence));

        if let Some((ppm, conf)) = best {
            for clip in &mut tracks[ti].clips {
                if clip.drift_ppm.abs() < 1e-6 && clip.drift_confidence == 0.0 {
                    clip.drift_ppm = ppm;
                    clip.drift_confidence = conf;
                    debug!(
                        "Inherited drift {:.2} ppm for short clip '{}'",
                        ppm, clip.name
                    );
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_delay_identical() {
        // A broadband signal correlated with itself should have delay = 0
        // Use a complex waveform (multiple frequencies) for a sharp correlation peak.
        let signal: Vec<f32> = (0..4000)
            .map(|i| {
                let t = i as f32 / 8000.0;
                (t * 440.0 * std::f32::consts::TAU).sin()
                    + 0.7 * (t * 1200.0 * std::f32::consts::TAU).sin()
                    + 0.3 * (t * 3500.0 * std::f32::consts::TAU).cos()
                    + 0.5 * (t * 780.0 * std::f32::consts::TAU).sin()
            })
            .collect();
        let (delay, conf) = compute_delay(&signal, &signal, 8000, None);
        assert_eq!(delay, 0);
        assert!(conf > 2.0, "Confidence {} should be reasonable for identical signals", conf);
    }

    #[test]
    fn test_compute_delay_shifted() {
        // Create a reference and a delayed copy
        let sr = 8000u32;
        let delay_samples = 400i64; // 50ms at 8kHz
        let len = 4000;

        let reference: Vec<f32> = (0..len + delay_samples as usize)
            .map(|i| (i as f32 * 0.05).sin() + (i as f32 * 0.13).cos() * 0.5)
            .collect();
        let target: Vec<f32> = reference[delay_samples as usize..].to_vec();

        let (detected_delay, conf) = compute_delay(&reference, &target, sr, None);
        assert!(
            (detected_delay - delay_samples).abs() <= 1,
            "Expected delay ~{}, got {}",
            delay_samples,
            detected_delay
        );
        assert!(conf > 3.0, "Confidence should be reasonable");
    }

    #[test]
    fn test_subsample_peak() {
        let data = vec![0.0f32, 0.5, 1.0, 0.8, 0.2];
        let peak = subsample_peak(&data, 2);
        assert!(peak > 1.5 && peak < 2.5, "Subsample peak = {}", peak);
    }

    #[test]
    fn test_compute_delay_empty_reference() {
        let reference: Vec<f32> = vec![];
        let target: Vec<f32> = vec![1.0, 2.0, 3.0];
        let (delay, conf) = compute_delay(&reference, &target, 8000, None);
        assert_eq!(delay, 0);
        assert_eq!(conf, 0.0);
    }

    #[test]
    fn test_compute_delay_empty_target() {
        let reference: Vec<f32> = vec![1.0, 2.0, 3.0];
        let target: Vec<f32> = vec![];
        let (delay, conf) = compute_delay(&reference, &target, 8000, None);
        assert_eq!(delay, 0);
        assert_eq!(conf, 0.0);
    }

    #[test]
    fn test_compute_delay_with_max_offset() {
        let sr = 8000u32;
        let delay_samples = 400i64;
        let len = 4000;

        let reference: Vec<f32> = (0..len + delay_samples as usize)
            .map(|i| (i as f32 * 0.05).sin() + (i as f32 * 0.13).cos() * 0.5)
            .collect();
        let target: Vec<f32> = reference[delay_samples as usize..].to_vec();

        // With sufficient max_offset, should find the delay
        let (detected, _) = compute_delay(&reference, &target, sr, Some(1.0));
        assert!(
            (detected - delay_samples).abs() <= 1,
            "Expected ~{}, got {}",
            delay_samples,
            detected
        );

        // With very small max_offset, might not find the correct delay
        let (detected_limited, _) = compute_delay(&reference, &target, sr, Some(0.01));
        // The result should still be valid (not crash), though may not match
        let _ = detected_limited;
    }

    #[test]
    fn test_compute_delay_negative_delay() {
        // Target starts before reference in the correlation
        let sr = 8000u32;
        let len = 4000;

        let signal: Vec<f32> = (0..len)
            .map(|i| (i as f32 * 0.05).sin() + (i as f32 * 0.13).cos() * 0.5)
            .collect();

        // Reference is a subset that starts later
        let reference = signal[200..].to_vec();
        let target = signal.clone();

        let (delay, _conf) = compute_delay(&reference, &target, sr, None);
        // Delay should be negative (target needs to shift left)
        assert!(delay < 0, "Expected negative delay, got {}", delay);
    }

    #[test]
    fn test_apply_drift_correction_identity() {
        let audio = vec![1.0f32, 2.0, 3.0, 4.0, 5.0];
        let result = apply_drift_correction(&audio, 0.0);
        assert_eq!(result.len(), audio.len());
    }

    #[test]
    fn test_apply_drift_correction_positive() {
        let audio: Vec<f32> = (0..10000).map(|i| (i as f32 * 0.01).sin()).collect();
        let result = apply_drift_correction(&audio, 100.0); // 100 ppm
        // Corrected should be slightly shorter
        assert!(result.len() < audio.len(), "Expected shorter output");
        assert!(result.len() > audio.len() - 10, "Should be close to original length");
    }

    #[test]
    fn test_apply_drift_correction_negative() {
        let audio: Vec<f32> = (0..10000).map(|i| (i as f32 * 0.01).sin()).collect();
        let result = apply_drift_correction(&audio, -100.0); // -100 ppm
        // Corrected should be slightly longer
        assert!(result.len() > audio.len(), "Expected longer output");
        assert!(result.len() < audio.len() + 10, "Should be close to original length");
    }

    #[test]
    fn test_select_reference_index_by_duration() {
        let mut tracks = vec![
            Track::new("Short".into()),
            Track::new("Long".into()),
        ];
        let mut c1 = Clip::new("a.wav".into(), "a.wav".into(), 48000, 1);
        c1.duration_s = 5.0;
        c1.samples = vec![0.0; 40000];
        tracks[0].clips.push(c1);

        let mut c2 = Clip::new("b.wav".into(), "b.wav".into(), 48000, 1);
        c2.duration_s = 60.0;
        c2.samples = vec![0.0; 480000];
        tracks[1].clips.push(c2);

        let idx = select_reference_index(&tracks);
        assert_eq!(idx, 1, "Longer track should be reference");
    }

    #[test]
    fn test_select_reference_user_override() {
        let mut tracks = vec![
            Track::new("Short".into()),
            Track::new("Long".into()),
        ];
        tracks[0].is_reference = true;
        let mut c = Clip::new("a.wav".into(), "a.wav".into(), 48000, 1);
        c.duration_s = 5.0;
        tracks[0].clips.push(c);
        let mut c2 = Clip::new("b.wav".into(), "b.wav".into(), 48000, 1);
        c2.duration_s = 60.0;
        tracks[1].clips.push(c2);

        let idx = select_reference_index(&tracks);
        assert_eq!(idx, 0, "User override should win");
    }

    #[test]
    fn test_analyze_empty_tracks() {
        let mut tracks: Vec<Track> = vec![];
        let config = SyncConfig::default();
        let result = analyze(&mut tracks, &config, &None, &None);
        assert!(result.is_err());
    }

    #[test]
    fn test_analyze_single_track_single_clip() {
        let mut tracks = vec![Track::new("Cam".into())];
        let mut clip = Clip::new("test.wav".into(), "test.wav".into(), 48000, 1);
        clip.duration_s = 2.0;
        clip.samples = (0..16000)
            .map(|i| (i as f32 * 0.05).sin())
            .collect();
        tracks[0].clips.push(clip);

        let config = SyncConfig::default();
        let result = analyze(&mut tracks, &config, &None, &None).unwrap();

        assert_eq!(result.reference_track_index, 0);
        assert!(tracks[0].is_reference);
        assert!(tracks[0].clips[0].analyzed);
        assert_eq!(tracks[0].clips[0].timeline_offset_samples, 0);
    }

    #[test]
    fn test_analyze_two_tracks_synthetic() {
        // Create two tracks with related signals
        let sr = ANALYSIS_SR;
        let len = 32000usize; // 4 seconds at 8kHz
        let delay_samples = 800i64; // 100ms

        let signal: Vec<f32> = (0..len + delay_samples as usize)
            .map(|i| {
                let t = i as f32 / sr as f32;
                (t * 440.0 * std::f32::consts::TAU).sin()
                    + 0.5 * (t * 1100.0 * std::f32::consts::TAU).sin()
                    + 0.3 * (t * 2200.0 * std::f32::consts::TAU).cos()
            })
            .collect();

        let ref_samples = signal.clone();
        let tgt_samples: Vec<f32> = signal[delay_samples as usize..].to_vec();

        let mut tracks = vec![
            Track::new("RefDev".into()),
            Track::new("Target".into()),
        ];

        let mut ref_clip = Clip::new("ref.wav".into(), "ref.wav".into(), 48000, 1);
        ref_clip.duration_s = ref_samples.len() as f64 / sr as f64;
        ref_clip.samples = ref_samples;
        tracks[0].clips.push(ref_clip);

        let mut tgt_clip = Clip::new("tgt.wav".into(), "tgt.wav".into(), 48000, 1);
        tgt_clip.duration_s = tgt_samples.len() as f64 / sr as f64;
        tgt_clip.samples = tgt_samples;
        tracks[1].clips.push(tgt_clip);

        let config = SyncConfig::default();
        let result = analyze(&mut tracks, &config, &None, &None).unwrap();

        // Reference should be track 0 (longer)
        assert_eq!(result.reference_track_index, 0);

        // Target clip should have offset close to delay_samples
        let tgt_offset = tracks[1].clips[0].timeline_offset_samples;
        assert!(
            (tgt_offset - delay_samples).abs() <= 2,
            "Expected offset ~{}, got {}",
            delay_samples,
            tgt_offset
        );

        // Confidence should be reasonable
        assert!(
            tracks[1].clips[0].confidence > 2.0,
            "Confidence {} too low",
            tracks[1].clips[0].confidence
        );
    }

    #[test]
    fn test_analyze_cancellation() {
        let mut tracks = vec![Track::new("Test".into())];
        let mut clip = Clip::new("t.wav".into(), "t.wav".into(), 48000, 1);
        clip.duration_s = 1.0;
        clip.samples = vec![0.0; 8000];
        tracks[0].clips.push(clip);

        let config = SyncConfig::default();
        let cancel = new_cancel_token();
        cancel.store(true, std::sync::atomic::Ordering::Relaxed);

        let result = analyze(&mut tracks, &config, &None, &Some(cancel));
        assert!(result.is_err());
    }

    #[test]
    fn test_fft_correlate_basic() {
        // Simple known case: correlate [1,0,0] with reversed [0,0,1] = convolve [1,0,0] with [1,0,0]
        let a = vec![1.0f32, 0.0, 0.0, 0.0];
        let b = vec![1.0f32, 0.0, 0.0, 0.0];
        let corr = fft_correlate(&a, &b);
        // Full convolution length = 4 + 4 - 1 = 7
        assert_eq!(corr.len(), 7);
        // Peak should be near the center
        let peak_idx = corr
            .iter()
            .enumerate()
            .max_by(|(_, a), (_, b)| a.abs().partial_cmp(&b.abs()).unwrap())
            .map(|(i, _)| i)
            .unwrap();
        // For identical short signals, peak at index = len(b) - 1 = 3
        assert_eq!(peak_idx, 3);
    }

    #[test]
    fn test_subsample_peak_edge_cases() {
        let data = vec![1.0f32]; // Single element
        assert_eq!(subsample_peak(&data, 0), 0.0);

        let data2 = vec![0.5f32, 1.0]; // Peak at end
        assert_eq!(subsample_peak(&data2, 1), 1.0); // No interpolation possible at boundary
    }
}
