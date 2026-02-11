//! AudioSync Pro — Tauri v2 desktop application.

mod commands;
mod menu;

use commands::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .setup(|app| {
            let handle = app.handle().clone();
            let m = menu::build_menu(&handle)?;
            app.set_menu(m)?;
            Ok(())
        })
        .on_menu_event(|app, event| {
            menu::handle_menu_event(app, event.id().as_ref());
        })
        .invoke_handler(tauri::generate_handler![
            commands::get_version,
            commands::import_files,
            commands::add_files_to_track,
            commands::create_track,
            commands::remove_track,
            commands::remove_clip,
            commands::get_tracks,
            commands::run_analysis,
            commands::run_sync_and_export,
            commands::measure_drift,
            commands::cancel_operation,
            commands::save_project,
            commands::load_project,
            commands::update_config,
            commands::get_file_groups,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
