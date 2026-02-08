# AudioSync Pro — Open Issues & Missing Features

Audit performed during v2.4.0 development. Items are grouped by priority.

---

## Critical

### 1. Saved projects have empty audio samples
When opening `.audiosync` files or cloud projects, clips are deserialized with empty `samples` arrays (`core/project_io.py` line 133 — "empty — reload needed"). Audio must be reloaded from source files after deserializing. Waveform view won't display audio and re-analysis fails.
- **Affects:** `app/main_window.py` (`_on_open_project`, `_on_cloud_project_opened`)
- **Fix:** After deserializing tracks, reload audio samples from source files using `load_clip()` for each clip.

### 2. No file path validation when opening projects
When opening saved projects (local or cloud), source audio/video files may have been moved or deleted. No check or warning is shown — the project appears loaded but operations fail silently.
- **Affects:** `app/main_window.py`, `core/project_io.py`
- **Fix:** Validate all clip `file_path` values exist on disk. Show a dialog listing missing files with options to relink or skip.

---

## High Priority

### 3. No onboarding / first-run experience
App opens to a completely blank window with no guidance. New users have no idea what to do.
- **Suggestion:** Add a simple "Getting Started" overlay or welcome tip on first launch. Could show the 3-step workflow (Import → Analyze & Sync → Export) with brief instructions.

### 4. Cloud save has no description field
The API supports descriptions (`save_project()` accepts a `description` parameter) but the save dialog only asks for a project name.
- **Affects:** `app/main_window.py` (`_on_save_to_cloud`)
- **Fix:** Add a description text field to the cloud save prompt.

### 5. No keyboard shortcuts for cloud operations
Save to Cloud and Open from Cloud have no keyboard shortcuts, unlike local File operations (Ctrl+S, Ctrl+O).
- **Suggestion:** Ctrl+Shift+S for Save to Cloud, Ctrl+Shift+O for Open from Cloud.

### 6. Silent exception swallowing in account indicator
`_update_account_indicator()` in `main_window.py` (line 508) catches all exceptions silently. Several `except: pass` blocks in `audio_io.py` and `cloud.py` also hide errors.
- **Fix:** Log exceptions at WARNING level minimum for debuggability.

---

## Medium Priority

### 7. No auto-save / auto-sync for cloud projects
Cloud save is manual only — there's no periodic auto-save or sync-on-change.
- **Suggestion:** Optional auto-save every N minutes when signed in and working on a cloud project.

### 8. No JWT token refresh
JWT expiry forces full re-authentication via the device code flow. There's no refresh token mechanism.
- **Affects:** `core/cloud.py`
- **Fix:** Implement token refresh endpoint on the API side and call it from `_request()` on 401 before falling through to "please sign in again."

### 9. No project version migration
`core/project_io.py` logs the project version but has no migration logic for format changes between versions.
- **Fix:** Add version migration functions that upgrade older project formats to the current version.

### 10. README doesn't mention cloud features
Cloud, account, and sync features are only described on the website. The README should mention them for GitHub visitors.

---

## Low Priority

### 11. `get_supported_formats()` empty fallback
When `opentimelineio` is not installed, `dialogs.py` line 46-47 returns an empty dict instead of a meaningful fallback.
- **Fix:** Return a message indicating OTIO is required, or disable the NLE export menu item entirely.

### 12. No corrupted project file recovery
If a `.audiosync` file has invalid JSON or missing fields, the error handling is generic. No partial recovery is attempted.

### 13. No cache cleanup on project open
Stale cache entries from previous sessions are not validated or cleaned when opening projects.

### 14. "My Account" dialog is a basic QMessageBox
Could be a proper styled dialog with the user's avatar, plan details, usage stats, and account management links.

### 15. No progress indication for cloud project loading
Loading cloud projects doesn't show progress, especially if audio samples need to be reloaded (which should be added per issue #1).
