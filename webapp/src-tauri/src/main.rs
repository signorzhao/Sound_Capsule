// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::sync::Mutex;

mod config;
mod paths;
mod sidecar;
mod port_manager;

// Sidecar 进程状态（使用 Arc<Mutex<>> 来管理共享状态）
struct SidecarState {
    process: Mutex<Option<sidecar::SidecarProcess>>,
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            // 初始化路径管理器
            let app_paths = paths::AppPaths::new()
                .expect("Failed to initialize app paths");

            // 准备 Sidecar 启动参数
            let config_dir = app_paths.app_data_dir.to_string_lossy().to_string();
            let resources_dir = app_paths.resources_dir.to_string_lossy().to_string();
            
            // export_dir 需要从配置文件读取，如果不存在则使用默认值
            let export_dir = app_paths.app_data_dir.join("output").to_string_lossy().to_string();
            
            app.manage(app_paths);

            // Phase G: 自动启动 Python 后端 Sidecar
            // 开发模式下禁用自动启动（手动在终端启动）
            #[cfg(debug_assertions)]
            {
                println!("⚠️ [DEV] 开发模式：跳过自动启动 Python 后端");
                println!("   请手动在终端运行：python3 capsule_api.py --config-dir ... --port 5002");
                app.manage(SidecarState {
                    process: Mutex::new(None),
                });
            }
            
            // 生产模式下自动启动
            #[cfg(not(debug_assertions))]
            {
                println!("🚀 启动 Python 后端...");
                println!("   配置目录: {}", config_dir);
                println!("   导出目录: {}", export_dir);
                println!("   资源目录: {}", resources_dir);
                
                match sidecar::SidecarProcess::start(
                    config_dir,
                    export_dir,
                    Some(resources_dir),
                    5002
                ) {
                    Ok(sidecar_process) => {
                        println!("✅ Python 后端启动成功");
                        app.manage(SidecarState {
                            process: Mutex::new(Some(sidecar_process)),
                        });
                    }
                    Err(e) => {
                        eprintln!("❌ Python 后端启动失败: {}", e);
                        app.manage(SidecarState {
                            process: Mutex::new(None),
                        });
                    }
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            config::get_app_config,
            config::save_app_config,
            config::reset_app_config,
            paths::get_app_paths,
            port_manager::get_available_port,
            sidecar::check_sidecar,
            sidecar::open_rpp_in_reaper,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
