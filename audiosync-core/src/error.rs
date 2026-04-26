//! AudioSync error types with user-friendly messages and recovery suggestions.

use std::fmt;
use std::path::PathBuf;

/// Main error type for AudioSync operations.
#[derive(Debug, Clone, PartialEq)]
pub enum AudioSyncError {
    /// File not found with suggested fix
    FileNotFound {
        path: String,
        suggestion: String,
    },

    /// Audio file is corrupted or unreadable
    CorruptAudio {
        path: String,
        details: String,
        suggestion: String,
    },

    /// FFmpeg is not installed or not found
    FfmpegMissing {
        install_instructions: String,
    },

    /// Insufficient audio overlap for reliable sync
    InsufficientOverlap {
        required_s: f64,
        actual_s: f64,
        suggestion: String,
    },

    /// Low confidence sync match
    LowConfidenceMatch {
        clip_name: String,
        confidence: f64,
        threshold: f64,
        suggestion: String,
    },

    /// Sample rate conversion error
    SampleRateError {
        from_sr: u32,
        to_sr: u32,
        details: String,
    },

    /// Export operation failed
    ExportFailed {
        path: String,
        reason: String,
        suggestion: String,
    },

    /// Import operation failed
    ImportFailed {
        path: String,
        reason: String,
        suggestion: String,
    },

    /// Project file error
    ProjectError {
        path: String,
        reason: String,
        suggestion: String,
    },

    /// Metadata extraction failed
    MetadataError {
        path: String,
        field: String,
        suggestion: String,
    },

    /// Operation cancelled by user
    Cancelled,

    /// Generic error with context
    Other {
        message: String,
        suggestion: String,
    },
}

impl AudioSyncError {
    /// Returns a user-friendly error message.
    pub fn message(&self) -> String {
        match self {
            AudioSyncError::FileNotFound { path, .. } => {
                format!("File not found: {}", path)
            }
            AudioSyncError::CorruptAudio { path, details, .. } => {
                format!("Corrupt audio file: {} — {}", path, details)
            }
            AudioSyncError::FfmpegMissing { .. } => {
                "FFmpeg is not installed or not found in PATH".to_string()
            }
            AudioSyncError::InsufficientOverlap { required_s, actual_s, .. } => {
                format!(
                    "Insufficient audio overlap: {:.1}s required, only {:.1}s available",
                    required_s, actual_s
                )
            }
            AudioSyncError::LowConfidenceMatch { clip_name, confidence, threshold, .. } => {
                format!(
                    "Low confidence match for '{}': {:.1} (threshold: {:.1})",
                    clip_name, confidence, threshold
                )
            }
            AudioSyncError::SampleRateError { from_sr, to_sr, details } => {
                format!(
                    "Sample rate conversion failed: {} Hz → {} Hz — {}",
                    from_sr, to_sr, details
                )
            }
            AudioSyncError::ExportFailed { path, reason, .. } => {
                format!("Export failed: {} — {}", path, reason)
            }
            AudioSyncError::ImportFailed { path, reason, .. } => {
                format!("Import failed: {} — {}", path, reason)
            }
            AudioSyncError::ProjectError { path, reason, .. } => {
                format!("Project error: {} — {}", path, reason)
            }
            AudioSyncError::MetadataError { path, field, .. } => {
                format!("Metadata error reading {} from {}", field, path)
            }
            AudioSyncError::Cancelled => "Operation cancelled".to_string(),
            AudioSyncError::Other { message, .. } => message.clone(),
        }
    }

    /// Returns a suggestion for fixing the error.
    pub fn suggestion(&self) -> Option<String> {
        match self {
            AudioSyncError::FileNotFound { suggestion, .. }
            | AudioSyncError::CorruptAudio { suggestion, .. }
            | AudioSyncError::InsufficientOverlap { suggestion, .. }
            | AudioSyncError::LowConfidenceMatch { suggestion, .. }
            | AudioSyncError::ExportFailed { suggestion, .. }
            | AudioSyncError::ImportFailed { suggestion, .. }
            | AudioSyncError::ProjectError { suggestion, .. }
            | AudioSyncError::MetadataError { suggestion, .. }
            | AudioSyncError::Other { suggestion, .. } => Some(suggestion.clone()),
            AudioSyncError::FfmpegMissing {
                install_instructions, ..
            } => Some(install_instructions.clone()),
            AudioSyncError::SampleRateError { .. } => {
                Some("Try exporting at the original sample rate or using a different format".to_string())
            }
            AudioSyncError::Cancelled => None,
        }
    }

    /// Create a file not found error with platform-specific suggestion.
    pub fn file_not_found(path: impl Into<String>) -> Self {
        let path = path.into();
        let suggestion = if cfg!(target_os = "windows") {
            format!("Check the file path and try again. If the file is on a network drive, ensure it's connected.")
        } else if cfg!(target_os = "macos") {
            format!("Check the file path. If the file is on an external drive, ensure it's mounted.")
        } else {
            format!("Check the file path and permissions. Use 'ls -la {}' to verify.", path)
        };
        AudioSyncError::FileNotFound { path, suggestion }
    }

    /// Create an FFmpeg missing error with platform-specific instructions.
    pub fn ffmpeg_missing() -> Self {
        let install_instructions = if cfg!(target_os = "macos") {
            "Install FFmpeg: brew install ffmpeg".to_string()
        } else if cfg!(target_os = "windows") {
            "Download FFmpeg from https://ffmpeg.org/download.html and add it to your PATH".to_string()
        } else if cfg!(target_os = "linux") {
            "Install FFmpeg:\n  sudo apt install ffmpeg  # Ubuntu/Debian\n  sudo dnf install ffmpeg  # Fedora\n  sudo pacman -S ffmpeg  # Arch".to_string()
        } else {
            "Install FFmpeg from https://ffmpeg.org/download.html".to_string()
        };
        AudioSyncError::FfmpegMissing {
            install_instructions,
        }
    }

    /// Create a corrupt audio error.
    pub fn corrupt_audio(path: impl Into<String>, details: impl Into<String>) -> Self {
        let path = path.into();
        let details = details.into();
        let suggestion = format!(
            "Try re-exporting the file from its original source. \
            If this is a video file, try extracting the audio with FFmpeg directly:\n  \
            ffmpeg -i \"{}\" -vn -acodec pcm_s16le temp.wav",
            path
        );
        AudioSyncError::CorruptAudio {
            path,
            details,
            suggestion,
        }
    }

    /// Create an insufficient overlap error.
    pub fn insufficient_overlap(required_s: f64, actual_s: f64) -> Self {
        let suggestion = if actual_s < 5.0 {
            format!(
                "The clips are too short to reliably sync. Try using longer clips, \
                or use the metadata fallback if available."
            )
        } else {
            format!(
                "Ensure the devices were recording at the same time. \
                You can adjust the maximum offset search with --max-offset."
            )
        };
        AudioSyncError::InsufficientOverlap {
            required_s,
            actual_s,
            suggestion,
        }
    }

    /// Create a low confidence match error.
    pub fn low_confidence(clip_name: impl Into<String>, confidence: f64, threshold: f64) -> Self {
        let clip_name = clip_name.into();
        let suggestion = format!(
            "The sync quality for '{}' is below the acceptable threshold. \
            This can happen with:\n  • Very quiet or noisy audio\n  • Different microphones \
            recording the same event\n  • Devices not recording at the same time\n\n\
            You can:\n  • Lower the confidence threshold (advanced)\n  • \
            Use manual adjustment to fine-tune the position\n  • Trust the metadata \
            offset if available",
            clip_name
        );
        AudioSyncError::LowConfidenceMatch {
            clip_name,
            confidence,
            threshold,
            suggestion,
        }
    }

    /// Create an export failed error.
    pub fn export_failed(path: impl Into<String>, reason: impl Into<String>) -> Self {
        let path = path.into();
        let reason = reason.into();
        let suggestion = format!(
            "Check:\n  • The output directory exists and is writable\n  • \
            There's enough disk space\n  • The file isn't open in another application"
        );
        AudioSyncError::ExportFailed {
            path,
            reason,
            suggestion,
        }
    }

    /// Create a project error.
    pub fn project_error(path: impl Into<String>, reason: impl Into<String>) -> Self {
        let path = path.into();
        let reason = reason.into();
        let suggestion = format!(
            "Try:\n  • Opening a backup of the project file\n  • \
            Re-importing the source files and creating a new project\n  • \
            Checking for file corruption"
        );
        AudioSyncError::ProjectError {
            path,
            reason,
            suggestion,
        }
    }
}

impl fmt::Display for AudioSyncError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.message())?;
        if let Some(suggestion) = self.suggestion() {
            write!(f, "\n\nFix it:\n{}", suggestion)?;
        }
        Ok(())
    }
}

impl std::error::Error for AudioSyncError {}

/// Convert from anyhow::Error — preserves the message but loses structured info.
impl From<anyhow::Error> for AudioSyncError {
    fn from(err: anyhow::Error) -> Self {
        let msg = err.to_string();
        // Try to extract meaningful info from common error patterns
        if msg.contains("No such file") || msg.contains("not found") {
            AudioSyncError::file_not_found(msg)
        } else if msg.contains("ffmpeg") || msg.contains("FFmpeg") {
            AudioSyncError::ffmpeg_missing()
        } else if msg.contains("cancelled") || msg.contains("canceled") {
            AudioSyncError::Cancelled
        } else {
            AudioSyncError::Other {
                message: msg,
                suggestion: "Check the file paths and try again. If the problem persists, \
                enable debug logging for more details.".to_string(),
            }
        }
    }
}

/// Convert from std::io::Error.
impl From<std::io::Error> for AudioSyncError {
    fn from(err: std::io::Error) -> Self {
        let msg = err.to_string();
        if err.kind() == std::io::ErrorKind::NotFound {
            AudioSyncError::file_not_found(msg)
        } else if err.kind() == std::io::ErrorKind::PermissionDenied {
            AudioSyncError::Other {
                message: format!("Permission denied: {}", msg),
                suggestion: "Check file permissions and try again.".to_string(),
            }
        } else {
            AudioSyncError::Other {
                message: msg,
                suggestion: "An I/O error occurred. Check the file and try again.".to_string(),
            }
        }
    }
}

/// Result type alias for AudioSync operations.
pub type Result<T> = std::result::Result<T, AudioSyncError>;

/// Helper to check if a file exists, returning a proper error if not.
pub fn check_file_exists(path: &str) -> Result<()> {
    if PathBuf::from(path).exists() {
        Ok(())
    } else {
        Err(AudioSyncError::file_not_found(path))
    }
}

/// Helper to check if multiple files exist, returning a list of missing files.
pub fn check_files_exist(paths: &[String]) -> Result<Vec<String>> {
    let missing: Vec<String> = paths
        .iter()
        .filter(|p| !PathBuf::from(p).exists())
        .cloned()
        .collect();

    if missing.is_empty() {
        Ok(paths.to_vec())
    } else {
        Err(AudioSyncError::Other {
            message: format!("{} file(s) not found", missing.len()),
            suggestion: format!(
                "Missing files:\n  {}\n\nUse the 'Relink Media' feature to locate these files.",
                missing.join("\n  ")
            ),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_message_display() {
        let err = AudioSyncError::file_not_found("/path/to/file.mp4");
        assert!(err.message().contains("file.mp4"));
        assert!(err.suggestion().is_some());
    }

    #[test]
    fn test_insufficient_overlap() {
        let err = AudioSyncError::insufficient_overlap(60.0, 15.0);
        assert!(err.message().contains("60.0s required"));
        assert!(err.message().contains("15.0s available"));
        assert!(err.suggestion().is_some());
    }

    #[test]
    fn test_low_confidence() {
        let err = AudioSyncError::low_confidence("Clip001.mp4", 2.5, 3.0);
        assert!(err.message().contains("Clip001.mp4"));
        assert!(err.message().contains("2.5"));
        assert!(err.suggestion().is_some());
    }

    #[test]
    fn test_check_file_exists() {
        assert!(check_file_exists("/nonexistent/file.wav").is_err());
        assert!(check_file_exists("/etc/passwd").is_ok() || cfg!(windows));
    }

    #[test]
    fn test_from_anyhow() {
        let anyhow_err = anyhow::anyhow!("No such file or directory: test.wav");
        let audio_err: AudioSyncError = anyhow_err.into();
        assert!(matches!(audio_err, AudioSyncError::FileNotFound { .. }));
    }
}
