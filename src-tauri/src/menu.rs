//! Native application menu for AudioSync Pro.
//!
//! Provides File, Edit, View, Help menus with accelerators.
//! Menu events are forwarded to the frontend as `menu-event` Tauri events.

use tauri::menu::{Menu, MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::{AppHandle, Emitter, Wry};

/// Build the native application menu.
pub fn build_menu(app: &AppHandle) -> Result<Menu<Wry>, tauri::Error> {
    // File menu
    let import = MenuItemBuilder::with_id("import", "Import Files...")
        .accelerator("CmdOrCtrl+O")
        .build(app)?;
    let open_project = MenuItemBuilder::with_id("open-project", "Open Project...")
        .accelerator("CmdOrCtrl+Shift+O")
        .build(app)?;
    let save_project = MenuItemBuilder::with_id("save-project", "Save Project...")
        .accelerator("CmdOrCtrl+S")
        .build(app)?;
    let export = MenuItemBuilder::with_id("export", "Export...")
        .accelerator("CmdOrCtrl+E")
        .build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "Quit")
        .accelerator("CmdOrCtrl+Q")
        .build(app)?;

    let file_menu = SubmenuBuilder::new(app, "File")
        .item(&import)
        .item(&open_project)
        .item(&save_project)
        .separator()
        .item(&export)
        .separator()
        .item(&quit)
        .build()?;

    // Edit menu
    let undo = MenuItemBuilder::with_id("undo", "Undo")
        .accelerator("CmdOrCtrl+Z")
        .build(app)?;
    let redo = MenuItemBuilder::with_id("redo", "Redo")
        .accelerator("CmdOrCtrl+Shift+Z")
        .build(app)?;
    let select_all = MenuItemBuilder::with_id("select-all", "Select All")
        .accelerator("CmdOrCtrl+A")
        .build(app)?;

    let edit_menu = SubmenuBuilder::new(app, "Edit")
        .item(&undo)
        .item(&redo)
        .separator()
        .item(&select_all)
        .build()?;

    // View menu
    let analyze = MenuItemBuilder::with_id("analyze", "Run Analysis")
        .accelerator("CmdOrCtrl+R")
        .build(app)?;
    let drift_tool = MenuItemBuilder::with_id("drift-tool", "Drift Measurement...")
        .accelerator("CmdOrCtrl+D")
        .build(app)?;
    let zoom_in = MenuItemBuilder::with_id("zoom-in", "Zoom In")
        .accelerator("CmdOrCtrl+=")
        .build(app)?;
    let zoom_out = MenuItemBuilder::with_id("zoom-out", "Zoom Out")
        .accelerator("CmdOrCtrl+-")
        .build(app)?;
    let zoom_reset = MenuItemBuilder::with_id("zoom-reset", "Zoom to Fit")
        .accelerator("CmdOrCtrl+0")
        .build(app)?;

    let view_menu = SubmenuBuilder::new(app, "View")
        .item(&analyze)
        .item(&drift_tool)
        .separator()
        .item(&zoom_in)
        .item(&zoom_out)
        .item(&zoom_reset)
        .build()?;

    // Help menu
    let about = MenuItemBuilder::with_id("about", "About AudioSync Pro")
        .build(app)?;
    let website = MenuItemBuilder::with_id("website", "Website")
        .build(app)?;
    let github = MenuItemBuilder::with_id("github", "GitHub Repository")
        .build(app)?;

    let help_menu = SubmenuBuilder::new(app, "Help")
        .item(&about)
        .separator()
        .item(&website)
        .item(&github)
        .build()?;

    let menu = MenuBuilder::new(app)
        .item(&file_menu)
        .item(&edit_menu)
        .item(&view_menu)
        .item(&help_menu)
        .build()?;

    Ok(menu)
}

/// Handle menu events by forwarding to the frontend.
pub fn handle_menu_event(app: &AppHandle, event_id: &str) {
    match event_id {
        "quit" => {
            std::process::exit(0);
        }
        "website" => {
            let _ = open::that("https://audiosync.pro");
        }
        "github" => {
            let _ = open::that("https://github.com/KEYHAN-A/audiosync");
        }
        _ => {
            // Forward to frontend
            let _ = app.emit("menu-event", event_id.to_string());
        }
    }
}
