# Changelog

All notable changes to AudioSync Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.2] - 2026-02-08

### Changed
- Website download buttons now link to GitHub latest release assets (macOS, Windows, Linux)
- Added GitHub Actions workflow for automatic website deployment via SSH + rsync
- Updated README with live website link and automated deploy documentation
- Updated version references across website, README, and version.py

## [2.2.1] - 2026-02-08

### Fixed
- Windows CI build: use `cmd` shell for `.bat` script execution on GitHub Actions
- Linux CI build: replace removed `libgl1-mesa-glx` with `libgl1` for Ubuntu 24.04

## [2.2.0] - 2026-02-08

### Added
- GitHub link in About dialog for easy access to source code
- `.gitignore`, `LICENSE` (GPLv3), and `CONTRIBUTING.md` for open-source readiness
- GitHub Actions workflow scaffold (`.github/`)
- `robots.txt` and `sitemap.xml` for website SEO
- README badges (license, version, platform, GitHub)
- High-quality audio processing section in README

### Changed
- Replaced toolbar with vertical splitter layout — track cards on top, timeline below
- Migrated track panel to card-based component (`track_card.py`)
- Streamlined main window layout with smaller default size
- Refined theme colors and styling
- Redesigned website landing page
- Improved README with expanded setup, usage, and architecture docs

## [2.1.0] - 2026-02-07

### Added
- Card-based track UI with glassmorphism design
- Cross-platform builds (macOS, Windows, Linux)
- LRU disk cache with configurable size limit (2 GB default)
- Session-aware caching — safe for multiple running instances
- Centralized version management (`version.py`)
- Landing page website with responsive design
- Auto-grouping of dropped files by device name
- Drag-and-drop onto individual track cards
- Email subscription form on website
- SEO-optimized website with JSON-LD structured data
- GitHub Actions release workflow scaffold

### Changed
- Redesigned desktop UI: toolbar removed, replaced with card-based layout
- Refined color palette — deep navy with cyan/violet accents
- Waveform timeline with rounded lanes and glass backgrounds
- Improved status bar with summary counts and progress indicator
- Cache directory moved to platform-standard locations

### Fixed
- Text color visibility on dark backgrounds
- Worker cleanup order preventing stale button states

## [2.0.0] - 2026-01-15

### Added
- Multi-device audio/video synchronization
- FFT cross-correlation analysis engine
- Multi-track waveform timeline view
- Workflow step indicator (Import → Analyze → Sync → Export)
- Support for WAV, AIFF, FLAC, MP3, MP4, MOV, MKV and more
- 24-bit PCM / 32-bit float high-quality audio processing
- Polyphase resampling via SciPy
- Sample-rate preservation on export
- Processing dialog with real-time progress and ETA
- macOS .app bundle build script

[2.2.2]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.2.2
[2.2.1]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.2.1
[2.2.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.2.0
[2.1.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.1.0
[2.0.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.0.0
