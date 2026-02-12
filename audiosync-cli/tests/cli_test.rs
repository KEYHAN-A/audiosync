//! CLI integration tests.
//!
//! These test the audiosync binary's argument parsing and basic output.
//! Full audio tests require fixtures (Phase 6+).

use std::process::Command;

fn audiosync_bin() -> Command {
    Command::new(env!("CARGO_BIN_EXE_audiosync"))
}

#[test]
fn test_version() {
    let output = audiosync_bin()
        .arg("--version")
        .output()
        .expect("Failed to run audiosync");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("3.1.1"),
        "Version output should contain 3.1.1, got: {}",
        stdout
    );
}

#[test]
fn test_help() {
    let output = audiosync_bin()
        .arg("--help")
        .output()
        .expect("Failed to run audiosync");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("audiosync"), "Should contain binary name");
    assert!(stdout.contains("analyze"));
    assert!(stdout.contains("sync"));
    assert!(stdout.contains("drift"));
    assert!(stdout.contains("info"));
}

#[test]
fn test_analyze_help() {
    let output = audiosync_bin()
        .args(["analyze", "--help"])
        .output()
        .expect("Failed to run audiosync");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("--json"));
    assert!(stdout.contains("--max-offset"));
}

#[test]
fn test_sync_help() {
    let output = audiosync_bin()
        .args(["sync", "--help"])
        .output()
        .expect("Failed to run audiosync");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("--format"));
    assert!(stdout.contains("--bit-depth"));
    assert!(stdout.contains("--output-dir"));
}

#[test]
fn test_info_no_files() {
    // Should fail because files are required
    let output = audiosync_bin()
        .arg("info")
        .output()
        .expect("Failed to run audiosync");
    assert!(!output.status.success());
}

#[test]
fn test_info_nonexistent_files() {
    let output = audiosync_bin()
        .args(["info", "nonexistent.wav", "nonexistent.mp4"])
        .output()
        .expect("Failed to run audiosync");
    // Should succeed but find 0 groups (files don't exist but are "supported" by extension)
    assert!(output.status.success());
}

#[test]
fn test_info_unsupported_files() {
    let output = audiosync_bin()
        .args(["info", "readme.txt", "photo.jpg"])
        .output()
        .expect("Failed to run audiosync");
    // Should succeed with 0 supported files
    assert!(output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("0 supported") || stderr.contains("0 group"),
        "Should report 0 supported files, got: {}",
        stderr
    );
}

#[test]
fn test_info_json() {
    let output = audiosync_bin()
        .args(["info", "--json", "CamA_001.wav", "CamA_002.wav", "Zoom_001.wav"])
        .output()
        .expect("Failed to run audiosync");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    // Should be valid JSON
    let parsed: serde_json::Value =
        serde_json::from_str(&stdout).expect("Output should be valid JSON");
    assert!(parsed.get("groups").is_some());
}

#[test]
fn test_analyze_no_files() {
    let output = audiosync_bin()
        .arg("analyze")
        .output()
        .expect("Failed to run audiosync");
    assert!(!output.status.success(), "Should fail without files");
}
