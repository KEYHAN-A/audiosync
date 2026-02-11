//! Audio I/O — load audio/video files, export aligned tracks.
//!
//! Performance strategy (same as Python version):
//! - On import: extract an 8 kHz mono analysis copy (tiny in memory).
//! - During analysis: only 8 kHz data lives in RAM.
//! - On export: re-read original files at full resolution, one clip at a time.

use anyhow::{anyhow, Context, Result};
use log::{debug, info};
use rubato::{FftFixedIn, Resampler};
use std::path::Path;
use std::process::Command;

use crate::metadata::{probe_audio_info, probe_creation_time};
use crate::models::{
    CancelToken, Clip, SyncConfig, Track, ANALYSIS_SR,
    check_cancelled,
};

// ---------------------------------------------------------------------------
//  File type detection
// ---------------------------------------------------------------------------

pub const AUDIO_EXTENSIONS: &[&str] = &[
    ".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg", ".opus",
];

pub const VIDEO_EXTENSIONS: &[&str] = &[
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".mts", ".m4v", ".mxf",
];

pub fn is_audio_file(path: &str) -> bool {
    let ext = Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_lowercase()))
        .unwrap_or_default();
    AUDIO_EXTENSIONS.contains(&ext.as_str())
}

pub fn is_video_file(path: &str) -> bool {
    let ext = Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_lowercase()))
        .unwrap_or_default();
    VIDEO_EXTENSIONS.contains(&ext.as_str())
}

pub fn is_supported_file(path: &str) -> bool {
    is_audio_file(path) || is_video_file(path)
}

// ---------------------------------------------------------------------------
//  ffmpeg helpers
// ---------------------------------------------------------------------------

fn find_ffmpeg() -> Result<String> {
    // Check common paths on macOS
    for path in &[
        "ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ] {
        if which_exists(path) {
            return Ok(path.to_string());
        }
    }
    Err(anyhow!(
        "ffmpeg not found in PATH. Install ffmpeg:\n\
         macOS:   brew install ffmpeg\n\
         Linux:   sudo apt install ffmpeg\n\
         Windows: https://ffmpeg.org/download.html"
    ))
}

fn which_exists(cmd: &str) -> bool {
    Command::new("which")
        .arg(cmd)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

/// Extract audio from video to mono WAV at the given sample rate using ffmpeg.
fn extract_audio_from_video(
    video_path: &str,
    output_wav: &str,
    sample_rate: u32,
    cancel: &Option<CancelToken>,
) -> Result<()> {
    let ffmpeg = find_ffmpeg()?;
    let output = Command::new(&ffmpeg)
        .args([
            "-y",
            "-i", video_path,
            "-vn",
            "-ac", "1",
            "-ar", &sample_rate.to_string(),
            "-acodec", "pcm_s16le",
            output_wav,
        ])
        .output()
        .context("Failed to run ffmpeg")?;

    check_cancelled(cancel).map_err(|e| anyhow!(e.to_string()))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let error_lines: Vec<&str> = stderr
            .lines()
            .filter(|l| {
                !l.starts_with("ffmpeg version")
                    && !l.starts_with("  built with")
                    && !l.starts_with("  configuration:")
                    && !l.starts_with("  libav")
                    && !l.starts_with("  libsw")
                    && !l.starts_with("  libpost")
            })
            .collect();
        let msg = if error_lines.is_empty() {
            stderr.chars().take(500).collect()
        } else {
            error_lines.iter().rev().take(20).rev().cloned().collect::<Vec<_>>().join("\n")
        };
        return Err(anyhow!("ffmpeg failed for {}:\n{}", video_path, msg));
    }

    Ok(())
}

/// Extract full-quality audio from video for export.
fn extract_audio_full_quality(
    video_path: &str,
    output_wav: &str,
    target_sr: u32,
    cancel: &Option<CancelToken>,
) -> Result<()> {
    let ffmpeg = find_ffmpeg()?;

    // Try 24-bit first, fall back to 16-bit
    let sr_str = target_sr.to_string();
    let attempts = vec![
        vec!["-y", "-i", video_path, "-vn", "-ar", sr_str.as_str(),
             "-acodec", "pcm_s24le", "-f", "wav", output_wav],
        vec!["-y", "-i", video_path, "-vn", "-ar", sr_str.as_str(),
             "-acodec", "pcm_s16le", "-f", "wav", output_wav],
    ];

    let mut last_error = String::new();
    for args in &attempts {
        let args_owned: Vec<String> = args.iter().map(|s| s.to_string()).collect();
        let output = Command::new(&ffmpeg)
            .args(&args_owned)
            .output()
            .context("Failed to run ffmpeg")?;

        check_cancelled(cancel).map_err(|e| anyhow!(e.to_string()))?;

        if output.status.success() && Path::new(output_wav).exists() {
            return Ok(());
        }

        last_error = String::from_utf8_lossy(&output.stderr).to_string();
        let _ = std::fs::remove_file(output_wav);
    }

    Err(anyhow!("ffmpeg export failed for {}:\n{}", video_path, last_error))
}

// ---------------------------------------------------------------------------
//  Audio loading via symphonia
// ---------------------------------------------------------------------------

/// Load an audio file and return (interleaved_samples, sample_rate, channels).
fn load_audio_symphonia(path: &str) -> Result<(Vec<f32>, u32, u32)> {
    use symphonia::core::audio::Signal;
    use symphonia::core::codecs::DecoderOptions;
    use symphonia::core::formats::FormatOptions;
    use symphonia::core::io::MediaSourceStream;
    use symphonia::core::meta::MetadataOptions;
    use symphonia::core::probe::Hint;

    let file = std::fs::File::open(path)
        .with_context(|| format!("Cannot open file: {}", path))?;
    let mss = MediaSourceStream::new(Box::new(file), Default::default());

    let mut hint = Hint::new();
    if let Some(ext) = Path::new(path).extension().and_then(|e| e.to_str()) {
        hint.with_extension(ext);
    }

    let probed = symphonia::default::get_probe()
        .format(&hint, mss, &FormatOptions::default(), &MetadataOptions::default())
        .with_context(|| format!("Cannot probe format: {}", path))?;

    let mut format = probed.format;
    let track = format
        .default_track()
        .ok_or_else(|| anyhow!("No audio track in {}", path))?;
    let codec_params = track.codec_params.clone();
    let sample_rate = codec_params.sample_rate.unwrap_or(48000);
    let channels = codec_params
        .channels
        .map(|c| c.count() as u32)
        .unwrap_or(2);
    let track_id = track.id;

    let mut decoder = symphonia::default::get_codecs()
        .make(&codec_params, &DecoderOptions::default())
        .with_context(|| format!("Cannot create decoder for {}", path))?;

    let mut all_samples: Vec<f32> = Vec::new();

    loop {
        match format.next_packet() {
            Ok(packet) => {
                if packet.track_id() != track_id {
                    continue;
                }
                match decoder.decode(&packet) {
                    Ok(buf) => {
                        let ch = buf.spec().channels.count();
                        let frames = buf.frames();
                        match buf {
                            symphonia::core::audio::AudioBufferRef::F32(ref b) => {
                                for frame in 0..frames {
                                    for c in 0..ch {
                                        all_samples.push(b.chan(c)[frame]);
                                    }
                                }
                            }
                            symphonia::core::audio::AudioBufferRef::S32(ref b) => {
                                let scale = 1.0 / i32::MAX as f32;
                                for frame in 0..frames {
                                    for c in 0..ch {
                                        all_samples.push(b.chan(c)[frame] as f32 * scale);
                                    }
                                }
                            }
                            symphonia::core::audio::AudioBufferRef::S16(ref b) => {
                                let scale = 1.0 / i16::MAX as f32;
                                for frame in 0..frames {
                                    for c in 0..ch {
                                        all_samples.push(b.chan(c)[frame] as f32 * scale);
                                    }
                                }
                            }
                            symphonia::core::audio::AudioBufferRef::U8(ref b) => {
                                for frame in 0..frames {
                                    for c in 0..ch {
                                        all_samples
                                            .push((b.chan(c)[frame] as f32 - 128.0) / 128.0);
                                    }
                                }
                            }
                            _ => {
                                // For other formats, try to use the generic conversion
                                debug!("Unsupported sample format, skipping packet");
                            }
                        }
                    }
                    Err(symphonia::core::errors::Error::DecodeError(msg)) => {
                        debug!("Decode error (skipping): {}", msg);
                        continue;
                    }
                    Err(e) => return Err(anyhow!("Decode error in {}: {}", path, e)),
                }
            }
            Err(symphonia::core::errors::Error::IoError(ref e))
                if e.kind() == std::io::ErrorKind::UnexpectedEof =>
            {
                break;
            }
            Err(e) => {
                debug!("Format read ended: {}", e);
                break;
            }
        }
    }

    Ok((all_samples, sample_rate, channels))
}

/// Load a WAV file at a specific path (used for cached/extracted audio).
fn load_wav_file(path: &str) -> Result<(Vec<f32>, u32, u32)> {
    let reader = hound::WavReader::open(path)
        .with_context(|| format!("Cannot open WAV: {}", path))?;
    let spec = reader.spec();
    let sample_rate = spec.sample_rate;
    let channels = spec.channels as u32;

    let samples: Vec<f32> = match spec.sample_format {
        hound::SampleFormat::Float => reader
            .into_samples::<f32>()
            .filter_map(|s| s.ok())
            .collect(),
        hound::SampleFormat::Int => {
            let bits = spec.bits_per_sample;
            let max_val = (1u32 << (bits - 1)) as f32;
            reader
                .into_samples::<i32>()
                .filter_map(|s| s.ok())
                .map(|s| s as f32 / max_val)
                .collect()
        }
    };

    Ok((samples, sample_rate, channels))
}

// ---------------------------------------------------------------------------
//  Resampling
// ---------------------------------------------------------------------------

/// Resample mono audio from source_sr to target_sr using rubato.
fn resample_mono(data: &[f32], source_sr: u32, target_sr: u32) -> Result<Vec<f32>> {
    if source_sr == target_sr {
        return Ok(data.to_vec());
    }

    let ratio = target_sr as f64 / source_sr as f64;
    let chunk_size = 1024;

    let mut resampler = FftFixedIn::<f32>::new(
        source_sr as usize,
        target_sr as usize,
        chunk_size,
        2, // sub_chunks
        1, // channels
    )
    .context("Failed to create resampler")?;

    let mut output = Vec::with_capacity((data.len() as f64 * ratio * 1.1) as usize);
    let mut pos = 0;

    while pos < data.len() {
        let end = (pos + chunk_size).min(data.len());
        let mut chunk = data[pos..end].to_vec();

        // Pad last chunk if needed
        if chunk.len() < chunk_size {
            chunk.resize(chunk_size, 0.0);
        }

        let input = vec![chunk];
        let resampled = resampler.process(&input, None)?;
        output.extend_from_slice(&resampled[0]);
        pos += chunk_size;
    }

    // Trim to expected length
    let expected_len = (data.len() as f64 * ratio).round() as usize;
    output.truncate(expected_len);

    Ok(output)
}

/// Resample mono f64 audio.
fn resample_mono_f64(data: &[f64], source_sr: u32, target_sr: u32) -> Result<Vec<f64>> {
    if source_sr == target_sr {
        return Ok(data.to_vec());
    }

    // Convert to f32, resample, convert back
    let f32_data: Vec<f32> = data.iter().map(|&x| x as f32).collect();
    let resampled = resample_mono(&f32_data, source_sr, target_sr)?;
    Ok(resampled.iter().map(|&x| x as f64).collect())
}

/// Convert interleaved multi-channel audio to mono by averaging.
fn to_mono(samples: &[f32], channels: u32) -> Vec<f32> {
    if channels <= 1 {
        return samples.to_vec();
    }
    let ch = channels as usize;
    let frames = samples.len() / ch;
    let mut mono = Vec::with_capacity(frames);
    for i in 0..frames {
        let sum: f32 = (0..ch).map(|c| samples[i * ch + c]).sum();
        mono.push(sum / ch as f32);
    }
    mono
}

// ---------------------------------------------------------------------------
//  Public API — Loading
// ---------------------------------------------------------------------------

/// Load an audio or video file as a Clip with 8 kHz mono analysis samples.
pub fn load_clip(path: &str, cancel: &Option<CancelToken>) -> Result<Clip> {
    let path = std::fs::canonicalize(path)
        .unwrap_or_else(|_| std::path::PathBuf::from(path));
    let path_str = path.to_string_lossy().to_string();
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("Unknown")
        .to_string();
    let is_video = is_video_file(&path_str);

    check_cancelled(cancel).map_err(|e| anyhow!(e.to_string()))?;

    let (orig_sr, orig_channels) = if is_video {
        probe_audio_info(&path_str).unwrap_or((48000, 2))
    } else {
        // Try to get info from the file
        probe_audio_info(&path_str).unwrap_or((48000, 2))
    };

    let (raw_samples, file_sr, file_ch) = if is_video {
        // Extract audio from video via ffmpeg to a temp WAV
        let temp_dir = std::env::temp_dir();
        let temp_wav = temp_dir.join(format!("audiosync_{}.wav", uuid::Uuid::new_v4().as_hyphenated()));
        let temp_path = temp_wav.to_string_lossy().to_string();

        extract_audio_from_video(&path_str, &temp_path, ANALYSIS_SR, cancel)?;
        let result = load_wav_file(&temp_path);
        let _ = std::fs::remove_file(&temp_path);
        result?
    } else {
        load_audio_symphonia(&path_str)?
    };

    check_cancelled(cancel).map_err(|e| anyhow!(e.to_string()))?;

    // Convert to mono
    let mono = to_mono(&raw_samples, file_ch);

    // Resample to analysis SR if needed
    let analysis_samples = if file_sr != ANALYSIS_SR {
        resample_mono(&mono, file_sr, ANALYSIS_SR)?
    } else {
        mono
    };

    let duration_s = analysis_samples.len() as f64 / ANALYSIS_SR as f64;
    let creation_time = probe_creation_time(&path_str);

    let mut clip = Clip::new(path_str, name, orig_sr, orig_channels);
    clip.samples = analysis_samples;
    clip.duration_s = duration_s;
    clip.is_video = is_video;
    clip.creation_time = creation_time;

    Ok(clip)
}

/// Re-read a clip's original file at full resolution, resampled to target_sr.
/// Returns mono f64 samples. Used only during export.
pub fn read_clip_full_res(
    clip: &Clip,
    target_sr: u32,
    cancel: &Option<CancelToken>,
) -> Result<Vec<f64>> {
    check_cancelled(cancel).map_err(|e| anyhow!(e.to_string()))?;

    let (raw_samples, file_sr, file_ch) = if clip.is_video {
        let temp_dir = std::env::temp_dir();
        let temp_wav = temp_dir.join(format!("audiosync_full_{}.wav", uuid::Uuid::new_v4().as_hyphenated()));
        let temp_path = temp_wav.to_string_lossy().to_string();

        extract_audio_full_quality(&clip.file_path, &temp_path, target_sr, cancel)?;
        let result = load_wav_file(&temp_path);
        let _ = std::fs::remove_file(&temp_path);
        result?
    } else {
        load_audio_symphonia(&clip.file_path)?
    };

    check_cancelled(cancel).map_err(|e| anyhow!(e.to_string()))?;

    // Convert to mono f64
    let ch = file_ch as usize;
    let frames = raw_samples.len() / ch.max(1);
    let mut mono = Vec::with_capacity(frames);
    for i in 0..frames {
        let sum: f64 = (0..ch).map(|c| raw_samples[i * ch + c] as f64).sum();
        mono.push(sum / ch as f64);
    }

    // Resample to target SR if needed
    if file_sr != target_sr {
        resample_mono_f64(&mono, file_sr, target_sr)
    } else {
        Ok(mono)
    }
}

// ---------------------------------------------------------------------------
//  Public API — Exporting
// ---------------------------------------------------------------------------

/// Export a track's synced audio to disk as WAV.
pub fn export_track(track: &Track, output_path: &str, config: &SyncConfig) -> Result<String> {
    let audio = track
        .synced_audio
        .as_ref()
        .ok_or_else(|| anyhow!("Track '{}' has no synced audio — run sync first", track.name))?;

    let output_path = std::fs::canonicalize(Path::new(output_path).parent().unwrap_or(Path::new(".")))
        .unwrap_or_default()
        .join(Path::new(output_path).file_name().unwrap_or_default());
    let output_str = output_path.to_string_lossy().to_string();

    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let sample_rate = config.export_sr.unwrap_or(48000);

    if config.is_lossy() {
        export_track_via_ffmpeg(audio, &output_str, sample_rate, config)?;
    } else {
        export_track_wav(audio, &output_str, sample_rate, config)?;
    }

    Ok(output_str)
}

fn export_track_wav(
    audio: &[f64],
    output_path: &str,
    sample_rate: u32,
    config: &SyncConfig,
) -> Result<()> {
    let (bits, sample_format) = match config.export_bit_depth {
        16 => (16, hound::SampleFormat::Int),
        32 => (32, hound::SampleFormat::Float),
        _ => (24, hound::SampleFormat::Int),
    };

    let spec = hound::WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: bits,
        sample_format,
    };

    let mut writer = hound::WavWriter::create(output_path, spec)?;

    match config.export_bit_depth {
        16 => {
            let max = i16::MAX as f64;
            for &s in audio {
                let clamped = s.clamp(-1.0, 1.0);
                writer.write_sample((clamped * max) as i16)?;
            }
        }
        32 => {
            for &s in audio {
                writer.write_sample(s.clamp(-1.0, 1.0) as f32)?;
            }
        }
        _ => {
            // 24-bit: write as i32 with 24-bit range
            let max = (1i32 << 23) as f64 - 1.0;
            for &s in audio {
                let clamped = s.clamp(-1.0, 1.0);
                writer.write_sample((clamped * max) as i32)?;
            }
        }
    }

    writer.finalize()?;
    info!("Exported WAV: {}", output_path);
    Ok(())
}

fn export_track_via_ffmpeg(
    audio: &[f64],
    output_path: &str,
    sample_rate: u32,
    config: &SyncConfig,
) -> Result<()> {
    let ffmpeg = find_ffmpeg()?;

    // Write temp WAV
    let temp_dir = std::env::temp_dir();
    let temp_wav = temp_dir.join(format!("audiosync_export_{}.wav", uuid::Uuid::new_v4().as_hyphenated()));
    let temp_path = temp_wav.to_string_lossy().to_string();

    let temp_config = SyncConfig {
        export_bit_depth: 24,
        export_format: "wav".to_string(),
        ..config.clone()
    };
    export_track_wav(audio, &temp_path, sample_rate, &temp_config)?;

    // Convert with ffmpeg
    let format = config.export_format.to_lowercase();
    let mut args = vec![
        "-y".to_string(),
        "-i".to_string(),
        temp_path.clone(),
    ];

    match format.as_str() {
        "mp3" => {
            args.extend_from_slice(&[
                "-codec:a".to_string(),
                "libmp3lame".to_string(),
                "-b:a".to_string(),
                format!("{}k", config.export_bitrate_kbps),
            ]);
        }
        "flac" => {
            args.extend_from_slice(&[
                "-codec:a".to_string(),
                "flac".to_string(),
            ]);
        }
        "aiff" => {
            args.extend_from_slice(&[
                "-codec:a".to_string(),
                "pcm_s24be".to_string(),
                "-f".to_string(),
                "aiff".to_string(),
            ]);
        }
        _ => {}
    }

    args.push(output_path.to_string());

    let output = Command::new(&ffmpeg)
        .args(&args)
        .output()
        .context("Failed to run ffmpeg for export")?;

    let _ = std::fs::remove_file(&temp_path);

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("ffmpeg export failed:\n{}", &stderr[stderr.len().saturating_sub(500)..]));
    }

    info!("Exported {}: {}", format, output_path);
    Ok(())
}

/// Detect the highest original sample rate across all clips.
pub fn detect_project_sample_rate(tracks: &[Track]) -> u32 {
    let mut max_sr = 44100u32;
    for track in tracks {
        for clip in &track.clips {
            if clip.original_sr > max_sr {
                max_sr = clip.original_sr;
            }
        }
    }
    max_sr
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_audio_file() {
        assert!(is_audio_file("test.wav"));
        assert!(is_audio_file("path/to/file.MP3"));
        assert!(is_audio_file("file.flac"));
        assert!(is_audio_file("file.aiff"));
        assert!(!is_audio_file("file.mp4"));
        assert!(!is_audio_file("file.txt"));
        assert!(!is_audio_file(""));
    }

    #[test]
    fn test_is_video_file() {
        assert!(is_video_file("test.mp4"));
        assert!(is_video_file("path/to/file.MOV"));
        assert!(is_video_file("file.mkv"));
        assert!(!is_video_file("file.wav"));
        assert!(!is_video_file("file.txt"));
    }

    #[test]
    fn test_is_supported_file() {
        assert!(is_supported_file("test.wav"));
        assert!(is_supported_file("test.mp4"));
        assert!(!is_supported_file("test.txt"));
        assert!(!is_supported_file("test.pdf"));
    }

    #[test]
    fn test_to_mono_passthrough() {
        let samples = vec![0.5f32, -0.5, 0.3, -0.3];
        let mono = to_mono(&samples, 1);
        assert_eq!(mono.len(), 4);
        assert!((mono[0] - 0.5).abs() < 1e-6);
    }

    #[test]
    fn test_to_mono_stereo() {
        // Interleaved stereo: [L, R, L, R, ...]
        let samples = vec![1.0f32, 0.0, 0.0, 1.0, 0.5, 0.5];
        let mono = to_mono(&samples, 2);
        assert_eq!(mono.len(), 3);
        assert!((mono[0] - 0.5).abs() < 1e-6); // (1.0 + 0.0) / 2
        assert!((mono[1] - 0.5).abs() < 1e-6); // (0.0 + 1.0) / 2
        assert!((mono[2] - 0.5).abs() < 1e-6); // (0.5 + 0.5) / 2
    }

    #[test]
    fn test_detect_project_sample_rate() {
        let mut tracks = vec![Track::new("A".into()), Track::new("B".into())];
        let c1 = Clip::new("a.wav".into(), "a.wav".into(), 48000, 2);
        tracks[0].clips.push(c1);
        let c2 = Clip::new("b.wav".into(), "b.wav".into(), 96000, 2);
        tracks[1].clips.push(c2);
        assert_eq!(detect_project_sample_rate(&tracks), 96000);
    }

    #[test]
    fn test_detect_project_sample_rate_empty() {
        let tracks: Vec<Track> = vec![];
        assert_eq!(detect_project_sample_rate(&tracks), 44100);
    }

    #[test]
    fn test_resample_mono_same_rate() {
        let data = vec![1.0f32, 2.0, 3.0, 4.0];
        let result = resample_mono(&data, 8000, 8000).unwrap();
        assert_eq!(result.len(), data.len());
    }
}
