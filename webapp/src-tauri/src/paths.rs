use std::fs;
use std::path::PathBuf;
use serde::{Serialize, Deserialize};

// 定义应用的关键路径结构
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AppPaths {
    pub app_data_dir: PathBuf,    // 应用数据 (Config, DB)
    pub resources_dir: PathBuf,   // 静态资源 (Bundled assets)
    pub scripts_dir: PathBuf,     // Lua 脚本路径 (Phase D3 预留)
    pub python_env_dir: PathBuf,  // Python 环境路径 (Phase D2 预留)
    pub temp_dir: PathBuf,        // 临时目录
}

impl AppPaths {
    // 初始化方法
    pub fn new() -> Result<Self, String> {
        // 1. 获取系统标准路径
        let app_data_dir = dirs::config_dir()
            .map(|p| p.join("com.soundcapsule.app"))
            .ok_or("Failed to resolve config directory")?;

        // 资源目录：开发环境使用项目根目录，生产环境使用应用目录
        let resources_dir = if cfg!(debug_assertions) {
            // 开发环境
            // CARGO_MANIFEST_DIR = webapp/src-tauri
            // ../.. = synesth (项目根目录)
            // data-pipeline = synesth/data-pipeline
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("..")
                .join("data-pipeline")
        } else {
            // 生产环境：根据操作系统选择正确的路径
            std::env::current_exe()
                .ok()
                .and_then(|exe_path| {
                    let exe_dir = exe_path.parent()?;
                    
                    #[cfg(target_os = "macos")]
                    {
                        // macOS: Tauri 2.0 保留相对路径结构
                        // 资源路径: Contents/Resources/_up_/_up_/data-pipeline/
                        let resources_base = exe_dir // Contents/MacOS
                            .parent()? // Contents
                            .join("Resources");
                        
                        // 优先尝试 Tauri 保留的相对路径结构
                        let tauri_path = resources_base
                            .join("_up_")
                            .join("_up_")
                            .join("data-pipeline");
                        
                        if tauri_path.join("lua_scripts").exists() {
                            Some(tauri_path)
                        } else if resources_base.join("lua_scripts").exists() {
                            // 扁平化结构（备用）
                            Some(resources_base)
                        } else {
                            // 降级到 Resources 目录
                            Some(resources_base)
                        }
                    }
                    
                    #[cfg(target_os = "windows")]
                    {
                        // Windows: Tauri 2.0 保留相对路径结构
                        // 资源路径: exe_dir/resources/_up_/_up_/data-pipeline/
                        let resources_base = exe_dir.join("resources");
                        
                        // 优先尝试 Tauri 保留的相对路径结构
                        let tauri_path = resources_base
                            .join("_up_")
                            .join("_up_")
                            .join("data-pipeline");
                        
                        if tauri_path.join("lua_scripts").exists() {
                            Some(tauri_path)
                        } else if resources_base.join("lua_scripts").exists() {
                            // 扁平化结构（备用）
                            Some(resources_base)
                        } else {
                            // 降级到 exe 同目录（用于开发/调试）
                            Some(exe_dir.to_path_buf())
                        }
                    }
                    
                    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
                    {
                        // Linux 等其他系统
                        Some(exe_dir.to_path_buf())
                    }
                })
                .ok_or("Failed to resolve resource directory")?
        };

        // 2. 定义子目录结构
        let scripts_dir = resources_dir.join("lua_scripts");
        let python_env_dir = resources_dir.join("exporters");

        // 临时目录使用系统临时目录下的专用文件夹
        let temp_dir = std::env::temp_dir().join("soundcapsule");

        // 3. 确保必要的目录存在 (mkdir -p)
        if !app_data_dir.exists() {
            fs::create_dir_all(&app_data_dir).map_err(|e| e.to_string())?;
        }
        // 确保临时目录存在
        if !temp_dir.exists() {
            fs::create_dir_all(&temp_dir).map_err(|e| e.to_string())?;
        }

        Ok(Self {
            app_data_dir,
            resources_dir,
            scripts_dir,
            python_env_dir,
            temp_dir,
        })
    }
}

// 暴露给前端的 Command
#[tauri::command]
pub fn get_app_paths(state: tauri::State<AppPaths>) -> AppPaths {
    state.inner().clone()
}