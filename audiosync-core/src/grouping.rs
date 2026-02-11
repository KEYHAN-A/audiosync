//! Auto-grouping — group files by device name prefix.
//!
//! Mirrors `python/core/grouping.py`.

use regex::Regex;
use std::collections::BTreeMap;
use std::path::Path;

/// Group file paths by their device/camera name prefix.
///
/// Algorithm: strip trailing digits then trailing separators from the
/// filename stem to get a "device key".
///
/// # Examples
/// ```
/// use audiosync_core::grouping::group_files_by_device;
///
/// let files = vec![
///     "GH010045.MP4".to_string(),
///     "GH010046.MP4".to_string(),
///     "ZOOM0001.WAV".to_string(),
/// ];
/// let groups = group_files_by_device(&files);
/// assert!(groups.contains_key("GH"));
/// assert!(groups.contains_key("ZOOM"));
/// ```
pub fn group_files_by_device(paths: &[String]) -> BTreeMap<String, Vec<String>> {
    let re = Regex::new(r"[\d]+$").unwrap();
    let mut groups: BTreeMap<String, Vec<String>> = BTreeMap::new();

    for path in paths {
        let stem = Path::new(path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("Import");

        // Strip trailing digits
        let key = re.replace(stem, "").to_string();
        // Strip trailing separators
        let key = key.trim_end_matches(|c: char| c == '_' || c == '-' || c == ' ' || c == '.');
        let key = if key.is_empty() {
            &stem[..stem.len().min(4)]
        } else {
            key
        };

        groups
            .entry(key.to_string())
            .or_default()
            .push(path.clone());
    }

    // Sort files within each group by name
    for files in groups.values_mut() {
        files.sort_by(|a, b| {
            let na = Path::new(a).file_name().unwrap_or_default();
            let nb = Path::new(b).file_name().unwrap_or_default();
            na.to_ascii_lowercase().cmp(&nb.to_ascii_lowercase())
        });
    }

    groups
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_group_gopro_files() {
        let files = vec![
            "GH010045.MP4".to_string(),
            "GH010046.MP4".to_string(),
        ];
        let groups = group_files_by_device(&files);
        assert_eq!(groups.len(), 1);
        assert!(groups.contains_key("GH"));
        assert_eq!(groups["GH"].len(), 2);
    }

    #[test]
    fn test_group_mixed_devices() {
        let files = vec![
            "CamA_001.mp4".to_string(),
            "CamA_002.mp4".to_string(),
            "ZOOM0001.WAV".to_string(),
            "ZOOM0002.WAV".to_string(),
        ];
        let groups = group_files_by_device(&files);
        assert_eq!(groups.len(), 2);
        assert!(groups.contains_key("CamA"));
        assert!(groups.contains_key("ZOOM"));
    }
}
