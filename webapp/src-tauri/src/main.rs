// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use std::sync::Mutex;
use std::fs::OpenOptions;
use std::io::Write;

mod config;
mod paths;
mod sidecar;
mod port_manager;

// 日志写入文件（用于调试 Release 模式）
fn log_to_file(message: &str) {
    if let Some(home) = dirs::home_dir() {
        let log_dir = home.join(".soundcapsule");
        let _ = std::fs::create_dir_all(&log_dir);
        let log_path = log_dir.join("tauri_debug.log");
        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
        {
            let _ = writeln!(file, "{}", message);
        }
    }
}

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
                log_to_file("🚀 启动 Python 后端...");
                log_to_file(&format!("   配置目录: {}", config_dir));
                log_to_file(&format!("   导出目录: {}", export_dir));
                log_to_file(&format!("   资源目录: {}", resources_dir));
                
                // 获取 exe 目录用于调试
                if let Ok(exe_path) = std::env::current_exe() {
                    if let Some(exe_dir) = exe_path.parent() {
                        log_to_file(&format!("   EXE目录: {}", exe_dir.display()));
                        
                        // 检查 Tauri _up_ 结构
                        let tauri_up_path = exe_dir.join("_up_").join("_up_").join("data-pipeline");
                        log_to_file(&format!("   Tauri _up_ 路径: {}", tauri_up_path.display()));
                        log_to_file(&format!("   Tauri _up_ 存在: {}", tauri_up_path.exists()));
                        
                        // 检查 resources 子目录
                        let resources_subdir = exe_dir.join("resources");
                        log_to_file(&format!("   resources子目录: {}", resources_subdir.display()));
                        log_to_file(&format!("   resources子目录存在: {}", resources_subdir.exists()));
                    }
                }
                
                // 检查 Lua 脚本是否存在
                let lua_scripts_path = std::path::Path::new(&resources_dir).join("lua_scripts");
                log_to_file(&format!("   Lua脚本目录: {}", lua_scripts_path.display()));
                log_to_file(&format!("   Lua脚本目录存在: {}", lua_scripts_path.exists()));
                
                // 检查具体脚本文件
                let windows_script = lua_scripts_path.join("auto_export_from_config_windows.lua");
                log_to_file(&format!("   Windows脚本: {}", windows_script.display()));
                log_to_file(&format!("   Windows脚本存在: {}", windows_script.exists()));
                
                // 检查数据库 schema
                let schema_path = std::path::Path::new(&resources_dir).join("database").join("capsule_schema.sql");
                log_to_file(&format!("   Schema路径: {}", schema_path.display()));
                log_to_file(&format!("   Schema存在: {}", schema_path.exists()));
                
                match sidecar::SidecarProcess::start(
                    config_dir,
                    export_dir,
                    Some(resources_dir),
                    5002
                ) {
                    Ok(sidecar_process) => {
                        log_to_file("✅ Python 后端启动成功");
                        app.manage(SidecarState {
                            process: Mutex::new(Some(sidecar_process)),
                        });
                    }
                    Err(e) => {
                        log_to_file(&format!("❌ Python 后端启动失败: {}", e));
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
        .on_window_event(|window, event| {
            // 当窗口关闭时，停止 sidecar 进程
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                log_to_file("🛑 窗口关闭请求，正在停止后端进程...");
                
                if let Some(state) = window.try_state::<SidecarState>() {
                    if let Ok(mut process_guard) = state.process.lock() {
                        if let Some(ref mut sidecar) = *process_guard {
                            log_to_file("🛑 正在终止 Python 后端进程...");
                            sidecar.stop();
                            log_to_file("✅ Python 后端进程已终止");
                        }
                        *process_guard = None;
                    }
                }
                
                // Windows 上额外使用 taskkill 确保进程被终止
                #[cfg(target_os = "windows")]
                {
                    log_to_file("🛑 [Windows] 使用 taskkill 清理残留进程...");
                    use std::os::windows::process::CommandExt;
                    const CREATE_NO_WINDOW: u32 = 0x08000000;
                    let _ = std::process::Command::new("taskkill")
                        .args(["/F", "/IM", "capsules_api.exe"])
                        .creation_flags(CREATE_NO_WINDOW)
                        .output();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
