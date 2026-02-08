# Changelog

All notable changes to AudioSync Pro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.1] - 2026-02-08

### Fixed
- DaVinci Resolve NLE export: FCPXML now default format (best media relinking)
- DaVinci Resolve media relinking — stores absolute paths in metadata for NLEs
- FFmpeg error messages now show actual errors instead of truncated version banner
- FFmpeg full-quality extraction falls back to 16-bit if 24-bit fails (Sony A7IV fix)
- NLE export button now visible in workflow bar after Analyze (was hidden in File menu only)
- Defensive import of opentimelineio — app starts even if OTIO isn't available
- PyInstaller bundling of OTIO plugin manifest and data files

### Changed
- Complete UI overhaul: frosted-glass theme matching website brand identity
- Track cards redesigned as media-folder cards with folder icons and emoji badges
- Workflow bar with larger circular indicators and cyan glow effects
- Gradient progress bar (cyan-to-purple), rounded 16px cards and buttons
- QPalette override forces all text to be light — no more black text on dark backgrounds
- Every Qt widget type explicitly styled (QSpinBox, QComboBox, QCheckBox, etc.)
- Better Resolve import instructions in export success dialog

## [2.3.0] - 2026-02-08

### Added
- DaVinci Resolve / NLE timeline export (OTIO, FCPXML, EDL formats)
- New `core/timeline_export.py` module using OpenTimelineIO
- "Export Timeline for NLE" menu item (Ctrl+Shift+T) — available after Analyze
- Timeline export dialog with format selection, frame rate, and timeline name
- `opentimelineio` dependency for industry-standard timeline interchange
- DaVinci Resolve export feature card and use case on website
- GitHub Pages deployment workflow (`pages.yml`)
- GitHub Pages mirror URL in README badges and docs

### Changed
- Updated website feature grid and use cases to highlight DaVinci Resolve workflow
- Updated meta description and SEO keywords for NLE export
- Expanded README with NLE export section, keyboard shortcut, and import instructions

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

[2.3.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.3.0
[2.2.2]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.2.2
[2.2.1]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.2.1
[2.2.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.2.0
[2.1.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.1.0
[2.0.0]: https://github.com/KEYHAN-A/audiosync/releases/tag/v2.0.0
