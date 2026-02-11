//! AudioSync Pro CLI — headless audio/video synchronization.
//!
//! Usage:
//!     audiosync analyze file1.mp4 file2.wav --json
//!     audiosync sync file1.mp4 file2.wav -o ./output --format wav
//!     audiosync drift -r reference.wav -t target.wav
//!     audiosync info *.mp4 *.wav

use clap::{Parser, Subcommand};
use std::path::Path;
use std::time::Instant;

use audiosync_core::audio_io::{export_track, is_supported_file, load_clip};
use audiosync_core::engine::{analyze, compute_delay, measure_drift, sync};
use audiosync_core::grouping::group_files_by_device;
use audiosync_core::models::*;
use audiosync_core::project_io::save_project;
use audiosync_core::timeline_export::{export_edl, export_fcpxml};

#[derive(Parser)]
#[command(
    name = "audiosync",
    version,
    about = "AudioSync Pro — Multi-device audio/video synchronization CLI",
    long_about = "Sync recordings from multiple cameras, microphones, and recorders \
                  using FFT cross-correlation. Export aligned audio files or use \
                  JSON output for pipeline integration."
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run analysis on audio/video files (no export)
    Analyze {
        /// Audio/video files to analyze
        #[arg(required = true)]
        files: Vec<String>,

        /// Maximum offset in seconds
        #[arg(long)]
        max_offset: Option<f64>,

        /// Output results as JSON to stdout
        #[arg(long)]
        json: bool,

        /// Save project file (.audiosync.json)
        #[arg(long)]
        save: Option<String>,

        /// Export FCPXML timeline
        #[arg(long)]
        fcpxml: Option<String>,

        /// Export EDL timeline
        #[arg(long)]
        edl: Option<String>,

        /// Verbose logging
        #[arg(short, long)]
        verbose: bool,
    },

    /// Analyze, sync, and export aligned audio files
    Sync {
        /// Audio/video files to sync
        #[arg(required = true)]
        files: Vec<String>,

        /// Output directory
        #[arg(short, long, default_value = "./audiosync_output")]
        output_dir: String,

        /// Export format: wav, aiff, flac, mp3
        #[arg(long, default_value = "wav")]
        format: String,

        /// Bit depth: 16, 24, 32
        #[arg(long, default_value = "24")]
        bit_depth: u32,

        /// Maximum offset in seconds
        #[arg(long)]
        max_offset: Option<f64>,

        /// Disable automatic clock drift correction
        #[arg(long)]
        no_drift_correction: bool,

        /// Save project file (.audiosync.json)
        #[arg(long)]
        save: Option<String>,

        /// Export FCPXML timeline
        #[arg(long)]
        fcpxml: Option<String>,

        /// Export EDL timeline
        #[arg(long)]
        edl: Option<String>,

        /// Output results as JSON to stdout
        #[arg(long)]
        json: bool,

        /// Verbose logging
        #[arg(short, long)]
        verbose: bool,
    },

    /// Measure clock drift between two files
    Drift {
        /// Reference audio/video file
        #[arg(short, long)]
        reference: String,

        /// Target audio/video file
        #[arg(short, long)]
        target: String,

        /// Output results as JSON to stdout
        #[arg(long)]
        json: bool,

        /// Verbose logging
        #[arg(short, long)]
        verbose: bool,
    },

    /// Show file info and auto-grouping
    Info {
        /// Audio/video files to inspect
        #[arg(required = true)]
        files: Vec<String>,

        /// Output as JSON to stdout
        #[arg(long)]
        json: bool,

        /// Verbose logging
        #[arg(short, long)]
        verbose: bool,
    },
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    // Set log level
    let verbose = match &cli.command {
        Commands::Analyze { verbose, .. }
        | Commands::Sync { verbose, .. }
        | Commands::Drift { verbose, .. }
        | Commands::Info { verbose, .. } => *verbose,
    };
    let level = if verbose { "debug" } else { "info" };
    // SAFETY: Called before any threads are spawned, at program start.
    unsafe {
        std::env::set_var("RUST_LOG", format!("audiosync={}", level));
    }
    env_logger::init();

    match cli.command {
        Commands::Analyze {
            files,
            max_offset,
            json,
            save,
            fcpxml,
            edl,
            ..
        } => cmd_analyze(files, max_offset, json, save, fcpxml, edl),

        Commands::Sync {
            files,
            output_dir,
            format,
            bit_depth,
            max_offset,
            no_drift_correction,
            save,
            fcpxml,
            edl,
            json,
            ..
        } => cmd_sync(
            files,
            output_dir,
            format,
            bit_depth,
            max_offset,
            no_drift_correction,
            save,
            fcpxml,
            edl,
            json,
        ),

        Commands::Drift {
            reference,
            target,
            json,
            ..
        } => cmd_drift(reference, target, json),

        Commands::Info { files, json, .. } => cmd_info(files, json),
    }
}

// ---------------------------------------------------------------------------
//  Commands
// ---------------------------------------------------------------------------

fn cmd_analyze(
    files: Vec<String>,
    max_offset: Option<f64>,
    json: bool,
    save: Option<String>,
    fcpxml: Option<String>,
    edl: Option<String>,
) -> anyhow::Result<()> {
    let t0 = Instant::now();

    let mut tracks = load_files_into_tracks(&files)?;
    if tracks.is_empty() {
        anyhow::bail!("No supported files found.");
    }

    let config = SyncConfig {
        max_offset_s: max_offset,
        ..Default::default()
    };

    let progress: Option<ProgressCallback> = if !json {
        Some(Box::new(|step, total, msg| {
            eprintln!("[{}/{}] {}", step, total, msg);
        }))
    } else {
        None
    };

    let result = analyze(&mut tracks, &config, &progress, &None)?;
    let elapsed = t0.elapsed().as_secs_f64();

    // Save project if requested
    if let Some(ref path) = save {
        save_project(path, &tracks, &config, Some(&result))?;
        if !json {
            eprintln!("Project saved: {}", path);
        }
    }

    // Export FCPXML
    if let Some(ref path) = fcpxml {
        export_fcpxml(&tracks, &result, path, None)?;
        if !json {
            eprintln!("FCPXML exported: {}", path);
        }
    }

    // Export EDL
    if let Some(ref path) = edl {
        export_edl(&tracks, &result, path, None)?;
        if !json {
            eprintln!("EDL exported: {}", path);
        }
    }

    if json {
        let output = serde_json::json!({
            "result": result,
            "tracks": tracks.iter().map(|t| serde_json::json!({
                "name": t.name,
                "is_reference": t.is_reference,
                "clips": t.clips.iter().map(|c| serde_json::json!({
                    "name": c.name,
                    "file_path": c.file_path,
                    "duration_s": c.duration_s,
                    "offset_s": c.timeline_offset_s,
                    "offset_samples": c.timeline_offset_samples,
                    "confidence": c.confidence,
                    "drift_ppm": c.drift_ppm,
                    "drift_confidence": c.drift_confidence,
                })).collect::<Vec<_>>(),
            })).collect::<Vec<_>>(),
            "elapsed_s": elapsed,
        });
        println!("{}", serde_json::to_string_pretty(&output)?);
    } else {
        print_analysis_report(&tracks, &result, elapsed);
    }

    Ok(())
}

fn cmd_sync(
    files: Vec<String>,
    output_dir: String,
    format: String,
    bit_depth: u32,
    max_offset: Option<f64>,
    no_drift_correction: bool,
    save: Option<String>,
    fcpxml: Option<String>,
    edl: Option<String>,
    json: bool,
) -> anyhow::Result<()> {
    let t0 = Instant::now();

    let mut tracks = load_files_into_tracks(&files)?;
    if tracks.is_empty() {
        anyhow::bail!("No supported files found.");
    }

    let mut config = SyncConfig {
        max_offset_s: max_offset,
        export_format: format.clone(),
        export_bit_depth: bit_depth,
        drift_correction: !no_drift_correction,
        ..Default::default()
    };

    let progress: Option<ProgressCallback> = if !json {
        Some(Box::new(|step, total, msg| {
            eprintln!("[{}/{}] {}", step, total, msg);
        }))
    } else {
        None
    };

    // Phase 1: Analyze
    let result = analyze(&mut tracks, &config, &progress, &None)?;

    // Phase 2: Sync
    sync(&mut tracks, &result, &mut config, &progress, &None)?;

    // Phase 3: Export
    std::fs::create_dir_all(&output_dir)?;
    let export_sr = config.export_sr.unwrap_or(48000);
    let mut exported_files: Vec<String> = Vec::new();

    for track in &tracks {
        let filename = format!(
            "{}_{}.{}",
            sanitize_filename(&track.name),
            export_sr,
            format
        );
        let output_path = Path::new(&output_dir).join(&filename);
        let output_str = output_path.to_string_lossy().to_string();

        if !json {
            eprintln!("Exporting '{}'...", filename);
        }

        export_track(track, &output_str, &config)?;
        exported_files.push(output_str);
    }

    let elapsed = t0.elapsed().as_secs_f64();

    // Save project if requested
    if let Some(ref path) = save {
        save_project(path, &tracks, &config, Some(&result))?;
    }

    // Export FCPXML
    if let Some(ref path) = fcpxml {
        export_fcpxml(&tracks, &result, path, None)?;
    }

    // Export EDL
    if let Some(ref path) = edl {
        export_edl(&tracks, &result, path, None)?;
    }

    if json {
        let output = serde_json::json!({
            "result": result,
            "exported_files": exported_files,
            "elapsed_s": elapsed,
        });
        println!("{}", serde_json::to_string_pretty(&output)?);
    } else {
        print_analysis_report(&tracks, &result, elapsed);
        eprintln!("\nExported {} files to '{}'", exported_files.len(), output_dir);
        for f in &exported_files {
            eprintln!("  {}", f);
        }
    }

    Ok(())
}

fn cmd_drift(reference: String, target: String, json: bool) -> anyhow::Result<()> {
    if !json {
        eprintln!("Loading reference: {}", reference);
    }
    let ref_clip = load_clip(&reference, &None)?;

    if !json {
        eprintln!("Loading target: {}", target);
    }
    let mut tgt_clip = load_clip(&target, &None)?;

    // First find the delay
    let (delay, conf) = compute_delay(
        &ref_clip.samples,
        &tgt_clip.samples,
        ANALYSIS_SR,
        None,
    );

    tgt_clip.timeline_offset_samples = delay;
    tgt_clip.timeline_offset_s = delay as f64 / ANALYSIS_SR as f64;
    tgt_clip.confidence = conf;
    tgt_clip.analyzed = true;

    if !json {
        eprintln!(
            "Delay: {:.3} s ({} samples), confidence: {:.1}",
            tgt_clip.timeline_offset_s,
            delay,
            conf
        );
    }

    // Build reference timeline (just the ref clip at offset 0)
    let ref_timeline = ref_clip.samples.clone();

    // Measure drift
    let (drift_ppm, r_sq) = measure_drift(&ref_timeline, &tgt_clip, ANALYSIS_SR);

    if json {
        let output = serde_json::json!({
            "reference": reference,
            "target": target,
            "delay_samples": delay,
            "delay_s": tgt_clip.timeline_offset_s,
            "confidence": conf,
            "drift_ppm": drift_ppm,
            "drift_r_squared": r_sq,
            "drift_significant": drift_ppm.abs() > 0.3 && r_sq > 0.5,
        });
        println!("{}", serde_json::to_string_pretty(&output)?);
    } else {
        eprintln!("\n--- Drift Measurement ---");
        eprintln!("Drift:       {:+.2} ppm", drift_ppm);
        eprintln!("R-squared:   {:.4}", r_sq);
        if drift_ppm.abs() > 0.3 && r_sq > 0.5 {
            eprintln!("Status:      DRIFT DETECTED — correction recommended");
        } else if r_sq < 0.3 {
            eprintln!("Status:      Measurement inconclusive (low R²)");
        } else {
            eprintln!("Status:      No significant drift");
        }
    }

    Ok(())
}

fn cmd_info(files: Vec<String>, json: bool) -> anyhow::Result<()> {
    let supported: Vec<String> = files
        .into_iter()
        .filter(|f| is_supported_file(f))
        .collect();

    let groups = group_files_by_device(&supported);

    if json {
        let output = serde_json::json!({
            "supported_files": supported.len(),
            "groups": groups,
        });
        println!("{}", serde_json::to_string_pretty(&output)?);
    } else {
        eprintln!("AudioSync Pro — File Info");
        eprintln!(
            "Found {} supported file(s) in {} group(s):\n",
            supported.len(),
            groups.len()
        );
        for (name, paths) in &groups {
            eprintln!("  Track: {} ({} files)", name, paths.len());
            for p in paths {
                let fname = Path::new(p)
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy();
                eprintln!("    {}", fname);
            }
        }
    }

    Ok(())
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

fn load_files_into_tracks(files: &[String]) -> anyhow::Result<Vec<Track>> {
    let supported: Vec<String> = files
        .iter()
        .filter(|f| is_supported_file(f))
        .cloned()
        .collect();

    if supported.is_empty() {
        anyhow::bail!(
            "No supported audio/video files found. \
             Supported: WAV, AIFF, FLAC, MP3, OGG, OPUS, MP4, MOV, MKV, AVI, etc."
        );
    }

    let groups = group_files_by_device(&supported);
    let mut tracks = Vec::new();

    for (device_name, paths) in groups {
        let mut track = Track::new(device_name.clone());
        for path in &paths {
            eprintln!("Loading: {}", Path::new(path).file_name().unwrap_or_default().to_string_lossy());
            match load_clip(path, &None) {
                Ok(clip) => {
                    eprintln!(
                        "  {} — {:.1}s, {} Hz, {} ch",
                        clip.name, clip.duration_s, clip.original_sr, clip.original_channels
                    );
                    track.clips.push(clip);
                }
                Err(e) => {
                    eprintln!("  WARNING: Failed to load {}: {}", path, e);
                }
            }
        }
        if !track.clips.is_empty() {
            tracks.push(track);
        }
    }

    Ok(tracks)
}

fn print_analysis_report(tracks: &[Track], result: &SyncResult, elapsed_s: f64) {
    eprintln!("\n============================");
    eprintln!("  AudioSync Pro — Results");
    eprintln!("============================\n");

    let total_clips: usize = tracks.iter().map(|t| t.clip_count()).sum();
    eprintln!("Tracks:           {}", tracks.len());
    eprintln!("Total clips:      {}", total_clips);
    eprintln!(
        "Timeline:         {:.1} s",
        result.total_timeline_s
    );
    eprintln!("Avg confidence:   {:.1}", result.avg_confidence);
    eprintln!(
        "Drift detected:   {}",
        if result.drift_detected { "YES" } else { "No" }
    );
    eprintln!("Elapsed:          {:.2} s", elapsed_s);

    for track in tracks {
        eprintln!(
            "\n  {} {}",
            if track.is_reference { "[REF]" } else { "     " },
            track.name
        );
        for clip in &track.clips {
            let offset_str = format!("{:+.3}s", clip.timeline_offset_s);
            let conf_str = format!("conf={:.1}", clip.confidence);
            let drift_str = if clip.drift_ppm.abs() > 0.1 {
                format!(", drift={:+.1}ppm", clip.drift_ppm)
            } else {
                String::new()
            };
            eprintln!(
                "    {} — {:.1}s @ {} ({}{})",
                clip.name, clip.duration_s, offset_str, conf_str, drift_str
            );
        }
    }

    if !result.warnings.is_empty() {
        eprintln!("\nWarnings:");
        for w in &result.warnings {
            eprintln!("  ⚠ {}", w);
        }
    }
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
