//! File validation and relinking utilities.

use crate::{
    error::{AudioSyncError, Result},
    Clip, Track,
};
use std::collections::HashMap;
use std::path::Path;

/// Validation result for a collection of clips.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ValidationResult {
    /// All files exist and are valid
    pub is_valid: bool,
    /// Files that were not found (path → original clip location)
    pub missing_files: Vec<MissingFileInfo>,
    /// Files that exist but may have issues
    pub warnings: Vec<FileWarning>,
}

/// Information about a missing file.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct MissingFileInfo {
    /// Original path from the clip
    pub original_path: String,
    /// Track name
    pub track_name: String,
    /// Clip name
    pub clip_name: String,
    /// Index of the track
    pub track_index: usize,
    /// Index of the clip
    pub clip_index: usize,
}

/// A warning about a file that exists but may have issues.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FileWarning {
    pub path: String,
    pub track_name: String,
    pub clip_name: String,
    pub warning: String,
}

/// Relinking result.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RelinkResult {
    /// Number of files successfully relinked
    pub relinked_count: usize,
    /// Files that still couldn't be found
    pub still_missing: Vec<String>,
    /// Any warnings that occurred during relinking
    pub warnings: Vec<String>,
}

/// Validate all source files in a collection of tracks.
pub fn validate_source_files(tracks: &[Track]) -> ValidationResult {
    let mut missing_files = Vec::new();
    let mut warnings = Vec::new();

    for (ti, track) in tracks.iter().enumerate() {
        for (ci, clip) in track.clips.iter().enumerate() {
            let path = &clip.file_path;

            // Check if file exists
            if !Path::new(path).exists() {
                missing_files.push(MissingFileInfo {
                    original_path: path.clone(),
                    track_name: track.name.clone(),
                    clip_name: clip.name.clone(),
                    track_index: ti,
                    clip_index: ci,
                });
                continue;
            }

            // Check for potential issues
            if let Some(warning) = check_file_for_issues(clip) {
                warnings.push(FileWarning {
                    path: path.clone(),
                    track_name: track.name.clone(),
                    clip_name: clip.name.clone(),
                    warning,
                });
            }
        }
    }

    ValidationResult {
        is_valid: missing_files.is_empty(),
        missing_files,
        warnings,
    }
}

/// Check a file for potential issues.
fn check_file_for_issues(clip: &Clip) -> Option<String> {
    let path = Path::new(&clip.file_path);

    // Check file size
    if let Ok(metadata) = path.metadata() {
        let size_bytes = metadata.len();
        if size_bytes == 0 {
            return Some("File is empty (0 bytes)".to_string());
        }
        if size_bytes < 1024 {
            return Some(format!(
                "File is very small ({} bytes) - may be corrupt",
                size_bytes
            ));
        }
    }

    // Check extension mismatch
    let expected_ext = if clip.is_video {
        vec!["mp4", "mov", "mkv", "avi", "webm", "mts", "m4v", "mxf"]
    } else {
        vec!["wav", "aiff", "aif", "flac", "mp3", "ogg", "opus"]
    };

    if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
        let ext_lower = ext.to_lowercase();
        if !expected_ext.contains(&ext_lower.as_str()) {
            // Not necessarily an error, but worth noting
            return Some(format!(
                "Unexpected extension for {}: .{}",
                if clip.is_video { "video" } else { "audio" },
                ext_lower
            ));
        }
    }

    None
}

/// Relink missing files using a mapping of old paths to new paths.
///
/// # Arguments
/// * `tracks` - Tracks to update (modified in place)
/// * `remapping` - Map from original paths to new paths
///
/// # Returns
/// A relink result with statistics.
pub fn relink_files(
    tracks: &mut [Track],
    remapping: &HashMap<String, String>,
) -> Result<RelinkResult> {
    let mut relinked_count = 0;
    let mut still_missing = Vec::new();
    let mut warnings = Vec::new();

    for track in tracks.iter_mut() {
        for clip in track.clips.iter_mut() {
            if let Some(new_path) = remapping.get(&clip.file_path) {
                // Verify the new path exists
                if Path::new(new_path).exists() {
                    // Update metadata if needed (e.g., if file changed)
                    let old_path = clip.file_path.clone();
                    clip.file_path = new_path.clone();
                    relinked_count += 1;

                    // Warn if file properties might have changed
                    if let Ok(new_metadata) = std::fs::metadata(new_path) {
                        let size_changed = new_metadata.len() != clip.duration_s as u64 * 48000 * 4; // Rough check
                        if size_changed {
                            warnings.push(format!(
                                "File properties may have changed: {} -> {}",
                                old_path, new_path
                            ));
                        }
                    }
                } else {
                    still_missing.push(clip.file_path.clone());
                }
            }
        }
    }

    Ok(RelinkResult {
        relinked_count,
        still_missing,
        warnings,
    })
}

/// Search for missing files in a directory.
///
/// This attempts to find files with the same name in the given directory.
///
/// # Arguments
/// * `missing_files` - List of missing file info
/// * `search_dir` - Directory to search in
///
/// # Returns
/// A map from original paths to found paths.
pub fn find_missing_files_in_directory(
    missing_files: &[MissingFileInfo],
    search_dir: &Path,
) -> Result<HashMap<String, String>> {
    let mut remapping = HashMap::new();

    if !search_dir.is_dir() {
        return Err(AudioSyncError::Other {
            message: format!("Not a directory: {}", search_dir.display()),
            suggestion: "Please select a valid directory to search for missing files.".to_string(),
        });
    }

    // Get all files in the directory recursively
    let mut available_files = Vec::new();
    if let Ok(entries) = std::fs::read_dir(search_dir) {
        for entry in entries.flatten() {
            if let Ok(file_type) = entry.file_type() {
                if file_type.is_file() {
                    if let Some(name) = entry.file_name().to_str() {
                        available_files.push((entry.path(), name.to_lowercase()));
                    }
                }
            }
        }
    }

    // Try to match by filename
    for missing in missing_files {
        let original_name = Path::new(&missing.original_path)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("");

        let original_name_lower = original_name.to_lowercase();

        // Look for exact match first
        let found = available_files
            .iter()
            .find(|(_, name)| name == &original_name_lower);

        if let Some((path, _)) = found {
            remapping.insert(missing.original_path.clone(), path.to_string_lossy().to_string());
        }
    }

    Ok(remapping)
}

/// Validate a single clip and return an error if the file doesn't exist.
pub fn validate_clip_file(clip: &Clip) -> Result<()> {
    if !Path::new(&clip.file_path).exists() {
        Err(AudioSyncError::file_not_found(&clip.file_path))
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_empty_tracks() {
        let tracks = vec![];
        let result = validate_source_files(&tracks);
        assert!(result.is_valid);
        assert!(result.missing_files.is_empty());
    }

    #[test]
    fn test_validate_all_exist() {
        // Create a temporary file for testing
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("audiosync_test_exist.wav");
        std::fs::write(&test_file, b"test").unwrap();

        // Verify the file was created
        assert!(test_file.exists());

        let mut track = Track::new("Test".to_string());
        let test_path = test_file.to_string_lossy().to_string();
        // Clip::new takes (file_path, name, ...) NOT (name, file_path, ...)
        let clip = Clip::new(test_path.clone(), "test.wav".to_string(), 48000, 2);
        track.clips.push(clip);

        let result = validate_source_files(&[track.clone()]);
        if !result.is_valid {
            eprintln!("Missing files: {:?}", result.missing_files);
            eprintln!("Clip path: {}", track.clips[0].file_path);
            eprintln!("File exists: {}", std::path::Path::new(&track.clips[0].file_path).exists());
            eprintln!("Test file path: {}", test_path);
            eprintln!("Test file exists: {}", std::path::Path::new(&test_path).exists());
        }
        assert!(result.is_valid, "Validation should succeed for existing file");

        // Clean up
        let _ = std::fs::remove_file(&test_file);
    }

    #[test]
    fn test_validate_missing_file() {
        let mut track = Track::new("Test".to_string());
        let clip = Clip::new(
            "/nonexistent/path/that/does/not/exist/missing.wav".to_string(),
            "missing.wav".to_string(),
            48000,
            2,
        );
        track.clips.push(clip);

        let result = validate_source_files(&[track]);
        assert!(!result.is_valid);
        assert_eq!(result.missing_files.len(), 1);
        assert_eq!(result.missing_files[0].clip_name, "missing.wav");
        assert_eq!(result.missing_files[0].original_path, "/nonexistent/path/that/does/not/exist/missing.wav");
    }

    #[test]
    fn test_relink_files() {
        // Create a temporary file for testing
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("audiosync_test_relink.wav");
        std::fs::write(&test_file, b"test").unwrap();
        let test_path = test_file.to_string_lossy().to_string();

        let mut track = Track::new("Test".to_string());
        let clip1 = Clip::new(
            "/nonexistent/missing1.wav".to_string(),
            "missing1.wav".to_string(),
            48000,
            2,
        );
        let clip2 = Clip::new(
            "/nonexistent/missing2.wav".to_string(),
            "missing2.wav".to_string(),
            48000,
            2,
        );
        track.clips.push(clip1);
        track.clips.push(clip2);

        let mut remapping = HashMap::new();
        // Relink only the first file
        remapping.insert("/nonexistent/missing1.wav".to_string(), test_path.clone());
        // Try to relink the second file but point to a non-existent path
        remapping.insert("/nonexistent/missing2.wav".to_string(), "/nonexistent/new_path.wav".to_string());

        let mut tracks = vec![track];
        let result = relink_files(&mut tracks, &remapping).unwrap();

        // First file should be relinked successfully
        assert_eq!(result.relinked_count, 1);
        // Second file remapping failed because the new path doesn't exist
        assert_eq!(result.still_missing.len(), 1);
        assert_eq!(tracks[0].clips[0].file_path, test_path);

        // Clean up
        let _ = std::fs::remove_file(&test_file);
    }
}
