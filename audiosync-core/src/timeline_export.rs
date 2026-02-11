//! Timeline export — FCPXML and EDL generation.
//!
//! Produces industry-standard timeline formats for NLE import
//! (Final Cut Pro, DaVinci Resolve, Premiere Pro, etc.).

use anyhow::Result;
use log::info;
use std::path::Path;

use crate::models::{SyncResult, Track};

// ---------------------------------------------------------------------------
//  FCPXML v1.11 (Final Cut Pro / DaVinci Resolve)
// ---------------------------------------------------------------------------

/// Generate FCPXML v1.11 from analyzed tracks and write to a file.
pub fn export_fcpxml(
    tracks: &[Track],
    result: &SyncResult,
    output_path: &str,
    project_name: Option<&str>,
) -> Result<String> {
    let name = project_name.unwrap_or("AudioSync Pro");
    let timeline_dur = result.total_timeline_s;
    let fps_num = 30000; // 29.97 NDF
    let fps_den = 1001;

    let mut xml = String::new();
    xml.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    xml.push_str("<!DOCTYPE fcpxml>\n");
    xml.push_str("<fcpxml version=\"1.11\">\n");
    xml.push_str("  <resources>\n");

    // Format resource
    xml.push_str(&format!(
        "    <format id=\"r1\" name=\"FFVideoFormatRateUndefined\" \
         frameDuration=\"{}/{}s\" width=\"1920\" height=\"1080\"/>\n",
        fps_den, fps_num
    ));

    // Asset resources for each clip
    let mut asset_id = 1;
    let mut asset_map: Vec<(usize, usize, usize)> = Vec::new(); // (track_idx, clip_idx, asset_id)

    for (ti, track) in tracks.iter().enumerate() {
        for (ci, clip) in track.clips.iter().enumerate() {
            asset_id += 1;
            xml.push_str(&format!(
                "    <asset id=\"r{}\" name=\"{}\" src=\"file://{}\" \
                 start=\"0s\" duration=\"{:.6}s\" hasAudio=\"1\"/>\n",
                asset_id,
                escape_xml(&clip.name),
                escape_xml(&clip.file_path),
                clip.duration_s,
            ));
            asset_map.push((ti, ci, asset_id));
        }
    }

    xml.push_str("  </resources>\n");

    // Library > Event > Project > Sequence
    xml.push_str("  <library>\n");
    xml.push_str(&format!(
        "    <event name=\"{}\">\n",
        escape_xml(name)
    ));
    xml.push_str(&format!(
        "      <project name=\"{}\">\n",
        escape_xml(name)
    ));
    xml.push_str(&format!(
        "        <sequence format=\"r1\" duration=\"{:.6}s\" tcStart=\"0s\" \
         tcFormat=\"NDF\">\n",
        timeline_dur
    ));
    xml.push_str("          <spine>\n");

    // Collect all clips with their lane assignment and asset id
    struct PlacedClip {
        lane: i32,
        offset_s: f64,
        dur_s: f64,
        aid: usize,
        name: String,
    }

    let mut primary_clips: Vec<PlacedClip> = Vec::new();
    let mut connected_clips: Vec<PlacedClip> = Vec::new();

    for (ti, track) in tracks.iter().enumerate() {
        let lane = ti as i32;
        for (ci, clip) in track.clips.iter().enumerate() {
            let aid = asset_map
                .iter()
                .find(|&&(t, c, _)| t == ti && c == ci)
                .map(|&(_, _, a)| a)
                .unwrap_or(2);
            let placed = PlacedClip {
                lane,
                offset_s: clip.timeline_offset_s,
                dur_s: clip.duration_s,
                aid,
                name: clip.name.clone(),
            };
            if lane == 0 {
                primary_clips.push(placed);
            } else {
                connected_clips.push(placed);
            }
        }
    }

    // Sort primary clips by offset
    primary_clips.sort_by(|a, b| {
        a.offset_s
            .partial_cmp(&b.offset_s)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // Build primary storyline with gap elements for DaVinci Resolve compatibility
    let mut cursor = 0.0f64;

    for pc in &primary_clips {
        // Insert a gap if there's dead time before this clip
        if pc.offset_s > cursor + 0.001 {
            let gap_dur = pc.offset_s - cursor;
            xml.push_str(&format!(
                "            <gap name=\"Gap\" offset=\"{:.6}s\" \
                 duration=\"{:.6}s\" start=\"3600s\"/>\n",
                cursor, gap_dur,
            ));
        }
        xml.push_str(&format!(
            "            <asset-clip ref=\"r{}\" name=\"{}\" \
             offset=\"{:.6}s\" duration=\"{:.6}s\" start=\"0s\"/>\n",
            pc.aid,
            escape_xml(&pc.name),
            pc.offset_s,
            pc.dur_s,
        ));
        cursor = pc.offset_s + pc.dur_s;
    }

    // Append a trailing gap to reach the full timeline duration if needed
    if cursor < timeline_dur - 0.001 {
        let gap_dur = timeline_dur - cursor;
        xml.push_str(&format!(
            "            <gap name=\"Gap\" offset=\"{:.6}s\" \
             duration=\"{:.6}s\" start=\"3600s\"/>\n",
            cursor, gap_dur,
        ));
    }

    // Connected clips (lane > 0) — placed with offset and lane attribute
    for cc in &connected_clips {
        xml.push_str(&format!(
            "            <asset-clip ref=\"r{}\" name=\"{}\" \
             offset=\"{:.6}s\" duration=\"{:.6}s\" start=\"0s\" \
             lane=\"{}\"/>\n",
            cc.aid,
            escape_xml(&cc.name),
            cc.offset_s,
            cc.dur_s,
            cc.lane,
        ));
    }

    xml.push_str("          </spine>\n");
    xml.push_str("        </sequence>\n");
    xml.push_str("      </project>\n");
    xml.push_str("    </event>\n");
    xml.push_str("  </library>\n");
    xml.push_str("</fcpxml>\n");

    if let Some(parent) = Path::new(output_path).parent() {
        std::fs::create_dir_all(parent).ok();
    }
    std::fs::write(output_path, &xml)?;
    info!("FCPXML exported: {}", output_path);
    Ok(output_path.to_string())
}

// ---------------------------------------------------------------------------
//  EDL (CMX 3600 format)
// ---------------------------------------------------------------------------

/// Generate a CMX 3600 EDL from analyzed tracks and write to a file.
pub fn export_edl(
    tracks: &[Track],
    _result: &SyncResult,
    output_path: &str,
    title: Option<&str>,
) -> Result<String> {
    let title = title.unwrap_or("AudioSync Pro");
    let fps = 29.97;

    let mut lines: Vec<String> = Vec::new();
    lines.push(format!("TITLE: {}", title));
    lines.push(format!("FCM: NON-DROP FRAME"));
    lines.push(String::new());

    let mut event_num = 1;

    for track in tracks {
        for clip in &track.clips {
            let src_in = "00:00:00:00".to_string();
            let src_out = seconds_to_timecode(clip.duration_s, fps);
            let rec_in = seconds_to_timecode(clip.timeline_offset_s, fps);
            let rec_out = seconds_to_timecode(
                clip.timeline_offset_s + clip.duration_s,
                fps,
            );

            // Event line
            lines.push(format!(
                "{:03}  {} AA/V  C        {} {} {} {}",
                event_num,
                sanitize_edl_reel(&clip.name),
                src_in,
                src_out,
                rec_in,
                rec_out,
            ));

            // Source file comment
            lines.push(format!(
                "* FROM CLIP NAME: {}",
                clip.name,
            ));
            lines.push(format!(
                "* SOURCE FILE: {}",
                clip.file_path,
            ));

            if clip.drift_ppm.abs() > 0.1 {
                lines.push(format!(
                    "* DRIFT: {:.2} ppm (R²={:.3})",
                    clip.drift_ppm, clip.drift_confidence
                ));
            }

            lines.push(String::new());
            event_num += 1;
        }
    }

    let content = lines.join("\n");
    if let Some(parent) = Path::new(output_path).parent() {
        std::fs::create_dir_all(parent).ok();
    }
    std::fs::write(output_path, &content)?;
    info!("EDL exported: {}", output_path);
    Ok(output_path.to_string())
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

fn escape_xml(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn seconds_to_timecode(seconds: f64, fps: f64) -> String {
    let total_frames = (seconds * fps).round() as u64;
    let frames = total_frames % (fps.round() as u64);
    let total_seconds = total_frames / (fps.round() as u64);
    let secs = total_seconds % 60;
    let mins = (total_seconds / 60) % 60;
    let hours = total_seconds / 3600;
    format!("{:02}:{:02}:{:02}:{:02}", hours, mins, secs, frames)
}

fn sanitize_edl_reel(name: &str) -> String {
    // EDL reel names: max 8 chars, alphanumeric + underscore
    let clean: String = name
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == '_')
        .take(8)
        .collect();
    if clean.is_empty() {
        "AX".to_string()
    } else {
        clean
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_timecode() {
        assert_eq!(seconds_to_timecode(0.0, 30.0), "00:00:00:00");
        assert_eq!(seconds_to_timecode(61.5, 30.0), "00:01:01:15");
    }

    #[test]
    fn test_escape_xml() {
        assert_eq!(escape_xml("a<b>c&d"), "a&lt;b&gt;c&amp;d");
    }

    #[test]
    fn test_sanitize_reel() {
        assert_eq!(sanitize_edl_reel("CamA_001.mp4"), "CamA_001");
        assert_eq!(sanitize_edl_reel(""), "AX");
    }
}
